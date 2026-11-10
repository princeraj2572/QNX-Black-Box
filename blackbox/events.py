"""Event model for the internal trace format (see docs/trace-format.md)."""

from dataclasses import dataclass, fields
from typing import ClassVar, Dict, Type


@dataclass(frozen=True)
class Event:
    kind: ClassVar[str] = ""
    ts_ns: int
    tid: int
    name: str
    prio: int

    def __post_init__(self):
        if self.ts_ns < 0:
            raise ValueError("ts_ns must be >= 0")
        if not self.name or any(c.isspace() for c in self.name) or "=" in self.name:
            raise ValueError("name must be non-empty with no whitespace or '='")

    def to_line(self) -> str:
        """Render as `<ts_ns> <EVENT> key=value ...`; optional fields at their default are left out."""
        pairs = " ".join(
            f"{f.name}={getattr(self, f.name)}" for f in fields(self)
            if f.name != "ts_ns" and not (f.name == "cpu" and self.cpu == 0)
        )
        return f"{self.ts_ns} {self.kind} {pairs}"


@dataclass(frozen=True)
class Run(Event):
    """Thread starts running on a CPU."""

    kind: ClassVar[str] = "RUN"
    cpu: int = 0  # optional; traces without it are treated as single-CPU


@dataclass(frozen=True)
class ThreadState(Event):
    """Thread changes scheduling state (free-form token, e.g. READY, BLOCKED)."""

    kind: ClassVar[str] = "THREAD_STATE"
    state: str = ""

    def __post_init__(self):
        super().__post_init__()
        if not self.state or any(c.isspace() for c in self.state):
            raise ValueError("state must be a non-empty token")


@dataclass(frozen=True)
class _Msg(Event):
    peer: int = -1  # tid of the other side of the message

    def __post_init__(self):
        super().__post_init__()
        if self.peer < 0:
            raise ValueError("peer tid is required")


@dataclass(frozen=True)
class MsgSend(_Msg):
    kind: ClassVar[str] = "MSG_SEND"


@dataclass(frozen=True)
class MsgReceive(_Msg):
    kind: ClassVar[str] = "MSG_RECEIVE"


@dataclass(frozen=True)
class MsgReply(_Msg):
    kind: ClassVar[str] = "MSG_REPLY"


EVENT_TYPES: Dict[str, Type[Event]] = {
    c.kind: c for c in (Run, ThreadState, MsgSend, MsgReceive, MsgReply)
}
