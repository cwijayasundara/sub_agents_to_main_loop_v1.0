# Proposal: Folding the Paid Media Agent into a Single Agent Loop

*Research synthesis + replication plan. Sources: Anthropic "Building agents: When to fold subagents into your main agent loop" (Diane Sarkis, Oct 2026), LangChain "Paid Media Agent" blog + OSS repo (`langchain-ai/paid-media-agent`), and `cwijayasundara/deep_agents_utils_v1.0` (decision_harness).*

---

## 1. What the Anthropic post actually argues

The core claim: **a single agent loop with progressive disclosure frequently beats orchestrator–subagent designs on quality, cost, and latency** — but subagents are still correct in three cases:

1. Measurable context bloat degrades a single loop.
2. Parallel tasks need fresh, discardable context windows.
3. A single agent struggles with tool selection or has conflicting prompt instructions.

**The target architecture** they describe:

- One model, one context window, an open-ended tool loop with **budgets and write gates enforced in the harness** (not the prompt).
- Each turn the model emits a batch of tool calls; raw results return to the *same* context; the model revises its own written plan mid-loop.
- Domain procedure → **skills** (progressively disclosed: title + description first, full load on demand).
- Actions, live data, hard precondition checks → **tools** (ideally MCP, **grouped by user intent**, never one-tool-per-API; degrade past 30–50 visible definitions → use tool search with deferred loading).
- Reference material → knowledge base behind a lookup tool (never code-pasted into prompts).
- Migration is **eval-driven and incremental**: build a task-completion eval first (10 golden examples is enough), then fold subagents one at a time — merge tightly-coupled specialists, expose the rest as tools, convert prompts to skills — and keep a subagent only if the folded version scores *worse*. Watch **which tasks flip**, not just aggregate scores (their example: folding a shipping specialist into the main loop broke delivery-date questions that only failed in one run out of two).

**Org doctrine**: split by *context*, not by problem type ("telephone game" between split-by-type agents degrades fidelity); a small central team owns the system prompt, tool/skill vetting, and end-to-end evals; domain teams own skills and tools. Conway's law is the failure mode to resist.

---

## 2. What the LangChain Paid Media Agent actually is

From the blog and the OSS repo:

**Architecture (Deep Agents harness + LangSmith Sandbox):**
- A coding-agent-as-knowledge-worker: microVM sandbox (pandas, DuckDB, openpyxl, WeasyPrint) with software + 19-page wiki baked into a snapshot.
- **Five context layers**: (1) thin system prompt that is a *map*, not the knowledge; (2) 6 skills, progressively disclosed; (3) wiki (company-specific facts — "a skill should work at another company, the wiki should not"); (4) live tools fetched at request time (~218 Pipeboard MCP ad-platform calls); (5) deterministic code for calculations, date windows, and **hard safeguards the model cannot override** (e.g., "don't cut a top pipeline driver after one bad week").
- **One graph, two capability profiles**: they started with two graphs (scheduled report agent + fast Slack agent), found every feature had to be built twice, and folded them into **one runtime instantiated fresh per request** — scheduled runs get a `task()` tool delegating to one subagent per platform; Slack gets read/warehouse/write-ops tools. *The PMA already performed one successful fold, for exactly the reasons Anthropic names (duplicated capability, stale feature skew, broken cross-entry-point follow-ups).*
- **Tool discovery instead of tool loading**: 200+ ad-platform tools behind a Search → Read → Run catalog; warehouse exposed as describe-tables + run-query instead of one fixed tool per question. First turn dropped from 38K → ~12K tokens at equal judged quality.
- **Judgment in the model, computation in code**: v1 loaded all rows into context and let the model compute → 3.9M input tokens, 1,112 s, $3/report. Moving math to code → **40× cheaper, 13× faster** (85 s).
- **Source-of-truth per metric** (ad platforms own spend/impressions/clicks; warehouse owns leads/pipeline), encoded in the wiki *and* enforced by removing tools that would query the wrong system.
- **Kept parent + per-platform subagents** after testing three architectures: separate runs per platform (worst — no cross-platform synthesis), one agent (worked), parent+subagents (chosen — small parent context, per-platform isolation). Then they had to *engineer* the isolation: per-platform report paths and completion flags (two subagents shared a "done" flag and silently stopped), and a 3-tool subagent diet (read context, compute, render) after one burned tokens re-verifying its own PDF.
- **Analysis → action path**: Slack Block Kit approval cards, server-side Slack-user-ID permission checks, code applies the approved change and verifies it landed. Humans gate writes; the agent proposes.

