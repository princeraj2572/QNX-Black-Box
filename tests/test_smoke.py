import unittest

import blackbox


class SmokeTest(unittest.TestCase):
    def test_package_has_version(self):
        self.assertTrue(blackbox.__version__)


if __name__ == "__main__":
    unittest.main()
