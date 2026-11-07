# Plan: QNX Black Box

Legend: `[ ]` todo, `[x]` done. `[HUMAN]` means it needs a person with a QNX SDP 8.0 install; the loop skips these.

Build order: (1) recorder + explainer must ship, (2) chaos injector should ship, (3) dashboard is nice to have.

## Features

- [x] F01 Scaffold: README stub, MIT LICENSE ("Copyright (c) 2026 princeraj2572"), pyproject.toml, package `blackbox/`, `tests/` with one smoke test. `python3 -m unittest discover -s tests` passes.
- [x] F02 Event model: `blackbox/events.py` dataclasses for RUN, THREAD_STATE, MSG_SEND, MSG_RECEIVE, MSG_REPLY (ts_ns, tid, name, prio, peer where relevant). Document the internal text format `<ts_ns> <EVENT> key=value ...` in docs/trace-format.md. Tests.
- [x] F03 Parser: `blackbox/parser.py` reads the internal format into events. Tolerates blank lines and `#` comments; errors include line numbers. Fixtures in tests/fixtures/. Tests.
- [x] F04 Config: `blackbox/config.py` loads a JSON file listing threads with period_ms, deadline_ms and priority. Validation and tests.
- [x] F05 Deadline-miss detector: `blackbox/deadlines.py` finds jobs (release to completion) that exceed their deadline. Fixture with one miss and one hit. Tests.
- [x] F06 Blocking chains: `blackbox/blocking.py` builds who-was-blocked-on-whom from SEND/RECEIVE/REPLY intervals. Tests.
- [x] F07 Priority inversion: detect a high-priority thread blocked on a lower-priority one while a medium-priority thread runs. Fixture and tests.
- [x] F08 Other causes: CPU starvation by a higher-priority thread, and long reply delay. Tests.
- [ ] F09 Explainer: `blackbox/explain.py` turns causes into plain-English text with timestamps and thread names. Golden-file tests.
- [ ] F10 JSON report: `blackbox/report.py` (misses, causes, timeline). Schema in docs/report-format.md. Tests.
- [ ] F11 CLI: `python3 -m blackbox analyze TRACE --config CONFIG [--json OUT]` prints the explanation; exit codes documented. Tests via subprocess.
- [ ] F12 Chaos scenarios: `blackbox/chaos/scenarios.py` declarative faults (kill_process, cpu_hog, delay_thread, memory_pressure) that produce lists of target shell commands. Pure and dry-run only. Tests.
- [ ] F13 Command runner: `blackbox/runner.py` with an SSH runner and a mock runner. No network in tests. Tests.
- [ ] F14 Record command: `blackbox record --target HOST --seconds N` wraps tracelogger start/stop and copies the trace file; works against the mock runner. Tests.
- [ ] F15 Chaos CLI: `blackbox chaos run SCENARIO [--dry-run]` ties F12 to F14 together. Tests.
- [ ] F16 Dashboard: `blackbox report-html REPORT.json OUT.html` writes one self-contained HTML timeline (no external assets, vanilla JS). Tests check key elements.
- [ ] F17 Docs: docs/codelab.md ("Debug a missed deadline on QNX in 30 minutes", with placeholders for real output) and a full README: install, usage, ASCII architecture diagram, and a QNX version / target / toolchain section.
- [ ] F17b Judge guide: docs/qnx-usage.md maps each QNX feature the project relies on (tracelogger, instrumented kernel, message passing, pidin, slog2) to the files and functions that use it, so reviewers can find it quickly. Mark anything unverified with TODO(human).
- [ ] F18 [HUMAN] Install QNX SDP 8.0, boot QEMU, confirm the instrumented kernel and `tracelogger` work.
- [ ] F19 [HUMAN] Capture a real trace, export it to text, save it under tests/fixtures/real/.
- [ ] F20 [HUMAN] Add `blackbox/adapters/tracelogger.py` mapping the real exported events to the internal format (or remove the HUMAN tag once the real fixture exists so the loop can do it).
- [ ] F21 [HUMAN] Write and build the C demo services under target/ with qcc: a sensor, a controller and a deliberate priority inversion. Verify how QNX priority inheritance affects message passing; use a mutex without priority inheritance if needed.
- [ ] F22 [HUMAN] Record the demo video (under 3 minutes) and put real measured numbers into the README and codelab.
- [ ] F23 [HUMAN] Check whether the High Availability Manager (watchdog) is available in SDP 8.0. If yes, add a demo where it restarts a killed service and the tool measures recovery time; record the result in docs/qnx-usage.md.
- [ ] F24 [HUMAN] Devpost submission checklist: public repo with a detectable open-source license, build/run instructions naming QNX version, target (QEMU or Raspberry Pi 5) and toolchain, written description, public YouTube demo under 3 minutes, selected category (Developer Tooling and Host Tools), codelab URL for the tutorial prize, and an explanation of how the project uses QNX. Check the Official Rules for any AI-tool disclosure requirement.
