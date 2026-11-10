import unittest

from blackbox.causes import find_mutex_waits, find_reply_delays, find_starvation
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

# ctl asks db; db (inherited prio 10) waits on a mutex while med (5) runs
# and lo (2) runs a little. idle (0) never counts.
MUTEX = f"""
0 THREAD_STATE tid=1 name=ctl prio=10 state=RELEASED
{1*MS} MSG_SEND tid=1 name=ctl prio=10 peer=5
{1*MS} MSG_RECEIVE tid=5 name=db prio=10 peer=1
{2*MS} THREAD_STATE tid=5 name=db prio=10 state=MUTEX
{2*MS} RUN tid=7 name=med prio=5
{8*MS} RUN tid=6 name=lo prio=2
{9*MS} RUN tid=9 name=idle prio=0
{10*MS} THREAD_STATE tid=5 name=db prio=10 state=READY
{10*MS} RUN tid=5 name=db prio=10
{11*MS} MSG_REPLY tid=5 name=db prio=10 peer=1
{12*MS} THREAD_STATE tid=1 name=ctl prio=10 state=DONE
"""


class CausesTest(unittest.TestCase):
    def test_starvation(self):
        events = parse_text(STARVED)
        misses = find_misses(events, CONFIG)
        (s,) = find_starvation(events, misses, CONFIG)
        self.assertEqual((s.hog_name, s.hog_prio, s.run_ns), ("logger", 30, 8 * MS))

    def test_brief_hog_is_not_starvation(self):
        events = parse_text(STARVED)
        misses = find_misses(events, CONFIG)
        deadline_ns = CONFIG["ctl"].deadline_ms * MS
        self.assertEqual(find_starvation(events, misses, CONFIG, 8 * MS / deadline_ns + 0.01), [])

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

    def test_mutex_wait_names_who_ran(self):
        events = parse_text(MUTEX)
        misses = find_misses(events, CONFIG)
        delays = find_reply_delays(events, misses, CONFIG)
        (w,) = find_mutex_waits(events, misses, CONFIG, delays)
        self.assertEqual((w.name, w.prio, w.end_ns - w.start_ns), ("db", 10, 8 * MS))
        self.assertEqual(w.ran, (("med", 5, 6 * MS), ("lo", 2, 1 * MS)))

    def test_short_mutex_wait_is_not_reported(self):
        events = parse_text(MUTEX.replace(f"{10*MS} THREAD_STATE tid=5", f"{3*MS} THREAD_STATE tid=5"))
        misses = find_misses(events, CONFIG)
        delays = find_reply_delays(events, misses, CONFIG)
        self.assertEqual(find_mutex_waits(events, misses, CONFIG, delays), [])

    def test_no_misses_no_causes(self):
        self.assertEqual(find_starvation([], [], CONFIG), [])
        self.assertEqual(find_reply_delays([], [], CONFIG), [])


if __name__ == "__main__":
    unittest.main()
