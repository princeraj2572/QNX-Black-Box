import os
import unittest

from blackbox.cli import build_parser

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

    def test_codelab_exists_with_placeholders(self):
        codelab = read("docs", "codelab.md")
        self.assertIn("30 minutes", codelab)
        self.assertIn("[REAL OUTPUT", codelab)


if __name__ == "__main__":
    unittest.main()
