import io
import json
import os
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from blackbox.analysis import analyze
from blackbox.cli import main
from blackbox.config import load_config
from blackbox.dashboard import ReportFormatError, render_html
from blackbox.parser import parse_file, parse_text
from blackbox.report import build_report

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def make_report(events=None):
    config = load_config(os.path.join(FIXTURES, "scenario_config.json"))
    if events is None:
        events = parse_file(os.path.join(FIXTURES, "scenario_inversion.trace"))
    return build_report(events, analyze(events, config), config)


class DashboardTest(unittest.TestCase):
    def test_key_elements(self):
        page = render_html(make_report())
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn('<svg id="timeline"', page)
        for table in ('id="steps"', 'id="jobs"', 'id="cpu"'):
            self.assertIn(table, page)
        self.assertIn('<script id="data" type="application/json">', page)
        self.assertIn("Priority inversion", page)  # static explanation text
        self.assertIn("high missed its 5.0 ms deadline", page)

    def test_embedded_data_is_the_report(self):
        report = make_report()
        page = render_html(report)
        raw = re.search(r'<script id="data"[^>]*>(.*?)</script>', page, re.S).group(1)
        self.assertEqual(json.loads(raw), report)

    def test_self_contained(self):
        page = render_html(make_report())
        for needle in ("src=", "href=", "<link", "@import", "url("):
            self.assertNotIn(needle, page)

    def test_hostile_thread_names_cannot_break_out(self):
        events = parse_text(
            "0 THREAD_STATE tid=1 name=</script><b>x prio=20 state=RELEASED\n"
            "9000000 THREAD_STATE tid=1 name=</script><b>x prio=20 state=DONE\n"
        )
        config = load_config(os.path.join(FIXTURES, "scenario_config.json"))
        config["</script><b>x"] = config["high"].__class__("</script><b>x", 20, 5, 20)
        report = build_report(events, analyze(events, config), config)
        page = render_html(report)
        self.assertEqual(page.count("</script>"), 2)  # only the two real ones
        self.assertNotIn("<b>x", page.split('<script id="data"')[0])  # static HTML is escaped
        self.assertIn("&lt;/script&gt;&lt;b&gt;x missed", page)

    def test_placeholder_text_in_data_is_not_substituted(self):
        report = make_report()
        report["threads"][0]["name"] = "__MISSES__"
        self.assertIn('"__MISSES__"', render_html(report))

    def test_no_misses(self):
        self.assertIn("No deadline misses found.", render_html(make_report([])))

    def test_rejects_non_report(self):
        for bad in ([], {}, {"version": 1}):
            with self.assertRaises(ReportFormatError):
                render_html(bad)


class RealDashboardTest(unittest.TestCase):
    """The summary and miss list are static HTML, so they read without JS."""

    def test_summary_list_and_fix(self):
        real = os.path.join(FIXTURES, "real")
        config = load_config(os.path.join(real, "inversion_demo.json"))
        events = parse_file(os.path.join(real, "inversion_demo.trace"))
        page = render_html(build_report(events, analyze(events, config), config))
        static = page.split('<script id="data"')[0]
        self.assertIn("controller missed its 20 ms deadline 10 times.", static)
        self.assertIn('10/10</span> server waited on a mutex while med preempted low', static)
        self.assertIn("PTHREAD_PRIO_INHERIT", static)
        self.assertEqual(static.count('class="row"'), 10)
        self.assertEqual(static.count('<article class="miss"'), 10)

    def test_single_miss_headline(self):
        self.assertIn("high missed its 5 ms deadline once.", render_html(make_report()))


class ReportHtmlCliTest(unittest.TestCase):
    def run_cli(self, *argv):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            return main(list(argv)), err.getvalue()

    def test_writes_page(self):
        with tempfile.TemporaryDirectory() as d:
            rp, out = os.path.join(d, "r.json"), os.path.join(d, "o.html")
            with open(rp, "w") as f:
                json.dump(make_report(), f)
            code, _ = self.run_cli("report-html", rp, out)
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as f:
                self.assertIn('id="timeline"', f.read())

    def test_bad_inputs_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.json")
            with open(bad, "w") as f:
                f.write("{")
            for report in (bad, os.path.join(d, "missing.json")):
                code, err = self.run_cli("report-html", report, os.path.join(d, "o.html"))
                self.assertEqual(code, 2)
                self.assertIn("error:", err)
            with open(bad, "w") as f:
                f.write("[]")
            self.assertEqual(self.run_cli("report-html", bad, os.path.join(d, "o.html"))[0], 2)


if __name__ == "__main__":
    unittest.main()
