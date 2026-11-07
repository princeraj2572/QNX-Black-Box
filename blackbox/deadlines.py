"""Find jobs that exceeded their deadline.

A job runs from a THREAD_STATE state=RELEASED event to the next
THREAD_STATE state=DONE event of the same thread (docs/trace-format.md).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import ThreadConfig
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
    open_jobs: Dict[str, ThreadState] = {}
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
            if e.name in open_jobs:  # released again before finishing
                close(open_jobs.pop(e.name), None)
            open_jobs[e.name] = e
        elif e.state == DONE and e.name in open_jobs:
            close(open_jobs.pop(e.name), e.ts_ns)
    for rel in open_jobs.values():
        close(rel, None)
    return sorted(jobs, key=lambda j: (j.release_ns, j.name))


def find_misses(events: List[Event], config: Dict[str, ThreadConfig]) -> List[Job]:
    return [j for j in find_jobs(events, config) if j.missed]
