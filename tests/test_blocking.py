import unittest

from blackbox.blocking import build_blocks, chain_at
from blackbox.parser import parse_text

# controller(4) -> sensor(7) -> driver(9); driver replies at 400, sensor at 500.
CHAIN = """
100 MSG_SEND tid=4 name=controller prio=20 peer=7
150 MSG_RECEIVE tid=7 name=sensor prio=10 peer=4
200 MSG_SEND tid=7 name=sensor prio=10 peer=9
250 MSG_RECEIVE tid=9 name=driver prio=5 peer=7
400 MSG_REPLY tid=9 name=driver prio=5 peer=7
500 MSG_REPLY tid=7 name=sensor prio=10 peer=4
"""


class BlockingTest(unittest.TestCase):
    def test_intervals(self):
        blocks = build_blocks(parse_text(CHAIN))
        self.assertEqual(len(blocks), 2)
        a, b = blocks
        self.assertEqual((a.blocked_name, a.on_name, a.start_ns, a.received_ns, a.end_ns),
                         ("controller", "sensor", 100, 150, 500))
        self.assertEqual((b.blocked_name, b.on_name, b.on_prio, b.start_ns, b.end_ns),
                         ("sensor", "driver", 5, 200, 400))

    def test_chain(self):
        blocks = build_blocks(parse_text(CHAIN))
        self.assertEqual([b.on_name for b in chain_at(blocks, 4, 300)], ["sensor", "driver"])
        self.assertEqual([b.on_name for b in chain_at(blocks, 4, 450)], ["sensor"])
        self.assertEqual(chain_at(blocks, 4, 50), [])
        self.assertEqual(chain_at(blocks, 4, 500), [])  # end is exclusive

    def test_unreplied_send_stays_open(self):
        blocks = build_blocks(parse_text("10 MSG_SEND tid=1 name=a prio=1 peer=2\n"))
        self.assertIsNone(blocks[0].end_ns)
        self.assertEqual(blocks[0].on_name, "tid2")
        self.assertTrue(blocks[0].active_at(10**9))

    def test_reply_from_wrong_thread_is_ignored(self):
        text = (
            "10 MSG_SEND tid=1 name=a prio=1 peer=2\n"
            "20 MSG_REPLY tid=3 name=c prio=1 peer=1\n"
        )
        self.assertIsNone(build_blocks(parse_text(text))[0].end_ns)

    def test_cycle_terminates(self):
        text = (
            "10 MSG_SEND tid=1 name=a prio=1 peer=2\n"
            "11 MSG_SEND tid=2 name=b prio=1 peer=1\n"
        )
        self.assertEqual(len(chain_at(build_blocks(parse_text(text)), 1, 12)), 1)


if __name__ == "__main__":
    unittest.main()
