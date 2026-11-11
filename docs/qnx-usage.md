# Where this project uses QNX

A guide for reviewers: each QNX feature the project relies on, and where to
find it in the code. Anything not yet verified on a real QNX 8.0 system is
marked `TODO(human)`.

Status: the tracelogger adapter and the priority inversion demo are verified
on SDP 8.0 with an x86_64 QEMU target (captures in `tests/fixtures/real/`).
The `record` command, the `kill_process` chaos fault and `recovery` are
verified there too. The other chaos faults and the HAM demo have not run on a
target yet.

## Feature map

| QNX feature | File | Symbols | What it does here |
|---|---|---|---|
| Instrumented kernel and tracelogger | `blackbox/record.py` | `record` | Starts tracelogger on the target, waits, stops it with slay, and copies the trace file back over scp. |
| Instrumented kernel and tracelogger | `docs/trace-format.md` | | Internal format the analyzer reads. |
| Instrumented kernel and tracelogger | `blackbox/adapters/tracelogger.py` | `convert` | Maps `traceprinter` text from a wide-mode (tracelogger -w) trace to the internal format. |
| Message passing (send, receive, reply) | `blackbox/events.py` | `MsgSend`, `MsgReceive`, `MsgReply` | Event types for the three sides of a QNX message exchange. |
| Message passing (send, receive, reply) | `blackbox/blocking.py` | `build_blocks`, `chain_at` | A sender is blocked on its peer from send until the peer's reply. |
| Message passing (send, receive, reply) | `blackbox/inversion.py` | `find_inversions` | Finds a high-priority sender blocked on a lower-priority server while a medium-priority thread runs. |
| Message passing (send, receive, reply) | `blackbox/causes.py` | `find_reply_delays` | Reports a slow reply to a message from a missed job's thread. |
| Thread priorities and scheduling | `blackbox/causes.py` | `find_starvation` | Finds higher-priority threads that ran while a missed job was in flight. |
| slay, on and sleep utilities | `blackbox/chaos/scenarios.py` | `FAULTS`, `parse_scenario` | Renders fault scenarios into target shell commands (kill, CPU hog, pause a process). |
| POSIX shared memory under /dev/shmem | `blackbox/chaos/scenarios.py` | `FAULTS` | The memory pressure fault fills a file in /dev/shmem. |
| High Availability Manager (ham) | `target/ham_demo.c` | | Has ham start a periodic worker and restart it on death (`ham_attach`, `CONDDEATH`, `ham_action_restart`). |
| High Availability Manager (ham) | `target/ham_kill.json` | | Chaos scenario that kills the worker with slay. |
| High Availability Manager (ham) | `blackbox/recovery.py` | `find_restarts` | Measures the gap between the killed thread's last event and its restarted copy's first event. |
| SSH access to the target | `blackbox/runner.py` | `SSHRunner`, `MockRunner` | Runs commands and fetches files; the mock runner is used by all tests. |

## Not used yet

- pidin: no code calls it yet. Planned use is listing threads and priorities
  on the target to generate the thread config. TODO(human): decide whether to
  add this.
- slog2: no code reads it yet. Planned use is correlating log messages with a
  missed deadline. TODO(human): decide whether to add this.

## High Availability Manager

Available in SDP 8.0: the 8.0 docs include the `ham` and `hamctrl` utilities
and the HAM API (`<ha/ham.h>`, `libham`). See the Utilities Reference entry for
ham and the High Availability Framework Developer's Guide at qnx.com.

- TODO(human): build and run `target/ham_demo.c`, kill the worker with
  `target/ham_kill.json`, and record the measured recovery time here.
- Checked on 2026-11-12: the local SDP 8.0 install has the HAM documentation
  but no `ham` binary, no `ha/ham.h` and no `libham`, and the QEMU image has
  no `ham` either. TODO(human): install the HAM package from the QNX
  Software Center (it may need a separate license), then run the demo.

## Measured recovery after a kill

Checked on SDP 8.0, x86_64 QEMU, 2026-11-12. A shell loop restarted
`inversion_demo` whenever it exited, and `blackbox chaos run` killed it with
`slay -s KILL inversion_demo` while recording. `blackbox recovery --name
controller --name server --name low --name med` found all four threads back
in a new process 94 to 99 ms after their last event in the old one
(`tests/fixtures/real/kill_demo.trace`). This measures a shell-loop restart,
not HAM.

## To verify on a real target

- TODO(human): the instrumented kernel image and boot steps needed for
  tracing on QEMU and on Raspberry Pi 5 (PLAN.md F18).
- `slay -s KILL` works as `kill_process` assumes (checked on QEMU, above).
  TODO(human): on -p, the shell variable SECONDS and /dev/shmem, used by the
  other faults.
- Priority inheritance in message passing (checked on SDP 8.0, x86_64 QEMU,
  with `target/inversion_demo.c`): the server runs at the sender's priority
  (20) from the moment it receives. The demo still misses its deadline because
  the server then waits on a mutex without inheritance held by `low` (5) while
  `med` (10) runs; with `--fixed` (PTHREAD_PRIO_INHERIT) the misses go from
  10 to 0. The analyzer reports a slow reply from the server, then the
  server's mutex wait and the lower-priority threads that ran during it (`med`
  and `low`), flagged as a likely priority inversion. It cannot name the
  holder: uncontended mutex locks never enter the kernel, so the trace has no
  owner.
