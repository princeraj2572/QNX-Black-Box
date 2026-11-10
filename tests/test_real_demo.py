"""End to end on a real capture: target/inversion_demo run for 5 s on QNX SDP
8.0 (x86_64 QEMU), recorded with tracelogger -w, decoded with traceprinter and
converted by blackbox.adapters.tracelogger."""

import os
import unittest

from blackbox.analysis import analyze
from blackbox.config import load_config
from blackbox.events import MsgReceive
from blackbox.parser import parse_file

REAL = os.path.join(os.path.dirname(__file__), "fixtures", "real")


class RealDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = parse_file(os.path.join(REAL, "inversion_demo.trace"))
        cls.result = analyze(cls.events, load_config(os.path.join(REAL, "inversion_demo.json")))

    def test_controller_misses_its_deadline(self):
        self.assertGreater(len(self.result.misses), 0)
        self.assertEqual({j.name for j in self.result.misses}, {"controller"})

    def test_misses_are_blamed_on_the_server_reply(self):
        slow = {d.job for d in self.result.reply_delays if d.block.on_name == "server"}
        self.assertEqual(slow, set(self.result.misses))

    def test_brief_kernel_threads_are_not_blamed(self):
        # 5% of the 20 ms deadline; interrupt threads run for microseconds
        self.assertTrue(all(s.run_ns >= 1_000_000 for s in self.result.starvation))

    def test_server_inherits_the_client_priority(self):
        # QNX runs the server at the sender's priority once it receives.
        prios = {e.prio for e in self.events if isinstance(e, MsgReceive) and e.name == "server"}
        self.assertEqual(prios, {20})


if __name__ == "__main__":
    unittest.main()
