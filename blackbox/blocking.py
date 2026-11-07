"""Who was blocked on whom, built from MSG_SEND / MSG_RECEIVE / MSG_REPLY.

A sender is blocked on its peer from its MSG_SEND until the peer's matching
MSG_REPLY. MSG_RECEIVE only records when the peer picked the message up.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .events import Event, MsgReceive, MsgReply, MsgSend


@dataclass(frozen=True)
class Block:
    blocked_tid: int
    blocked_name: str
    blocked_prio: int
    on_tid: int
    on_name: str
    on_prio: int
    start_ns: int
    received_ns: Optional[int]  # when the peer received it; None if it never did
    end_ns: Optional[int]  # reply time; None if never replied before trace end

    def active_at(self, ts_ns: int) -> bool:
        return self.start_ns <= ts_ns and (self.end_ns is None or ts_ns < self.end_ns)


def build_blocks(events: List[Event]) -> List[Block]:
    """Return blocking intervals ordered by start time."""
    events = sorted(events, key=lambda e: e.ts_ns)
    first: Dict[int, Tuple[str, int]] = {}
    for e in events:
        first.setdefault(e.tid, (e.name, e.prio))
    latest: Dict[int, Tuple[str, int]] = {}
    open_: Dict[int, dict] = {}  # sender tid -> pending block fields
    done: List[dict] = []

    def info(tid):
        return latest.get(tid) or first.get(tid) or (f"tid{tid}", -1)

    for e in events:
        latest[e.tid] = (e.name, e.prio)
        if isinstance(e, MsgSend):
            if e.tid in open_:  # a new send implies the old one is over
                done.append(open_.pop(e.tid))
            name, prio = info(e.peer)
            open_[e.tid] = dict(
                blocked_tid=e.tid, blocked_name=e.name, blocked_prio=e.prio,
                on_tid=e.peer, on_name=name, on_prio=prio,
                start_ns=e.ts_ns, received_ns=None, end_ns=None,
            )
        elif isinstance(e, (MsgReceive, MsgReply)):
            blk = open_.get(e.peer)  # e.peer is the sender
            if blk is None or blk["on_tid"] != e.tid:
                continue
            if isinstance(e, MsgReceive):
                if blk["received_ns"] is None:
                    blk["received_ns"] = e.ts_ns
            else:
                blk["end_ns"] = e.ts_ns
                blk["on_name"], blk["on_prio"] = e.name, e.prio
                done.append(open_.pop(e.peer))
    done.extend(open_.values())
    return sorted((Block(**d) for d in done), key=lambda b: (b.start_ns, b.blocked_tid))


def chain_at(blocks: List[Block], tid: int, ts_ns: int) -> List[Block]:
    """Follow blocked-on edges from tid at ts_ns: A on B, then B on C, ..."""
    chain, seen = [], {tid}
    while True:
        nxt = next((b for b in blocks if b.blocked_tid == tid and b.active_at(ts_ns)), None)
        if nxt is None or nxt.on_tid in seen:
            return chain
        chain.append(nxt)
        seen.add(nxt.on_tid)
        tid = nxt.on_tid
