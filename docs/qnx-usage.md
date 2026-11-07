# Where this project uses QNX

A guide for reviewers: each QNX feature the project relies on, and where to
find it in the code. Anything not yet verified on a real QNX 8.0 system is
marked `TODO(human)`.

Honest status: no code here has run on a QNX target yet. The host-side tool
works on the internal trace format (`docs/trace-format.md`) and is tested with
fixtures and a mock runner.

## Feature map

| QNX feature | File | Symbols | What it does here |
|---|---|---|---|
| Instrumented kernel and tracelogger | `blackbox/record.py` | `record` | Starts tracelogger on the target, waits, stops it with slay, and copies the trace file back over scp. |
| Instrumented kernel and tracelogger | `docs/trace-format.md` | | Internal format that real trace events must be mapped onto (adapter is PLAN.md F20). |
| Message passing (send, receive, reply) | `blackbox/events.py` | `MsgSend`, `MsgReceive`, `MsgReply` | Event types for the three sides of a QNX message exchange. |
| Message passing (send, receive, reply) | `blackbox/blocking.py` | `build_blocks`, `chain_at` | A sender is blocked on its peer from send until the peer's reply. |
| Message passing (send, receive, reply) | `blackbox/inversion.py` | `find_inversions` | Finds a high-priority sender blocked on a lower-priority server while a medium-priority thread runs. |
| Message passing (send, receive, reply) | `blackbox/causes.py` | `find_reply_delays` | Reports a slow reply to a message from a missed job's thread. |
| Thread priorities and scheduling | `blackbox/causes.py` | `find_starvation` | Finds higher-priority threads that ran while a missed job was in flight. |
| slay, on and sleep utilities | `blackbox/chaos/scenarios.py` | `FAULTS`, `parse_scenario` | Renders fault scenarios into target shell commands (kill, CPU hog, pause a process). |
| POSIX shared memory under /dev/shmem | `blackbox/chaos/scenarios.py` | `FAULTS` | The memory pressure fault fills a file in /dev/shmem. |
| SSH access to the target | `blackbox/runner.py` | `SSHRunner`, `MockRunner` | Runs commands and fetches files; the mock runner is used by all tests. |

## Not used yet

- pidin: no code calls it yet. Planned use is listing threads and priorities
  on the target to generate the thread config. TODO(human): decide whether to
  add this.
- slog2: no code reads it yet. Planned use is correlating log messages with a
  missed deadline. TODO(human): decide whether to add this.

## To verify on a real target

- TODO(human): tracelogger flags used by `record` (output file option,
  running in the background) and that slay stops it cleanly.
- TODO(human): the instrumented kernel image and boot steps needed for
  tracing on QEMU and on Raspberry Pi 5 (PLAN.md F18).
- TODO(human): slay -s, on -p and the shell variable SECONDS behave as the
  chaos commands assume.
- TODO(human): how priority inheritance changes message-passing priorities
  in real traces, since the detectors compare the priorities recorded in each
  event (PLAN.md F21).
- TODO(human): how real tracelogger events yield the RELEASED and DONE job
  markers.
