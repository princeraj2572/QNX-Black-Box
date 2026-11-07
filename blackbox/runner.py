"""Run commands on the target and fetch files from it.

SSHRunner shells out to ssh/scp. MockRunner records commands for tests and
dry runs, and never touches the network.
"""

import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


class RunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Runner:
    def run(self, command: str, timeout: Optional[float] = None) -> Result:
        raise NotImplementedError

    def get(self, remote_path: str, local_path: str) -> None:
        raise NotImplementedError


_HOST = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.@:\[\]-]*")


class SSHRunner(Runner):
    def __init__(self, host: str, ssh: str = "ssh", scp: str = "scp",
                 exec_fn: Callable = subprocess.run):
        # A leading '-' would let the host be parsed as an ssh option.
        if not _HOST.fullmatch(host):
            raise RunnerError(f"invalid host {host!r}")
        self.host, self.ssh, self.scp, self._exec = host, ssh, scp, exec_fn

    def _call(self, argv: List[str], timeout: Optional[float]):
        try:
            return self._exec(argv, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RunnerError(f"{argv[0]} failed: {exc}") from None

    def run(self, command: str, timeout: Optional[float] = None) -> Result:
        argv = [self.ssh, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                self.host, command]
        p = self._call(argv, timeout)
        return Result(p.returncode, p.stdout, p.stderr)

    def get(self, remote_path: str, local_path: str) -> None:
        argv = [self.scp, "-o", "BatchMode=yes", f"{self.host}:{remote_path}", local_path]
        p = self._call(argv, None)
        if p.returncode != 0:
            raise RunnerError(f"scp exited {p.returncode}: {p.stderr.strip()}")


class MockRunner(Runner):
    """Records commands; `responses` maps an exact command to a Result."""

    def __init__(self, responses: Optional[Dict[str, Result]] = None,
                 files: Optional[Dict[str, bytes]] = None):
        self.responses = responses or {}
        self.files = files or {}
        self.commands: List[str] = []
        self.fetched: List[str] = []

    def run(self, command: str, timeout: Optional[float] = None) -> Result:
        self.commands.append(command)
        return self.responses.get(command, Result(0))

    def get(self, remote_path: str, local_path: str) -> None:
        if remote_path not in self.files:
            raise RunnerError(f"no such remote file: {remote_path}")
        self.fetched.append(remote_path)
        with open(local_path, "wb") as f:
            f.write(self.files[remote_path])
