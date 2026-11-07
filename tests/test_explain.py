import os
import unittest

from blackbox.analysis import analyze
from blackbox.config import load_config
from blackbox.explain import explain
from blackbox.parser import parse_file, parse_text

HERE = os.path.dirname(__file__)


def read(*parts):
    with open(os.path.join(HERE, *parts), encoding="utf-8") as f:
        return f.read()


class ExplainTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(os.path.join(HERE, "fixtures", "scenario_config.json"))

    def test_golden_inversion(self):
        events = parse_file(os.path.join(HERE, "fixtures", "scenario_inversion.trace"))
        text = explain(analyze(events, self.config), self.config)
        self.assertEqual(text, read("golden", "scenario_inversion.txt"))

    def test_no_misses(self):
        events = parse_text(
            "0 THREAD_STATE tid=1 name=high prio=20 state=RELEASED\n"
            "1000000 THREAD_STATE tid=1 name=high prio=20 state=DONE\n"
        )
        self.assertEqual(explain(analyze(events, self.config), self.config),
                         "No deadline misses found.\n")

    def test_miss_without_cause(self):
        events = parse_text(
            "0 THREAD_STATE tid=1 name=high prio=20 state=RELEASED\n"
            "9000000 THREAD_STATE tid=1 name=high prio=20 state=DONE\n"
        )
        text = explain(analyze(events, self.config), self.config)
        self.assertIn("No cause was identified", text)

    def test_unfinished_job_wording(self):
        events = parse_text(
            "0 THREAD_STATE tid=1 name=high prio=20 state=RELEASED\n"
            "9000000 RUN tid=2 name=med prio=10\n"
        )
        text = explain(analyze(events, self.config), self.config)
        self.assertIn("had not finished by the end of the trace", text)


if __name__ == "__main__":
    unittest.main()
