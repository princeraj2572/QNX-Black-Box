import json
import os
import unittest

from blackbox.analysis import analyze
from blackbox.config import load_config
from blackbox.parser import parse_file
from blackbox.report import build_report, report_json

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(os.path.join(FIXTURES, "scenario_config.json"))
        self.events = parse_file(os.path.join(FIXTURES, "scenario_inversion.trace"))
        self.report = build_report(
            self.events, analyze(self.events, self.config), self.config
        )

    def test_shape(self):
        r = self.report
        self.assertEqual(r["version"], 1)
        self.assertEqual(r["trace_end_ns"], 10_000_000)
        self.assertEqual([t["name"] for t in r["threads"]], ["high", "med", "low"])
        self.assertEqual(len(r["timeline"]), len(self.events))

    def test_miss(self):
        (m,) = self.report["misses"]
        self.assertEqual((m["thread"], m["response_ns"], m["late_ns"]),
                         ("high", 10_000_000, 5_000_000))
        self.assertEqual([c["type"] for c in m["causes"]],
                         ["priority_inversion", "slow_reply"])
        self.assertEqual(m["causes"][0]["medium"], "med")
        self.assertTrue(m["explanation"][0].startswith("high missed"))

    def test_timeline_entries(self):
        t = self.report["timeline"]
        self.assertEqual(t[0]["event"], "THREAD_STATE")
        self.assertEqual(t[0]["state"], "RELEASED")
        send = next(e for e in t if e["event"] == "MSG_SEND")
        self.assertEqual(send["peer"], 3)

    def test_json_roundtrip(self):
        self.assertEqual(json.loads(report_json(self.report)), self.report)

    def test_no_misses(self):
        r = build_report([], analyze([], self.config), self.config)
        self.assertEqual((r["misses"], r["timeline"]), ([], []))


if __name__ == "__main__":
    unittest.main()
