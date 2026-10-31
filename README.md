# sub_agents_to_main_loop_v1.0

Replicating [LangChain's Paid Media Agent](https://www.langchain.com/blog/paid-media-agent)
using the doctrine from Anthropic's
["When to fold subagents into your main agent loop"](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop),
with intent-routed tool selection from
[decision_harness](https://github.com/cwijayasundara/deep_agents_utils_v1.0).

See **[PROPOSAL.md](PROPOSAL.md)** for the full research synthesis and staged plan.

## Stage 0 (this repo, current state): eval harness

Eval-first, per the Anthropic doctrine: no architecture changes are made before
a task-completion eval exists to measure them.

- **Fixtures** (`src/pmf_evals/fixtures.py`): deterministic synthetic daily rows
  for google_ads / meta_ads / reddit_ads, generated against a fixed anchor and
  date-shifted at load, so "last week vs prior week" is always answerable and
  ground-truth totals are shift-invariant. Built-in movers: Google spikes, Meta
  dips, Reddit flat.
- **Golden set** (`evals/scenarios/golden.json`): 15 scenarios across
  `weekly_report` (5), `q_and_a` (5), `write_proposal` (3), `cross_platform`
  (2), each with rubric criteria and, where deterministic,
  `(platform, window, metric)` figure specs the grader computes exactly.
- **Runner** (`src/pmf_evals/runner.py`): agent-agnostic (`AgentUnderTest`
  protocol); one JSONL row per scenario with tokens, cost, latency, tool calls;
  agent crashes become `failed` rows, never suite crashes.
- **Grader** (`src/pmf_evals/grader.py`): deterministic numeric checks
  (currency/separator tolerant, date-immune) + rubric criteria (`skipped`
  offline, pass/fail with a judge callable).
- **Flip report** (`src/pmf_evals/report.py`): per-scenario verdicts, flipped
  tasks, and latency/cost aggregates for the Stage 5 A/B.
- **EchoAgent**: quotes fixture ground truth; proves the pipeline end to end.

## Usage

```bash
pip install -e ".[dev]"
pytest                                                        # 28 tests
python -m pmf_evals run --agent echo --out results/smoke.jsonl
python -m pmf_evals grade --results results/smoke.jsonl
python -m pmf_evals compare results/a.jsonl results/b.jsonl
```

Set `PMF_FIXTURE_ANCHOR=YYYY-MM-DD` to pin the replay date.

## Stages ahead (per PROPOSAL.md)

1. Single loop + capability profiles (no subagents) — baseline fold
2. Intent-routed tool surface via decision_harness middlewares
3. Skills/wiki lifted from the PMA
4. Approval-gated writes (code-enforced gates)
5. A/B: folded loop vs parent+per-platform-subagents; keep subagents only
   where the folded version scores worse
