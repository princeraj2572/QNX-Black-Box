import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
CONFIG = os.path.join(FIXTURES, "scenario_config.json")


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "blackbox", *args],
        cwd=ROOT, capture_output=True, text=True,
    )


class CliTest(unittest.TestCase):
    def test_miss_exits_1_and_explains(self):
        r = run("analyze", os.path.join(FIXTURES, "scenario_inversion.trace"), "--config", CONFIG)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("Priority inversion", r.stdout)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.json")
            r = run("analyze", os.path.join(FIXTURES, "scenario_inversion.trace"),
                    "--config", CONFIG, "--json", out)
            self.assertEqual(r.returncode, 1, r.stderr)
            with open(out, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["misses"][0]["thread"], "high")

    def test_no_miss_exits_0(self):
        with tempfile.TemporaryDirectory() as d:
            trace = os.path.join(d, "ok.trace")
            with open(trace, "w") as f:
                f.write("0 THREAD_STATE tid=1 name=high prio=20 state=RELEASED\n"
                        "1000000 THREAD_STATE tid=1 name=high prio=20 state=DONE\n")
            r = run("analyze", trace, "--config", CONFIG)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("No deadline misses", r.stdout)

    def test_errors_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.trace")
            with open(bad, "w") as f:
                f.write("1 RUN tid=1 name=a prio=1\n2 BOGUS\n")
            r = run("analyze", bad, "--config", CONFIG)
            self.assertEqual(r.returncode, 2)
            self.assertIn("line 2", r.stderr)
        r = run("analyze", os.path.join(FIXTURES, "nope.trace"), "--config", CONFIG)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(run("analyze").returncode, 2)
        self.assertEqual(run().returncode, 2)


if __name__ == "__main__":
    unittest.main()
