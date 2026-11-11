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

    def test_analyze_without_config_infers_it(self):
        r = run("analyze", os.path.join(FIXTURES, "real", "inversion_demo.trace"),
                "--deadline", "controller=20")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("Inferred from the trace: controller every 50.1 ms, priority 20, deadline 20 ms.", r.stdout)
        self.assertIn("Found 10 deadline misses.", r.stdout)
        r = run("analyze", os.path.join(FIXTURES, "basic.trace"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("pass --config", r.stderr)
        r = run("analyze", os.path.join(FIXTURES, "real", "inversion_demo.trace"), "--deadline", "x")
        self.assertEqual(r.returncode, 2)

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

    def test_reads_traceprinter_text_directly(self):
        text = (
            "  TRACE_CYCLES_PER_SEC:: 1000000000\n"
            "t:0x00000001 CPU:00 CONTROL         :TIME               msb:0x00000000 lsb(offset):0x00000001\n"
            "t:0x00000001 CPU:00 PROCESS         :PROCTHREAD_NAME\n"
            "                       pid:7\n"
            "                       tid:1\n"
            "                      name:high\n"
            "t:0x00000002 CPU:00 THREAD          :THRUNNING          pid:7 tid:1 priority:20 policy:1\n"
            't:0x00000003 CPU:00 USREVENT        :EVENT:100          STR:"blackbox RELEASED", d0:0x0\n'
            't:0x01000000 CPU:00 USREVENT        :EVENT:100          STR:"blackbox DONE", d0:0x0\n'
        )
        with tempfile.TemporaryDirectory() as d:
            trace = os.path.join(d, "trace.txt")
            with open(trace, "w") as f:
                f.write(text)
            r = run("analyze", trace, "--config", CONFIG)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("high missed its 5.0 ms deadline", r.stdout)

    def test_binary_kev_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            kev = os.path.join(d, "trace.kev")
            with open(kev, "wb") as f:
                f.write(bytes([0x88, 0, 0, 0, 0xff]) * 10)
            r = run("analyze", kev, "--config", CONFIG)
        self.assertEqual(r.returncode, 2)
        self.assertIn("decode it with traceprinter", r.stderr)


if __name__ == "__main__":
    unittest.main()
