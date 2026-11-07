"""Render a JSON report (docs/report-format.md) as one self-contained HTML page.

No external assets: styles and script are inline. The miss explanations are
also written as static HTML so the page is readable without JavaScript.
"""

import json
import re
from html import escape

REQUIRED_KEYS = ("version", "trace_end_ns", "threads", "misses", "timeline")


class ReportFormatError(ValueError):
    pass


def check_report(report) -> None:
    if not isinstance(report, dict) or any(k not in report for k in REQUIRED_KEYS):
        raise ReportFormatError(f"not a blackbox report; expected keys {list(REQUIRED_KEYS)}")


def _embed(report: dict) -> str:
    # '</' would end the script block early; U+2028/9 break older JS parsers.
    s = json.dumps(report).replace("</", "<\\/")
    return s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _misses_html(report: dict) -> str:
    if not report["misses"]:
        return "<p>No deadline misses found.</p>"
    parts = []
    for m in report["misses"]:
        lines = m["explanation"]
        items = "".join(f"<li>{escape(x.strip().lstrip('- '))}</li>" for x in lines[1:])
        parts.append(
            f'<div class="miss"><p><strong>{escape(lines[0])}</strong></p><ul>{items}</ul></div>'
        )
    return "".join(parts)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QNX Black Box report</title>
<style>
:root { --bg:#fff; --fg:#1b1f24; --muted:#59636e; --run:#4c8bf5; --miss:#d93025;
        --line:#d0d7de; --send:#e8710a; --recv:#188038; --reply:#9334e6; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#12161b; --fg:#e6edf3; --muted:#9aa4af; --run:#6ea0ff; --miss:#ff6b60;
          --line:#30363d; --send:#ffa040; --recv:#4ccf75; --reply:#c58bff; }
}
body { background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif;
       margin:0 auto; max-width:1100px; padding:16px; }
h1 { font-size:1.4rem; } h2 { font-size:1.1rem; margin-top:1.6rem; }
.miss { border-left:4px solid var(--miss); padding:2px 12px; margin:10px 0; }
.legend span { margin-right:14px; color:var(--muted); font-size:.85rem; }
svg { width:100%; height:auto; border:1px solid var(--line); border-radius:6px; }
text { fill:var(--fg); font-size:11px; }
.axis { stroke:var(--line); }
</style>
</head>
<body>
<h1>QNX Black Box report</h1>
<h2>Why deadlines were missed</h2>
<div id="misses">__MISSES__</div>
<h2>Timeline</h2>
<p class="legend"><span>blue bar: thread running</span><span>red band: missed job window</span>
<span style="color:var(--send)">&#9679; send</span><span style="color:var(--recv)">&#9679; receive</span>
<span style="color:var(--reply)">&#9679; reply</span></p>
<svg id="timeline" viewBox="0 0 1000 120" role="img" aria-label="Thread timeline"></svg>
<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  var NS = "http://www.w3.org/2000/svg";
  var d = JSON.parse(document.getElementById("data").textContent);
  var svg = document.getElementById("timeline");
  var end = Math.max(d.trace_end_ns, 1), X0 = 120, W = 860, ROW = 26, TOP = 20;
  var lanes = [];
  function lane(n) { if (lanes.indexOf(n) < 0) lanes.push(n); }
  d.threads.forEach(function (t) { lane(t.name); });
  d.timeline.forEach(function (e) { lane(e.name); });
  var byTid = {};
  d.timeline.forEach(function (e) { byTid[e.tid] = e.name; });
  function x(ts) { return X0 + (ts / end) * W; }
  function el(tag, attrs, title) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (title) { var t = document.createElementNS(NS, "title"); t.textContent = title; n.appendChild(t); }
    svg.appendChild(n); return n;
  }
  function label(txt, px, py, anchor) {
    var n = el("text", { x: px, y: py, "text-anchor": anchor || "start" }); n.textContent = txt;
  }
  var h = TOP + lanes.length * ROW + 24;
  svg.setAttribute("viewBox", "0 0 1000 " + h);
  d.misses.forEach(function (m) {
    var stop = m.done_ns === null ? d.trace_end_ns : m.done_ns;
    el("rect", { x: x(m.release_ns), y: TOP - 6, width: Math.max(x(stop) - x(m.release_ns), 1),
                 height: lanes.length * ROW + 6, fill: "var(--miss)", opacity: 0.15 },
       m.thread + " job: " + m.release_ns + " to " + stop + " ns");
    el("line", { x1: x(m.deadline_ns), x2: x(m.deadline_ns), y1: TOP - 6,
                 y2: TOP + lanes.length * ROW, stroke: "var(--miss)", "stroke-dasharray": "4 3" },
       m.thread + " deadline at " + m.deadline_ns + " ns");
  });
  lanes.forEach(function (n, i) {
    var y = TOP + i * ROW;
    el("line", { x1: X0, x2: X0 + W, y1: y + ROW, y2: y + ROW, class: "axis" });
    label(n, X0 - 6, y + 16, "end");
  });
  var runs = d.timeline.filter(function (e) { return e.event === "RUN"; });
  runs.forEach(function (r, i) {
    var stop = i + 1 < runs.length ? runs[i + 1].ts_ns : d.trace_end_ns;
    el("rect", { x: x(r.ts_ns), y: TOP + lanes.indexOf(r.name) * ROW + 4,
                 width: Math.max(x(stop) - x(r.ts_ns), 1), height: ROW - 10, fill: "var(--run)" },
       r.name + " (prio " + r.prio + ") runs " + r.ts_ns + " to " + stop + " ns");
  });
  var colors = { MSG_SEND: "var(--send)", MSG_RECEIVE: "var(--recv)", MSG_REPLY: "var(--reply)" };
  d.timeline.forEach(function (e) {
    if (!colors[e.event]) return;
    el("circle", { cx: x(e.ts_ns), cy: TOP + lanes.indexOf(e.name) * ROW + ROW / 2, r: 3.5,
                   fill: colors[e.event] },
       e.event + " " + e.name + " -> " + (byTid[e.peer] || ("tid " + e.peer)) + " at " + e.ts_ns + " ns");
  });
  label("0 ms", X0, h - 6); label((end / 1e6).toFixed(3) + " ms", X0 + W, h - 6, "end");
})();
</script>
</body>
</html>
"""


def render_html(report: dict) -> str:
    check_report(report)
    # One pass, so placeholder-like text inside the substituted values is left alone.
    values = {"__MISSES__": _misses_html(report), "__DATA__": _embed(report)}
    return re.sub(r"__MISSES__|__DATA__", lambda m: values[m.group(0)], TEMPLATE)
