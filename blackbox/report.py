"""Build the JSON report described in docs/report-format.md."""

import json
from dataclasses import asdict
from typing import Dict, List

from .analysis import Analysis
from .config import ThreadConfig
from .events import Event
from .explain import explain_miss

REPORT_VERSION = 1


def _causes(job, a: Analysis) -> List[dict]:
    end = a.trace_end_ns if job.done_ns is None else job.done_ns
    causes = []
    for inv in a.inversions:
        b = inv.block
        if b.blocked_tid == job.tid and job.release_ns <= b.start_ns <= end:
            causes.append({
                "type": "priority_inversion",
                "blocked": b.blocked_name,
                "blocked_on": b.on_name,
                "medium": inv.medium_name,
                "start_ns": inv.start_ns,
                "end_ns": inv.end_ns,
            })
    for s in a.starvation:
        if s.job == job:
            causes.append({
                "type": "cpu_starvation",
                "thread": s.hog_name,
                "priority": s.hog_prio,
                "run_ns": s.run_ns,
            })
    for d in a.reply_delays:
        if d.job == job:
            causes.append({
                "type": "slow_reply",
                "from": d.block.on_name,
                "send_ns": d.block.start_ns,
                "duration_ns": d.duration_ns,
            })
    for w in a.mutex_waits:
        if w.job == job:
            causes.append({
                "type": "mutex_wait",
                "thread": w.name,
                "priority": w.prio,
                "start_ns": w.start_ns,
                "end_ns": w.end_ns,
                "ran": [{"thread": n, "priority": p, "run_ns": t} for n, p, t in w.ran],
            })
    return causes


def build_report(events: List[Event], a: Analysis, config: Dict[str, ThreadConfig]) -> dict:
    misses = []
    for job in a.misses:
        misses.append({
            "thread": job.name,
            "tid": job.tid,
            "release_ns": job.release_ns,
            "deadline_ns": job.deadline_ns,
            "done_ns": job.done_ns,
            "response_ns": job.response_ns,
            "late_ns": None if job.done_ns is None else job.done_ns - job.deadline_ns,
            "causes": _causes(job, a),
            "explanation": explain_miss(job, a, config),
        })
    timeline = [dict(asdict(e), event=e.kind) for e in sorted(events, key=lambda e: e.ts_ns)]
    return {
        "version": REPORT_VERSION,
        "trace_end_ns": a.trace_end_ns,
        "threads": [asdict(t) for t in config.values()],
        "misses": misses,
        "timeline": timeline,
    }


def report_json(report: dict) -> str:
    return json.dumps(report, indent=2) + "\n"
