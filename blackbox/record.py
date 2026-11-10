"""Record a trace on the target with tracelogger and copy it back.

Checked on QNX SDP 8.0 (x86_64 QEMU): `-w` records wide events (thread
priorities, which the adapter needs), `-n 0` logs until stopped instead of the
default 32 buffers, and `slay tracelogger` stops it and leaves a valid file.
The file copied back is raw; decode it with `traceprinter` on the host and map
it with `blackbox/adapters/tracelogger.py`.
"""

import shlex
from typing import Iterable, List

from .runner import Runner, RunnerError

DEFAULT_REMOTE_PATH = "/tmp/blackbox.kev"


def record(runner: Runner, seconds: int, out_path: str,
           remote_path: str = DEFAULT_REMOTE_PATH,
           inject: Iterable[str] = ()) -> List[str]:
    """Start tracelogger, run `inject` commands, wait, stop, copy the file.

    Returns the commands that were run on the target, in order.
    """
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
        raise ValueError("seconds must be a positive integer")
    remote = shlex.quote(remote_path)
    start = f"(tracelogger -w -n 0 -f {remote} >/dev/null 2>&1 &)"
    stop = "slay tracelogger"
    ran = []

    def run(cmd: str, timeout=None):
        ran.append(cmd)
        return runner.run(cmd, timeout=timeout)

    res = run(start)
    if res.returncode != 0:
        raise RunnerError(f"could not start tracelogger: {res.stderr.strip()}")
    try:
        for cmd in inject:
            run(cmd)
        run(f"sleep {seconds}", timeout=seconds + 30)
    finally:
        run(stop)  # never leave the logger running, even if a step failed
    runner.get(remote_path, out_path)
    return ran
