"""Find jobs that exceeded their deadline.

A job runs from a THREAD_STATE state=RELEASED event to the next
THREAD_STATE state=DONE event of the same thread (docs/trace-format.md).
"""

from collections import Counter
from dataclasses import dataclass, replace
from statistics import median
from typing import Dict, List, Optional

from .config import ConfigError, ThreadConfig
from .events import Event, ThreadState

RELEASED = "RELEASED"
DONE = "DONE"


@dataclass(frozen=True)
class Job:
    name: str
    tid: int
    release_ns: int
    done_ns: Optional[int]  # None: still unfinished when the trace ended
    deadline_ns: int  # absolute time the job had to finish by
    missed: bool

    @property
    def response_ns(self) -> Optional[int]:
        return None if self.done_ns is None else self.done_ns - self.release_ns


def find_jobs(events: List[Event], config: Dict[str, ThreadConfig]) -> List[Job]:
    """Return every job of configured threads, ordered by release time."""
    end_ns = max((e.ts_ns for e in events), default=0)
    open_jobs: Dict[int, ThreadState] = {}  # by tid: names can repeat across processes
    jobs = []

    def close(rel: ThreadState, done_ns: Optional[int]):
        deadline = rel.ts_ns + int(config[rel.name].deadline_ms * 1_000_000)
        # An unfinished job only counts as missed once its deadline passed.
        missed = (done_ns if done_ns is not None else end_ns) > deadline
        jobs.append(Job(rel.name, rel.tid, rel.ts_ns, done_ns, deadline, missed))

    for e in events:
        if not isinstance(e, ThreadState) or e.name not in config:
            continue
        if e.state == RELEASED:
            if e.tid in open_jobs:  # released again before finishing
                close(open_jobs.pop(e.tid), None)
            open_jobs[e.tid] = e
        elif e.state == DONE and e.tid in open_jobs:
            close(open_jobs.pop(e.tid), e.ts_ns)
    for rel in open_jobs.values():
        close(rel, None)
    return sorted(jobs, key=lambda j: (j.release_ns, j.name))


def find_misses(events: List[Event], config: Dict[str, ThreadConfig]) -> List[Job]:
    return [j for j in find_jobs(events, config) if j.missed]


def infer_config(events: List[Event], deadlines: Optional[Dict[str, float]] = None
                 ) -> Dict[str, ThreadConfig]:
    """Build the thread config from the trace's job markers.

    Every thread with at least two RELEASED markers is periodic: its period is
    the median gap between releases of one tid, its priority the most common
    one at release. The trace cannot show a deadline, so it defaults to the
    period unless `deadlines` (ms by name) gives one.
    """
    releases: Dict[str, Dict[int, List[ThreadState]]] = {}
    for e in events:
        if isinstance(e, ThreadState) and e.state == RELEASED:
            releases.setdefault(e.name, {}).setdefault(e.tid, []).append(e)
    config = {}
    for name, by_tid in releases.items():
        gaps = [b.ts_ns - a.ts_ns for rel in by_tid.values() for a, b in zip(rel, rel[1:])]
        if not gaps:
            continue
        period = round(median(gaps) / 1e6, 1)
        prio = Counter(e.prio for rel in by_tid.values() for e in rel).most_common(1)[0][0]
        config[name] = ThreadConfig(name, period, period, prio)
    return with_deadlines(config, deadlines)


def with_deadlines(config: Dict[str, ThreadConfig], deadlines: Optional[Dict[str, float]]
                   ) -> Dict[str, ThreadConfig]:
    """Override deadlines (ms by thread name); unknown names are an error."""
    for name, ms in (deadlines or {}).items():
        if name not in config:
            raise ConfigError(f"--deadline {name}: no periodic thread of that name")
        config = {**config, name: replace(config[name], deadline_ms=ms)}
    return config
