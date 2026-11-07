"""Record a trace on the target with tracelogger and copy it back.

TODO(human): confirm the tracelogger flags on QNX 8.0 (output file option,
running it in the background) and that `slay tracelogger` stops it cleanly.
The file copied back is the raw tracelogger output; converting it to the
internal text format is the adapter's job (PLAN.md F20).
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
    start = f"(tracelogger -f {remote} >/dev/null 2>&1 &)"
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
