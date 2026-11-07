import io
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout

from blackbox.cli import main
from blackbox.serve import make_server

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
CONFIG = os.path.join(FIXTURES, "scenario_config.json")
TRACE = os.path.join(FIXTURES, "scenario_inversion.trace")


class ServeTest(unittest.TestCase):
    def start(self, trace):
        server = make_server(trace, CONFIG, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def get(self, url):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8")

    def test_serves_dashboard_with_auto_refresh(self):
        status, body = self.get(self.start(TRACE) + "/")
        self.assertEqual(status, 200)
        self.assertIn('id="timeline"', body)
        self.assertIn('<meta http-equiv="refresh"', body)
        self.assertIn("Priority inversion", body)

    def test_rebuilds_on_every_request(self):
        with tempfile.TemporaryDirectory() as d:
            trace = os.path.join(d, "t.trace")
            shutil.copy(TRACE, trace)
            base = self.start(trace)
            self.assertIn("Priority inversion", self.get(base + "/")[1])
            with open(trace, "w") as f:
                f.write("0 THREAD_STATE tid=1 name=high prio=20 state=RELEASED\n"
                        "1000000 THREAD_STATE tid=1 name=high prio=20 state=DONE\n")
            self.assertIn("No deadline misses found.", self.get(base + "/")[1])

    def test_bad_trace_is_a_500_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            trace = os.path.join(d, "t.trace")
            with open(trace, "w") as f:
                f.write("1 BOGUS\n")
            base = self.start(trace)
            status, body = self.get(base + "/")
            self.assertEqual(status, 500)
            self.assertIn("line 1", body)
            with open(trace, "w") as f:  # fixing the file recovers the page
                f.write("")
            self.assertEqual(self.get(base + "/")[0], 200)

    def test_other_paths_are_404(self):
        self.assertEqual(self.get(self.start(TRACE) + "/etc/passwd")[0], 404)

    def test_binds_loopback_only(self):
        server = make_server(TRACE, CONFIG, port=0)
        self.addCleanup(server.server_close)
        self.assertEqual(server.server_address[0], "127.0.0.1")


class ServeCliTest(unittest.TestCase):
    def test_bad_inputs_exit_2_before_serving(self):
        for argv in (["serve", os.path.join(FIXTURES, "nope.trace"), "--config", CONFIG],
                     ["serve", TRACE, "--config", os.path.join(FIXTURES, "nope.json")]):
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                self.assertEqual(main(argv), 2)
            self.assertIn("error:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
