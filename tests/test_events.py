import unittest

from blackbox.events import (
    EVENT_TYPES,
    MsgReceive,
    MsgReply,
    MsgSend,
    Run,
    ThreadState,
)


class EventTest(unittest.TestCase):
    def test_to_line(self):
        cases = [
            (Run(1000, 4, "controller", 20), "1000 RUN tid=4 name=controller prio=20"),
            (
                ThreadState(2500, 4, "controller", 20, state="READY"),
                "2500 THREAD_STATE tid=4 name=controller prio=20 state=READY",
            ),
            (
                MsgSend(1500, 4, "controller", 20, peer=7),
                "1500 MSG_SEND tid=4 name=controller prio=20 peer=7",
            ),
            (
                MsgReceive(1600, 7, "sensor", 10, peer=4),
                "1600 MSG_RECEIVE tid=7 name=sensor prio=10 peer=4",
            ),
            (
                MsgReply(2400, 7, "sensor", 10, peer=4),
                "2400 MSG_REPLY tid=7 name=sensor prio=10 peer=4",
            ),
        ]
        for event, line in cases:
            self.assertEqual(event.to_line(), line)

    def test_registry_covers_all_kinds(self):
        self.assertEqual(
            sorted(EVENT_TYPES),
            ["MSG_RECEIVE", "MSG_REPLY", "MSG_SEND", "RUN", "THREAD_STATE"],
        )
        for kind, cls in EVENT_TYPES.items():
            self.assertEqual(cls.kind, kind)

    def test_rejects_bad_values(self):
        with self.assertRaises(ValueError):
            Run(-1, 1, "a", 1)
        with self.assertRaises(ValueError):
            Run(0, 1, "has space", 1)
        with self.assertRaises(ValueError):
            Run(0, 1, "", 1)
        with self.assertRaises(ValueError):
            ThreadState(0, 1, "a", 1)  # state missing
        with self.assertRaises(ValueError):
            MsgSend(0, 1, "a", 1)  # peer missing

    def test_events_are_immutable(self):
        e = Run(0, 1, "a", 1)
        with self.assertRaises(Exception):
            e.prio = 2


if __name__ == "__main__":
    unittest.main()
