import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from blackbox.cli import main
from blackbox.runner import MockRunner

SCENARIO = os.path.join(os.path.dirname(__file__), "fixtures", "scenario_chaos.json")
START = "(tracelogger -f /tmp/blackbox.kev >/dev/null 2>&1 &)"


def run_cli(argv, runner=None):
    def no_network(host):
        raise AssertionError("dry run must not create a runner")

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv, runner_factory=(lambda host: runner) if runner else no_network)
    return code, out.getvalue(), err.getvalue()


class ChaosCliTest(unittest.TestCase):
    def test_dry_run_prints_commands_and_connects_to_nothing(self):
        code, out, _ = run_cli(["chaos", "run", SCENARIO, "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("slay -s KILL sensor", out)
        self.assertIn("slay -s STOP controller", out)
        self.assertIn("nothing executed", out)

    def test_run_injects_between_start_and_stop(self):
        m = MockRunner(files={"/tmp/blackbox.kev": b"RAW"})
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "t.kev")
            code, out, _ = run_cli(
                ["chaos", "run", SCENARIO, "--target", "root@qnx", "--seconds", "4",
                 "--out", dest], m)
            self.assertTrue(os.path.exists(dest))
        self.assertEqual(code, 0)
        self.assertEqual(m.commands[0], START)
        self.assertEqual(m.commands[1], "slay -s KILL sensor")
        self.assertEqual(m.commands[-2:], ["sleep 4", "slay tracelogger"])

    def test_target_required_without_dry_run(self):
        code, _, err = run_cli(["chaos", "run", SCENARIO], MockRunner())
        self.assertEqual(code, 2)
        self.assertIn("--target", err)

    def test_bad_scenario_file_exits_2(self):
        for path in (os.path.join(os.path.dirname(SCENARIO), "nope.json"),
                     os.path.join(os.path.dirname(SCENARIO), "basic.trace")):
            code, _, err = run_cli(["chaos", "run", path, "--dry-run"])
            self.assertEqual(code, 2)
            self.assertIn("error:", err)

    def test_target_failure_exits_2(self):
        code, _, err = run_cli(["chaos", "run", SCENARIO, "--target", "h"], MockRunner())
        self.assertEqual(code, 2)  # mock has no trace file to copy back


if __name__ == "__main__":
    unittest.main()
