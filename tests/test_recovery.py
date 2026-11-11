import os
import subprocess
import sys
import tempfile
import unittest

from blackbox.parser import parse_file, parse_lines
from blackbox.recovery import find_restarts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# worker (pid 7) is killed after 20 ms; ham starts pid 9 at 25 ms.
TRACE = """\
0 RUN tid=7001 name=worker prio=15
10000000 THREAD_STATE tid=7001 name=worker prio=15 state=RELEASED
20000000 THREAD_STATE tid=7001 name=worker prio=15 state=DONE
1000 RUN tid=3001 name=pool prio=10
2000 RUN tid=3002 name=pool prio=10
30000000 RUN tid=3001 name=pool prio=10
25000000 RUN tid=9001 name=worker prio=15
35000000 THREAD_STATE tid=9001 name=worker prio=15 state=RELEASED
"""


class RecoveryTest(unittest.TestCase):
    def test_finds_restart_and_ignores_overlapping_threads(self):
        restarts = find_restarts(parse_lines(TRACE.splitlines()))
        self.assertEqual(len(restarts), 1)
        r = restarts[0]
        self.assertEqual((r.name, r.old_tid, r.new_tid), ("worker", 7001, 9001))
        self.assertEqual(r.recovery_ns, 5000000)

    def test_name_filter(self):
        events = parse_lines(TRACE.splitlines())
        self.assertEqual(find_restarts(events, ["pool"]), [])
        self.assertEqual(len(find_restarts(events, ["worker"])), 1)

    def test_real_kill_on_qemu(self):
        events = parse_file(os.path.join(ROOT, "tests", "fixtures", "real", "kill_demo.trace"))
        restarts = find_restarts(events, ["controller", "server", "low", "med"])
        self.assertEqual(sorted(r.name for r in restarts), ["controller", "low", "med", "server"])
        for r in restarts:
            self.assertTrue(90e6 < r.recovery_ns < 100e6, r)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.trace")
            with open(path, "w") as f:
                f.write(TRACE)
            r = subprocess.run([sys.executable, "-m", "blackbox", "recovery", path],
                               cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("worker", r.stdout)
        self.assertIn("recovered in 5.000 ms", r.stdout)


if __name__ == "__main__":
    unittest.main()
