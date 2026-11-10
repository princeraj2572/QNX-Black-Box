"""Map `traceprinter` text from a QNX 8.0 wide-mode trace to the internal format.

Record with `tracelogger -w`: fast-mode events carry no thread priority.
Job markers come from user string events the traced program logs itself,
e.g. `trace_logf(100, "blackbox RELEASED")`; they apply to the running thread.

    python -m blackbox.adapters.tracelogger trace.txt > internal.txt
"""

import re
import sys
from typing import List

from ..events import Event, MsgReceive, MsgReply, MsgSend, Run, ThreadState

HEAD = re.compile(r"t:0x([0-9a-f]+) CPU:(\d+) (\w+)\s*:(\S+)\s*(.*)")
FIELD = re.compile(r"(\w+):(\S+)")
STR = re.compile(r'STR:"([^"]*)"')
MARK = re.compile(r"blackbox (RELEASED|DONE)")
CPS = re.compile(r"TRACE_CYCLES_PER_SEC::\s*(\d+)")


class AdapterError(ValueError):
    pass


def _records(lines):
    """Yield [cycles, cpu, class, event, fields] in file order."""
    msb, last, cur = {}, {}, None
    for line in lines:
        m = HEAD.match(line)
        if m:
            if cur:
                yield cur
            lsb, cpu, f = int(m[1], 16), int(m[2]), dict(FIELD.findall(m[5]))
            s = STR.search(m[5])
            if s:
                f["STR"] = s[1]
            if m[4] == "TIME" and re.fullmatch(r"0x[0-9a-f]+", f.get("msb", "")):
                msb[cpu] = int(f["msb"], 16)
            elif cpu in last and lsb < last[cpu]:
                msb[cpu] = msb.get(cpu, 0) + 1  # low 32 bits wrapped inside a buffer
            last[cpu] = lsb
            cur = [(msb.get(cpu, 0) << 32) | lsb, cpu, m[3], m[4], f]
        elif cur and line[:1].isspace() and ":" in line:
            key, _, value = line.strip().partition(":")
            cur[4].setdefault(key, value.strip())  # a lost header line must not override fields
    if cur:
        yield cur


def convert(text: str) -> List[Event]:
    m = CPS.search(text)
    if not m:
        raise AdapterError("no TRACE_CYCLES_PER_SEC header: not traceprinter output?")
    cps = int(m[1])
    # Output is grouped per CPU buffer, so sort; the sort is stable within a CPU.
    recs = sorted(_records(text.splitlines()), key=lambda r: r[0])
    if not recs:
        return []

    pname, tname = {}, {}
    for _, _, _, ev, f in recs:
        if ev == "PROCCREATE_NAME":
            pname[f.get("pid")] = f.get("name", "")
        elif ev == "PROCTHREAD_NAME":
            tname[(f.get("pid"), f.get("tid"))] = f.get("name", "")

    def ident(pid, tid):
        proc = (pname.get(pid) or f"pid{pid}").rsplit("/", 1)[-1]
        name = tname.get((pid, tid)) or f"{proc}.{tid}"
        if int(tid) >= 1000:
            raise AdapterError(f"tid {tid} in pid {pid} does not fit the pid*1000+tid scheme")
        return int(pid) * 1000 + int(tid), re.sub(r"[\s=]", "_", name)

    start, running, pending, out, bad = recs[0][0], {}, {}, [], 0
    for rec in recs:
        try:
            _apply(rec, (rec[0] - start) * 10**9 // cps, ident, running, pending, out)
        except AdapterError:
            raise
        except (ValueError, KeyError):
            bad += 1  # garbled record, e.g. a truncated last line
    if bad > max(10, len(recs) // 100):
        raise AdapterError(f"{bad} of {len(recs)} records are unreadable: is the file corrupt?")
    out.sort(key=lambda e: e.ts_ns)
    return out


def _apply(rec, ns, ident, running, pending, out):
    """Turn one record into internal events, appended to `out`."""
    _, cpu, cls, ev, f = rec
    if cls == "THREAD" and "pid" in f and "tid" in f:
        if "priority" not in f:
            if ev == "THRUNNING":
                raise AdapterError("no thread priorities: record with tracelogger -w")
            return  # THCREATE/THDESTROY carry no priority
        tid, name = ident(f["pid"], f["tid"])
        prio = int(f["priority"])
        if ev == "THRUNNING":
            running[cpu] = (tid, name, prio)
            out.append(Run(ns, tid, name, prio, cpu=cpu))
        else:
            out.append(ThreadState(ns, tid, name, prio, state=ev[2:]))
    elif cls == "COMM" and cpu in running:
        me = running[cpu]
        if ev == "SND_MESSAGE":
            # The receiver is only known once it picks the message up.
            pending[f.get("rcvid")] = (ns, me)
        elif ev == "REC_MESSAGE" and me[0] // 1000 == int(f.get("pid", -1)):
            sent = pending.pop(f.get("rcvid"), None)
            if sent:
                out.append(MsgSend(sent[0], *sent[1], peer=me[0]))
                out.append(MsgReceive(ns, *me, peer=sent[1][0]))
        elif ev == "REPLY_MESSAGE" and "pid" in f and "tid" in f:
            out.append(MsgReply(ns, *me, peer=ident(f["pid"], f["tid"])[0]))
    elif cls == "USREVENT" and cpu in running:
        mark = MARK.fullmatch(f.get("STR", ""))
        if mark:
            out.append(ThreadState(ns, *running[cpu], state=mark[1]))


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m blackbox.adapters.tracelogger TRACEPRINTER_TXT", file=sys.stderr)
        return 2
    with open(args[0], encoding="utf-8", errors="replace") as f:
        text = f.read()
    try:
        events = convert(text)
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write("# ts_ns EVENT key=value ...\n")
    sys.stdout.writelines(e.to_line() + "\n" for e in events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
