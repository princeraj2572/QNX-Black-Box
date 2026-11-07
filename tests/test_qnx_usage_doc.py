import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "qnx-usage.md")


class QnxUsageDocTest(unittest.TestCase):
    def test_every_referenced_file_and_symbol_exists(self):
        with open(DOC, encoding="utf-8") as f:
            rows = [line for line in f if line.startswith("| ") and "`" in line]
        self.assertGreater(len(rows), 5)
        for row in rows:
            tokens = re.findall(r"`([^`]+)`", row)
            path = tokens[0]
            full = os.path.join(ROOT, *path.split("/"))
            self.assertTrue(os.path.exists(full), f"{path} does not exist")
            if not path.endswith(".py"):
                continue
            with open(full, encoding="utf-8") as src:
                text = src.read()
            for symbol in tokens[1:]:
                self.assertRegex(text, rf"\b{re.escape(symbol)}\b", f"{symbol} not in {path}")

    def test_covers_required_features(self):
        with open(DOC, encoding="utf-8") as f:
            text = f.read()
        for feature in ("tracelogger", "Instrumented kernel", "Message passing", "pidin", "slog2"):
            self.assertIn(feature, text)
        self.assertIn("TODO(human)", text)


if __name__ == "__main__":
    unittest.main()
