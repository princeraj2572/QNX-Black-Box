# Target demo services

Built and run on QNX SDP 8.0 (x86_64 QEMU). A 5 s run misses the 20 ms
deadline 10 times (replies up to ~80 ms); with `--fixed` (priority
inheritance on the mutex) it misses none. The captures are
`tests/fixtures/real/inversion_demo.trace` and `inversion_demo_fixed.trace`.

`inversion_demo.c` runs four threads in one process: a controller (prio 20),
a server (prio 5), a low-priority mutex holder (prio 5) and a medium-priority
busy thread (prio 10). The controller has a 20 ms reply deadline.

## Build

Source the SDP environment script first (`source <sdp>/qnxsdp-env.sh` in a
bash shell; on Windows use Git Bash), then for x86_64 QEMU:

    qcc -Vgcc_ntox86_64 -Wall -o inversion_demo inversion_demo.c

This builds cleanly with SDP 8.0. TODO(human): the Raspberry Pi 5 variant
(aarch64) is untested.

## Run

Copy `inversion_demo` to the target and run it as root (setting SCHED_FIFO
priorities needs privilege):

    ./inversion_demo 10            # priority inversion: misses
    ./inversion_demo 10 --fixed    # PTHREAD_PRIO_INHERIT: no misses

It prints a line whenever the controller's reply takes longer than 20 ms.
Record a trace while it runs:

    python3 -m blackbox record --target root@<ip> --seconds 10

## What a real run shows

- Misses start after a quiet 2 s, once `low` starts waking `med` while it
  holds the mutex.
- Thread names (`controller`, `server`, `low`, `med`) appear in the trace.
- Analyze it with `tests/fixtures/real/inversion_demo.json` (controller
  `period_ms` 50, `deadline_ms` 20, `priority` 20). Each miss is blamed on a
  slow reply from `server`.
