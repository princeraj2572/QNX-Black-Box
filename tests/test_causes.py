import unittest

from blackbox.causes import find_reply_delays, find_starvation
from blackbox.config import ThreadConfig
from blackbox.deadlines import find_misses
from blackbox.parser import parse_text

CONFIG = {"ctl": ThreadConfig("ctl", 10, 8, 10)}  # 8 ms deadline, prio 10
MS = 1_000_000

STARVED = f"""
0 THREAD_STATE tid=1 name=ctl prio=10 state=RELEASED
{1*MS} RUN tid=2 name=logger prio=30
{9*MS} RUN tid=1 name=ctl prio=10
{12*MS} THREAD_STATE tid=1 name=ctl prio=10 state=DONE
"""

SLOW_REPLY = f"""
0 THREAD_STATE tid=1 name=ctl prio=10 state=RELEASED
{1*MS} MSG_SEND tid=1 name=ctl prio=10 peer=5
{2*MS} MSG_RECEIVE tid=5 name=db prio=10 peer=1
{11*MS} MSG_REPLY tid=5 name=db prio=10 peer=1
{12*MS} THREAD_STATE tid=1 name=ctl prio=10 state=DONE
"""


class CausesTest(unittest.TestCase):
    def test_starvation(self):
        events = parse_text(STARVED)
        misses = find_misses(events, CONFIG)
        (s,) = find_starvation(events, misses, CONFIG)
        self.assertEqual((s.hog_name, s.hog_prio, s.run_ns), ("logger", 30, 8 * MS))

    def test_lower_priority_runner_is_not_starvation(self):
        events = parse_text(STARVED.replace("prio=30", "prio=3"))
        misses = find_misses(events, CONFIG)
        self.assertEqual(find_starvation(events, misses, CONFIG), [])

    def test_reply_delay(self):
        events = parse_text(SLOW_REPLY)
        misses = find_misses(events, CONFIG)
        (d,) = find_reply_delays(events, misses, CONFIG)
        self.assertEqual((d.block.on_name, d.duration_ns), ("db", 10 * MS))

    def test_short_reply_is_not_reported(self):
        events = parse_text(SLOW_REPLY.replace(f"{11*MS} MSG_REPLY", f"{2*MS+1} MSG_REPLY"))
        misses = find_misses(events, CONFIG)
        self.assertEqual(find_reply_delays(events, misses, CONFIG), [])

    def test_no_misses_no_causes(self):
        self.assertEqual(find_starvation([], [], CONFIG), [])
        self.assertEqual(find_reply_delays([], [], CONFIG), [])


if __name__ == "__main__":
    unittest.main()
