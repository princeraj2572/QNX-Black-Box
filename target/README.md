# Target demo services

DRAFT: this code has never been compiled or run. Everything below is for a
person with a QNX SDP 8.0 install to verify (PLAN.md F21).

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

    ./inversion_demo 10

It prints a line whenever the controller's reply takes longer than 20 ms.
Record a trace while it runs:

    python3 -m blackbox record --target root@<ip> --seconds 10

## Things to check

- Does a miss appear after the 2 s delay when `med` starts? If not, see the
  TODO(human) notes at the top of the source.
- Does the controller's thread name show up in the trace?
- Thread config for the analyzer: controller `period_ms` 50, `deadline_ms` 20,
  `priority` 20.
