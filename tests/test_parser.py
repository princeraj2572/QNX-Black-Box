import os
import unittest

from blackbox.events import MsgSend, Run, ThreadState
from blackbox.parser import ParseError, parse_file, parse_text

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class ParserTest(unittest.TestCase):
    def test_parse_fixture(self):
        events = parse_file(os.path.join(FIXTURES, "basic.trace"))
        self.assertEqual(len(events), 5)
        self.assertEqual(events[0], Run(1000, 4, "controller", 20))
        self.assertEqual(events[1], MsgSend(1500, 4, "controller", 20, peer=7))
        self.assertEqual(events[4], ThreadState(2500, 4, "controller", 20, state="READY"))

    def test_roundtrip(self):
        events = parse_file(os.path.join(FIXTURES, "basic.trace"))
        text = "\n".join(e.to_line() for e in events)
        self.assertEqual(parse_text(text), events)

    def test_blank_and_comment_only(self):
        self.assertEqual(parse_text("\n# hi\n   \n"), [])

    def assertErrorAt(self, text, lineno):
        with self.assertRaises(ParseError) as ctx:
            parse_text(text)
        self.assertEqual(ctx.exception.lineno, lineno)
        self.assertIn(f"line {lineno}:", str(ctx.exception))

    def test_errors_carry_line_numbers(self):
        good = "1 RUN tid=1 name=a prio=1\n"
        self.assertErrorAt(good + "\n2 BOGUS tid=1 name=a prio=1", 3)
        self.assertErrorAt(good + "x RUN tid=1 name=a prio=1", 2)
        self.assertErrorAt(good + "3 RUN tid=1 name=a", 2)
        self.assertErrorAt(good + "3 RUN tid=1 name=a prio=1 peer=2", 2)
        self.assertErrorAt(good + "3 MSG_SEND tid=1 name=a prio=1", 2)
        self.assertErrorAt(good + "3 RUN tid=one name=a prio=1", 2)
        self.assertErrorAt(good + "3 RUN tid=1 tid=2 name=a prio=1", 2)
        self.assertErrorAt(good + "3 RUN junk", 2)
        self.assertErrorAt(good + "3", 2)


if __name__ == "__main__":
    unittest.main()
