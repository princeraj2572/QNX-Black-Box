# Internal trace format

This is the project's own text format, not a QNX file format. The analyzer only
reads this format. Real `tracelogger` output is mapped onto it by an adapter
(see PLAN.md F20).

TODO(human): confirm how real tracelogger events map onto these fields.

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
| `RUN`          | none         | Thread starts running on a CPU            |
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

TODO(human): decide how real tracelogger events yield RELEASED and DONE.

## Example

    # ts_ns EVENT key=value ...
    1000 RUN tid=4 name=controller prio=20
    1500 MSG_SEND tid=4 name=controller prio=20 peer=7
    1600 MSG_RECEIVE tid=7 name=sensor prio=10 peer=4
    2400 MSG_REPLY tid=7 name=sensor prio=10 peer=4
    2500 THREAD_STATE tid=4 name=controller prio=20 state=READY
