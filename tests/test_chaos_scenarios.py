import json
import os
import tempfile
import unittest

from blackbox.chaos.scenarios import ScenarioError, load_scenario, parse_scenario


def one(**fault):
    return parse_scenario({"name": "t", "faults": [fault]}).commands()


class ScenarioTest(unittest.TestCase):
    def test_kill_process(self):
        self.assertEqual(one(type="kill_process", process="sensor"), ["slay -s KILL sensor"])
        self.assertEqual(one(type="kill_process", process="sensor", signal="TERM"),
                         ["slay -s TERM sensor"])

    def test_process_names_are_quoted(self):
        (cmd,) = one(type="kill_process", process="a; rm -rf /")
        self.assertEqual(cmd, "slay -s KILL 'a; rm -rf /'")

    def test_cpu_hog(self):
        cmds = one(type="cpu_hog", priority=30, seconds=5, count=2)
        self.assertEqual(len(cmds), 2)
        self.assertTrue(cmds[0].startswith("on -p 30 sh -c "))
        self.assertIn("SECONDS+5", cmds[0])
        self.assertTrue(cmds[0].endswith("&"))

    def test_delay_thread(self):
        self.assertEqual(
            one(type="delay_thread", process="controller", seconds=2),
            ["(slay -s STOP controller; sleep 2; slay -s CONT controller) &"],
        )

    def test_memory_pressure(self):
        (cmd,) = one(type="memory_pressure", megabytes=64, seconds=5)
        self.assertIn("count=64", cmd)
        self.assertIn("sleep 5", cmd)

    def test_multiple_faults_keep_order(self):
        s = parse_scenario({"name": "t", "faults": [
            {"type": "kill_process", "process": "a"},
            {"type": "delay_thread", "process": "b", "seconds": 1},
        ]})
        self.assertTrue(s.commands()[0].startswith("slay -s KILL"))
        self.assertIn("STOP b", s.commands()[1])

    def test_rejects_bad_scenarios(self):
        bad = [
            [], {}, {"name": "x"}, {"name": "x", "faults": []},
            {"name": "", "faults": [{"type": "cpu_hog"}]},
            {"name": "x", "faults": [{"type": "reboot"}]},
            {"name": "x", "faults": ["kill"]},
            {"name": "x", "faults": [{"type": "kill_process"}]},
            {"name": "x", "faults": [{"type": "kill_process", "process": "a", "signal": "kill"}]},
            {"name": "x", "faults": [{"type": "cpu_hog", "priority": 0, "seconds": 1}]},
            {"name": "x", "faults": [{"type": "cpu_hog", "priority": 5, "seconds": "1"}]},
            {"name": "x", "faults": [{"type": "memory_pressure", "megabytes": 1}]},
        ]
        for data in bad:
            with self.assertRaises(ScenarioError, msg=repr(data)):
                parse_scenario(data)

    def test_load_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            with open(p, "w") as f:
                json.dump({"name": "x", "faults": [{"type": "kill_process", "process": "a"}]}, f)
            self.assertEqual(load_scenario(p).name, "x")
            with open(p, "w") as f:
                f.write("[")
            with self.assertRaises(ScenarioError):
                load_scenario(p)


if __name__ == "__main__":
    unittest.main()
