"""Other causes of a missed deadline: CPU starvation and slow replies."""

from dataclasses import dataclass
from typing import Dict, List

from .blocking import Block, build_blocks
from .config import ThreadConfig
from .deadlines import Job
from .events import Event
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
    events: List[Event], misses: List[Job], config: Dict[str, ThreadConfig]
) -> List[Starvation]:
    """Higher-priority threads that ran while a missed job was in flight.

    shortcut: counts all their run time in the window, even while the victim
    was blocked; refine if reports blame hogs for time the victim couldn't run.
    """
    trace_end = max((e.ts_ns for e in events), default=0)
    intervals = run_intervals(events)
    found = []
    for job in misses:
        prio, end = config[job.name].priority, _window_end(job, trace_end)
        totals: Dict[int, list] = {}
        for run, start, stop in intervals:
            lo, hi = max(start, job.release_ns), min(stop, end)
            if lo < hi and run.prio > prio and run.tid != job.tid:
                entry = totals.setdefault(run.tid, [run, 0])
                entry[1] += hi - lo
        for run, total in totals.values():
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
