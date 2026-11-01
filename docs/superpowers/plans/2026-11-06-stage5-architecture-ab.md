# Stage 5: Architecture A/B — Folded Loop vs Parent+Per-Platform Subagents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer the proposal's central question with data: build the PMA-style hierarchical architecture (parent + one subagent per platform) as a second `AgentUnderTest`, run the same 15 golden scenarios on the same model, and let the flip report adjudicate per task type.

**Architecture:** `create_hierarchical_agent`: parent keeps intent-level tools (`list_platforms`, `propose_campaign_change` on slack) plus the `task` tool for delegation; three platform subagents (google_ads/meta_ads/reddit_ads), each with platform-scoped read tools and the same skills (isolation per PMA lesson 4: scoped tools, scoped prompt, returns synthesized findings). Same model (`glm-5p3-flash`) both sides; only the harness differs.

**Tech Stack:** deepagents 0.7.32 declarative `SubAgent` specs.

**Spec:** `PROPOSAL.md` Stage 5; PMA lesson 4 (isolation must be engineered).

## Global Constraints

- Same model, same scenarios, same anchor both sides — only architecture varies.
- Subagents never see `propose_campaign_change` (writes stay at the parent, per the PMA's "three tool diet").
- Subagent tools are platform-scoped (isolation engineered, not assumed).
- All Stage 1–4 guarantees hold on the hierarchical side too (eval, gates).

## Review Focus

- Parent must not be able to call platform read tools directly (it delegates) — that's the architecture under test.
- Subagent name mismatch / unknown platform in factory → clear error.
- The A/B must run both sides at the same anchor; grading must be post-hoc identical.

---

### Task 1: Platform-scoped read tools + hierarchical factory

**Files:** Create `src/pmf_agent/subagent_arch.py`; Test `tests/pmf_agent/test_subagent_arch.py`

- [ ] RED: test `platform_read_tools("google_ads")` returns read tools that ignore/override a platform arg and always report google_ads; test `create_hierarchical_agent("slack", model=fake)` builds and exposes `pmf_subagents` with 3 platform names; scheduled variant has no propose tool; unknown platform raises
- [ ] GREEN: implement declarative SubAgent specs
- [ ] pytest green; commit

### Task 2: Adapter + CLI registration

**Files:** Modify `src/pmf_agent/adapter.py`, `src/pmf_evals/__main__.py`; Test `tests/pmf_agent/test_adapter.py`, `tests/test_cli.py` additions

- [ ] RED: test `FireworksAgentUnderTest(arch="hierarchical", model=fake)` runs and satisfies protocol; CLI `fireworks-hierarchical` registered lazily
- [ ] GREEN: implement
- [ ] pytest green; commit

### Task 3: Live A/B + final report

**Files:** Create `results/ab-report.md`; Update README

- [ ] Live: run all 15 scenarios through `fireworks-hierarchical` (same anchor) → grade → `compare` vs `fw-skills.jsonl`
- [ ] Write `results/ab-report.md`: per-category verdicts, flips, latency/cost deltas, and the Stage 5 decision (which architecture per entry point)
- [ ] pytest green; commit
