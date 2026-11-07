import os
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from blackbox.runner import MockRunner, Result, RunnerError, SSHRunner


class FakeExec:
    def __init__(self, returncode=0, stdout="", stderr="", raises=None):
        self.calls = []
        self.out = SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
        self.raises = raises

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self.raises:
            raise self.raises
        return self.out


class SSHRunnerTest(unittest.TestCase):
    def test_run_builds_ssh_argv(self):
        ex = FakeExec(stdout="hi\n")
        r = SSHRunner("root@10.0.0.2", exec_fn=ex).run("pidin", timeout=5)
        argv, kwargs = ex.calls[0]
        self.assertEqual(argv[0], "ssh")
        self.assertEqual(argv[-2:], ["root@10.0.0.2", "pidin"])
        self.assertIn("BatchMode=yes", argv)
        self.assertEqual(kwargs["timeout"], 5)
        self.assertEqual(r, Result(0, "hi\n", ""))

    def test_get_uses_scp(self):
        ex = FakeExec()
        SSHRunner("qnx", exec_fn=ex).get("/tmp/t.kev", "out.kev")
        argv, _ = ex.calls[0]
        self.assertEqual(argv[0], "scp")
        self.assertEqual(argv[-2:], ["qnx:/tmp/t.kev", "out.kev"])

    def test_get_failure_raises(self):
        with self.assertRaises(RunnerError):
            SSHRunner("qnx", exec_fn=FakeExec(returncode=1, stderr="no")).get("/x", "y")

    def test_missing_binary_and_timeout_raise_runner_error(self):
        with self.assertRaises(RunnerError):
            SSHRunner("qnx", exec_fn=FakeExec(raises=FileNotFoundError("ssh"))).run("x")
        timeout = subprocess.TimeoutExpired("ssh", 1)
        with self.assertRaises(RunnerError):
            SSHRunner("qnx", exec_fn=FakeExec(raises=timeout)).run("x", timeout=1)

    def test_rejects_option_like_hosts(self):
        for host in ["-oProxyCommand=evil", "", "a b", "a;b"]:
            with self.assertRaises(RunnerError, msg=host):
                SSHRunner(host)


class MockRunnerTest(unittest.TestCase):
    def test_records_and_responds(self):
        m = MockRunner({"fail": Result(3, "", "boom")})
        self.assertEqual(m.run("ok"), Result(0))
        self.assertEqual(m.run("fail").returncode, 3)
        self.assertEqual(m.commands, ["ok", "fail"])

    def test_get(self):
        m = MockRunner(files={"/r": b"data"})
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "f")
            m.get("/r", dest)
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"data")
            with self.assertRaises(RunnerError):
                m.get("/missing", dest)


if __name__ == "__main__":
    unittest.main()
