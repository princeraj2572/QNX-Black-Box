"""Service recovery: how long a restarted thread was gone.

A restarted process gets a new pid, so its threads get new tids (the adapter
uses pid * 1000 + tid) but keep their names. A restart is a tid whose events
all come after the last event of an earlier tid with the same name; the gap
between them is the recovery time.

shortcut: threads that are deliberately created one after another under one
name look like restarts; filter by name if that ever matters.
"""

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class Restart:
    name: str
    old_tid: int
    new_tid: int
    down_ns: int  # last event of the old instance
    up_ns: int    # first event of the new instance

    @property
    def recovery_ns(self) -> int:
        return self.up_ns - self.down_ns


def find_restarts(events: Iterable) -> List[Restart]:
    spans = {}  # tid -> [name, first_ts, last_ts]
    for e in events:
        s = spans.setdefault(e.tid, [e.name, e.ts_ns, e.ts_ns])
        s[1], s[2] = min(s[1], e.ts_ns), max(s[2], e.ts_ns)
    by_name = {}
    for tid, (name, first, last) in spans.items():
        by_name.setdefault(name, []).append((first, last, tid))
    restarts = []
    for name, lives in by_name.items():
        lives.sort()
        for (_, last, old), (first, _, new) in zip(lives, lives[1:]):
            if first > last:  # overlapping lives are two threads, not a restart
                restarts.append(Restart(name, old, new, last, first))
    return sorted(restarts, key=lambda r: r.down_ns)
