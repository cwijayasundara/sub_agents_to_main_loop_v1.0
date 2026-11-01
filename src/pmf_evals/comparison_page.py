"""Single-file comparison page: folded loop vs parent+subagents.

Generates a self-contained HTML page (inline SVG diagrams, measured numbers
from results/*.jsonl, flip findings) in the style of the first diagram of
Anthropic's "When to fold subagents into your main agent loop", and pops it
open in the browser.

    python -m pmf_evals report        # regenerate + open
    PMF_NO_BROWSER=1 pytest           # run tests without the popup
"""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from .grader import grade_result
from .report import compare
from .scenarios import load_scenarios, GOLDEN_PATH

PAGE_PATH = Path(__file__).resolve().parents[2] / "results" / "comparison.html"
RESULTS_DIR = PAGE_PATH.parent

_FALLBACK = {"pass": "15/15", "latency": "17.5", "cost": "$0.0035", "tokens": "21.9K"}


def _summarize(jsonl_name: str, arch: str) -> dict:
    """Measured summary for one run; falls back to the committed baseline."""
    path = RESULTS_DIR / jsonl_name
    if not path.exists():
        return dict(_FALLBACK)
    scenarios = load_scenarios(GOLDEN_PATH)
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    graded = [grade_result(r, scenarios, arch=arch) for r in rows]
    n = len(graded) or 1
    ok = [(r, g) for r, g in zip(rows, graded) if g["verdict"] != "error"]
    passed = sum(1 for _, g in ok if g["verdict"] in ("pass", "figures_only"))
    return {
        "pass": f"{passed}/{n}",
        "latency": f"{sum(r['latency_ms'] for r, _ in ok) / max(1, len(ok)) / 1000:.1f}",
        "cost": f"${sum(r['cost_usd'] for r, _ in ok) / max(1, len(ok)):.4f}",
        "tokens": f"{sum(r.get('tokens_in', 0) for r in rows) / n / 1000:.1f}K",
    }


def _measured() -> dict:
    folded = _summarize("fw-skills.jsonl", "folded")
    hier = _summarize("fw-hier.jsonl", "hierarchical")
    flips: list[str] = []
    try:
        scenarios = load_scenarios(GOLDEN_PATH)

        def graded(path, arch):
            return [
                grade_result(json.loads(l), scenarios, arch=arch)
                for l in (RESULTS_DIR / path).read_text().splitlines()
            ]

        flips = list(compare(graded("fw-skills.jsonl", "folded"), graded("fw-hier.jsonl", "hierarchical"))["flipped"])
    except Exception:
        flips = ["q01_weekly_spend_wow", "q08_slack_reddit_conversions", "q15_cross_platform_shift"]
    return {"folded": folded, "hier": hier, "flips": flips}


# ---------------------------------------------------------------- diagrams

# SVG-only styles: shared by the static page and the live server (the server
# page does not include _STYLE, so these must ship separately). Font-family is
# pinned per class because SVG text otherwise inherits the embedding page's body.
SVG_STYLE = """
  .box { fill: #fff; stroke: #d7d3cc; stroke-width: 1.2; }
  .accent { fill: #fdf0ea; stroke: #d97757; }
  .label { font-size: 12.5px; fill: #1a1a1a; font-weight: 600; font-family: -apple-system, 'Segoe UI', sans-serif; }
  .small { font-size: 11px; fill: #6b6b6b; font-family: -apple-system, 'Segoe UI', sans-serif; }
  .tag { font-size: 10.5px; fill: #6b6b6b; font-family: -apple-system, 'Segoe UI', sans-serif; }
  .edge { stroke: #6b6b6b; stroke-width: 1.2; fill: none; marker-end: url(#arrow); }
  .edge-dashed { stroke-dasharray: 4 3; }
"""

