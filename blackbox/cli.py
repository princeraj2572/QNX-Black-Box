"""Command line interface: python3 -m blackbox <command>."""

import argparse
import json
import sys

from .analysis import analyze
from .chaos.scenarios import ScenarioError, load_scenario
from .config import ConfigError, load_config
from .dashboard import render_html
from .explain import explain
from .parser import ParseError, parse_file
from .recovery import find_restarts
from .record import DEFAULT_REMOTE_PATH, decode, record
from .report import build_report, report_json
from .runner import RunnerError, SSHRunner
from .serve import build_page, make_server

EXIT_OK = 0
EXIT_MISSES = 1
EXIT_ERROR = 2

EPILOG = """exit codes:
  0  analysis ran, no deadline misses
  1  analysis ran, at least one deadline miss
  2  bad input (unreadable file, parse error, invalid config) or bad usage
"""


DECODE_HELP = ("also decode the trace with the host traceprinter (QNX SDP) "
               "into a .txt next to --out, ready for analyze")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="blackbox",
        description="Explain why a real-time deadline was missed.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser(
        "analyze", help="explain deadline misses in a trace",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    a.add_argument("trace", help="internal-format trace, or traceprinter text of a tracelogger -w capture")
    a.add_argument("--config", required=True, help="thread config JSON")
    a.add_argument("--json", metavar="OUT", help="also write the JSON report to OUT")
    r = sub.add_parser("record", help="record a trace on the target and copy it back")
    r.add_argument("--target", required=True, help="ssh host, e.g. root@192.168.1.50")
    r.add_argument("--seconds", required=True, type=int, help="how long to record")
    r.add_argument("--out", default="trace.kev", help="local file for the raw trace")
    r.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH,
                   help="trace file path on the target")
    r.add_argument("--decode", action="store_true", help=DECODE_HELP)
    v = sub.add_parser("recovery", help="measure how long restarted threads were gone")
    v.add_argument("trace", help="internal-format trace, or traceprinter text of a tracelogger -w capture")
    h = sub.add_parser("report-html", help="render a JSON report as a self-contained HTML page")
    h.add_argument("report", help="report JSON written by `analyze --json`")
    h.add_argument("out", help="HTML file to write")
    s = sub.add_parser("serve", help="live preview: serve the dashboard for a trace on localhost")
    s.add_argument("trace", help="internal-format trace, or traceprinter text of a tracelogger -w capture")
    s.add_argument("--config", required=True, help="thread config JSON")
    s.add_argument("--port", type=int, default=8000, help="port on 127.0.0.1 (default 8000)")
    c = sub.add_parser("chaos", help="inject faults on the target")
    csub = c.add_subparsers(dest="chaos_command", required=True)
    cr = csub.add_parser("run", help="run a fault scenario while recording a trace")
    cr.add_argument("scenario", help="scenario JSON file")
    cr.add_argument("--dry-run", action="store_true",
                    help="print the target commands and exit; connects to nothing")
    cr.add_argument("--target", help="ssh host (required unless --dry-run)")
    cr.add_argument("--seconds", type=int, default=10, help="recording length")
    cr.add_argument("--out", default="trace.kev", help="local file for the raw trace")
    cr.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH,
                    help="trace file path on the target")
    cr.add_argument("--decode", action="store_true", help=DECODE_HELP)
    return p


def cmd_analyze(args) -> int:
    try:
        config = load_config(args.config)
        events = parse_file(args.trace)
    except (OSError, ParseError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    result = analyze(events, config)
    sys.stdout.write(explain(result, config))
    if args.json:
        try:
            with open(args.json, "w", encoding="utf-8") as f:
                f.write(report_json(build_report(events, result, config)))
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
    return EXIT_MISSES if result.misses else EXIT_OK


def cmd_recovery(args) -> int:
    try:
        events = parse_file(args.trace)
    except (OSError, ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    restarts = find_restarts(events)
    for r in restarts:
        print(f"{r.name} gone at {r.down_ns / 1e6:.3f} ms, back at {r.up_ns / 1e6:.3f} ms: "
              f"recovered in {r.recovery_ns / 1e6:.3f} ms (tid {r.old_tid} -> {r.new_tid})")
    if not restarts:
        print("No restarted threads found.")
    return EXIT_OK


def cmd_record(args, runner_factory) -> int:
    try:
        runner = runner_factory(args.target)
        record(runner, args.seconds, args.out, args.remote_path)
        print(f"saved trace to {args.out}")
        if args.decode:
            print(f"decoded to {decode(args.out)}")
    except (OSError, ValueError, RunnerError) as exc:  # RunnerError is a RuntimeError
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def cmd_serve(args) -> int:
    try:
        build_page(args.trace, args.config)  # fail fast on bad input
        server = make_server(args.trace, args.config, args.port)
    except (OSError, ParseError, ConfigError, OverflowError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"serving http://127.0.0.1:{server.server_port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return EXIT_OK


def cmd_report_html(args) -> int:
    try:
        with open(args.report, "r", encoding="utf-8") as f:
            page = render_html(json.load(f))
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(page)
    except (OSError, ValueError) as exc:  # includes JSON and report-format errors
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"wrote {args.out}")
    return EXIT_OK


def cmd_chaos_run(args, runner_factory) -> int:
    try:
        scenario = load_scenario(args.scenario)
    except (OSError, ScenarioError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    commands = scenario.commands()
    if args.dry_run:
        print(f"# scenario {scenario.name}: {len(commands)} command(s), nothing executed")
        for cmd in commands:
            print(cmd)
        return EXIT_OK
    if not args.target:
        print("error: --target is required unless --dry-run is given", file=sys.stderr)
        return EXIT_ERROR
    try:
        record(runner_factory(args.target), args.seconds, args.out,
               args.remote_path, inject=commands)
        print(f"ran scenario {scenario.name}; saved trace to {args.out}")
        if args.decode:
            print(f"decoded to {decode(args.out)}")
    except (OSError, ValueError, RunnerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def main(argv=None, runner_factory=SSHRunner) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on bad usage, 0 on --help
        return exc.code if isinstance(exc.code, int) else EXIT_ERROR
    if args.command == "record":
        return cmd_record(args, runner_factory)
    if args.command == "chaos":
        return cmd_chaos_run(args, runner_factory)
    if args.command == "report-html":
        return cmd_report_html(args)
    if args.command == "recovery":
        return cmd_recovery(args)
    if args.command == "serve":
        return cmd_serve(args)
    return cmd_analyze(args)
