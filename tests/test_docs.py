import os
import unittest

from blackbox.analysis import analyze
from blackbox.cli import build_parser
from blackbox.config import load_config
from blackbox.explain import explain
from blackbox.parser import parse_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class DocsTest(unittest.TestCase):
    def test_readme_covers_every_command(self):
        readme = read("README.md")
        commands = next(a for a in build_parser()._actions if a.dest == "command").choices
        for name in commands:
            self.assertIn(f"-m blackbox {name}", readme)

    def test_readme_sections(self):
        readme = read("README.md")
        for heading in ("## Install", "## Usage", "## Architecture",
                        "## QNX version, target and toolchain"):
            self.assertIn(heading, readme)
        for fact in ("SDP 8.0", "QEMU", "Raspberry Pi 5", "qcc"):
            self.assertIn(fact, readme)

    def test_codelab_shows_real_output(self):
        codelab = read("docs", "codelab.md")
        self.assertIn("30 minutes", codelab)
        self.assertNotIn("[REAL OUTPUT", codelab)
        real = os.path.join(ROOT, "tests", "fixtures", "real")
        events = parse_file(os.path.join(real, "inversion_demo.trace"))
        config = load_config(os.path.join(real, "inversion_demo.json"))
        text = explain(analyze(events, config), config)
        for line in text.splitlines()[:8]:  # header and summary are quoted verbatim
            self.assertIn(line.strip(), codelab)


if __name__ == "__main__":
    unittest.main()
