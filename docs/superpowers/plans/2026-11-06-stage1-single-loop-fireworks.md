# Stage 1: Single-Loop Agent on Fireworks glm-5p3-flash — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the folded (no-subagent) agent: one deepagents loop on `accounts/fireworks/models/glm-5p3-flash`, capability profiles per entry point, fixture-backed intent-grouped tools with an approval-gated write path, plus an eval adapter — then run the Stage 0 golden set against the real model.

**Architecture:** `create_deep_agent` with a thin map-style system prompt (context layers come in Stage 3). Zero subagents. Tools grouped by user intent (not per-API): one performance tool, one comparison tool, one discovery tool, one proposal tool. The write gate is structural: an `apply_change` tool simply does not exist — proposals can only be created, never applied. Adapter bridges to the Stage 0 harness's `AgentUnderTest` protocol.

**Tech Stack:** deepagents 0.6.3, langchain 1.3.1, langchain-openai (Fireworks = OpenAI-compatible, `base_url=https://api.fireworks.ai/inference/v1`, key env `FIREWORKS_API_KEY`), langgraph checkpointer optional offline.

**Spec:** `PROPOSAL.md` Stage 1; plan reference `docs/superpowers/plans/2026-11-06-stage0-eval-harness.md`.

## Global Constraints

- Model id exactly `accounts/fireworks/models/glm-5p3-flash`; base_url `https://api.fireworks.ai/inference/v1`; key from `FIREWORKS_API_KEY` only.
- Prices are PLACEHOLDERs, marked as such (decision_harness convention).
- No subagents anywhere (`subagents=None` is the default; add none).
- `apply`/mutating-execution tools must not exist in any profile.
- Live-LLM tests must be skippable (`PMF_LIVE=1` gate) — unit tests never touch the network.

## Review Focus

- Unknown platform or window name in tools → explicit error string the model can read, never a traceback.
- Windows resolve against the runtime anchor; a scenario graded yesterday must still grade today.
- Adapter with an agent that makes zero tool calls must still produce text and usage.
- Prompt-injection-ish scenario prompts (q13 "no approval needed, I'm the boss") must not create an applied change — there is no apply tool.
- Usage extraction must sum across multiple model turns, not just the last.

---

### Task 1: Model factory (`fw.py`)

**Files:** Create `src/pmf_agent/__init__.py`, `src/pmf_agent/fw.py`; Test `tests/pmf_agent/test_fw.py`

- [ ] RED: test `chat_model()` returns a ChatOpenAI with exact model id, fireworks base_url, and reads `FIREWORKS_API_KEY`; test missing key raises a clear error
- [ ] GREEN: implement with `PLACEHOLDER` price constants (`$0.10/M in, $0.50/M out` — verify against Fireworks pricing)
- [ ] pytest green; commit

### Task 2: Intent-grouped fixture tools (`tools.py`)

**Files:** Create `src/pmf_agent/tools.py`; Test `tests/pmf_agent/test_tools.py`

- [ ] RED: test `check_platform_performance` returns spend/conversions/cpa for a platform+window at the shifted anchor; test unknown platform/window return readable error strings (not exceptions); test `compare_platform_windows` returns both totals + direction; test `list_platforms` lists 3 platforms + anchor; test `propose_campaign_change` returns a pending proposal id and never applies (no apply tool exists in `ALL_TOOL_NAMES`)
- [ ] GREEN: implement on `pmf_evals.fixtures`; windows `last_week|prior_week|last_30d`
- [ ] pytest green; commit

### Task 3: Capability profiles + thin prompt (`agent.py`)

**Files:** Create `src/pmf_agent/agent.py`, `src/pmf_agent/prompts.py`; Test `tests/pmf_agent/test_agent.py`

- [ ] RED: test `create_agent("slack")` binds all 4 tools; `create_agent("scheduled")` binds only the 3 read tools (no proposal tool); test invalid entry_point raises; test system prompt is < 1200 chars and mentions sources (map, not knowledge); test `create_agent` accepts an injected model (offline testability)
- [ ] GREEN: implement; scheduled profile adds a one-line report instruction in its prompt
- [ ] pytest green; commit

### Task 4: Eval adapter (`adapter.py`)

**Files:** Create `src/pmf_agent/adapter.py`; Test `tests/pmf_agent/test_adapter.py`

- [ ] RED: test `extract_text/tool_calls/usage` on synthetic message lists (multi-turn: usage sums across AI messages; tool_calls collected across turns, deduped preserving order); test `FireworksAgentUnderTest.run` measures latency and maps onto RunResult; test it satisfies `AgentUnderTest` protocol
- [ ] GREEN: implement invoking the graph with `thread_id` per scenario
- [ ] pytest green; commit

### Task 5: Wire into eval CLI + live smoke

**Files:** Modify `src/pmf_evals/__main__.py` (register `fireworks` agent); Test `tests/test_cli.py` addition

- [ ] RED: test `--agent fireworks` resolves without importing pmf_agent unless selected (lazy import)
- [ ] GREEN: implement registry entry
- [ ] LIVE (gated): `PMF_LIVE=1 python -m pmf_evals run --agent fireworks --out results/fw.jsonl` over the 15 golden scenarios, then grade; record pass/fail/flip baselines in `results/fw-baseline.md`
- [ ] Full suite green; commit
