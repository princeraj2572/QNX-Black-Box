# Debug a missed deadline on QNX in 30 minutes

You will record a trace, break the system on purpose, and let QNX Black Box
explain which deadline was missed and why.

Placeholders marked `[REAL OUTPUT]` must be replaced with output captured on a
real QNX 8.0 target (PLAN.md F19 and F22). The sample outputs below come from
the sample fixture in `tests/fixtures/`, not from a QNX system.

## 0. What you need (about 5 minutes)

- A QNX SDP 8.0 target (QEMU or Raspberry Pi 5) reachable over SSH, with
  `tracelogger` available. `[REAL OUTPUT: tracelogger -h]`
- Python 3.8+ on your computer and this repository.
- The demo services from `target/`, built with `qcc`: a sensor, a controller
  and a low-priority data service the controller depends on.

Run the tests to check your setup:

    python3 -m unittest discover -s tests

## 1. Describe your threads (2 minutes)

List each periodic thread with its period, deadline and priority in a JSON
file, for example `tests/fixtures/scenario_config.json`:

    {"threads": [
      {"name": "high", "period_ms": 20, "deadline_ms": 5, "priority": 20},
      {"name": "low",  "period_ms": 50, "deadline_ms": 50, "priority": 5}]}

## 2. Preview the fault (2 minutes)

A scenario file lists the faults to inject. See what would run on the target
without touching it:

    python3 -m blackbox chaos run tests/fixtures/scenario_chaos.json --dry-run

    # scenario demo: 2 command(s), nothing executed
    slay -s KILL sensor
    (slay -s STOP controller; sleep 2; slay -s CONT controller) &

## 3. Record while injecting the fault (5 minutes)

    python3 -m blackbox chaos run scenario.json --target root@<target-ip> --seconds 10 --out trace.kev

    [REAL OUTPUT]

This starts `tracelogger`, runs the faults, waits, stops the logger and copies
the raw trace to `trace.kev`.

## 4. Convert the trace (3 minutes)

The analyzer reads the internal text format (`docs/trace-format.md`). Export
the raw trace to text and map it with the tracelogger adapter.

    [REAL OUTPUT: adapter command, PLAN.md F20]

## 5. Ask why (3 minutes)

    python3 -m blackbox analyze trace.txt --config config.json --json report.json

Sample output (from the fixture):

    Found 1 deadline miss.

    high missed its 5.0 ms deadline: the job released at 0.000 ms finished at 10.000 ms, a response time of 10.000 ms, 5.000 ms late.
      - Priority inversion: high (priority 20) was blocked on low (priority 5) from 2.000 ms, and med (priority 10) ran for 5.000 ms in the meantime, so low could not finish and reply.
      - Slow reply: high sent a message to low at 2.000 ms and waited 7.000 ms for the reply.

    [REAL OUTPUT]

The exit code is `1` when a deadline was missed, so you can use it in scripts.

## 6. Look at the timeline (3 minutes)

    python3 -m blackbox report-html report.json report.html

Open `report.html` in a browser. Blue bars show which thread ran, the red band
is the missed job, and the dots are message sends, receives and replies.

## 7. Fix it (5 minutes)

Pick the fix that matches the explanation, rebuild, and record again:

- Priority inversion: shorten the low-priority critical section, or make the
  server run at the priority of its clients. Check how QNX priority
  inheritance affects message passing first (PLAN.md F21).
- CPU starvation: lower the hog's priority or budget its CPU time.
- Slow reply: make the server reply sooner, or send asynchronously.

Re-run step 3 to 5. The miss should disappear and `analyze` should exit `0`.

    [REAL OUTPUT: before and after]
