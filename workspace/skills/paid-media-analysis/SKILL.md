---
name: paid-media-analysis
description: How to investigate paid media performance across platforms - which tools to call, how to compare windows, and how to state figures so they can be verified.
---

# Paid Media Analysis

## Workflow

1. Call `list_platforms` first if you are unsure what platforms, metrics, or
   windows exist.
2. For a single platform question, call `check_platform_performance`.
3. For any "did it get better or worse" question, call
   `compare_platform_windows` - never compute week-over-week changes in your
   head from two separate checks.
4. For cross-platform questions, check every platform, then compare shares.

## How to state figures

- Quote the **absolute values for both windows**, not just the recent value
  with a percentage. "Spend moved from $5,377.43 to $8,029.35 (+49.3%)" is
  correct; "spend is up 49%" alone is not.
- Name the metric, platform, window dates, and source with every figure.
- Never mix metrics across sources: media metrics (spend, impressions, clicks,
  conversions) come from the ad platforms. Pipeline outcomes come from the
  warehouse (see the wiki's source-of-truth page).
- If the data window is incomplete, say so explicitly and give the last
  complete date.

## Judgment

- Small conversion volumes make percentage changes noisy - flag wide
  uncertainty instead of over-reading a move.
- Do not recommend cutting the top spend driver off one bad week.
- A performance change without a plausible driver is a question to
  investigate, not a fact to report.
