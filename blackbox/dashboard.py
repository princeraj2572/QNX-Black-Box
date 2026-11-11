"""Render a JSON report (docs/report-format.md) as one self-contained HTML page.

No external assets: styles and script are inline. The summary, the miss list
and every explanation are static HTML, so the page reads without JavaScript;
the script only draws the overview strip and the close-up timeline.
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


def _ms(ns) -> str:
    return f"{ns / 1_000_000:.3f} ms"


def _cause_label(c: dict) -> str:
    t = c.get("type")
    if t == "priority_inversion":
        return f"{c['medium']} ran while {c['blocked_on']} held up {c['blocked']}"
    if t == "slow_reply":
        return f"slow reply from {c['from']}"
    if t == "mutex_wait":
        ran = c.get("ran") or []
        if len({r["priority"] for r in ran}) > 1:
            low = min(ran, key=lambda r: r["priority"])["thread"]
            high = max(ran, key=lambda r: r["priority"])["thread"]
            return f"{c['thread']} waited on a mutex while {high} preempted {low}"
        return f"{c['thread']} waited on a mutex"
    if t == "cpu_starvation":
        return f"{c['thread']} (priority {c['priority']}) took the CPU"
    return str(t)


def _mutex_inversion(report: dict) -> bool:
    return any(c.get("type") == "mutex_wait" and len({r["priority"] for r in c.get("ran") or []}) > 1
               for m in report["misses"] for c in m["causes"])


def _summary_html(report: dict) -> str:
    misses = report["misses"]
    if not misses:
        return ('<h1>No deadline misses found.</h1>'
                '<p class="lede">Every job in this trace finished before its deadline.</p>')
    names = list(dict.fromkeys(m["thread"] for m in misses))
    deadlines = {t["name"]: t.get("deadline_ms") for t in report["threads"]}
    if len(names) == 1:
        dl = deadlines.get(names[0])
        dl = f"{dl:g} ms " if isinstance(dl, (int, float)) else ""
        times = "once" if len(misses) == 1 else f"{len(misses)} times"
        head = f"{names[0]} missed its {dl}deadline {times}."
    else:
        head = f"{len(misses)} deadline misses across {len(names)} threads."
    late = [m["late_ns"] for m in misses if m["late_ns"] is not None]
    stats = []
    if late:
        stats.append(f"Worst {_ms(max(late))} late, average {_ms(sum(late) // len(late))} late.")
    if len(late) < len(misses):
        stats.append(f"{len(misses) - len(late)} still unfinished when the trace ended.")
    counts: dict = {}
    for m in misses:
        for label in dict.fromkeys(_cause_label(c) for c in m["causes"]):
            counts[label] = counts.get(label, 0) + 1
    rows = "".join(
        f'<li><span class="frac">{k}/{len(misses)}</span> {escape(label)}</li>'
        for label, k in sorted(counts.items(), key=lambda kv: -kv[1]))
    out = [f"<h1>{escape(head)}</h1>", f'<p class="lede">{escape(" ".join(stats))}</p>']
    if rows:
        out.append(f'<ul class="causes" aria-label="Causes, by how many misses they explain">{rows}</ul>')
    if _mutex_inversion(report):
        out.append('<p class="fix"><strong>Suggested fix:</strong> create the mutex with priority '
                   'inheritance, <code>pthread_mutexattr_setprotocol(&amp;attr, '
                   'PTHREAD_PRIO_INHERIT)</code>, so the holder runs at the waiter\'s priority.</p>')
    return "".join(out)


def _list_html(report: dict) -> str:
    misses = report["misses"]
    if not misses:
        return ""
    worst = max([m["late_ns"] for m in misses if m["late_ns"] is not None] or [1]) or 1
    many = len({m["thread"] for m in misses}) > 1
    rows = []
    for i, m in enumerate(misses):
        late = m["late_ns"]
        pct = 100 if late is None else max(2, round(100 * late / worst))
        late_txt = "unfinished" if late is None else f"+{_ms(late)}"
        rows.append(
            f'<li><button type="button" class="row" data-i="{i}">'
            f'<span class="n">{i + 1}</span>'
            f'<span class="t">{escape(m["thread"]) + " at " if many else "released "}{_ms(m["release_ns"])}</span>'
            f'<span class="late">{late_txt}</span>'
            f'<span class="bar" style="width:{pct}%"></span></button></li>')
    return f'<ol class="list">{"".join(rows)}</ol>'


def _details_html(report: dict) -> str:
    parts = []
    for i, m in enumerate(report["misses"]):
        lines = m["explanation"]
        items = "".join(f"<li>{escape(x.strip().lstrip('- '))}</li>" for x in lines[1:])
        parts.append(f'<article class="miss" id="miss-{i + 1}" data-i="{i}">'
                     f'<h3>{escape(lines[0])}</h3><ul>{items}</ul></article>')
    return "".join(parts)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QNX Black Box report</title>
<style>
:root {
  --paper:#eef1f4; --panel:#f8f9fb; --ink:#17202b; --muted:#56616e; --rule:#cbd2da;
  --victim:#2c5da8; --culprit:#b4232a; --holder:#6e8b3d; --waiter:#7a5ba6; --other:#8b95a1;
  --late:#e0a100; --focus:#2c5da8;
  --cond: Bahnschrift, "DIN Alternate", "DIN 2014", "Barlow Semi Condensed", "Roboto Condensed", "Arial Narrow", sans-serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper:#11161d; --panel:#18202a; --ink:#e3e8ee; --muted:#9aa5b1; --rule:#2c3644;
    --victim:#6f9be0; --culprit:#ef5b5b; --holder:#a3c06e; --waiter:#b39ae0; --other:#7d8895;
    --late:#f2c14e; --focus:#8fb4ff; color-scheme: dark;
  }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--paper); color:var(--ink);
       font:16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width:1180px; margin:0 auto; padding:32px 16px 64px; }
h1, h2, h3, .n, .late, .frac, .num { font-family:var(--cond); font-variant-numeric:tabular-nums; }
h1 { font-size:clamp(1.9rem, 4.5vw, 3.1rem); line-height:1.05; font-weight:600;
     letter-spacing:-0.01em; margin:0 0 .4rem; max-width:22ch; }
h2 { font-size:1.25rem; font-weight:600; margin:2.4rem 0 .6rem; }
h3 { font-size:1.1rem; font-weight:500; line-height:1.3; margin:0 0 .5rem; }
.brand { color:var(--muted); margin:0 0 1.2rem; font-size:.95rem; }
.lede { color:var(--muted); margin:0 0 1rem; font-size:1.05rem; }
.causes { list-style:none; padding:0; margin:0 0 1rem; max-width:70ch; }
.causes li { padding:.2rem 0; }
.frac { display:inline-block; min-width:3.2em; font-size:1.05rem; font-weight:600; color:var(--culprit); }
.fix { max-width:70ch; border-left:3px solid var(--holder); padding:.1rem 0 .1rem .8rem; }
code { font-size:.9em; overflow-wrap:anywhere; }
#overview { display:block; width:100%; height:auto; }
.ov-mark { cursor:pointer; }
.grid { display:grid; grid-template-columns:minmax(220px, 300px) 1fr; gap:24px; align-items:start; }
@media (max-width:760px) { .grid { grid-template-columns:1fr; } }
.list { list-style:none; margin:0; padding:0; max-height:560px; overflow:auto;
        border-top:1px solid var(--rule); }
.row { position:relative; display:grid; grid-template-columns:2.2em 1fr auto; gap:6px;
       width:100%; padding:8px 8px 12px; color:inherit; font:inherit; text-align:left; cursor:pointer;
       background:none; border:0; border-bottom:1px solid var(--rule); }
.row:hover { background:var(--panel); }
.row[aria-current="true"] { background:var(--panel); box-shadow:inset 3px 0 0 var(--victim); }
.row:focus-visible, .ov-mark:focus-visible { outline:2px solid var(--focus); outline-offset:-2px; }
.n { color:var(--muted); }
.t { font-size:.9rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.late { font-weight:600; }
.bar { position:absolute; left:8px; bottom:5px; height:3px; background:var(--late); max-width:calc(100% - 16px); }
.detail { background:var(--panel); border:1px solid var(--rule); padding:18px 18px 8px; min-width:0; }
.scroll { overflow-x:auto; margin:4px 0 14px; }
#timeline { display:block; width:100%; min-width:640px; height:auto; }
.miss ul { padding-left:1.1rem; margin:0 0 .8rem; max-width:78ch; }
.miss li { margin:.35rem 0; }
.js .miss { display:none; } .js .miss.on { display:block; }
.js .miss h3 { display:none; }
.noscript-only { color:var(--muted); }
svg text { fill:var(--ink); font-family:var(--cond); font-size:16px; }
svg .sub { fill:var(--muted); font-size:13.5px; }
svg .grid-line { stroke:var(--rule); }
svg .victim { fill:var(--victim); } svg .culprit { fill:var(--culprit); }
svg .holder { fill:var(--holder); } svg .waiter { fill:var(--waiter); } svg .other { fill:var(--other); }
svg .on-bar { fill:var(--panel); font-size:14px; font-weight:600; pointer-events:none; }
svg .wait { fill:none; stroke:var(--ink); stroke-dasharray:3 3; opacity:.55; }
svg .overrun { fill:var(--late); opacity:.16; }
svg .deadline { stroke:var(--ink); stroke-width:1.5; }
svg .late-mark { fill:var(--late); } svg .sel { fill:var(--victim); }
svg .ov-base { stroke:var(--rule); }
.pager { display:flex; align-items:center; gap:12px; margin:0 0 12px; }
.pager button { font:inherit; font-size:.9rem; color:var(--ink); background:var(--paper); cursor:pointer;
                border:1px solid var(--rule); padding:4px 12px; }
.pager button:disabled { opacity:.4; cursor:default; }
.pager button:focus-visible { outline:2px solid var(--focus); outline-offset:1px; }
#pos { color:var(--muted); }
.legend { display:flex; flex-wrap:wrap; gap:4px 18px; font-size:.85rem; color:var(--muted); margin:0; }
.legend i { display:inline-block; width:12px; height:8px; margin-right:6px; vertical-align:middle; }
</style>
</head>
<body>
<main>
<p class="brand">QNX Black Box report</p>
__SUMMARY__
<h2>Misses across the trace</h2>
<svg id="overview" viewBox="0 0 1000 70" role="img" aria-label="Each mark is one missed deadline; taller marks were later"></svg>
<h2>Each miss up close</h2>
<div class="grid">
<nav aria-label="Missed deadlines">__LIST__</nav>
<section class="detail" aria-live="polite">
<div class="pager" hidden><button type="button" id="prev">Previous miss</button><span id="pos" class="num"></span><button type="button" id="next">Next miss</button></div>
<h3 id="detail-title"></h3>
<div class="scroll"><svg id="timeline" viewBox="0 0 1000 200" role="img" aria-label="Close-up timeline of the selected miss"></svg></div>
<p class="legend" id="legend"></p>
<div id="misses">__MISSES__</div>
</section>
</div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  var NS = "http://www.w3.org/2000/svg";
  var d = JSON.parse(document.getElementById("data").textContent);
  document.documentElement.className = "js";
  var END = Math.max(d.trace_end_ns, 1);

  // Run intervals per thread name; a run ends at the next RUN on the same CPU.
  var runs = {}, open = {};
  d.timeline.forEach(function (e) {
    if (e.event !== "RUN") return;
    var c = e.cpu || 0;
    if (open[c]) open[c].end = e.ts_ns;
    var iv = { start: e.ts_ns, end: d.trace_end_ns, cpu: c, prio: e.prio };
    open[c] = iv;
    (runs[e.name] = runs[e.name] || []).push(iv);
  });

  function el(svg, tag, attrs, title) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (title) { var t = document.createElementNS(NS, "title"); t.textContent = title; n.appendChild(t); }
    svg.appendChild(n); return n;
  }
  function text(svg, s, x, y, attrs) {
    var n = el(svg, "text", attrs || {}); n.setAttribute("x", x); n.setAttribute("y", y);
    n.textContent = s; return n;
  }
  function ms(ns) { return (ns / 1e6).toFixed(3) + " ms"; }
  function clear(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }

  // Who plays which part in one miss, in the order the story is told.
  function cast(m) {
    var roles = [], seen = {};
    function add(name, role, word) {
      if (!name || seen[name]) return; seen[name] = 1; roles.push({ name: name, role: role, word: word });
    }
    add(m.thread, "victim", "missed its deadline");
    m.causes.forEach(function (c) {
      if (c.type === "slow_reply") add(c.from, "waiter", "slow to reply");
      if (c.type === "mutex_wait") {
        add(c.thread, "waiter", "waiting on a mutex");
        var ran = c.ran.slice().sort(function (a, b) { return b.priority - a.priority; });
        var inv = ran.length > 1 && ran[0].priority !== ran[ran.length - 1].priority;
        ran.forEach(function (r, i) {
          if (inv && i === 0) add(r.thread, "culprit", "preempted the holder");
          else if (inv && i === ran.length - 1) add(r.thread, "holder", "likely holds the mutex");
          else add(r.thread, "other", "ran meanwhile");
        });
      }
      if (c.type === "priority_inversion") {
        add(c.blocked_on, "holder", "held up " + c.blocked);
        add(c.medium, "culprit", "ran instead");
      }
      if (c.type === "cpu_starvation") add(c.thread, "culprit", "took the CPU");
    });
    return roles;
  }
  function waits(m) {
    var w = [];
    m.causes.forEach(function (c) {
      if (c.type === "slow_reply") w.push({ name: m.thread, start: c.send_ns, end: c.send_ns + c.duration_ns, what: "waiting for reply" });
      if (c.type === "mutex_wait") w.push({ name: c.thread, start: c.start_ns, end: c.end_ns, what: "waiting on mutex" });
    });
    return w;
  }
  function step(span) {
    var ticks = [1e5, 2e5, 5e5, 1e6, 2e6, 5e6, 1e7, 2e7, 5e7, 1e8, 2e8, 5e8, 1e9, 2e9, 5e9, 1e10];
    for (var i = 0; i < ticks.length; i++) if (span / ticks[i] <= 7) return ticks[i];
    return ticks[ticks.length - 1];
  }

  function drawDetail(m) {
    var svg = document.getElementById("timeline"); clear(svg);
    var stop = m.done_ns === null ? d.trace_end_ns : m.done_ns;
    var lo = m.release_ns, hi = Math.max(stop, m.deadline_ns), pad = (hi - lo) * 0.05 || 1e5;
    var a = lo - pad, b = hi + pad, X0 = 200, W = 785, ROW = 52, TOP = 34;
    function x(t) { return X0 + (Math.min(Math.max(t, a), b) - a) / (b - a) * W; }
    var roles = cast(m), H = TOP + roles.length * ROW + 30;
    svg.setAttribute("viewBox", "0 0 1000 " + H);
    var s = step(b - a);
    for (var t = Math.ceil((a - lo) / s) * s; lo + t <= b; t += s) {
      el(svg, "line", { x1: x(lo + t), x2: x(lo + t), y1: TOP - 6, y2: H - 22, class: "grid-line" });
      text(svg, (t >= 0 ? "+" : "") + (t / 1e6) + " ms", x(lo + t), H - 6, { "text-anchor": "middle", class: "sub" });
    }
    if (m.done_ns === null || m.done_ns > m.deadline_ns)
      el(svg, "rect", { x: x(m.deadline_ns), y: TOP - 6, width: Math.max(x(stop) - x(m.deadline_ns), 1),
                        height: roles.length * ROW + 6, class: "overrun" },
         (m.late_ns === null ? "unfinished" : ms(m.late_ns) + " late"));
    var ws = waits(m);
    roles.forEach(function (r, i) {
      var y = TOP + i * ROW;
      text(svg, r.name, X0 - 12, y + 20, { "text-anchor": "end" });
      text(svg, r.word, X0 - 12, y + 37, { "text-anchor": "end", class: "sub" });
      (runs[r.name] || []).forEach(function (iv) {
        if (iv.end < a || iv.start > b) return;
        el(svg, "rect", { x: x(iv.start), y: y + 10, width: Math.max(x(iv.end) - x(iv.start), 1.5), height: 26,
                          class: r.role }, r.name + " ran on CPU " + iv.cpu + " at priority " + iv.prio +
                          ", " + ms(iv.start - lo) + " to " + ms(iv.end - lo) + " after release");
        var x1 = x(iv.start), x2 = x(iv.end);
        if (x2 - x1 >= 64) text(svg, ((Math.min(iv.end, b) - Math.max(iv.start, a)) / 1e6).toFixed(1) + " ms",
                                (x1 + x2) / 2, y + 28, { "text-anchor": "middle", class: "on-bar" });
      });
      ws.forEach(function (w) {
        if (w.name !== r.name) return;
        el(svg, "rect", { x: x(w.start), y: y + 6, width: Math.max(x(w.end) - x(w.start), 1), height: 34,
                          class: "wait" }, r.name + " " + w.what + " for " + ms(w.end - w.start));
      });
    });
    el(svg, "line", { x1: x(m.release_ns), x2: x(m.release_ns), y1: TOP - 12, y2: H - 22, class: "deadline", "stroke-dasharray": "2 3" });
    text(svg, "released", x(m.release_ns) + 4, TOP - 14, { class: "sub" });
    el(svg, "line", { x1: x(m.deadline_ns), x2: x(m.deadline_ns), y1: TOP - 12, y2: H - 22, class: "deadline" });
    text(svg, "deadline", x(m.deadline_ns) - 4, TOP - 14, { "text-anchor": "end" });
    if (m.late_ns !== null && m.late_ns > 0)
      text(svg, "+" + ms(m.late_ns) + " late", x(m.deadline_ns) + 4, TOP - 14, {});

    var lg = document.getElementById("legend"); lg.textContent = "";
    [["victim", "missed the deadline"], ["waiter", "waiting"], ["culprit", "ran ahead of it"],
     ["holder", "likely lock holder"]].forEach(function (p) {
      if (!roles.some(function (r) { return r.role === p[0]; })) return;
      var sp = document.createElement("span"), sw = document.createElement("i");
      sw.style.background = "var(--" + p[0] + ")"; sp.appendChild(sw);
      sp.appendChild(document.createTextNode(p[1])); lg.appendChild(sp);
    });
    var sp = document.createElement("span"), sw = document.createElement("i");
    sw.style.border = "1px dashed var(--ink)"; sp.appendChild(sw);
    sp.appendChild(document.createTextNode("blocked")); lg.appendChild(sp);
  }

  function drawOverview(sel) {
    var svg = document.getElementById("overview"); clear(svg);
    var X0 = 10, W = 980, BASE = 50;
    function x(t) { return X0 + t / END * W; }
    el(svg, "line", { x1: X0, x2: X0 + W, y1: BASE, y2: BASE, class: "ov-base" });
    var worst = 1;
    d.misses.forEach(function (m) { if (m.late_ns !== null) worst = Math.max(worst, m.late_ns); });
    d.misses.forEach(function (m, i) {
      var h = m.late_ns === null ? 40 : 8 + 32 * m.late_ns / worst;
      var g = el(svg, "g", { class: "ov-mark", tabindex: "0", role: "button",
                             "aria-label": "Miss " + (i + 1) + ", " + (m.late_ns === null ? "unfinished" : ms(m.late_ns) + " late") });
      var n = document.createElementNS(NS, "rect");
      n.setAttribute("x", x(m.release_ns) - 3); n.setAttribute("y", BASE - h);
      n.setAttribute("width", 6); n.setAttribute("height", h);
      n.setAttribute("class", i === sel ? "sel" : "late-mark"); g.appendChild(n);
      g.addEventListener("click", function () { select(i); });
      g.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(i); } });
    });
    text(svg, "0 s", X0, 66, { class: "sub" });
    text(svg, (END / 1e9).toFixed(2) + " s", X0 + W, 66, { "text-anchor": "end", class: "sub" });
  }

  function select(i) {
    if (!d.misses.length) return;
    i = Math.max(0, Math.min(i, d.misses.length - 1));
    var m = d.misses[i];
    document.getElementById("detail-title").textContent = m.explanation[0];
    document.querySelectorAll(".miss").forEach(function (a) { a.classList.toggle("on", +a.dataset.i === i); });
    document.querySelectorAll(".row").forEach(function (r) { r.setAttribute("aria-current", +r.dataset.i === i ? "true" : "false"); });
    cur = i;
    document.getElementById("pos").textContent = (i + 1) + " of " + d.misses.length;
    document.getElementById("prev").disabled = i === 0;
    document.getElementById("next").disabled = i === d.misses.length - 1;
    drawDetail(m); drawOverview(i);
    if (location.hash !== "#miss-" + (i + 1)) history.replaceState(null, "", "#miss-" + (i + 1));
  }
  document.querySelectorAll(".row").forEach(function (r) {
    r.addEventListener("click", function (ev) { ev.preventDefault(); select(+r.dataset.i); });
  });
  var cur = 0;
  document.querySelector(".pager").hidden = d.misses.length < 2;
  document.getElementById("prev").addEventListener("click", function () { select(cur - 1); });
  document.getElementById("next").addEventListener("click", function () { select(cur + 1); });
  document.addEventListener("keydown", function (ev) {
    if (ev.altKey || ev.ctrlKey || ev.metaKey || /INPUT|TEXTAREA/.test(ev.target.tagName)) return;
    if (ev.key === "ArrowRight" || ev.key === "j") { select(cur + 1); ev.preventDefault(); }
    if (ev.key === "ArrowLeft" || ev.key === "k") { select(cur - 1); ev.preventDefault(); }
  });
  var hm = /^#miss-(\\d+)$/.exec(location.hash);
  if (d.misses.length) select(hm ? +hm[1] - 1 : 0);
  else { document.querySelector(".grid").hidden = true; drawOverview(-1); }
})();
</script>
</body>
</html>
"""


def render_html(report: dict) -> str:
    check_report(report)
    # One pass, so placeholder-like text inside the substituted values is left alone.
    values = {"__SUMMARY__": _summary_html(report), "__LIST__": _list_html(report),
              "__MISSES__": _details_html(report), "__DATA__": _embed(report)}
    return re.sub(r"__SUMMARY__|__LIST__|__MISSES__|__DATA__", lambda m: values[m.group(0)], TEMPLATE)
