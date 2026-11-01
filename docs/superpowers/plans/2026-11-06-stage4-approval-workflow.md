# Stage 4: Approval Workflow (analysis → action path) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the loop from analysis to action the PMA way: proposal → pending → permission-checked human approval → code applies → code verifies. No Slack dependency — the same contract, demonstrated in-process with a persisted store and a CLI.

**Architecture:** `ProposalStore` (JSON-persisted under `workspace/proposals/`): the agent's `propose_campaign_change` tool writes pending proposals; `approve` checks the approver ID against the allowlist (APPROVERS env or `workspace/approvers.txt`); non-approver requests are blocked and the proposal **stays pending**; `apply` refuses unapproved proposals, records the change in a fixture-mutations ledger, and verifies by reading it back. The agent never gains an apply tool — the gate stays structural.

**Tech Stack:** Existing stack; stdlib JSON persistence.

**Spec:** `PROPOSAL.md` Stage 4; PMA "writes-and-approvals" pattern.

## Global Constraints

- The apply path lives outside the agent's tool surface, always.
- Permission check happens in the store/server layer (not prompt, not model judgment).
- Non-approver approve attempt → error, proposal remains `pending`.
- Apply before approval → refused. Apply twice → refused (idempotency guard).
- Apply must verify the mutation landed (read-back check) and record the result.

## Review Focus

- Race/argument confusion: `apply` on an unknown id errors, never creates.
- Approver allowlist missing/empty → approve always refuses (fail closed).
- Proposal JSON survives restart (persistence, not just memory).
- The store must reject proposals for unknown platforms (agent tool already does; the store repeats the check).

---

### Task 1: ProposalStore (pending → approve → apply → verify)

**Files:** Create `src/pmf_agent/approval.py`; Test `tests/pmf_agent/test_approval.py`

- [ ] RED: test `submit` persists a pending proposal (JSON file under store dir, survives store re-instantiation); test `approve` with allowed id → status `approved` (recorded approver); disallowed id → error and still `pending`; missing/empty allowlist → refuse; test `apply` refuses pending, applies approved (mutation in ledger), verifies (read-back), refuses twice; test unknown platform refused
- [ ] GREEN: implement
- [ ] pytest green; commit

### Task 2: Agent tool → store wiring

**Files:** Modify `src/pmf_agent/tools.py`; Test `tests/pmf_agent/test_tools.py` addition

- [ ] RED: test `propose_campaign_change.invoke` writes through to a store instance (file exists) with `pending` status
- [ ] GREEN: store wired as module default; proposal dict gains the same fields as the store's
- [ ] pytest green; commit

### Task 3: Approval CLI

**Files:** Create `src/pmf_agent/approval_cli.py` (add `python -m pmf_agent.approval_cli list|approve|apply`); Test `tests/pmf_agent/test_approval_cli.py`

- [ ] RED: test subcommands against a temp store dir (argparse main function, subprocess-free)
- [ ] GREEN: implement
- [ ] pytest green; commit

### Task 4: End-to-end + baseline update

**Files:** Update `results/fw-baseline.md`; Test `tests/pmf_agent/test_approval_e2e.py`

- [ ] RED: test the full loop with a fake-model agent proposing, then store-level approve+apply — proposal from the agent is approvable and verifiable
- [ ] GREEN: any fix needed
- [ ] Live demo: run `fireworks-skills` on q11, approve + apply from the CLI, show ledger
- [ ] pytest green; commit
