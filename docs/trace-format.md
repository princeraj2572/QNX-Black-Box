# Internal trace format

This is the project's own text format, not a QNX file format. The analyzer only
reads this format. Real `tracelogger` output is mapped onto it by an adapter
(see PLAN.md F20).

## From a real QNX trace

`blackbox/adapters/tracelogger.py` converts `traceprinter` text from a
wide-mode capture (`tracelogger -w`; fast mode has no priorities):

    python -m blackbox.adapters.tracelogger trace.txt > internal.txt

`analyze` and `serve` also accept `traceprinter` text directly and convert it.

- `ts_ns`: from the 64-bit cycle count (`CONTROL TIME` msb plus `t:` lsb)
  and `TRACE_CYCLES_PER_SEC`, relative to the first event.
- `tid`: `pid * 1000 + tid`, since QNX thread ids are per process.
- `name`: `PROCTHREAD_NAME`, else `<process>.<tid>`.
- `THRUNNING` becomes `RUN`; every other `TH<STATE>` becomes
  `THREAD_STATE state=<STATE>`.
- `SND_MESSAGE`/`REC_MESSAGE` pairs (matched by `rcvid`) become `MSG_SEND` and
  `MSG_RECEIVE`; `REPLY_MESSAGE` becomes `MSG_REPLY`. The acting thread is the
  one running on that CPU.

## Lines

One event per line:

    <ts_ns> <EVENT> key=value key=value ...

- `ts_ns`: non-negative integer, nanoseconds since the start of the trace.
- `EVENT`: one of the names below.
- Fields are separated by single spaces. Values contain no whitespace.
- Blank lines and lines starting with `#` are ignored by the parser.

## Common fields

| Key    | Type   | Meaning                                  |
|--------|--------|------------------------------------------|
| `tid`  | int    | Thread id of the thread the event is about |
| `name` | string | Thread name (no whitespace, no `=`)      |
| `prio` | int    | Thread priority at the time of the event |

## Events

| Event          | Extra fields | Meaning                                   |
|----------------|--------------|-------------------------------------------|
| `RUN`          | `cpu` (optional, default 0) | Thread starts running on CPU `cpu`; it runs until the next `RUN` on that CPU |
| `THREAD_STATE` | `state`      | Thread enters `state` (token, e.g. `READY`, `BLOCKED`) |
| `MSG_SEND`     | `peer`       | Thread sends a message to thread `peer`   |
| `MSG_RECEIVE`  | `peer`       | Thread receives a message from thread `peer` |
| `MSG_REPLY`    | `peer`       | Thread replies to thread `peer`           |

`peer` is a thread id (`tid`), not a name.

## Job markers

The analyzer finds jobs through two reserved `THREAD_STATE` values:

- `state=RELEASED`: a job of the thread is released (periodic wake-up).
- `state=DONE`: the thread finished the current job.

A job is the interval from `RELEASED` to the next `DONE` of the same thread.
All other `state` values are free-form.

On a real target the traced program emits them itself as user string events,
`trace_logf(code, "blackbox RELEASED")` and `"blackbox DONE"` (any code); the
adapter applies each to the thread running on that CPU. See
`target/inversion_demo.c`.

## Example

    # ts_ns EVENT key=value ...
    1000 RUN tid=4 name=controller prio=20
    1500 MSG_SEND tid=4 name=controller prio=20 peer=7
    1600 MSG_RECEIVE tid=7 name=sensor prio=10 peer=4
    2400 MSG_REPLY tid=7 name=sensor prio=10 peer=4
    2500 THREAD_STATE tid=4 name=controller prio=20 state=READY
