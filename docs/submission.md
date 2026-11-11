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

## Written description (draft)

**QNX Black Box** is a host tool that explains, in plain English, why a
real-time deadline was missed on QNX 8.0.

You record a system trace with the instrumented kernel and `tracelogger`, give
the tool a small config listing each thread's period, deadline and priority,
and it finds every job that missed its deadline and names the cause:
priority inversion, CPU starvation by a higher-priority thread, or a slow
reply to a QNX message. It follows send/receive/reply chains across threads,
so a miss in a client is traced back to the server that held it up.

It also injects faults on the target while recording (kill a process, CPU hog,
pause a process, memory pressure), measures how long a service was down
before the High Availability Manager restarted it, and renders a
self-contained HTML report with a close-up of each miss.

Verified on QNX SDP 8.0 with an x86_64 QEMU target: a demo with a deliberate
priority inversion misses its 20 ms deadline 10 times in 5 s, and the tool
blames each miss on the server's mutex wait while a medium-priority thread
ran. With `PTHREAD_PRIO_INHERIT` the misses go to zero.

Built with: Python 3 standard library only on the host; C and `qcc` for the
target demos.
