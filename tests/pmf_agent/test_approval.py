import json

import pytest


def _allowlist(tmp_path, ids):
    (tmp_path / "approvers.txt").write_text("\n".join(ids))


def _submit(store, **kw):
    base = dict(
        platform="google_ads",
        change_type="add_keywords",
        details="add: ppc attribution (phrase)",
        rationale="coverage gap on attribution terms",
    )
    base.update(kw)
    return store.submit(**base)


def test_submit_persists_pending_and_survives_restart(tmp_path):
    from pmf_agent.approval import ProposalStore

    store = ProposalStore(tmp_path, allowlist_path=tmp_path / "approvers.txt")
    p = _submit(store)
    assert p["status"] == "pending"
    assert (tmp_path / "proposals" / f"{p['proposal_id']}.json").exists()

    reloaded = ProposalStore(tmp_path, allowlist_path=tmp_path / "approvers.txt").get(p["proposal_id"])
    assert reloaded["status"] == "pending"


def test_approve_permission_checked(tmp_path):
    from pmf_agent.approval import ProposalStore

    _allowlist(tmp_path, ["U123"])
    store = ProposalStore(tmp_path, allowlist_path=tmp_path / "approvers.txt")
    p = _submit(store)

    with pytest.raises(PermissionError):
        store.approve(p["proposal_id"], approver_id="U999")  # not on allowlist: blocked
    assert store.get(p["proposal_id"])["status"] == "pending"  # stays pending

    store.approve(p["proposal_id"], approver_id="U123")
    approved = store.get(p["proposal_id"])
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "U123"


def test_approve_fails_closed_without_allowlist(tmp_path):
    from pmf_agent.approval import ProposalStore

    store = ProposalStore(tmp_path, allowlist_path=tmp_path / "missing.txt")
    p = _submit(store)
    with pytest.raises(PermissionError):
        store.approve(p["proposal_id"], approver_id="U123")


def test_apply_only_after_approval_and_verifies(tmp_path):
    from pmf_agent.approval import ProposalStore

    _allowlist(tmp_path, ["U123"])
    store = ProposalStore(tmp_path, allowlist_path=tmp_path / "approvers.txt")
    p = _submit(store)

    with pytest.raises(RuntimeError, match="pending"):
        store.apply(p["proposal_id"])  # not approved yet

    store.approve(p["proposal_id"], approver_id="U123")
    result = store.apply(p["proposal_id"])
    assert result["status"] == "applied"
    assert result["verified"] is True
    # read-back: the mutation ledger has it
    ledger = json.loads((tmp_path / "proposals" / "_mutations.json").read_text())
    assert any(m["proposal_id"] == p["proposal_id"] for m in ledger)

    with pytest.raises(RuntimeError, match="already"):
        store.apply(p["proposal_id"])  # idempotency guard


def test_apply_unknown_platform_refused(tmp_path):
    from pmf_agent.approval import ProposalStore

    _allowlist(tmp_path, ["U123"])
    store = ProposalStore(tmp_path, allowlist_path=tmp_path / "approvers.txt")
    with pytest.raises(ValueError, match="platform"):
        _submit(store, platform="tiktok_ads")  # store rejects at submit time
