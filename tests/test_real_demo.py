"""End to end on real captures: target/inversion_demo run for 5 s on QNX SDP
8.0 (x86_64 QEMU), without and with --fixed, recorded with tracelogger -w,
decoded with traceprinter and converted by blackbox.adapters.tracelogger."""

import os
import unittest

from blackbox.analysis import analyze
from blackbox.config import load_config
from blackbox.events import MsgReceive
from blackbox.explain import explain
from blackbox.parser import parse_file

REAL = os.path.join(os.path.dirname(__file__), "fixtures", "real")


class RealDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_config(os.path.join(REAL, "inversion_demo.json"))
        cls.events = parse_file(os.path.join(REAL, "inversion_demo.trace"))
        cls.config = config
        cls.result = analyze(cls.events, config)
        cls.fixed = analyze(parse_file(os.path.join(REAL, "inversion_demo_fixed.trace")), config)

    def test_controller_misses_its_deadline(self):
        self.assertGreater(len(self.result.misses), 0)
        self.assertEqual({j.name for j in self.result.misses}, {"controller"})

    def test_misses_are_blamed_on_the_server_reply(self):
        slow = {d.job for d in self.result.reply_delays if d.block.on_name == "server"}
        self.assertEqual(slow, set(self.result.misses))

    def test_priority_inheritance_fixes_it(self):
        self.assertEqual(len(self.result.misses), 10)  # the demo printed 10 too
        self.assertEqual(self.fixed.misses, [])

    def test_mutex_wait_points_at_med_and_low(self):
        by_job = {w.job: w for w in self.result.mutex_waits}
        self.assertEqual(set(by_job), set(self.result.misses))
        for w in by_job.values():
            self.assertEqual((w.name, w.prio), ("server", 20))
            self.assertLessEqual({"med", "low"}, {n for n, _, _ in w.ran})
        self.assertEqual(self.fixed.mutex_waits, [])

    def test_brief_kernel_threads_are_not_blamed(self):
        # 5% of the 20 ms deadline; interrupt threads run for microseconds
        self.assertTrue(all(s.run_ns >= 1_000_000 for s in self.result.starvation))

    def test_server_inherits_the_client_priority(self):
        # QNX runs the server at the sender's priority once it receives.
        prios = {e.prio for e in self.events if isinstance(e, MsgReceive) and e.name == "server"}
        self.assertEqual(prios, {20})

    def test_summary_names_the_pattern_once(self):
        text = explain(self.result, self.config)
        head = text.split("Details:")[0]
        self.assertIn("controller: 10 misses", head)
        self.assertIn("Cause in 10 of 10: slow reply from server", head)
        self.assertIn("med preempted low", head)
        self.assertEqual(text.count("PTHREAD_PRIO_INHERIT"), 1)


if __name__ == "__main__":
    unittest.main()
