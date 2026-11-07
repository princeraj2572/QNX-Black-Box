"""Priority inversion: a high-priority thread blocked on a lower-priority one
while a medium-priority thread runs.

Assumes a single CPU: the running thread is the one from the latest RUN event.
shortcut: no CPU id in the internal format, add one to support SMP traces.
"""

from dataclasses import dataclass
from typing import List, Tuple

from .blocking import Block, build_blocks
from .events import Event, Run


@dataclass(frozen=True)
class Inversion:
    block: Block  # high-priority thread blocked on a lower-priority one
    medium_tid: int
    medium_name: str
    medium_prio: int
    start_ns: int
    end_ns: int


def run_intervals(events: List[Event]) -> List[Tuple[Run, int, int]]:
    """(run event, start_ns, end_ns) for each stretch a thread was running."""
    runs = sorted((e for e in events if isinstance(e, Run)), key=lambda e: e.ts_ns)
    trace_end = max((e.ts_ns for e in events), default=0)
    ends = [r.ts_ns for r in runs[1:]] + [trace_end]
    return [(r, r.ts_ns, end) for r, end in zip(runs, ends)]


def find_inversions(events: List[Event]) -> List[Inversion]:
    trace_end = max((e.ts_ns for e in events), default=0)
    intervals = run_intervals(events)
    found = []
    for b in build_blocks(events):
        if b.blocked_prio <= b.on_prio:
            continue
        b_end = trace_end if b.end_ns is None else b.end_ns
        for run, start, end in intervals:
            lo, hi = max(start, b.start_ns), min(end, b_end)
            if lo < hi and b.on_prio < run.prio < b.blocked_prio:
                found.append(Inversion(b, run.tid, run.name, run.prio, lo, hi))
    return sorted(found, key=lambda i: (i.start_ns, i.medium_tid))
