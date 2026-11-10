"""Other causes of a missed deadline: CPU starvation and slow replies."""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .blocking import Block, build_blocks
from .config import ThreadConfig
from .deadlines import DONE, RELEASED, Job
from .events import Event, ThreadState
from .inversion import run_intervals


@dataclass(frozen=True)
class Starvation:
    job: Job
    hog_tid: int
    hog_name: str
    hog_prio: int
    run_ns: int  # time the higher-priority thread ran inside the job's window


@dataclass(frozen=True)
class ReplyDelay:
    job: Job
    block: Block
    duration_ns: int  # time from MSG_SEND to MSG_REPLY (or trace end)


def _window_end(job: Job, trace_end: int) -> int:
    return trace_end if job.done_ns is None else job.done_ns


def find_starvation(
    events: List[Event],
    misses: List[Job],
    config: Dict[str, ThreadConfig],
    min_fraction: float = 0.05,
) -> List[Starvation]:
    """Higher-priority threads that ran >= min_fraction of the deadline while a
    missed job was in flight (real traces are full of brief kernel threads).

    shortcut: counts all their run time in the window, even while the victim
    was blocked; refine if reports blame hogs for time the victim couldn't run.
    """
    trace_end = max((e.ts_ns for e in events), default=0)
    intervals = run_intervals(events)
    found = []
    for job in misses:
        prio, end = config[job.name].priority, _window_end(job, trace_end)
        limit = config[job.name].deadline_ms * 1_000_000 * min_fraction
        totals: Dict[int, list] = {}
        for run, start, stop in intervals:
            lo, hi = max(start, job.release_ns), min(stop, end)
            if lo < hi and run.prio > prio and run.tid != job.tid:
                entry = totals.setdefault(run.tid, [run, 0])
                entry[1] += hi - lo
        for run, total in totals.values():
            if total >= limit:
                found.append(Starvation(job, run.tid, run.name, run.prio, total))
    return sorted(found, key=lambda s: (s.job.release_ns, -s.run_ns))


def find_reply_delays(
    events: List[Event],
    misses: List[Job],
    config: Dict[str, ThreadConfig],
    min_fraction: float = 0.25,
) -> List[ReplyDelay]:
    """Sends by a missed job's thread that took >= min_fraction of its deadline."""
    trace_end = max((e.ts_ns for e in events), default=0)
    blocks = build_blocks(events)
    found = []
    for job in misses:
        limit = config[job.name].deadline_ms * 1_000_000 * min_fraction
        end = _window_end(job, trace_end)
        for b in blocks:
            if b.blocked_tid != job.tid or not job.release_ns <= b.start_ns <= end:
                continue
            duration = (trace_end if b.end_ns is None else b.end_ns) - b.start_ns
            if duration >= limit:
                found.append(ReplyDelay(job, b, duration))
    return sorted(found, key=lambda r: (r.job.release_ns, r.block.start_ns))


@dataclass(frozen=True)
class MutexWait:
    job: Job
    tid: int  # the waiting thread: the job's own, or a server it waits on
    name: str
    prio: int
    start_ns: int
    end_ns: int
    # (name, priority, run_ns) of lower-priority threads that ran meanwhile,
    # most first. The trace has no mutex owner (uncontended locks never enter
    # the kernel), so the holder is among these at best, never named outright.
    ran: Tuple[Tuple[str, int, int], ...]


def find_mutex_waits(
    events: List[Event],
    misses: List[Job],
    config: Dict[str, ThreadConfig],
    reply_delays: List[ReplyDelay],
    min_fraction: float = 0.25,
    min_share: float = 0.1,
) -> List[MutexWait]:
    """MUTEX waits >= min_fraction of the deadline by a missed job's thread or
    the server of one of its slow replies, with the threads that ran meanwhile
    (each >= min_share of the wait; idle threads at priority 0 left out)."""
    trace_end = max((e.ts_ns for e in events), default=0)
    waits, since = [], {}  # tid -> MUTEX state event still open
    for e in events:
        if not isinstance(e, ThreadState) or e.state in (RELEASED, DONE):
            continue
        if e.tid in since:
            waits.append((since.pop(e.tid), e.ts_ns))
        if e.state == "MUTEX":
            since[e.tid] = e
    waits += [(s, trace_end) for s in since.values()]
    intervals = run_intervals(events)
    found = []
    for job in misses:
        limit = config[job.name].deadline_ms * 1_000_000 * min_fraction
        end = _window_end(job, trace_end)
        tids = {job.tid} | {d.block.on_tid for d in reply_delays if d.job == job}
        for s, stop in waits:
            if s.tid not in tids or stop - s.ts_ns < limit or not job.release_ns <= s.ts_ns <= end:
                continue
            totals: Dict[tuple, int] = {}
            for run, lo, hi in intervals:
                lo, hi = max(lo, s.ts_ns), min(hi, stop)
                if lo < hi and 0 < run.prio < s.prio and run.tid != s.tid:
                    key = (run.name, run.prio)
                    totals[key] = totals.get(key, 0) + hi - lo
            ran = tuple(sorted(
                ((n, p, t) for (n, p), t in totals.items() if t >= (stop - s.ts_ns) * min_share),
                key=lambda r: -r[2]))
            found.append(MutexWait(job, s.tid, s.name, s.prio, s.ts_ns, stop, ran))
    return sorted(found, key=lambda w: (w.job.release_ns, w.start_ns))
