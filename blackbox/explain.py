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


def causes_of(job, a: Analysis) -> List[str]:
    """Short labels for each cause found for one missed job, in causal order."""
    end = a.trace_end_ns if job.done_ns is None else job.done_ns
    found = [f"priority inversion: {i.medium_name} ran while {i.block.on_name} held up "
             f"{job.name}" for i in a.inversions if i.block.blocked_tid == job.tid
             and job.release_ns <= i.block.start_ns <= end]
    found += [f"slow reply from {d.block.on_name}" for d in a.reply_delays if d.job == job]
    for w in a.mutex_waits:
        if w.job == job:
            if len({p for _, p, _ in w.ran}) > 1:
                low = min(w.ran, key=lambda r: r[1])[0]
                high = max(w.ran, key=lambda r: r[1])[0]
                found.append(f"{w.name} waited on a mutex while {high} preempted {low} "
                             f"(likely priority inversion)")
            else:
                found.append(f"{w.name} waited on a mutex")
    found += [f"CPU starvation by {s.hog_name}" for s in a.starvation if s.job == job]
    return list(dict.fromkeys(found))


def summary(a: Analysis) -> List[str]:
    out = ["Summary:"]
    by_name: Dict[str, list] = {}
    for job in a.misses:
        by_name.setdefault(job.name, []).append(job)
    for name, jobs in by_name.items():
        late = [j.done_ns - j.deadline_ns for j in jobs if j.done_ns is not None]
        line = f"  - {name}: {len(jobs)} miss{'es' if len(jobs) != 1 else ''}"
        if late:
            line += f", worst {ms(max(late))} late, average {ms(sum(late) // len(late))} late"
        if len(late) < len(jobs):
            line += f", {len(jobs) - len(late)} unfinished at the end of the trace"
        out.append(line + ".")
    counts: Dict[str, int] = {}
    for job in a.misses:
        for c in causes_of(job, a):
            counts[c] = counts.get(c, 0) + 1
    n = len(a.misses)
    for c, k in sorted(counts.items(), key=lambda kv: -kv[1]):  # stable: keeps causal order
        out.append(f"  - Cause in {k} of {n}: {c}.")
    if any(len({p for _, p, _ in w.ran}) > 1 for w in a.mutex_waits):
        out.append("  - Suggested fix: create the mutex with priority inheritance "
                   "(pthread_mutexattr_setprotocol(&attr, PTHREAD_PRIO_INHERIT)).")
    return out + [""]


def explain(a: Analysis, config: Dict[str, ThreadConfig]) -> str:
    if not a.misses:
        return "No deadline misses found.\n"
    out = [f"Found {len(a.misses)} deadline miss{'es' if len(a.misses) != 1 else ''}.", ""]
    if len(a.misses) > 1:  # one miss: the details below already are the summary
        out += summary(a) + ["Details:", ""]
    for job in a.misses:
        out += explain_miss(job, a, config)
        out.append("")
    return "\n".join(out)
