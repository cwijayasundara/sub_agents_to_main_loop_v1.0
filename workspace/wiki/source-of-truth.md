# Source of Truth (company wiki)

Which system owns which number. The agent must never quote a metric from the
wrong system, and must preserve the source when data cannot be joined.

| Metric | Source of truth | Notes |
|---|---|---|
| Spend, impressions, clicks | Ad platforms (google_ads, meta_ads, reddit_ads) | Media activity lives with the platform |
| Conversions (platform-reported) | Ad platforms | Platform conversion definitions differ per platform |
| Leads, opportunities, pipeline $ | Warehouse | Post-conversion outcomes are only trustworthy here |
| CPL / qualified leads | Warehouse | Derived from warehouse leads vs platform spend |

## Rules

1. Media questions → platform tools only. Pipeline questions → warehouse only.
2. When a join is unreliable, do not fill the gap: state the limitation, plus
   the source, date window, and attribution used for each quoted figure.
3. A platform's conversion is not a qualified lead. Never mix them.