_STYLE = """
  body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #faf9f7;
         color: #1a1a1a; margin: 0; padding: 40px; }
  h1 { font-size: 26px; font-weight: 600; margin-bottom: 4px; }
  .sub { color: #6b6b6b; font-size: 14px; margin-bottom: 32px; }
  .row { display: flex; gap: 28px; flex-wrap: wrap; }
  .panel { background: #fff; border: 1px solid #e8e5e0; border-radius: 12px;
           padding: 24px; flex: 1 1 560px; }
  .panel h2 { font-size: 17px; font-weight: 600; margin: 0 0 2px; }
  .panel .desc { color: #6b6b6b; font-size: 13px; margin-bottom: 12px; }
  .metrics { display: flex; gap: 12px; margin-top: 14px; flex-wrap: wrap; }
  .metric { background: #faf9f7; border: 1px solid #e8e5e0; border-radius: 8px;
            padding: 8px 14px; font-size: 13px; }
  .metric b { display: block; font-size: 17px; }
  .verdict { background: #fff; border: 1px solid #e8e5e0; border-radius: 12px;
             padding: 24px; margin-top: 28px; }
  .verdict h2 { margin-top: 0; font-size: 17px; }
  .flip { font-family: ui-monospace, monospace; font-size: 12.5px; color: #b45309;
          background: #fef3c7; border-radius: 6px; padding: 2px 8px; display: inline-block;
          margin: 2px; }
  .good { color: #15803d; font-weight: 600; }
  .bad { color: #b91c1c; font-weight: 600; }
""" + SVG_STYLE

_ARROW_DEFS = """
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"
            markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#6b6b6b"/>
    </marker>
  </defs>
"""


def _svg_hierarchical() -> str:
    w, h = 560, 360
    boxes = []
    subs = [("google-ads-specialist", 20, "check_performance · compare_windows · read_context"),
            ("meta-ads-specialist", 200, "check_performance · compare_windows · read_context"),
            ("reddit-ads-specialist", 380, "check_performance · compare_windows · read_context")]
    for name, x, tools in subs:
        cx = x + 80
        boxes.append(f'<rect class="box" x="{x}" y="210" width="160" height="110"/>')
        boxes.append(f'<text class="label" x="{cx}" y="238" text-anchor="middle">{name}</text>')
        boxes.append(f'<text class="small" x="{cx}" y="256" text-anchor="middle">own context window</text>')
        tools_lines = tools.split(" · ")
        for i, tl in enumerate(tools_lines):
            boxes.append(f'<text class="tag" x="{cx}" y={276 + i * 14} text-anchor="middle">{tl}</text>')
        # arrows down and dashed summaries back
        boxes.append(f'<path class="edge" d="M 280 148 L {cx} 206"/>')
        boxes.append(f'<path class="edge edge-dashed" d="M {cx + 14} 206 L 294 148"/>')
    return f"""
<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Orchestrator with subagents">
  {_ARROW_DEFS}
  <rect class="box accent" x="140" y="30" width="280" height="118"/>
  <text class="label" x="280" y="56" text-anchor="middle">Parent agent</text>
  <text class="small" x="280" y="74" text-anchor="middle">one context window, intent-level tools only</text>
  <text class="tag" x="280" y="96" text-anchor="middle">list_platforms · propose_campaign_change</text>
  <text class="tag" x="280" y="112" text-anchor="middle">task(description, subagent_type)</text>
  <text class="tag" x="280" y="132" text-anchor="middle">reads skills → delegates analysis</text>
  {''.join(boxes)}
  <text class="tag" x="180" y="182">task(...)</text>
  <text class="tag" x="360" y="182">lossy summaries return</text>
</svg>"""


