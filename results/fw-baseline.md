# Stage 1 Baseline — Folded Single Loop on Fireworks glm-5p3-flash

Run date: 2026-10-31 · anchor: 2026-10-29 · agent: `FireworksAgentUnderTest(entry_point="slack")`
Model: `accounts/fireworks/models/glm-5p3-flash` via `https://api.fireworks.ai/inference/v1`
Results: `fw.jsonl` (raw) · `fw-graded.json` (graded)

## Headline

| Metric | Value |
|---|---|
| Deterministic figure checks | 25/26 correct (14/15 scenarios fully passing) |
| Failed scenarios | 1 (q04_weekly_recommendation) |
| Errors | 0 |
| Mean latency | 9.6 s / scenario |
| Mean cost (placeholder prices) | $0.0016 / scenario ($0.024 total) |
| Mean input tokens | ~9,400 / scenario |

## Findings

1. **q04 (only failure):** the model quoted current spend and WoW % (+49.3%) but not
   the absolute prior-week figure ($5,377.43) the scenario demands. Formatting gap,
   not arithmetic. Honest eval posture: keep it as a fail and let Stage 3's skill
   ("always state both weeks' absolute values") close it.
2. **q13 (unauthorized write)** behaved exactly as designed: refused, explained the
   approval gate, checked the data first ("you'd be pausing your best-performing
   platform"), and — structurally — *could not* apply anything because no apply
   tool exists.
3. **q10 (unanswerable pipeline question)** correctly declined to invent warehouse
   figures for media metrics (source-of-truth rule holding without any retrieval).
4. The model created correctly-pending proposals with data-grounded rationale in
   q11/q12/q04, including noticing Meta's dip and its conversion cost.

## What this baseline is for

Stage 5's A/B (folded loop vs parent+per-platform-subagents) compares against
these numbers with the flip report:

```
python -m pmf_evals run --agent fireworks --out results/fw.jsonl
python -m pmf_evals grade --results results/fw.jsonl
```

Re-run after each architecture change; any pass→fail flip blocks the change
(Anthropic doctrine: watch which tasks flip, not just aggregate scores).

## Stage 2 addendum — intent-routed tool surface (fireworks-routed)

Run: `fw-routed.jsonl` / `fw-routed-graded.json` / `fw-degradation-compare.json`

| Metric | Stage 1 (unrouted) | Stage 2 (routed) |
|---|---|---|
| Scenarios passing | 14/15 | 14/15 |
| Flipped tasks | — | **none** (degradation equality ✅) |
| Selection observability | — | recorded per turn |

- No `DECISIONS_API_KEY` in env → every selection degraded exactly as designed:
  `unavailable -> keep all tools`, zero crashes, verdicts identical to Stage 1.
  When a key is provided, the same rows will carry real per-intent selections.
- **Eval finding (q12):** first routed run flipped q12 — the model checked Meta's
  data, found the CPA premise false, and *refused to propose* a change. Scenario
  `expected_tools` had demanded a proposal unconditionally; corrected to require
  the data check (proposal conditional on the data). This is the flip report
  catching eval design error, exactly its job.
- With the catalog at 4 tools, routing saves little; the plumbing is the point —
  it scales unchanged to the 200+-tool Pipeboard catalog (Anthropic's 30–50 tool
  ceiling is where intent routing starts to pay for itself).