---

## 3. Where your decision_harness fits

`deep_agents_utils_v1.0` provides two deepagents middlewares backed by the OpenAI Decisions API (one typed-questions request, calibrated probabilities, circuit breaker, graceful degradation, cost ledger):

- `ToolSelectionMiddleware` — per-request tool filtering: one predicate question per tool, threshold + `max_tools` + `always_include` + `on_none` fallbacks. Validated at ~350 ms over 10 tools. Degrades to "keep all tools" on failure.
- `ModelSelectionMiddleware` — sticky per-thread model tiering.

This matters because the OSS PMA's `src/paid_media_agent/middleware/tool_selection.py` has exactly two selection strategies today:

| PMA strategy | Mechanism | Cost per turn |
|---|---|---|
| `PROVIDER_NATIVE` | Anthropic tool search (bm25/regex) / OpenAI Responses `tool_search` | cheap, but **provider-locked** — the repo's own capability registry marks Google and gateway models `native_tool_search=False` |
| `PORTABLE_SELECTOR` | LangChain `LLMToolSelectorMiddleware` | a **full LLM call** per selection |

Your `ToolSelectionMiddleware` is a **third, cheaper portable strategy**: typed-questions instead of a full LLM call (~350 ms / sub-cent vs. a full model invocation), provider-agnostic, with the same graceful-degradation contract the PMA already requires ("A failed connector does not discard the others" / fallback = all tools). It slots in as `SelectionStrategy.DECISIONS_API` with a three-line change to their strategy dispatch. The PMA's docs also warn: *"Do not create a third custom search/run mini-protocol unless measured framework behavior cannot meet the authorization and context budgets"* — middleware filtering is not a third mini-protocol; it is a drop-in replacement for the second path.

---

## 4. Where the two sources agree — and the one real tension

**Agreement** (the PMA independently arrived at Anthropic's doctrine):
- Thin prompt-as-map + skills + wiki + live tools = Anthropic's "progressive disclosure."
- Hard rules and computation in code = Anthropic's "limits set in the harness," "hard limits move into tools."
- One runtime, capability profiles per entry point = Anthropic's "one model and one context window."
- Tool discovery over tool loading = Anthropic's "tool search with deferred loading," including the intent-grouping/30–50-tool ceiling.
- Eval-driven iteration = PMA's repo literally ships `tests/eval/`, `tests/behavior/`, frozen test sets.

**The tension**: Anthropic's default is *fold the subagents in*; the PMA's lesson 4 *keeps* per-platform subagents. This is not a contradiction — it's Anthropic's exception #2 (parallel fresh-context work) applied honestly. The weekly Monday report runs N platforms in parallel with per-platform isolation that had to be explicitly engineered. A naive "fold everything" replication would regress exactly the way Anthropic warns (watch which tasks flip).

**But** the folding logic cuts the other way for Slack traffic: a Slack question ("why did CPL jump?") rarely needs platform-isolated parallel context — it's a 1–3 tool-call lookup + judgment, and the subagent hop is pure latency there.

---

## 5. The proposal: replicate PMA as a "fold-first" build

Goal: rebuild the Paid Media Agent with Anthropic's migration doctrine applied **from the start**, using your decision_harness middlewares where they win. Target repo: this directory (`sub_agents_to_main_loop_v1.0`).

### Stage 0 — Evals before architecture (Anthropic step 1)
- Central end-to-end task-completion set: ~15 golden scenarios (5 weekly-report, 5 Slack Q&A, 3 write-proposal, 2 cross-platform synthesis), graded against a rubric; track latency, cost, completion.
- Also track **routing accuracy** while any router exists (did it pick the right skill/tool?) — this is the metric that *replaces* subagent-routing accuracy post-fold.
- Use the PMA's fixture data (`tools/fixtures.py`, Google/Meta/Reddit coverage) for replayability. Record timestamps on live events so runs can be replayed later (Anthropic's technique).

