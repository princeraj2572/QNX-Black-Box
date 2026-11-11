# QNX Black Box

Host-side tooling that records a QNX 8.0 system trace, injects faults, and
explains in plain English why a real-time deadline was missed.

You give it a trace and a small config listing each thread's period, deadline
and priority. It finds every job that missed its deadline and says why:
priority inversion, CPU starvation by a higher-priority thread, or a slow
reply to a message.

```
high missed its 5.0 ms deadline: the job released at 0.000 ms finished at 10.000 ms, ...
  - Priority inversion: high (priority 20) was blocked on low (priority 5) from 2.000 ms,
    and med (priority 10) ran for 5.000 ms in the meantime, so low could not finish and reply.
```

## Install

Python 3.8 or newer, standard library only. No packages to install.

    git clone https://github.com/princeraj2572/QNX-Black-Box.git
    cd QNX-Black-Box
    python3 -m unittest discover -s tests      # optional: run the tests

Run everything as `python3 -m blackbox <command>` from the repo root.

## Usage

Explain the misses in a trace (internal text format, see `docs/trace-format.md`):

    python3 -m blackbox analyze tests/fixtures/scenario_inversion.trace \
        --config tests/fixtures/scenario_config.json --json report.json

Exit codes: `0` no misses, `1` at least one miss, `2` bad input or usage.

No config file? If the traced program logs job markers (`docs/trace-format.md`),
`analyze` finds each periodic thread's period and priority in the trace. Give
the deadlines on the command line; without one, a thread's deadline is its
period:

    python3 -m blackbox analyze tests/fixtures/real/inversion_demo.trace --deadline controller=20

Render the JSON report as one self-contained HTML timeline:

    python3 -m blackbox report-html report.json report.html

Live preview: serve the dashboard on `http://127.0.0.1:8000/`. It re-reads the
trace and config on every request and refreshes itself every 2 seconds, so you
can edit the trace and watch the page change:

    python3 -m blackbox serve tests/fixtures/scenario_inversion.trace \
        --config tests/fixtures/scenario_config.json [--port 8000]

Record a trace on the target over SSH (copies the raw tracelogger file back):

    python3 -m blackbox record --target root@192.168.1.50 --seconds 10 --out trace.kev --decode
    python3 -m blackbox analyze trace.txt --config config.json

`--decode` runs the SDP's host `traceprinter` (source `qnxsdp-env.sh` first)
and writes `trace.txt` next to the raw trace; `chaos run` takes it too. For a
QEMU target behind a forwarded port, add an alias to `~/.ssh/config` and use
`--target qnxvm`:

    Host qnxvm
        HostName localhost
        Port 2222
        User root

Inject faults while recording. `--dry-run` only prints the commands that would
run on the target and connects to nothing:

    python3 -m blackbox chaos run tests/fixtures/scenario_chaos.json --dry-run
    python3 -m blackbox chaos run scenario.json --target root@192.168.1.50 --seconds 10

Fault types (parameters in `blackbox/chaos/scenarios.py`):

| Fault | Status |
|---|---|
| `kill_process` | verified on QNX 8.0 (x86_64 QEMU) |
| `cpu_hog`, `delay_thread`, `memory_pressure` | experimental: checked in dry runs only, and the CLI prints a warning when a scenario uses one |

Measure how long a killed service was gone before something (for example the
QNX High Availability Manager) restarted it. A restart is a thread name that
reappears under a new tid after its old one went quiet:

    python3 -m blackbox recovery trace.txt --name controller --name server

Without `--name`, thread pools and SSH sessions also show up, since their
threads reuse names.

See `target/README.md` for the HAM demo.

The report format is in `docs/report-format.md`. A guided walkthrough is in
`docs/codelab.md`.

## Architecture

```
 QNX target                          host (this repo)
+--------------------+   ssh/scp   +--------------------------------------------+
| services           |<------------| chaos  (scenarios -> shell commands)       |
| tracelogger        |------------>| record (start/stop tracelogger, copy file) |
+--------------------+  raw trace  +--------------------------------------------+
                                          | adapter (traceprinter text -> internal)
                                          v
              trace.txt --> parser --> events --> detectors --> explainer --> text
              config.json -----------------------^   |  deadlines, blocking,
                                                     |  inversion, starvation,
                                                     v  slow replies
                                                  report.json --> report-html --> report.html
```

## QNX version, target and toolchain

| Item      | Value |
|-----------|-------|
| QNX       | QNX Software Development Platform (SDP) 8.0 |
| Target    | QEMU virtual machine or Raspberry Pi 5 |
| Toolchain | `qcc` from SDP 8.0 builds the C demo services in `target/` |
| Host      | any OS with Python 3 and an `ssh`/`scp` client |

Status: verified on SDP 8.0 with an x86_64 QEMU target. The priority
inversion demo in `target/` was built with `qcc`, traced with `tracelogger -w`,
and its captures are analyzed in the tests (`tests/fixtures/real/`). `record`, the
`kill_process` fault and `recovery` were also run there: a killed service's
threads came back in 94 to 99 ms. Not yet verified: Raspberry Pi 5, the other
chaos faults, and the HAM demo;
these are marked `TODO(human)` in the code and docs.

## License

MIT, see LICENSE.
