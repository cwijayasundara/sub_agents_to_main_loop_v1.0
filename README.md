# sub_agents_to_main_loop_v1.0

Replicating [LangChain's Paid Media Agent](https://www.langchain.com/blog/paid-media-agent)
using the doctrine from Anthropic's
["When to fold subagents into your main agent loop"](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop),
with intent-routed tool selection from
[decision_harness](https://github.com/cwijayasundara/deep_agents_utils_v1.0).

**Verdict of the Stage 5 A/B** ([`results/ab-report.md`](results/ab-report.md)):
the folded single loop wins 15/15 vs 12/15 at 1.8× less latency — the
hierarchical architecture failed in exactly the ways the article predicts
(lossy handoffs, skill/ability mismatch, delegation without synthesis).

See **[PROPOSAL.md](PROPOSAL.md)** for the full research synthesis.

## How to run the app

There are three runnable surfaces: the **eval harness** (run/grade/compare the
15 golden scenarios against any agent), the **agent CLI registry** (five
swap-in architectures), and the **approval CLI** (the human side of the
write gate).

### 1. Setup

```bash
# Python 3.11+
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # pmf_evals + pmf_agent + pytest
```

Copy `.env-template` to `.env` and fill in what you need:

| Key | Required for |
|---|---|
| `FIREWORKS_API_KEY` | any `fireworks*` agent (live LLM runs) |
| `DECISIONS_API_KEY` or `OPENAI_API_KEY` | intent-routed tool selection (optional — without it, routing degrades to keep-all-tools) |
| `PMF_FIXTURE_ANCHOR` | pinning the fixture replay date (optional; default = today−2) |
| `PMF_STORE_DIR` | proposal store root (optional; default `workspace/`) |
| `PMF_APPROVERS` | approver allowlist (optional; alternative to `workspace/approvers.txt`, fail-closed if both absent) |

### 2. Run the tests (no keys needed)

```bash
pytest          # 100 tests, fully offline (fixtures + fake models)
```

### 3. Run the eval suite

```bash
# offline sanity: EchoAgent quotes fixture ground truth, 15/15 by construction
python -m pmf_evals run --agent echo --out results/smoke.jsonl
python -m pmf_evals grade --results results/smoke.jsonl

# live runs (needs FIREWORKS_API_KEY): pick an architecture; --trace-dir
# writes one human-readable transcript per scenario (every tool call + result)
python -m pmf_evals run --agent fireworks               --out results/fw.jsonl        # folded single loop
python -m pmf_evals run --agent fireworks-routed        --out results/fw-routed.jsonl # + Decisions intent routing
python -m pmf_evals run --agent fireworks-skills        --out results/fw-skills.jsonl # + skills/wiki
python -m pmf_evals run --agent fireworks-hierarchical  --out results/fw-hier.jsonl   # parent + platform subagents
python -m pmf_evals run --agent fireworks-50            --out results/fw-50.jsonl     # 50-tool GTM-scale catalog
python -m pmf_evals run --agent fireworks-skills        --trace-dir results/traces/folded
python -m pmf_evals run --agent fireworks-hierarchical  --trace-dir results/traces/hier

# grade (use --arch hierarchical for subagent runs: task-delegation counts
# as correct routing) + compare two architectures (the flip report)
python -m pmf_evals grade --results results/fw-hier.jsonl --arch hierarchical --out results/fw-hier-graded.json
python -m pmf_evals compare results/fw-skills.jsonl results/fw-hier.jsonl
```

`compare` prints per-scenario verdicts, which tasks **flipped**, and
latency/cost aggregates — any pass→fail flip blocks an architecture change.

Example traces are committed under `results/traces/{folded,hier}/` — the same
question answered by both architectures, side by side.

### 4. Run the approval workflow (analysis → action)

The agent can only *propose*; a human approves; code applies and verifies:

```bash
# 1) get a proposal: run an agent scenario (e.g. q11) or propose via the tool;
#    proposals land in $PMF_STORE_DIR/proposals/ as pending JSON
python -m pmf_agent.approval_cli list --store workspace

# 2) authorize approvers (IDs are arbitrary strings, e.g. Slack user IDs)
printf "U123\nU777\n" > workspace/approvers.txt

# 3) approve + apply (permission-checked; non-approvers are refused, proposal stays pending)
python -m pmf_agent.approval_cli approve prop-abc123 --approver U123 --store workspace
python -m pmf_agent.approval_cli apply prop-abc123 --store workspace   # records + verifies the mutation
```

The apply path exists **only** in this CLI/server layer — the agent's tool
surface has no way to reach it, so prompt injection cannot cross the gate.

### 5. Chat with the agent directly

```bash
# one-off question (live LLM)
python -m pmf_agent "How did Google spend move last week vs the week before?"

# interactive multi-turn session (one thread; :quit or Ctrl-D to exit)
python -m pmf_agent

# architecture / profile flags
python -m pmf_agent --arch hierarchical "Which platform gained spend share?"
python -m pmf_agent --entry-point scheduled --no-stream "Produce the weekly report"
```

Each turn prints the tools the agent called, the answer, and its
token/cost footprint.

## What's inside

```
├── evals/scenarios/golden.json  # 15 golden scenarios (data, not code)
├── src/pmf_evals/               # eval harness: fixtures, runner, grader, flip report, CLI
├── src/pmf_agent/               # agents: folded loop, hierarchical, routing, approval
├── workspace/                   # skills/ + wiki/ (progressive disclosure) + proposals/
└── results/                     # baselines, traces/, ab-report.md, tools50-report.md
```

- **Fixtures**: deterministic synthetic ad data (Google spikes, Meta dips,
  Reddit flat), date-shifted so "last week" is always answerable; ground-truth
  totals are shift-invariant.
- **Grader**: exact figure checks (currency-tolerant, date-immune) + rubric
  criteria + architecture-aware tool-routing expectations.
- **Agents**: all built on deepagents 0.7.32; one model
  (`accounts/fireworks/models/glm-5p3-flash` via Fireworks), no subagents by
  default; hard rules and the write gate live in code, never in prompts.

## Stage history (per PROPOSAL.md)

| Stage | Status | Evidence |
|---|---|---|
| 0 Eval harness | done | 100 tests, 15 golden scenarios, flip report |
| 1 Folded single loop | done | `results/fw-baseline.md` (14/15 baseline) |
| 2 Intent routing (decision_harness) | done | degradation equality, zero flips |
| 3 Skills + wiki | done | 15/15, q04 closed by the report skill |
| 4 Approval workflow | done | fail-closed allowlist, verified apply |
| 5 Architecture A/B | done | **folded wins 15/15 vs 12/15 at 1.8× less latency** |
| 6 50-tool ceiling | done | **`results/tools50-report.md`: quality holds (14/15) but 2.2× tokens; per-turn LLM selector loses; intent routing + deferred loading are the levers** |
