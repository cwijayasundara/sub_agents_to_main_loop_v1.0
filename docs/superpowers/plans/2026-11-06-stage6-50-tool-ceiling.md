# Stage 6: The 50-Tool Ceiling — Folded Loop at GTM-Scale Catalog

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure what happens to the folded single loop when the tool catalog scales from 4 to 50 tools (LangChain GTM-agent scale), with and without selection middleware. Answer: does tool choice degrade, what does it cost in tokens/latency, and does middleware claw it back?

**Architecture:** `catalog50.py` generates a 50-tool surface data-driven from a spec table: the 4 core fixture-backed tools, ~10 useful fixture-backed reads, and ~36 plausible GTM/marketing-ops distractor tools (functional schemas, fixture-stub behavior). Three configurations compared live on the same scenarios: `fireworks-skills` (4 tools), `fireworks-50` (50 visible), `fireworks-50-routed` (50 + `LLMToolSelectorMiddleware`, the portable full-LLM selector — runnable without a Decisions key).

**Tech Stack:** deepagents 0.7.32, langchain 1.4.7 `LLMToolSelectorMiddleware`.

**Spec:** Anthropic "30-50 tool ceiling"; PMA Search/Read/Run; GTM agent's constrained-tool-subagent pattern (context for the writeup).

## Global Constraints

- Same model, scenarios, anchor across all three runs.
- Distractor tools must have realistic names/descriptions/args (the degradation under test is a *context/discrimination* effect, not fake stubs being ignored).
- The 4 core tools keep identical names/descriptions in every configuration.
- Middleware config: `always_include` the 4 core tools? NO — that would defeat the test; middleware must be free to drop reads, but `propose_campaign_change` must always be visible when present (write-gate visibility).

## Review Focus

- Catalog must contain exactly 50 unique tool names (no dupes with core).
- Distractor read tools that could plausibly answer eval questions (e.g. `get_spend_daily`) must still return real fixture data — so a "wrong but data-backed" tool choice isn't an automatic error.
- runs must record tokens_in so first-turn/catalog overhead is measurable.
- If middleware drops the tool an eval needs, the flip report must show it (that's the finding, not a bug).

---

### Task 1: 50-tool catalog generator

**Files:** Create `src/pmf_agent/catalog50.py`; Test `tests/pmf_agent/test_catalog50.py`

- [ ] RED: test `build_catalog_50()` returns exactly 50 tools, unique names, superset of the 4 core tools; test distractor tools are invocable (return dicts, no exceptions); test `get_spend_daily` returns fixture-backed numbers for google_ads
- [ ] GREEN: implement spec-table generator
- [ ] pytest green; commit

### Task 2: 50-tool agent profiles

**Files:** Modify `src/pmf_agent/main.py` (`--tools core|full50`), `src/pmf_agent/agent.py` (`tools_override` param); Test `tests/pmf_agent/test_main.py` additions

- [ ] RED: test `_build_agent(tools_surface="full50")` builds with 50 tools; `core` keeps 4; eval-CLI agents `fireworks-50` and `fireworks-50-routed` registered lazily
- [ ] GREEN: implement
- [ ] pytest green; commit

### Task 3: Live three-way comparison + report

**Files:** Create `results/tools50-report.md`

- [ ] Live: run 15 scenarios × {`fireworks-skills` (4t, reuse `fw-skills.jsonl`), `fireworks-50`, `fireworks-50-routed`} at the same anchor; grade (folded arch) all three
- [ ] Analyze: tokens_in ratio (catalog overhead), latency, pass rates, flips; write `results/tools50-report.md` with the verdict and its implication for the GTM/Pipeboard scale question
- [ ] commit
