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
| Instrumented kernel and tracelogger | `docs/trace-format.md` | | Internal format the analyzer reads. |
| Instrumented kernel and tracelogger | `blackbox/adapters/tracelogger.py` | `convert` | Maps `traceprinter` text from a wide-mode (tracelogger -w) trace to the internal format. |
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

- TODO(human): the instrumented kernel image and boot steps needed for
  tracing on QEMU and on Raspberry Pi 5 (PLAN.md F18).
- TODO(human): slay -s, on -p and the shell variable SECONDS behave as the
  chaos commands assume.
- Priority inheritance in message passing (checked on SDP 8.0, x86_64 QEMU,
  with `target/inversion_demo.c`): the server runs at the sender's priority
  (20) from the moment it receives. The demo still misses its deadline because
  the server then waits on a mutex without inheritance held by `low` (5) while
  `med` (10) runs; with `--fixed` (PTHREAD_PRIO_INHERIT) the misses go from
  10 to 0. The analyzer reports this as a slow reply from the server;
  it does not yet name the mutex holder, because uncontended mutex locks never
  enter the kernel and so leave no owner in the trace. TODO(human): decide
  whether to model mutex waits.
