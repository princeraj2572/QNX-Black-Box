import os
import unittest

from blackbox.inversion import find_inversions, run_intervals
from blackbox.parser import parse_file, parse_text

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class InversionTest(unittest.TestCase):
    def test_fixture(self):
        (inv,) = find_inversions(parse_file(os.path.join(FIXTURES, "inversion.trace")))
        self.assertEqual(inv.medium_name, "med")
        self.assertEqual((inv.start_ns, inv.end_ns), (200, 700))
        self.assertEqual(inv.block.blocked_name, "high")
        self.assertEqual(inv.block.on_name, "low")

    def test_run_intervals_are_per_cpu(self):
        events = parse_text(
            "0 RUN tid=1 name=a prio=1\n"
            "2 RUN tid=2 name=b prio=1 cpu=1\n"
            "5 RUN tid=3 name=c prio=1\n"
            "9 RUN tid=4 name=d prio=1 cpu=1\n"
        )
        spans = [(r.name, lo, hi) for r, lo, hi in run_intervals(events)]
        self.assertEqual(spans, [("a", 0, 5), ("b", 2, 9), ("c", 5, 9), ("d", 9, 9)])

    def test_no_inversion_when_blocker_runs(self):
        text = (
            "100 MSG_SEND tid=1 name=high prio=20 peer=3\n"
            "120 RUN tid=3 name=low prio=5\n"
            "900 MSG_REPLY tid=3 name=low prio=5 peer=1\n"
        )
        self.assertEqual(find_inversions(parse_text(text)), [])

    def test_lower_priority_runner_is_not_inversion(self):
        text = (
            "100 MSG_SEND tid=1 name=high prio=20 peer=3\n"
            "120 RUN tid=2 name=idle prio=2\n"
            "900 MSG_REPLY tid=3 name=low prio=5 peer=1\n"
        )
        self.assertEqual(find_inversions(parse_text(text)), [])

    def test_blocked_on_higher_priority_is_not_inversion(self):
        text = (
            "100 MSG_SEND tid=1 name=low prio=5 peer=3\n"
            "120 RUN tid=2 name=med prio=10\n"
            "900 MSG_REPLY tid=3 name=high prio=20 peer=1\n"
        )
        self.assertEqual(find_inversions(parse_text(text)), [])

    def test_unreplied_block_extends_to_trace_end(self):
        text = (
            "100 MSG_SEND tid=1 name=high prio=20 peer=3\n"
            "200 RUN tid=2 name=med prio=10\n"
            "500 RUN tid=3 name=low prio=5\n"
        )
        (inv,) = find_inversions(parse_text(text))
        self.assertEqual((inv.start_ns, inv.end_ns), (200, 500))


if __name__ == "__main__":
    unittest.main()
