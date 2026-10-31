# Stage 0: Eval Set + Fixture Replay Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the eval-first foundation (Anthropic step 1): a deterministic fixture dataset, a 15-scenario golden set, a runner that records tokens/cost/latency/tool-calls, a grader with deterministic numeric checks plus rubric flags, and a flip-report comparing two architectures.

**Architecture:** Agent-agnostic harness. The runner executes scenarios against any `AgentUnderTest` (protocol: `run(scenario) -> RunResult`), so Stage 5's A/B (folded loop vs parent+subagents) plugs in two different agents with zero harness changes. Fixtures are synthetic, seeded, generated against a fixed SHIPPED_ANCHOR and date-shifted at load (PMA's replay technique), so numeric ground truth is stable and windows are always "last week vs prior week."

**Tech Stack:** Python 3.11+, pytest, stdlib only at core (dataclasses, json, argparse). No LLM deps in Stage 0; the judge is a protocol with an offline default.

**Spec:** `PROPOSAL.md` (Stage 0 section). Repo: `langchain-ai/paid-media-agent` `tests/eval/` is the pattern reference.

## Global Constraints

- Python >= 3.11. Core package `pmf_evals` under `src/`.
- Fixture data is synthetic only — no network, no credentials (PMA rule, adopted).
- All dates generated relative to `SHIPPED_ANCHOR = 2026-08-28`; runtime anchor = `PMF_FIXTURE_ANCHOR` env or `today - 2 days`.
- Window totals must be identical regardless of anchor (shift-invariant).
- Eval scenarios are data (JSON), never code.

## Review Focus

- Non-determinism: any use of `date.today()` outside `anchor()` must fail a test.
- Number parsing: grader must match "3,862.42", "$3862.4", "3862" — but NOT numbers inside ids/dates.
- Empty/failed agent runs must produce a `failed` result row, never crash the runner.
- Comparing runs with mismatched scenario sets must error, not silently drop.
- Rubric grading offline must skip judgment criteria with an explicit `skipped` verdict, not score 0.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/pmf_evals/__init__.py`
- Test: `tests/test_package.py`

- [ ] Write failing test: `import pmf_evals; pmf_evals.__version__` exists
- [ ] Run pytest, verify it fails (module missing)
- [ ] Create `pyproject.toml` (name `pmf-evals`, hatchling, pytest config, `src` layout), package init with `__version__ = "0.1.0"`
- [ ] Run pytest, verify pass; git init + commit

### Task 2: Deterministic fixture dataset

**Files:**
- Create: `src/pmf_evals/fixtures.py`
- Test: `tests/test_fixtures.py`

- [ ] RED: test `load_dataset()` returns 3 platforms (google_ads, meta_ads, reddit_ads), ~6 weeks of daily rows ending at SHIPPED_ANCHOR, deterministic across two calls; test `shift_dataset(ds, offset)` moves every `date` by offset and preserves per-platform totals; test `window_totals(platform, window)` computes exact spend/conversions/cpa from rows; test `anchor()` honours `PMF_FIXTURE_ANCHOR` else `today-2`
- [ ] Run, verify correct failures
- [ ] GREEN: implement seeded generator (fixed seed, hand-authored weekly patterns so CPL "movers" exist — one platform with a spend spike, one with a conversions dip) + shift/totals helpers
- [ ] pytest green; commit

### Task 3: Scenario schema + golden set data

**Files:**
- Create: `src/pmf_evals/scenarios.py`, `evals/scenarios/golden.json`
- Test: `tests/test_scenarios.py`

- [ ] RED: test `Scenario` dataclass fields (`id, entry_point in {slack, scheduled}, category, prompt, rubric: list[str], figure_specs: list[FigureSpec]`); test `load_scenarios(path)` validates unique ids, valid entry_points; test shipped `golden.json` loads exactly 15 scenarios with >=5 slack, >=5 scheduled, >=3 write-proposal category
- [ ] GREEN: implement; author the 15 scenarios (5 weekly-report, 5 Slack Q&A, 3 write-proposal, 2 cross-platform synthesis per PROPOSAL Stage 0), each with rubric criteria and, where deterministic, figure_specs naming platform/window/metric
- [ ] pytest green; commit

### Task 4: Runner + result ledger

**Files:**
- Create: `src/pmf_evals/runner.py`
- Test: `tests/test_runner.py`

- [ ] RED: test `AgentUnderTest` protocol (`run(scenario) -> RunResult(text, tool_calls, tokens_in, tokens_out, cost_usd, latency_ms)`); test `run_suite(agent, scenarios)` writes one JSONL row per scenario and continues after a raised exception (row marked `failed`); test rows carry scenario id, anchor, timestamp
- [ ] GREEN: implement with stdlib json writer
- [ ] pytest green; commit

### Task 5: Grader (deterministic figures + rubric flags)

**Files:**
- Create: `src/pmf_evals/grader.py`
- Test: `tests/test_grader.py`

- [ ] RED: test `grade_result(row, scenarios, dataset)` — deterministic check passes when the answer contains the exact expected figure for each figure_spec (computed via `window_totals` at the shifted anchor) with currency/thousand-separator tolerance, and fails listing missing figures; test a wrong number fails; test number-in-a-date ("2026-08-28") does not satisfy a figure check; test rubric criteria return `skipped` without a judge and `pass/fail` with a `Judge` callable; test failed runs grade as `error`
- [ ] GREEN: implement regex number extraction + judge protocol
- [ ] pytest green; commit

### Task 6: Flip report

**Files:**
- Create: `src/pmf_evals/report.py`
- Test: `tests/test_report.py`

- [ ] RED: test `compare(results_a, results_b)` returns per-scenario verdicts and a `flipped` list (pass→fail and fail→pass); test raises `ValueError` on scenario-id mismatch between files; test aggregates mean latency/cost per run
- [ ] GREEN: implement
- [ ] pytest green; commit

### Task 7: CLI + end-to-end smoke

**Files:**
- Create: `src/pmf_evals/__main__.py`, `src/pmf_evals/echo_agent.py`
- Test: `tests/test_cli.py`

- [ ] RED: test `EchoAgent` (echoes scenario prompt + fixture totals) run over golden set produces 15 valid JSONL rows that grade with all deterministic checks passing; test CLI `run` and `compare` subcommands execute
- [ ] GREEN: implement argparse CLI (`run --agent echo --out results.jsonl`, `compare a.jsonl b.jsonl`)
- [ ] pytest green; full suite green; commit
