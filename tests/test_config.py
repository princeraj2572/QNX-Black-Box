import json
import os
import tempfile
import unittest

from blackbox.config import ConfigError, ThreadConfig, load_config, parse_config

GOOD = {"threads": [{"name": "controller", "period_ms": 10, "deadline_ms": 8, "priority": 20}]}


class ConfigTest(unittest.TestCase):
    def test_parse_good(self):
        self.assertEqual(parse_config(GOOD), [ThreadConfig("controller", 10, 8, 20)])

    def test_load_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            with open(p, "w") as f:
                json.dump(GOOD, f)
            self.assertEqual(load_config(p)["controller"].deadline_ms, 8)
            with open(p, "w") as f:
                f.write("{nope")
            with self.assertRaises(ConfigError):
                load_config(p)

    def test_rejects_bad_configs(self):
        base = GOOD["threads"][0]
        bad = [
            [],
            {},
            {"threads": "x"},
            {"threads": [1]},
            {"threads": [dict(base, name="")]},
            {"threads": [dict(base, name="a b")]},
            {"threads": [dict(base, period_ms=0)]},
            {"threads": [dict(base, deadline_ms=-1)]},
            {"threads": [dict(base, deadline_ms="8")]},
            {"threads": [dict(base, priority=-1)]},
            {"threads": [dict(base, priority=1.5)]},
            {"threads": [dict(base, priority=True)]},
            {"threads": [base, base]},
            {"threads": [{"name": "x"}]},
        ]
        for data in bad:
            with self.assertRaises(ConfigError, msg=repr(data)):
                parse_config(data)


if __name__ == "__main__":
    unittest.main()
