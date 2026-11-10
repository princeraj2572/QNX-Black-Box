import os
import unittest

from blackbox.config import ThreadConfig
from blackbox.deadlines import find_jobs, find_misses
from blackbox.parser import parse_file, parse_text

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
CONFIG = {"controller": ThreadConfig("controller", 10, 8, 20)}


class DeadlineTest(unittest.TestCase):
    def test_one_miss_one_hit(self):
        events = parse_file(os.path.join(FIXTURES, "deadline.trace"))
        jobs = find_jobs(events, CONFIG)
        self.assertEqual([j.missed for j in jobs], [False, True])
        self.assertEqual(jobs[0].response_ns, 5_000_000)
        self.assertEqual(jobs[1].deadline_ns, 18_000_000)
        misses = find_misses(events, CONFIG)
        self.assertEqual(len(misses), 1)
        self.assertEqual(misses[0].release_ns, 10_000_000)

    def test_unfinished_job_past_deadline_is_a_miss(self):
        events = parse_text(
            "0 THREAD_STATE tid=4 name=controller prio=20 state=RELEASED\n"
            "20000000 RUN tid=9 name=other prio=1\n"
        )
        (job,) = find_jobs(events, CONFIG)
        self.assertIsNone(job.done_ns)
        self.assertTrue(job.missed)

    def test_unfinished_job_before_deadline_is_not_a_miss(self):
        events = parse_text(
            "0 THREAD_STATE tid=4 name=controller prio=20 state=RELEASED\n"
            "2000000 RUN tid=9 name=other prio=1\n"
        )
        self.assertEqual(find_misses(events, CONFIG), [])

    def test_unconfigured_threads_and_stray_done_ignored(self):
        events = parse_text(
            "0 THREAD_STATE tid=9 name=other prio=1 state=RELEASED\n"
            "1 THREAD_STATE tid=4 name=controller prio=20 state=DONE\n"
        )
        self.assertEqual(find_jobs(events, CONFIG), [])

    def test_release_while_open_closes_previous_as_unfinished(self):
        events = parse_text(
            "0 THREAD_STATE tid=4 name=controller prio=20 state=RELEASED\n"
            "10000000 THREAD_STATE tid=4 name=controller prio=20 state=RELEASED\n"
            "12000000 THREAD_STATE tid=4 name=controller prio=20 state=DONE\n"
        )
        jobs = find_jobs(events, CONFIG)
        self.assertEqual([j.missed for j in jobs], [True, False])

    def test_same_name_in_two_threads_kept_apart(self):
        # e.g. a controller restarted by a chaos run while the old one finishes
        events = parse_text(
            "0 THREAD_STATE tid=4 name=controller prio=20 state=RELEASED\n"
            "1000000 THREAD_STATE tid=5 name=controller prio=20 state=RELEASED\n"
            "3000000 THREAD_STATE tid=4 name=controller prio=20 state=DONE\n"
            "4000000 THREAD_STATE tid=5 name=controller prio=20 state=DONE\n"
        )
        jobs = find_jobs(events, CONFIG)
        self.assertEqual([(j.tid, j.response_ns) for j in jobs], [(4, 3_000_000), (5, 3_000_000)])


if __name__ == "__main__":
    unittest.main()
