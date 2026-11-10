"""Parse the internal trace format (docs/trace-format.md) into events."""

from dataclasses import fields
from typing import Iterable, List

from .events import EVENT_TYPES, Event


class ParseError(ValueError):
    def __init__(self, lineno, message: str):
        super().__init__(message if lineno is None else f"line {lineno}: {message}")
        self.lineno = lineno


def parse_line(line: str, lineno: int = 1):
    """Return an Event, or None for blank and comment lines."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split()
    if len(parts) < 2:
        raise ParseError(lineno, "expected '<ts_ns> <EVENT> key=value ...'")
    ts, kind, rest = parts[0], parts[1], parts[2:]
    cls = EVENT_TYPES.get(kind)
    if cls is None:
        raise ParseError(lineno, f"unknown event {kind!r}")
    if not ts.isdigit():
        raise ParseError(lineno, f"bad timestamp {ts!r}")
    kv = {}
    for item in rest:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise ParseError(lineno, f"bad field {item!r}, expected key=value")
        if key in kv:
            raise ParseError(lineno, f"duplicate field {key!r}")
        kv[key] = value
    allowed = {f.name for f in fields(cls)} - {"ts_ns"}
    unknown = set(kv) - allowed
    if unknown:
        raise ParseError(lineno, f"unknown field {sorted(unknown)[0]!r} for {kind}")
    for required in ("tid", "name", "prio"):
        if required not in kv:
            raise ParseError(lineno, f"missing field {required!r}")
    try:
        args = {"ts_ns": int(ts)}
        for key, value in kv.items():
            args[key] = value if key in ("name", "state") else int(value)
        return cls(**args)
    except ValueError as exc:
        raise ParseError(lineno, str(exc)) from None


def parse_lines(lines: Iterable[str]) -> List[Event]:
    events = []
    for lineno, line in enumerate(lines, 1):
        event = parse_line(line, lineno)
        if event is not None:
            events.append(event)
    return events


def parse_text(text: str) -> List[Event]:
    return parse_lines(text.splitlines())


def parse_file(path: str) -> List[Event]:
    """Read the internal format, or traceprinter text, which is converted."""
    with open(path, "rb") as f:
        data = f.read()
    if b"\0" in data[:4096]:
        raise ParseError(None, f"{path} is a binary trace: decode it with traceprinter first")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError(None, f"{path} is not UTF-8 text: {exc}") from None
    if "TRACE_CYCLES_PER_SEC::" in text[:4096]:
        from .adapters.tracelogger import AdapterError, convert
        try:
            return convert(text)
        except AdapterError as exc:
            raise ParseError(None, f"{path}: {exc}") from None
    return parse_text(text)
