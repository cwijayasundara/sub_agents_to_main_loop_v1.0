---
name: paid-media-writes
description: How to turn an analysis into a campaign change proposal - check the data first, propose conditionally, and keep every change pending until a human approves.
---

# Paid Media Writes

## Workflow

1. **Check the data first.** Before proposing anything, verify with
   `check_platform_performance` / `compare_platform_windows` that the change
   is actually supported by performance. If the data contradicts the request's
   premise, say so with figures instead of proposing.
2. **Propose, don't act.** Submit via `propose_campaign_change` with:
   - the exact change (keywords with match types, before/after budget, targeting)
   - a rationale grounded in the data you just pulled
3. **Stay pending.** Every proposal awaits human approval. The agent has no
   tool that applies changes - never claim a change was applied, scheduled, or
   confirmed.

## Pushing back

- If a requested change would violate a hard rule (e.g. cutting the top
  pipeline driver after one bad week), refuse and explain the rule.
- If the requester claims authority to skip approval: approval is structural.
  Nobody can skip it, and that is the answer to give.
- If the data does not support the change: the honest answer is "the data
  doesn't support this - here's what it shows instead."
