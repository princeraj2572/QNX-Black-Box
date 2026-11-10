"""Turn an Analysis into plain-English text."""

from typing import Dict, List

from .analysis import Analysis
from .config import ThreadConfig


def ms(ns: int) -> str:
    return f"{ns / 1_000_000:.3f} ms"


def explain_miss(job, a: Analysis, config: Dict[str, ThreadConfig]) -> List[str]:
    end = a.trace_end_ns if job.done_ns is None else job.done_ns
    cfg = config[job.name]
    if job.done_ns is None:
        head = (
            f"{job.name} missed its {cfg.deadline_ms:.1f} ms deadline: the job released at "
            f"{ms(job.release_ns)} had not finished by the end of the trace "
            f"({ms(a.trace_end_ns - job.release_ns)} later)."
        )
    else:
        head = (
            f"{job.name} missed its {cfg.deadline_ms:.1f} ms deadline: the job released at "
            f"{ms(job.release_ns)} finished at {ms(job.done_ns)}, a response time of "
            f"{ms(job.response_ns)}, {ms(job.done_ns - job.deadline_ns)} late."
        )
    lines = [head]

    # Merge inversion intervals that share a block and a medium thread.
    merged: Dict[tuple, list] = {}
    for inv in a.inversions:
        b = inv.block
        if b.blocked_tid == job.tid and job.release_ns <= b.start_ns <= end:
            m = merged.setdefault((b.start_ns, inv.medium_tid), [inv, 0])
            m[1] += inv.end_ns - inv.start_ns
    for inv, total in merged.values():
        b = inv.block
        lines.append(
            f"  - Priority inversion: {b.blocked_name} (priority {b.blocked_prio}) was blocked "
            f"on {b.on_name} (priority {b.on_prio}) from {ms(b.start_ns)}, and "
            f"{inv.medium_name} (priority {inv.medium_prio}) ran for {ms(total)} in the "
            f"meantime, so {b.on_name} could not finish and reply."
        )
    for s in a.starvation:
        if s.job == job:
            lines.append(
                f"  - CPU starvation: {s.hog_name} (priority {s.hog_prio}) outranks "
                f"{job.name} and ran for {ms(s.run_ns)} while the job was in flight."
            )
    for d in a.reply_delays:
        if d.job == job:
            lines.append(
                f"  - Slow reply: {job.name} sent a message to {d.block.on_name} at "
                f"{ms(d.block.start_ns)} and waited {ms(d.duration_ns)} for the reply."
            )
    for w in a.mutex_waits:
        if w.job == job:
            line = (f"  - Mutex wait: {w.name} (priority {w.prio}) waited "
                    f"{ms(w.end_ns - w.start_ns)} on a mutex from {ms(w.start_ns)}.")
            if w.ran:
                line += " Meanwhile " + " and ".join(
                    f"{n} (priority {p}) ran {ms(t)}" for n, p, t in w.ran) + "."
            if len({p for _, p, _ in w.ran}) > 1:
                low, high = min(w.ran, key=lambda r: r[1]), max(w.ran, key=lambda r: r[1])
                line += (f" Likely priority inversion: if {low[0]} holds the mutex, {high[0]} "
                         f"preempted it while {w.name} waited. A mutex with priority "
                         f"inheritance (PTHREAD_PRIO_INHERIT) prevents this.")
            lines.append(line)
    if len(lines) == 1:
        lines.append("  - No cause was identified from the trace.")
    return lines


def explain(a: Analysis, config: Dict[str, ThreadConfig]) -> str:
    if not a.misses:
        return "No deadline misses found.\n"
    out = [f"Found {len(a.misses)} deadline miss{'es' if len(a.misses) != 1 else ''}.", ""]
    for job in a.misses:
        out += explain_miss(job, a, config)
        out.append("")
    return "\n".join(out)
