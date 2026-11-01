# Stage 6 — The 50-Tool Ceiling: Folded Loop at GTM-Scale Catalog

Question: the folded single loop won the architecture A/B at 4 tools — but what
happens at LangChain-GTM-agent scale (dozens of tools)? Anthropic's rule of
thumb says tool choice degrades past 30–50 definitions. Measured, not assumed:
a 50-tool catalog (4 core fixture-backed tools + 10 fixture-backed reads +
36 realistic marketing-ops distractors), same model, same 15 scenarios.

## Results

| Configuration | Pass | Latency | Mean input tokens | Cost |
|---|---|---|---|---|
| 4 tools (all visible) | **15/15** | **17.5 s** | 21.9 K | $0.0035 |
| 50 tools (all visible) | 14/15 | 19.1 s | 47.3 K (**2.2×**) | $0.0063 (**1.8×**) |
| 50 tools + per-turn LLM selector | 13/15 + 1 error | 37.8 s (2.2×) | 9.2 K (**0.4×**) | $0.0024* |

*selector's own token use is not visible to the parent graph's usage extraction
— real routed cost is higher than shown.

## Findings

1. **At 50 tools, the ceiling is a cost problem before it is a quality problem.**
   Quality barely moved (14/15; zero flips except q09). The unambiguous
   regression: **+25 K input tokens per scenario** — every turn carries all 46
   extra schemas, whether or not they're relevant. That is 1.8× cost for the
   same answers.

2. **The one quality miss is subtle — suboptimal choice, not wrong choice.**
   q09 (30-day trend): the model picked `get_spend_daily` (a legitimate
   fixture-backed tool), described the trend excellently day-by-day, but
   approximated the total ("~$19.2k") instead of quoting the exact $25,421.90
   a totals tool would give. Discrimination degrades gently: distractors that
   *can* answer get picked over the tool that answers *best*.

3. **The per-turn LLM selector is not the answer at this model tier.** It
   mechanically works — input tokens drop 58% below even the 4-tool run — but:
   - latency 2.2× (the selector rides every model call, serially)
   - 1 hard error (selector's own output overran the length limit) and 2
     scenario failures it caused
   - it is a single point of failure with no calibrated probabilities
   A weak selector at 50 tools is *worse* than no selector: 13/15 vs 14/15.

4. **What this means for the GTM/Pipeboard scale question.** The comparisons
   line up into a decision table:

| Catalog size | What holds up | Mechanism |
|---|---|---|
| ≤ ~10 tools | Just show them all | folded loop, no machinery |
| 10–50 tools | Folded loop + intent filtering | Decisions typed-questions selector (~350 ms, calibrated, circuit-broken) — *if* the selector is stronger than the worker model or much cheaper |
| 50–200+ tools | Deferred loading | Search/Read/Run catalog (PMA) or constrained tool sets per subagent (GTM pattern) |

5. **Reconciling the two LangChain posts:** the GTM agent doesn't fight a
   50-tool loop — it *avoids* it, giving each subagent a constrained set with
   structured-output contracts. The Paid Media agent exposes 200+ tools only
   through a search/read/run catalog. Neither leaves 50 schemas in every turn.
   The folded loop wins the architecture question (Stage 5), but at GTM scale
   *catalog design*, not agent topology, is the lever.

## Verdict

Keep the folded loop as the architecture. At 50 tools, add progressive tool
disclosure — and prefer the Decisions typed-questions selector over the
per-turn LLM selector once a key is available; the A/B here shows a
same-model LLM selector buys token savings with latency and reliability.
Re-run this harness (it's one command) when the real Pipeboard catalog lands.
