import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from blackbox.cli import main
from blackbox.record import record
from blackbox.runner import MockRunner, Result, RunnerError

START = "(tracelogger -w -n 0 -f /tmp/blackbox.kev >/dev/null 2>&1 &)"


class RecordTest(unittest.TestCase):
    def test_sequence_and_copy(self):
        m = MockRunner(files={"/tmp/blackbox.kev": b"RAW"})
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "t.kev")
            ran = record(m, 7, out, inject=["slay -s KILL sensor"])
            with open(out, "rb") as f:
                self.assertEqual(f.read(), b"RAW")
        self.assertEqual(ran, [START, "slay -s KILL sensor", "sleep 7", "slay tracelogger"])
        self.assertEqual(m.commands, ran)

    def test_start_failure_raises_without_stop(self):
        m = MockRunner({START: Result(1, "", "no tracelogger")})
        with self.assertRaises(RunnerError):
            record(m, 5, "x")
        self.assertEqual(m.commands, [START])

    def test_logger_stopped_when_a_step_fails(self):
        class Boom(MockRunner):
            def run(self, command, timeout=None):
                if command.startswith("sleep"):
                    raise RunnerError("ssh dropped")
                return super().run(command, timeout)

        m = Boom()
        with self.assertRaises(RunnerError):
            record(m, 5, "x")
        self.assertEqual(m.commands[-1], "slay tracelogger")

    def test_missing_remote_file_raises(self):
        with self.assertRaises(RunnerError):
            record(MockRunner(), 5, "x")

    def test_bad_seconds(self):
        for s in (0, -1, True, "5"):
            with self.assertRaises(ValueError):
                record(MockRunner(), s, "x")

    def test_remote_path_is_quoted(self):
        m = MockRunner(files={"/tmp/a b": b""})
        with tempfile.TemporaryDirectory() as d:
            record(m, 1, os.path.join(d, "o"), remote_path="/tmp/a b")
        self.assertIn("-f '/tmp/a b'", m.commands[0])


class RecordCliTest(unittest.TestCase):
    def run_cli(self, argv, files):
        m = MockRunner(files=files)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv, runner_factory=lambda host: m)
        return code, out.getvalue(), err.getvalue()

    def test_record_ok(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "t.kev")
            code, out, _ = self.run_cli(
                ["record", "--target", "root@qnx", "--seconds", "3", "--out", dest],
                {"/tmp/blackbox.kev": b"RAW"})
            self.assertEqual(code, 0)
            self.assertIn(dest, out)
            self.assertTrue(os.path.exists(dest))

    def test_record_failure_exits_2(self):
        code, _, err = self.run_cli(["record", "--target", "h", "--seconds", "3"], {})
        self.assertEqual(code, 2)
        self.assertIn("error:", err)

    def test_record_bad_seconds_exits_2(self):
        code, _, err = self.run_cli(["record", "--target", "h", "--seconds", "0"], {})
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
