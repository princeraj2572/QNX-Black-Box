import os
import unittest

from blackbox.adapters.tracelogger import AdapterError, convert
from blackbox.events import MsgReceive, MsgReply, MsgSend, Run, ThreadState
from blackbox.parser import parse_text

REAL = os.path.join(os.path.dirname(__file__), "fixtures", "real")

# 1e9 cycles/s so 1 cycle == 1 ns. CPU 1's buffer is printed after CPU 0's
# although its events happen in between, and CPU 0's low word wraps.
SNIPPET = """\
  TRACE_CYCLES_PER_SEC:: 1000000000
 -- KERNEL EVENTS --
t:0xfffffff0 CPU:00 CONTROL         :TIME               msb:0x00000000 lsb(offset):0xfffffff0
t:0xfffffff0 CPU:00 PROCESS         :PROCTHREAD_NAME
                       pid:7
                       tid:2
                      name:controller
t:0xfffffff1 CPU:00 THREAD          :THRUNNING          pid:7 tid:2 priority:20 policy:1
t:0xfffffff1 CPU:00 USREVENT        :EVENT:100          STR:"blackbox RELEASED", d0:0x52206262 d1:0x41454c45 d2:0x00444553 d3:0x00000000
t:0xfffffff2 CPU:00 COMM            :SND_MESSAGE        rcvid:0x0001 pid:9
t:0xfffffff3 CPU:00 THREAD          :THREPLY            pid:7 tid:2 priority:20 policy:1
t:0x00000005 CPU:00 THREAD          :THREADY            pid:7 tid:2 priority:20 policy:1
t:0xfffffff4 CPU:01 CONTROL         :TIME               msb:0x00000000 lsb(offset):0xfffffff4
t:0xfffffff4 CPU:01 THREAD          :THRUNNING          pid:9 tid:1 priority:5 policy:1
t:0xfffffff5 CPU:01 COMM            :REC_MESSAGE        rcvid:0x0001 pid:9
t:0xfffffff6 CPU:01 COMM            :REPLY_MESSAGE      tid:2 pid:7
t:0xfffffff7 CPU:01 USREVENT        :EVENT:100          STR:"blackbox DONE", d0:0x44206262 d1:0x00454e4f
t:0xfffffff8 CPU:01 USREVENT        :EVENT:100          STR:"other text", d0:0x44206262
"""


class SnippetTest(unittest.TestCase):
    def test_maps_threads_messages_and_time(self):
        ev = convert(SNIPPET)
        lines = [e.to_line() for e in ev]
        self.assertEqual(lines, [
            "1 RUN tid=7002 name=controller prio=20",
            "1 THREAD_STATE tid=7002 name=controller prio=20 state=RELEASED",
            "2 MSG_SEND tid=7002 name=controller prio=20 peer=9001",
            "3 THREAD_STATE tid=7002 name=controller prio=20 state=REPLY",
            "4 RUN tid=9001 name=pid9.1 prio=5",
            "5 MSG_RECEIVE tid=9001 name=pid9.1 prio=5 peer=7002",
            "6 MSG_REPLY tid=9001 name=pid9.1 prio=5 peer=7002",
            "7 THREAD_STATE tid=9001 name=pid9.1 prio=5 state=DONE",
            "21 THREAD_STATE tid=7002 name=controller prio=20 state=READY",
        ])

    def test_fast_mode_is_rejected(self):
        with self.assertRaises(AdapterError):
            convert(SNIPPET.replace(" priority:20 policy:1", ""))

    def test_needs_traceprinter_header(self):
        with self.assertRaises(AdapterError):
            convert("hello")


class RealTraceTest(unittest.TestCase):
    """Wide-mode capture from QNX SDP 8.0 on x86_64 QEMU."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REAL, "wide.txt"), encoding="utf-8") as f:
            cls.events = convert(f.read())

    def test_round_trips_through_parser(self):
        text = "\n".join(e.to_line() for e in self.events)
        self.assertEqual(parse_text(text), self.events)

    def test_sorted_and_covers_event_kinds(self):
        ts = [e.ts_ns for e in self.events]
        self.assertEqual(ts, sorted(ts))
        kinds = {type(e) for e in self.events}
        self.assertEqual(kinds, {Run, ThreadState, MsgSend, MsgReceive, MsgReply})

    def test_names_and_priorities(self):
        idle = [e for e in self.events if isinstance(e, Run) and e.name == "idle_cpu_0"]
        self.assertTrue(idle)
        self.assertEqual(idle[0].prio, 0)

    def test_every_send_is_received(self):
        sends = [(e.tid, e.peer) for e in self.events if isinstance(e, MsgSend)]
        recvs = [(e.peer, e.tid) for e in self.events if isinstance(e, MsgReceive)]
        self.assertEqual(sorted(sends), sorted(recvs))

    def test_fast_mode_fixture_is_rejected(self):
        with open(os.path.join(REAL, "test.txt"), encoding="utf-8") as f:
            with self.assertRaises(AdapterError):
                convert(f.read())


if __name__ == "__main__":
    unittest.main()