### Stage 1 — One loop, capability profiles, zero subagents (baseline fold)
Build the single graph from day one, per entry point:
- **Slack / interactive**: full tool surface, filtered per intent (below). No sandbox for pure lookups; sandbox attached on demand for analysis. Read/write split enforced by middleware (`authorization.py` pattern from PMA).
- **Scheduled weekly**: same runtime, runs the report skill; per-platform *fan-out done as parallel tool calls in one loop* (batched tool calls per Anthropic's design), with **per-platform result artifacts written to distinct workspace paths** — adopting PMA's isolation fix (separate report paths, separate completion state) but *inside* the single loop rather than in subagent land.
- The plan is written by the model into context on turn one and revised as results arrive — no planner code step.

### Stage 2 — Intent-routed tool surface via decision_harness
- Group the ~218 ad-platform calls **by user intent** behind a small catalog (Search/Read/Run as PMA does), plus warehouse describe/query.
- Add `ToolSelectionMiddleware(ToolSelector(DecisionsClient), always_include=[approval, lookup-always-needed], max_tools=~12, on_none="all")`:
  - one ~350 ms typed-questions request filters the visible tool set per user message;
  - `always_include` pins the safety-critical tools (approval-gated writes, source-of-truth guard tool) so selection can never hide a gate;
  - failure → keep all tools (never break the agent);
  - measurable claim to verify: PMA reported 38K→12K tokens with Search/Read/Run; intent-filtering should get the *interactive* first turn lower still, because the model never spends a turn searching.
- Keep `ModelSelectionMiddleware` sticky per-thread: scheduled reports route to the performance tier, Slack lookups to fast tier — this is the PMA's "two graphs, two models" instinct, preserved **without** two graphs. This is where the original 40×/13× optimization generalizes.

### Stage 3 — Skills and wiki, lifted from the PMA
- Reuse the PMA's six skills (analysis, report, wiki, writes, report-design) verbatim as the skill library; they already pass the "works at another company" test.
- Wiki = your company's campaigns/goals/decisions. Source-of-truth rules live in the wiki **and** are enforced structurally (tool removal per Anthropic; the PMA does both).

### Stage 4 — Action path with gates in code, not prompts
- Port the approval workflow unchanged: proposal → Block Kit card → human approve → code applies → code verifies. Write tools check Slack user ID server-side.
- Keep PMA's hard safeguards (don't-cut-top-drivers, date-window alignment) in deterministic code.

### Stage 5 — The A/B that answers the article's question
Run the eval set against two harnesses:
1. **Folded** (Stages 1–4, single loop + middleware).
2. **Parent + per-platform subagents** (the PMA's production choice), subagents reduced to the 3-tool diet PMA arrived at.

Decide per Anthropic's rule: keep the subagent architecture **only where the folded version scores worse** — the honest expectation is that scheduled cross-platform reports may keep subagents (parallel, isolated, heavy), while all interactive Slack traffic lives in the folded loop. That hybrid *is* the article's end state.

### What we deliberately keep from each source
| From Anthropic | From LangChain PMA | From decision_harness |
|---|---|---|
| Single-loop default; fold one subagent at a time | Deep Agents harness, sandbox + snapshot, skills/wiki layering, Search-Read-Run catalog, approval workflow, fixture replay | `ToolSelectionMiddleware` as the portable intent filter; `ModelSelectionMiddleware` for per-entry-point tiering; cost ledger as the eval instrumentation |
| Eval-first; watch flipped tasks; central team owns prompt + tool vetting | Compute in code; source-of-truth per metric; engineered isolation semantics | Graceful degradation + circuit breaker as non-negotiable middleware contract |

### Risks
- **Intent misclassification hides a needed tool** → mitigated by `always_include` for gates, `on_none="all"`, and eval scenarios that force cross-intent questions (Anthropic's "flipped task" discipline).
- **Single-loop weekly report bloats context** (5 platforms × raw rows) → deterministic compute writes compact per-platform summaries to the workspace; the loop reads summaries, not rows (PMA's lesson 1 already solves this).
- **Decisions API dependency** → circuit breaker + offline fallback already in the library; eval stage 5 quantifies the cost of running without it.
- **Slack thread follow-ups spanning an old report** → one runtime + workspace artifacts (PMA's fix) handles this without subagents.

---

## 6. Suggested repo skeleton

```
sub_agents_to_main_loop_v1.0/
├── src/paid_media_folded/
│   ├── agent.py              # create_deep_agent + middleware stack + capability profiles
│   ├── entrypoints/          # slack.py, schedule.py (same graph factory)
│   ├── tools/                # catalog (search/read/run), warehouse, writes, compute
│   ├── skills/               # lifted from langchain-ai/paid-media-agent
│   └── wiki/                 # your company context
├── evals/                    # golden set, rubric grader, flip-report
└── docs/decisions/           # ADRs: fold vs keep, per subagent
```

**Next step if approved**: Stage 0 (eval set + fixture replay) — one focused session — then Stage 1 skeleton.
