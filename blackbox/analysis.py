"""Run every detector over a trace and collect the results."""

from dataclasses import dataclass
from typing import Dict, List

from .causes import ReplyDelay, Starvation, find_reply_delays, find_starvation
from .config import ThreadConfig
from .deadlines import Job, find_misses
from .events import Event
from .inversion import Inversion, find_inversions


@dataclass(frozen=True)
class Analysis:
    trace_end_ns: int
    misses: List[Job]
    inversions: List[Inversion]
    starvation: List[Starvation]
    reply_delays: List[ReplyDelay]


def analyze(events: List[Event], config: Dict[str, ThreadConfig]) -> Analysis:
    misses = find_misses(events, config)
    return Analysis(
        trace_end_ns=max((e.ts_ns for e in events), default=0),
        misses=misses,
        inversions=find_inversions(events),
        starvation=find_starvation(events, misses, config),
        reply_delays=find_reply_delays(events, misses, config),
    )