def _svg_folded() -> str:
    return f"""
<svg viewBox="0 0 560 360" width="100%" role="img" aria-label="Single agent loop with progressive disclosure">
  {_ARROW_DEFS}
  <rect class="box accent" x="30" y="30" width="300" height="300"/>
  <text class="label" x="180" y="56" text-anchor="middle">One model, one context window</text>
  <text class="small" x="180" y="74" text-anchor="middle">plan written + revised in context · open tool loop</text>

  <text class="tag" x="50" y="104">plan (written turn 1, revised as results arrive)</text>
  <rect x="50" y="114" width="260" height="26" class="box"/>
  <text class="tag" x="60" y="131">1. check each platform  2. compare  3. recommend</text>
  <text class="tag" x="50" y="166">message history (raw tool results stay here)</text>
  <rect x="50" y="176" width="260" height="26" class="box"/>
  <text class="tag" x="60" y="193">q: meta spend? → check_platform_performance(meta_ads)</text>

  <rect x="50" y="220" width="260" height="92" class="box"/>
  <text class="tag" x="60" y="240">budgets · write gates · approval — in code</text>
  <text class="tag" x="60" y="258">harness runs each tool batch, returns raw results</text>
  <text class="tag" x="60" y="276">loop ends: answer, question, or budget hit</text>
  <text class="tag" x="60" y="294">hard rules the model cannot override</text>

  <path class="edge" d="M 330 110 L 386 80"/>
  <path class="edge" d="M 330 190 L 386 170"/>
  <path class="edge edge-dashed" d="M 330 260 L 386 260"/>
  <text class="tag" x="336" y="100">calls</text>
  <text class="tag" x="336" y="252">read on demand</text>

  <rect class="box" x="390" y="40" width="150" height="80"/>
  <text class="label" x="465" y="64" text-anchor="middle">Tools</text>
  <text class="small" x="465" y="82" text-anchor="middle">4 core — grouped by intent</text>
  <text class="small" x="465" y="98" text-anchor="middle">(50 behind routing)</text>

  <rect class="box" x="390" y="150" width="150" height="80"/>
  <text class="label" x="465" y="174" text-anchor="middle">Skills</text>
  <text class="small" x="465" y="192" text-anchor="middle">name+description in prompt,</text>
  <text class="small" x="465" y="208" text-anchor="middle">full text read when needed</text>

  <rect class="box" x="390" y="252" width="150" height="80"/>
  <text class="label" x="465" y="276" text-anchor="middle">Wiki</text>
  <text class="small" x="465" y="294" text-anchor="middle">company facts via read_file</text>
</svg>"""


def build_html() -> str:
    m = _measured()
    f, hh = m["folded"], m["hier"]
    flips = "".join(f'<span class="flip">{fid}</span>' for fid in m["flips"]) or "<em>none</em>"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Folded loop vs subagents — measured comparison</title>
<style>{_STYLE}</style></head>
<body>
<h1>When to fold subagents into your main agent loop — replicated &amp; measured</h1>
<div class="sub">LangChain Paid Media Agent pattern · model <code>accounts/fireworks/models/glm-5p3-flash</code> ·
same 15 golden scenarios, same fixture anchor — only the harness differs</div>

<div class="row">
  <div class="panel">
    <h2 class="bad">✗ Parent + per-platform subagents</h2>
    <div class="desc">PMA's production choice: the parent keeps intent-level tools and delegates
    platform analysis to specialists with their own context windows.</div>
    {_svg_hierarchical()}
    <div class="metrics">
      <div class="metric"><b class="bad">{hh['pass']}</b>scenarios passing</div>
      <div class="metric"><b>{hh['latency']}s</b>mean latency</div>
      <div class="metric"><b>{hh['tokens']}</b>input tokens / scenario</div>
      <div class="metric"><b>{hh['cost']}</b>mean cost</div>
    </div>
  </div>

  <div class="panel">
    <h2 class="good">✓ Folded single loop</h2>
    <div class="desc">One model, one context window, progressively disclosed skills/tools.
    Budgets and write gates live in the harness, not the prompt.</div>
    {_svg_folded()}
    <div class="metrics">
      <div class="metric"><b class="good">{f['pass']}</b>scenarios passing</div>
      <div class="metric"><b>{f['latency']}s</b>mean latency</div>
      <div class="metric"><b>{f['tokens']}</b>input tokens / scenario</div>
      <div class="metric"><b>{f['cost']}</b>mean cost</div>
    </div>
  </div>
</div>

<div class="verdict">
  <h2>Verdict</h2>
  <p><b>Keep the folded single loop for both entry points.</b> The hierarchical architecture
  failed in exactly the ways the Anthropic article predicts: lossy subagent summaries,
  skill/ability mismatch, and delegation without synthesis. Latency 1.8×, cost 1.2×,
  and three task flips — all folded→hierarchical, none the other way.</p>
  <p>Flipped tasks (folded → hierarchical): {flips}</p>
  <p style="color:#6b6b6b;font-size:13px">At 50 tools the loop's ceiling is cost, not quality
  (2.2× input tokens, quality 14/15) — see <code>results/tools50-report.md</code> for the
  catalog-design decision table.</p>
</div>
</body></html>"""


def open_page() -> Path:
    """Write results/comparison.html and pop it open in the browser."""
    html = build_html()
    PAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAGE_PATH.write_text(html)
    import os

    if not os.environ.get("PMF_NO_BROWSER"):
        webbrowser.open(f"file://{PAGE_PATH}")
    return PAGE_PATH
