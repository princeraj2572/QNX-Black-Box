"""Optional AI step: ask a language model for a code fix for the misses in a report.

The analysis itself stays deterministic. This step only takes its findings (thread
config, causes and timings, never the raw timeline) plus, if given, the source file,
and asks a model to propose a change. The answer is a suggestion to check, and the
check is a second trace: apply the change, record again, run `analyze`.

Uses the Gemini API over HTTPS with the standard library only. The key comes from
the GEMINI_API_KEY environment variable. `build_prompt` needs no network, so the
prompt can also be pasted into any other assistant.
"""

import json
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional

DEFAULT_MODEL = "gemini-flash-lite-latest"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_MISSES = 5          # misses described in full; the rest are counted
MAX_SOURCE_CHARS = 20000


class SuggestError(RuntimeError):
    pass


def _ms(ns) -> str:
    return "unknown" if ns is None else f"{ns / 1_000_000:.3f} ms"


def _cause_counts(misses: List[dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for m in misses:
        for kind in dict.fromkeys(c["type"] for c in m.get("causes", [])):
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def build_prompt(report: dict, source: Optional[str] = None, source_name: str = "source") -> str:
    """The text sent to the model. Raises SuggestError if the report has no misses."""
    misses = report.get("misses") or []
    if not misses:
        raise SuggestError("the report has no deadline misses, so there is nothing to fix")
    out = [
        "You are helping debug a real-time system running on QNX 8.0.",
        "A trace analyzer found the deadline misses below. Its findings are measured facts.",
        "Propose the smallest code change that removes the cause, as a unified diff if source",
        "is given, and say in one sentence how a second trace would confirm it.",
        "Do not invent facts the findings do not support; say so if they are not enough.",
        "",
        "Threads (period, deadline, priority):",
    ]
    for t in report.get("threads", []):
        out.append(f"- {t.get('name')}: period {t.get('period_ms')} ms, "
                   f"deadline {t.get('deadline_ms')} ms, priority {t.get('priority')}")
    out += ["", f"Deadline misses: {len(misses)}. Causes found (misses affected):"]
    for kind, n in _cause_counts(misses).items():
        out.append(f"- {kind}: {n} of {len(misses)}")
    out += ["", f"First {min(MAX_MISSES, len(misses))} misses in detail:"]
    for m in misses[:MAX_MISSES]:
        out.append(f"- {m.get('thread')}: response {_ms(m.get('response_ns'))}, "
                   f"late by {_ms(m.get('late_ns'))}")
        out += [f"  {line.strip()}" for line in m.get("explanation", [])[1:]]
    if source:
        if len(source) > MAX_SOURCE_CHARS:
            source = source[:MAX_SOURCE_CHARS] + "\n[truncated]"
        out += ["", f"Source file {source_name}:", "```", source.rstrip("\n"), "```"]
    return "\n".join(out) + "\n"


def _post(url: str, headers: Dict[str, str], body: bytes, timeout: float) -> bytes:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def suggest(prompt: str, api_key: str, model: str = DEFAULT_MODEL, timeout: float = 60.0,
            post: Callable[[str, Dict[str, str], bytes, float], bytes] = _post) -> str:
    """Send the prompt to the model and return its text. `post` is replaceable for tests."""
    if not api_key:
        raise SuggestError("set GEMINI_API_KEY (a free key: https://aistudio.google.com/apikey), "
                           "or use --print-prompt and paste the prompt into any assistant")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    try:
        raw = post(API_URL.format(model=model), headers, body, timeout)
    except urllib.error.HTTPError as exc:
        raise SuggestError(f"the model API answered HTTP {exc.code}") from None
    except (urllib.error.URLError, OSError) as exc:
        raise SuggestError(f"could not reach the model API: {exc}") from None
    try:
        parts = json.loads(raw)["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise SuggestError("the model API returned an answer in an unexpected shape") from None
    if not text:
        raise SuggestError("the model returned an empty answer")
    return text
