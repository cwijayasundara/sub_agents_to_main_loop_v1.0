# Stage 2: Intent-Routed Tool Surface (decision_harness middlewares) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put `decision_harness.ToolSelectionMiddleware` (Decisions-API intent routing) in front of the Stage 1 loop, add a routing-accuracy metric to the eval harness (`expected_tools` / `forbidden_tools` on scenarios), and wire a `fireworks-routed` agent into the CLI.

**Architecture:** `routing.py` builds the middleware: a recording wrapper around `ToolSelector` captures per-turn selections; `always_include=["list_platforms"]` (discovery never hidden), `on_none="all"` (conservative). `create_agent` accepts extra middleware. Adapter threads selection events into result rows. With only 4 tools the filtering effect is small — the point is measured plumbing that scales to the 200+-tool Pipeboard catalog in later stages. ModelSelectionMiddleware is NOT wired: the user pinned glm-5p3-flash as the LLM.

**Tech Stack:** decision_harness (installed from `cwijayasundara/deep_agents_utils_v1.0`), existing Stage 0/1 stack.

**Spec:** `PROPOSAL.md` Stage 2; `SPEC.md` of decision_harness (degradation contract).

## Global Constraints

- No key in env: live runs must degrade to keep-all-tools, never crash (decision_harness contract: "the agent never loses its tools because of the router").
- Routing accuracy = "did the agent load/call the right tool for the intent" (Anthropic's post-fold metric replacing subagent-routing accuracy).
- `expected_tools` semantics: pass if ANY expected tool was called; `forbidden_tools`: fail if any was called.
- Selector wire calls only via the real `DecisionsClient` when a key exists; unit tests use fakes.

## Review Focus

- A selection event must be recorded even when selection is degraded (event: "unavailable, kept all").
- Scenario with no expected_tools must not change its verdict.
- Comparing results files with and without routing events must not break `compare`.
- The routed agent with a broken/failing selector must produce identical verdicts to Stage 1's unrouted agent (degradation equality).

---

### Task 1: Routing factory with recording selector

**Files:** Create `src/pmf_agent/routing.py`; Test `tests/pmf_agent/test_routing.py`

- [ ] RED: test `tool_selection_middleware()` returns ToolSelectionMiddleware whose selector is the recording proxy; test the proxy records (task_text, selected) tuples across select() calls; test `always_include=["list_platforms"]` and `on_none="all"`; test SelectorUnavailable still records a degraded event
- [ ] GREEN: implement
- [ ] pytest green; commit

### Task 2: create_agent middleware wiring

**Files:** Modify `src/pmf_agent/agent.py`; Test `tests/pmf_agent/test_agent.py` addition

- [ ] RED: test `create_agent(..., middleware=[m])` passes middleware through to deepagents; test routed profile builds (model=fake) with the middleware present
- [ ] GREEN: implement `middleware: Sequence | None = None`
- [ ] pytest green; commit

### Task 3: Routing metric in scenarios + grader

**Files:** Modify `src/pmf_evals/scenarios.py`, `grader.py`, `evals/scenarios/golden.json`; Test `tests/test_scenarios.py`, `tests/test_grader.py` additions

- [ ] RED: test Scenario accepts optional `expected_tools`/`forbidden_tools` (JSON round-trip); test grader emits `tools` section (expected_found, forbidden_violations) and `fail` when an expected tool is missing or a forbidden tool called; test scenarios without tool expectations grade unchanged
- [ ] GREEN: implement; add expected_tools to golden.json (q01 compare/check, q06 check/compare, q07 check, q08 check, q09 check, q12 propose, q11 propose, q14 check; q13 forbidden: none)
- [ ] pytest green; commit

### Task 4: Adapter routing events + routed CLI agent

**Files:** Modify `src/pmf_agent/adapter.py`, `src/pmf_evals/runner.py`, `src/pmf_evals/__main__.py`; Test `tests/pmf_agent/test_adapter.py`, `tests/test_cli.py` additions

- [ ] RED: test RunResult accepts optional `selections`; routed adapter surfaces middleware selections; CLI `--agent fireworks-routed` resolves lazily
- [ ] GREEN: implement; runner writes `selections` into the row when present
- [ ] pytest green; commit

### Task 5: Live routed baseline + degradation check

**Files:** Update `results/fw-baseline.md`

- [ ] Live: `PMF_LIVE=1 python -m pmf_evals run --agent fireworks-routed --out results/fw-routed.jsonl` (no key -> degraded keep-all expected); grade; confirm verdicts identical to Stage 1 baseline (degradation equality); record routing-accuracy measurement plan for when DECISIONS_API_KEY exists
- [ ] commit
