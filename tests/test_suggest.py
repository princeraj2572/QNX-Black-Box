import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from blackbox.analysis import analyze
from blackbox.cli import main
from blackbox.config import load_config
from blackbox.parser import parse_file
from blackbox.report import build_report
from blackbox.suggest import API_URL, SuggestError, build_prompt, suggest

ROOT = os.path.join(os.path.dirname(__file__), "..")
REAL = os.path.join(os.path.dirname(__file__), "fixtures", "real")


def real_report() -> dict:
    config = load_config(os.path.join(REAL, "inversion_demo.json"))
    events = parse_file(os.path.join(REAL, "inversion_demo.trace"))
    return build_report(events, analyze(events, config), config)


def answer(text: str) -> bytes:
    return json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode()


class PromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = real_report()

    def test_prompt_carries_the_findings_but_not_the_timeline(self):
        prompt = build_prompt(self.report)
        self.assertIn("controller: period 50", prompt)
        self.assertIn("Deadline misses: 10", prompt)
        self.assertIn("mutex_wait: 10 of 10", prompt)
        self.assertIn("Mutex wait: server (priority 20)", prompt)
        self.assertLess(len(prompt), 6000)  # the raw timeline is megabytes; it must not be sent

    def test_only_the_first_misses_are_described(self):
        prompt = build_prompt(self.report)
        self.assertEqual(prompt.count("- controller: response"), 5)

    def test_source_is_included_and_truncated(self):
        prompt = build_prompt(self.report, "int main(void) { return 0; }\n", "demo.c")
        self.assertIn("Source file demo.c:", prompt)
        self.assertIn("int main(void)", prompt)
        self.assertIn("[truncated]", build_prompt(self.report, "x" * 30000, "big.c"))

    def test_a_report_without_misses_is_refused(self):
        with self.assertRaises(SuggestError):
            build_prompt({"misses": [], "threads": []})


class SuggestTest(unittest.TestCase):
    def test_posts_the_prompt_and_returns_the_text(self):
        seen = {}

        def post(url, headers, body, timeout):
            seen.update(url=url, headers=headers, body=json.loads(body))
            return answer("Use PTHREAD_PRIO_INHERIT.")

        self.assertEqual(suggest("why late?", "KEY", "m1", post=post), "Use PTHREAD_PRIO_INHERIT.")
        self.assertEqual(seen["url"], API_URL.format(model="m1"))
        self.assertEqual(seen["headers"]["x-goog-api-key"], "KEY")
        self.assertNotIn("KEY", seen["url"])  # the key travels in a header, never in the URL
        self.assertEqual(seen["body"]["contents"][0]["parts"][0]["text"], "why late?")

    def test_missing_key_never_reaches_the_network(self):
        def post(*a):
            raise AssertionError("must not connect without a key")

        with self.assertRaises(SuggestError):
            suggest("p", "", post=post)

    def test_api_failures_become_readable_errors(self):
        def http_error(url, headers, body, timeout):
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", None, None)

        def offline(url, headers, body, timeout):
            raise urllib.error.URLError("no route")

        for post, text in ((http_error, "HTTP 429"), (offline, "could not reach"),
                           (lambda *a: b"not json", "unexpected shape"),
                           (lambda *a: b'{"candidates": []}', "unexpected shape"),
                           (lambda *a: answer("  "), "empty answer")):
            with self.assertRaises(SuggestError) as ctx:
                suggest("p", "KEY", post=post)
            self.assertIn(text, str(ctx.exception))
            self.assertNotIn("KEY", str(ctx.exception))


class SuggestCliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.report = os.path.join(self.dir.name, "report.json")
        with open(self.report, "w", encoding="utf-8") as f:
            json.dump(real_report(), f)

    def run_cli(self, argv, env=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env or {}, clear=False), \
                redirect_stdout(out), redirect_stderr(err):
            os.environ.pop("GEMINI_API_KEY", None) if env is None else None
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_print_prompt_needs_no_key_and_no_network(self):
        src = os.path.join(ROOT, "target", "inversion_demo.c")
        code, out, err = self.run_cli(["suggest", self.report, "--source", src, "--print-prompt"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Source file inversion_demo.c:", out)
        self.assertIn("pthread_mutex", out)

    def test_without_a_key_it_explains_what_to_set(self):
        code, out, err = self.run_cli(["suggest", self.report])
        self.assertEqual(code, 2)
        self.assertIn("GEMINI_API_KEY", err)
        self.assertEqual(out, "")

    def test_bad_report_is_a_clean_error(self):
        bad = os.path.join(self.dir.name, "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(self.run_cli(["suggest", bad, "--print-prompt"])[0], 2)
        self.assertEqual(self.run_cli(["suggest", os.path.join(self.dir.name, "none.json")])[0], 2)

    def test_answer_is_labelled_as_unverified(self):
        from blackbox import cli
        args = cli.build_parser().parse_args(["suggest", self.report, "--model", "m1"])
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.cmd_suggest(args, ask=lambda prompt, key, model: "Set PTHREAD_PRIO_INHERIT.")
        self.assertEqual(code, 0)
        self.assertIn("not verified", out.getvalue())
        self.assertIn("Set PTHREAD_PRIO_INHERIT.", out.getvalue())

    def test_module_entry_point(self):
        r = subprocess.run([sys.executable, "-m", "blackbox", "suggest", self.report, "--print-prompt"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Deadline misses: 10", r.stdout)


if __name__ == "__main__":
    unittest.main()
