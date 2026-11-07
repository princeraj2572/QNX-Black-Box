# JSON report format

Produced by `blackbox.report.build_report` (and the CLI `--json` option).
All times are integer nanoseconds from the start of the trace.

```
{
  "version": 1,
  "trace_end_ns": int,
  "threads": [
    {"name": str, "period_ms": number, "deadline_ms": number, "priority": int}
  ],
  "misses": [
    {
      "thread": str, "tid": int,
      "release_ns": int, "deadline_ns": int,     // deadline_ns is absolute
      "done_ns": int | null,                      // null: unfinished at trace end
      "response_ns": int | null,
      "late_ns": int | null,
      "causes": [ <cause>, ... ],
      "explanation": [str, ...]                   // plain-English lines
    }
  ],
  "timeline": [
    {"event": "RUN|THREAD_STATE|MSG_SEND|MSG_RECEIVE|MSG_REPLY",
     "ts_ns": int, "tid": int, "name": str, "prio": int,
     "state": str,   // THREAD_STATE only
     "peer": int}    // MSG_* only
  ]
}
```

## Causes

Each cause has a `type`:

| type                | fields |
|---------------------|--------|
| `priority_inversion` | `blocked`, `blocked_on`, `medium`, `start_ns`, `end_ns` |
| `cpu_starvation`     | `thread`, `priority`, `run_ns` |
| `slow_reply`         | `from`, `send_ns`, `duration_ns` |

`misses` is empty when no deadline was missed. `timeline` is sorted by `ts_ns`.
