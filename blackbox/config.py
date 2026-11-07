"""Load and validate the thread configuration JSON.

Format: {"threads": [{"name": "controller", "period_ms": 10,
"deadline_ms": 10, "priority": 20}, ...]}
"""

import json
from dataclasses import dataclass
from typing import Dict, List


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ThreadConfig:
    name: str
    period_ms: float
    deadline_ms: float
    priority: int


def _num(entry, key, where):
    v = entry.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        raise ConfigError(f"{where}: {key} must be a positive number")
    return v


def parse_config(data) -> List[ThreadConfig]:
    if not isinstance(data, dict) or not isinstance(data.get("threads"), list):
        raise ConfigError("config must be an object with a 'threads' list")
    threads, seen = [], set()
    for i, entry in enumerate(data["threads"]):
        where = f"threads[{i}]"
        if not isinstance(entry, dict):
            raise ConfigError(f"{where}: must be an object")
        name = entry.get("name")
        if not isinstance(name, str) or not name or any(c.isspace() for c in name):
            raise ConfigError(f"{where}: name must be a non-empty string without whitespace")
        if name in seen:
            raise ConfigError(f"{where}: duplicate thread name {name!r}")
        seen.add(name)
        period = _num(entry, "period_ms", where)
        deadline = _num(entry, "deadline_ms", where)
        prio = entry.get("priority")
        if isinstance(prio, bool) or not isinstance(prio, int) or prio < 0:
            raise ConfigError(f"{where}: priority must be a non-negative integer")
        threads.append(ThreadConfig(name, period, deadline, prio))
    return threads


def load_config(path: str) -> Dict[str, ThreadConfig]:
    """Return thread configs keyed by name."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON: {exc}") from None
    return {t.name: t for t in parse_config(data)}
