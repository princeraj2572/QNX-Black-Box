# Devpost submission checklist

QNX Global Hackathon 2026. Deadline: 15 December 2026, 2:00 PM Eastern
(per the public listing; confirm on qnx.devpost.com).

| Item | Status | Where |
|---|---|---|
| Public repo | TODO(human): make the GitHub repo public | https://github.com/princeraj2572/QNX-Black-Box |
| Open-source license, detectable | Done: MIT, in `LICENSE` at the root | `LICENSE` |
| Build and run instructions naming QNX version, target and toolchain | Done | README "Install", "Usage", "QNX version, target and toolchain"; `target/README.md` |
| Written description | Draft below; paste into Devpost | this file |
| Public YouTube demo under 3 minutes | TODO(human): record and upload (PLAN.md F22) | |
| Category: Developer Tooling and Host Tools | TODO(human): select on Devpost | |
| Codelab URL (tutorial prize) | Done; submit the GitHub URL of `docs/codelab.md` once public. TODO(human): replace its `[REAL OUTPUT ...]` placeholders (F22) | `docs/codelab.md` |
| How the project uses QNX | Done | `docs/qnx-usage.md` |
| AI-tool disclosure in the Official Rules | TODO(human): the rules page on qnx.devpost.com needs a login; read it and disclose if required | |
| Build instructions tested on a clean machine | TODO(human): suggested by the listing | |

## Submission draft

Paste each part into the matching Devpost field. Lines in `[brackets]` are
for you to fill in or confirm.

### Project name

QNX Black Box

### Elevator pitch (200 characters max)

A flight recorder for QNX 8.0: record a system trace, break the system on
purpose, and get a plain-English answer to "why did this real-time deadline
miss?"

### About the project

#### Inspiration

When a real-time thread misses its deadline, the evidence is in a kernel
trace with thousands of events, and finding the cause means reading it by
hand: who preempted whom, who was blocked on which server, and for how long.
We wanted a tool that reads the trace for you and names the cause, the way a
flight recorder is read after an incident. [Add your own reason here if you
have one.]

#### What it does

- **Records** a trace on a QNX 8.0 target over SSH (`tracelogger -w` with the
  instrumented kernel) and decodes it on the host with the SDP's
  `traceprinter`.
- **Finds every missed deadline** from a small config listing each thread's
  period, deadline and priority.
- **Explains each miss in plain English**, with timestamps and thread names:
  priority inversion, CPU starvation by a higher-priority thread, or a slow
  reply to a QNX message. It follows send/receive/reply chains, so a miss in a
  client is traced back to the server that held it up.
- **Injects faults** while recording: kill a process, CPU hog, pause a
  process, memory pressure in `/dev/shmem`.
- **Measures recovery**: how long a killed service was gone before something
  (such as the High Availability Manager) restarted it.
- **Writes a report**: JSON, plus a self-contained HTML page with a close-up
  of each miss, step-by-step events, per-thread jobs and CPU time. `serve`
  shows it live in the browser.

#### How we built it

The host tool is Python 3 using only the standard library, so there is
nothing to install. An adapter maps `traceprinter` output to a small internal
text format (`docs/trace-format.md`). Detectors for deadlines, blocking
chains, inversion, starvation and slow replies run over that format, and an
explainer turns their findings into sentences. Target programs mark job
boundaries with `trace_logf()` user events. The demo services in `target/`
are C, built with `qcc` from SDP 8.0 and run on an x86_64 QEMU target. The
tool has 126 unit tests, including tests on real captures from QEMU.

#### Challenges we ran into

- **QNX's own fixes kept removing the bug we were trying to demo.** Message
  passing already applies priority inheritance: the server runs at the
  sender's priority from the moment it receives. To get a real inversion, the
  demo has the server wait on a mutex that has no priority inheritance.
- **A multi-core target hid the inversion.** On SMP the medium-priority thread
  simply ran on another core, so the demo pins its threads to one CPU.
- **Some facts never reach the trace.** An uncontended mutex lock never
  enters the kernel, so the trace cannot say who holds the mutex. The report
  says so plainly rather than guessing.
- **Fast-mode traces carry no priorities**, so recording uses wide mode
  (`tracelogger -w`).

#### Accomplishments that we're proud of

On a real QNX 8.0 target, the inversion demo misses its 20 ms deadline 10
times in 5 seconds. QNX Black Box blames each miss on the server's mutex
wait while the medium-priority thread ran. Switch the mutex to
`PTHREAD_PRIO_INHERIT` and the misses drop to zero, and the tool confirms it.

#### What we learned

[Your words. Suggestions: how QNX message passing and priority inheritance
interact; what the instrumented kernel records and what it cannot see.]

#### What's next

- Run the High Availability Manager demo and publish measured recovery times
  (the code is in `target/ham_demo.c`; HAM was not in our SDP install).
- Raspberry Pi 5 support.
- Generate the thread config from `pidin`, and correlate misses with `slog2`
  logs.

### Built with

python, c, qnx, qnx-sdp-8.0, qcc, tracelogger, qemu, html, javascript

### Try it out links

- Code: https://github.com/princeraj2572/QNX-Black-Box
- Codelab: https://github.com/princeraj2572/QNX-Black-Box/blob/master/docs/codelab.md
- How it uses QNX: https://github.com/princeraj2572/QNX-Black-Box/blob/master/docs/qnx-usage.md

### Video demo link

[YouTube URL, under 3 minutes]

### Category

Developer Tooling & Host Tools

### Testing instructions for judges

No QNX target is needed to try the analyzer:

    git clone https://github.com/princeraj2572/QNX-Black-Box.git
    cd QNX-Black-Box
    python3 -m unittest discover -s tests
    python3 -m blackbox analyze tests/fixtures/real/inversion_demo.trace \
        --config tests/fixtures/real/inversion_demo.json

The second command explains the deadline misses in a real trace captured on
QNX 8.0 (QEMU). For a live target, see "Record" in the README and
`target/README.md`.
