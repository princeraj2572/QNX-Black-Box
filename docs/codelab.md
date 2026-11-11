# Debug a missed deadline on QNX in 30 minutes

A real-time thread on QNX 8.0 keeps missing its 20 ms deadline, and nothing
in its own code is slow. In this codelab you build the program, record a
kernel trace of it, and let QNX Black Box explain the miss: a priority
inversion hidden behind a message pass. Then you fix it with one line and
prove the fix with a second trace.

You will learn:

- how to record a trace with the instrumented kernel and `tracelogger`
- how QNX message passing gives a server its client's priority, and where
  that protection stops
- how to turn a trace into a plain-English answer to "why was this late?"

All output below is real: it comes from QNX SDP 8.0 on an x86_64 QEMU target,
and the two traces are in `tests/fixtures/real/`, so you can follow steps 4 to
7 on any computer, even without a QNX target.

## 0. What you need (5 minutes)

- QNX SDP 8.0 (free with QNX Everywhere) and a QNX 8.0 target reachable over
  SSH as root. A QEMU image built with the SDP works; this codelab used one.
- Python 3.8 or newer. QNX Black Box uses only the standard library.
- This repository:

      git clone https://github.com/princeraj2572/QNX-Black-Box.git
      cd QNX-Black-Box
      python3 -m unittest discover -s tests

If the target is QEMU with SSH forwarded to port 2222, give it a short name
in `~/.ssh/config` so the tool can reach it:

    Host qnxvm
        HostName localhost
        Port 2222
        User root

## 1. Meet the program (3 minutes)

`target/inversion_demo.c` runs four threads in one process, all on one CPU:

| Thread | Priority | What it does |
|---|---|---|
| `controller` | 20 | Every 50 ms, sends a message to `server` and needs the reply within 20 ms |
| `server` | 5 | Receives the message, takes a shared mutex, replies |
| `low` | 5 | Holds the same mutex for 10 ms, then releases it for 10 ms |
| `med` | 10 | After 2 s, `low` sometimes wakes it while holding the mutex; it then busy-loops for 60 ms |

The controller marks each job with two trace events, so the tool knows where
a job starts and ends:

    trace_logf(TRACE_CODE, "blackbox RELEASED");
    ... MsgSend() to the server ...
    trace_logf(TRACE_CODE, "blackbox DONE");

## 2. Build and run it on the target (5 minutes)

In a shell with the SDP environment (`source qnxsdp-env.sh`):

    qcc -Vgcc_ntox86_64 -Wall -o inversion_demo target/inversion_demo.c
    scp inversion_demo qnxvm:/tmp/

On the target, as root (SCHED_FIFO priorities need it), run it for 10 seconds:

    /tmp/inversion_demo 10

It prints a line each time the controller's reply takes longer than 20 ms.

## 3. Record a trace while it runs (3 minutes)

While the demo runs, record from your computer:

    python3 -m blackbox record --target qnxvm --seconds 10 --out trace.kev --decode

This starts `tracelogger -w` on the target (wide mode: fast mode has no
thread priorities), waits, stops it with `slay`, copies the raw trace back,
and decodes it with the SDP's `traceprinter` into `trace.txt`.

## 4. Tell the tool what "on time" means (2 minutes)

The only thing the trace cannot tell the tool is the deadline. The quickest
way is to give it on the command line, `--deadline controller=20`: the tool
finds the controller's 50 ms period and priority 20 in the trace by itself.
For a fixed setup, put everything in a config file instead, one entry per
periodic thread. For this demo it is `tests/fixtures/real/inversion_demo.json`:

    {
      "threads": [
        {"name": "controller", "period_ms": 50, "deadline_ms": 20, "priority": 20}
      ]
    }

## 5. Ask why (5 minutes)

    python3 -m blackbox analyze trace.txt --config tests/fixtures/real/inversion_demo.json --json report.json

No target? Use the trace recorded for this codelab:

    python3 -m blackbox analyze tests/fixtures/real/inversion_demo.trace \
        --config tests/fixtures/real/inversion_demo.json --json report.json

