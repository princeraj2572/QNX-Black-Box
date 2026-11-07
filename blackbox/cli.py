"""Command line interface: python3 -m blackbox <command>."""

import argparse
import sys

from .analysis import analyze
from .config import ConfigError, load_config
from .explain import explain
from .parser import ParseError, parse_file
from .record import DEFAULT_REMOTE_PATH, record
from .report import build_report, report_json
from .runner import RunnerError, SSHRunner

EXIT_OK = 0
EXIT_MISSES = 1
EXIT_ERROR = 2

EPILOG = """exit codes:
  0  analysis ran, no deadline misses
  1  analysis ran, at least one deadline miss
  2  bad input (unreadable file, parse error, invalid config) or bad usage
"""


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
    a.add_argument("trace", help="trace file in the internal format")
    a.add_argument("--config", required=True, help="thread config JSON")
    a.add_argument("--json", metavar="OUT", help="also write the JSON report to OUT")
    r = sub.add_parser("record", help="record a trace on the target and copy it back")
    r.add_argument("--target", required=True, help="ssh host, e.g. root@192.168.1.50")
    r.add_argument("--seconds", required=True, type=int, help="how long to record")
    r.add_argument("--out", default="trace.kev", help="local file for the raw trace")
    r.add_argument("--remote-path", default=DEFAULT_REMOTE_PATH,
                   help="trace file path on the target")
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


def cmd_record(args, runner_factory) -> int:
    try:
        runner = runner_factory(args.target)
        record(runner, args.seconds, args.out, args.remote_path)
    except (OSError, ValueError, RunnerError) as exc:  # RunnerError is a RuntimeError
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"saved trace to {args.out}")
    return EXIT_OK


def main(argv=None, runner_factory=SSHRunner) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on bad usage, 0 on --help
        return exc.code if isinstance(exc.code, int) else EXIT_ERROR
    if args.command == "record":
        return cmd_record(args, runner_factory)
    return cmd_analyze(args)
