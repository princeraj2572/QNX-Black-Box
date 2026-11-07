"""Declarative fault scenarios. Pure: they only build command strings.

Scenario JSON:
{"name": "demo", "faults": [
  {"type": "kill_process", "process": "sensor", "signal": "KILL"},
  {"type": "cpu_hog", "priority": 30, "seconds": 5, "count": 1},
  {"type": "delay_thread", "process": "controller", "seconds": 2},
  {"type": "memory_pressure", "megabytes": 64, "seconds": 5}]}

Every fault renders to commands that return quickly (long-running work is
backgrounded) so the runner can start the next fault right away.

TODO(human): verify each rendered command on a real QNX 8.0 target (slay -s,
on -p, $SECONDS in the target shell, /dev/shmem).
"""

import json
import re
import shlex
from dataclasses import dataclass
from typing import List, Tuple


class ScenarioError(ValueError):
    pass


def _pos_int(spec, key, default=None):
    v = spec.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise ScenarioError(f"{spec.get('type')}: {key} must be a positive integer")
    return v


def _process(spec):
    p = spec.get("process")
    if not isinstance(p, str) or not p:
        raise ScenarioError(f"{spec.get('type')}: process must be a non-empty string")
    return p


def _kill_process(spec) -> List[str]:
    sig = spec.get("signal", "KILL")
    if not isinstance(sig, str) or not re.fullmatch(r"[A-Z]+|[0-9]+", sig):
        raise ScenarioError("kill_process: signal must be like KILL, TERM or 9")
    return [f"slay -s {sig} {shlex.quote(_process(spec))}"]


def _cpu_hog(spec) -> List[str]:
    prio, secs = _pos_int(spec, "priority"), _pos_int(spec, "seconds")
    script = f"end=$((SECONDS+{secs})); while [ $SECONDS -lt $end ]; do :; done"
    one = f"on -p {prio} sh -c {shlex.quote(script)} &"
    return [one] * _pos_int(spec, "count", 1)


def _delay_thread(spec) -> List[str]:
    # Pauses the whole owning process; the internal model has no per-thread control.
    name, secs = shlex.quote(_process(spec)), _pos_int(spec, "seconds")
    return [f"(slay -s STOP {name}; sleep {secs}; slay -s CONT {name}) &"]


def _memory_pressure(spec) -> List[str]:
    mb, secs = _pos_int(spec, "megabytes"), _pos_int(spec, "seconds")
    f = "/dev/shmem/blackbox_mem"
    return [f"(dd if=/dev/zero of={f} bs=1M count={mb}; sleep {secs}; rm -f {f}) &"]


FAULTS = {
    "kill_process": _kill_process,
    "cpu_hog": _cpu_hog,
    "delay_thread": _delay_thread,
    "memory_pressure": _memory_pressure,
}


@dataclass(frozen=True)
class Scenario:
    name: str
    faults: Tuple[dict, ...]

    def commands(self) -> List[str]:
        out: List[str] = []
        for spec in self.faults:
            out += FAULTS[spec["type"]](spec)
        return out


def parse_scenario(data) -> Scenario:
    if not isinstance(data, dict) or not isinstance(data.get("name"), str) or not data["name"]:
        raise ScenarioError("scenario must be an object with a non-empty 'name'")
    faults = data.get("faults")
    if not isinstance(faults, list) or not faults:
        raise ScenarioError("scenario needs a non-empty 'faults' list")
    for spec in faults:
        if not isinstance(spec, dict) or spec.get("type") not in FAULTS:
            raise ScenarioError(f"unknown fault: {spec!r}; known: {sorted(FAULTS)}")
    scenario = Scenario(data["name"], tuple(faults))
    scenario.commands()  # validate every fault's parameters up front
    return scenario


def load_scenario(path: str) -> Scenario:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return parse_scenario(json.load(f))
    except json.JSONDecodeError as exc:
        raise ScenarioError(f"{path}: invalid JSON: {exc}") from None