Output (first two of ten misses shown):

    Found 10 deadline misses.

    Summary:
      - controller: 10 misses, worst 41.036 ms late, average 18.430 ms late.
      - Cause in 10 of 10: slow reply from server.
      - Cause in 10 of 10: server blocked on a mutex while med preempted low.
      - Cause in 1 of 10: CPU starvation by pf_purge.
      - Likely fix, if the lower-priority thread holds the mutex: set PTHREAD_PRIO_INHERIT on it with pthread_mutexattr_setprotocol().

    Details:

    controller missed its 20.0 ms deadline: the job released at 3551.468 ms finished at 3576.070 ms, a response time of 24.601 ms, 4.601 ms late.
      - Slow reply: controller sent a message to server at 3551.498 ms and waited 24.490 ms for the reply.
      - Mutex wait: server (priority 20) blocked 24.291 ms on a mutex from 3551.607 ms. In that time med (priority 10) ran 14.195 ms, low (priority 5) ran 10.086 ms. Priority inversion if low holds the mutex.

    controller missed its 20.0 ms deadline: the job released at 3801.272 ms finished at 3857.677 ms, a response time of 56.405 ms, 36.405 ms late.
      - Slow reply: controller sent a message to server at 3801.311 ms and waited 56.194 ms for the reply.
      - Mutex wait: server (priority 20) blocked 55.975 ms on a mutex from 3801.444 ms. In that time med (priority 10) ran 45.883 ms, low (priority 5) ran 10.082 ms. Priority inversion if low holds the mutex.

The exit code is `1` because deadlines were missed, so you can use it in a
script or CI job.

## 6. Read the answer (3 minutes)

Follow one miss from the top:

1. **Slow reply.** The controller itself did almost nothing. It sent a message
   and spent the whole job blocked waiting for `server` to reply.
2. **The server had the right priority.** Notice `server (priority 20)`. The
   server was created at priority 5, but QNX message passing gave it the
   controller's priority when it received the message. That is QNX
   protecting you, and it works.
3. **The protection stops at the mutex.** The server then blocked on a mutex.
   That mutex has no priority inheritance, so `low` (priority 5), which holds
   it, kept its own low priority. `med` (priority 10) outranks `low`, so `med`
   ran and `low` could not finish and release the mutex. A priority 10 thread
   delayed a priority 20 one: a priority inversion.

The tool says "if low holds the mutex" because the trace cannot prove it:
locking a free mutex never enters the kernel, so no event records the
owner. It reports what the trace shows and stops there.

The one miss that also lists `pf_purge` is real noise from the system: a
priority 21 system thread ran for 1.4 ms during that job. It was not the
main cause.

## 7. Look at the timeline (2 minutes)

    python3 -m blackbox report-html report.json report.html

Open `report.html`. Each miss has a close-up: which thread ran when, the
message send, receive and reply, and the steps that led to the miss. To get
a live page that rebuilds on refresh instead, run
`python3 -m blackbox serve trace.txt --config tests/fixtures/real/inversion_demo.json`.

## 8. Fix it and prove it (5 minutes)

The fix is the one the summary names: give the mutex priority inheritance.

    pthread_mutexattr_setprotocol(&attr, PTHREAD_PRIO_INHERIT);

The demo has this behind a flag. Run it again on the target:

    /tmp/inversion_demo 10 --fixed

Record and analyze as in steps 3 and 5. Without a target, use the second
recorded trace:

    python3 -m blackbox analyze tests/fixtures/real/inversion_demo_fixed.trace \
        --config tests/fixtures/real/inversion_demo.json

    No deadline misses found.

The exit code is `0`. Now `low` runs at the waiting server's priority while
it holds the mutex, `med` cannot preempt it, and the chain from controller to
server to `low` keeps priority 20 the whole way.

## Going further: break it on purpose

`blackbox chaos run` injects faults on the target while recording (kill a
process, a CPU hog, pause a process, fill memory). Preview what a scenario
would run, without touching the target:

    python3 -m blackbox chaos run tests/fixtures/scenario_chaos.json --dry-run

    # scenario demo: 2 command(s), nothing executed
    slay -s KILL sensor
    (slay -s STOP controller; sleep 2; slay -s CONT controller) &

Drop `--dry-run` and add `--target qnxvm --decode` to run it for real, then
analyze the trace as in step 5.

## What you learned

- QNX message passing passes the client's priority to the server, but a mutex
  needs `PTHREAD_PRIO_INHERIT` to pass it on further.
- `tracelogger -w` plus a few `trace_logf()` job markers are enough to find
  every missed deadline in a trace.
- QNX Black Box turns that trace into a cause you can act on, and a second
  trace proves the fix.
