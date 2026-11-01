# Stage 5 — Architecture A/B: Folded Loop vs Parent + Per-Platform Subagents

Same model (`glm-5p3-flash`), same 15 golden scenarios, same anchor (2026-10-30),
same skills, same fixture ground truth. Only the harness differs.

| | Folded single loop | Parent + per-platform subagents |
|---|---|---|
| Scenarios passing | **15/15** | 12/15 |
| Mean latency | **17.5 s** | 31.7 s (1.8×) |
| Mean cost (placeholder) | **$0.0035** | $0.0041 (1.2×) |
| Mean input tokens | ~19K | ~35K (1.8×, from repo data) |

## Flips (folded → hierarchical)

| Scenario | What happened |
|---|---|
| q01_weekly_spend_wow | Parent read the skills, but the skills instruct calling platform tools the parent doesn't hold (they live in subagents). It concluded the tools "aren't callable" and didn't re-derive figures. **Skill/ability mismatch.** |
| q08_slack_reddit_conversions | Parent delegated, then produced an **empty final message** — delegation without synthesis. |
| q15_cross_platform_shift | Same class as q01: cross-platform figures never reached the final text. |

Zero flips in the other direction: the folded loop matched or beat the
hierarchy everywhere.

## Verdict (per the Anthropic doctrine's own test)

Keep the folded single loop for **both** entry points at this scale. The
hierarchical architecture paid the exact taxes the article describes —
"each call still hands back a lossy summary", nested loops add latency,
and every boundary needs engineered coordination — while the folded loop
held all raw tool outputs in one context.

The subagent exceptions (parallel fresh-context work, context-bloat escape
hatch) remain valid for a catalog much larger than three fixture platforms;
the harness (`compare`) is ready to re-adjudicate when that day comes.
`expected_tools` routing metric is now architecture-aware (delegation counts
as routing in the hierarchy), which was itself a lesson: **a routing metric
written for one architecture silently mis-grades another.**

## Failure-mode notes (for whichever architecture runs next)

1. Skills must match the architecture's tool surface, or the prompt promises
   abilities the agent doesn't have (q01).
2. Delegation without a synthesis contract can end in an empty answer (q08);
   the PMA fixed the same class of bug with per-platform completion state —
   a subagent-response schema would do the same here.
3. Cost/latency of the hierarchy (~2×) came from duplicated context: each
   subagent re-read skills + platform data the folded loop reads once.
