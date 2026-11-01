import json

import pytest


def _store(tmp_path):
    (tmp_path / "approvers.txt").write_text("U123\n")
    from pmf_agent.approval import ProposalStore

    return ProposalStore(tmp_path, allowlist_path=tmp_path / "approvers.txt")


def _submit(tmp_path):
    store = _store(tmp_path)
    p = store.submit(
        platform="google_ads",
        change_type="add_keywords",
        details="add: ppc attribution (phrase)",
        rationale="coverage gap",
    )
    return store, p


def test_cli_list_shows_pending(tmp_path, capsys):
    from pmf_agent.approval_cli import main

    _submit(tmp_path)
    rc = main(["list", "--store", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "pending" in out and "add_keywords" in out


def test_cli_approve_and_apply(tmp_path, capsys):
    from pmf_agent.approval_cli import main

    _, p = _submit(tmp_path)
    rc = main(["approve", p["proposal_id"], "--approver", "U123", "--store", str(tmp_path)])
    assert rc == 0
    rc = main(["apply", p["proposal_id"], "--store", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "applied" in out and "verified" in out


def test_cli_approve_unauthorized_reports_error(tmp_path, capsys):
    from pmf_agent.approval_cli import main

    _, p = _submit(tmp_path)
    rc = main(["approve", p["proposal_id"], "--approver", "U999", "--store", str(tmp_path)])
    assert rc == 1  # non-zero, proposal stays pending
    store = _store(tmp_path)
    assert store.get(p["proposal_id"])["status"] == "pending"
