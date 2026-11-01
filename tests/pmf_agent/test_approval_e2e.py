def test_full_loop_agent_proposes_human_approves_code_applies(tmp_path, monkeypatch):
    """Agent proposes (tool) -> human approves (allowlist) -> code applies + verifies."""
    monkeypatch.setenv("PMF_STORE_DIR", str(tmp_path))

    from pmf_agent.approval import ProposalStore
    from pmf_agent.tools import propose_campaign_change

    # --- agent side: proposes via its (only) write tool
    result = propose_campaign_change.invoke(
        {
            "platform": "google_ads",
            "change_type": "add_keywords",
            "details": "add: ppc attribution (phrase), gtm tracking (exact)",
            "rationale": "top converting campaign, expanding coverage",
        }
    )
    assert result["status"] == "pending"

    # --- human side: permission-checked approval
    (tmp_path / "approvers.txt").write_text("U123\n")
    store = ProposalStore(tmp_path, allowlist_path=tmp_path / "approvers.txt")

    # unauthorized human is blocked; proposal stays pending
    try:
        store.approve(result["proposal_id"], approver_id="U999")
        raise AssertionError("should have raised")
    except PermissionError:
        assert store.get(result["proposal_id"])["status"] == "pending"

    store.approve(result["proposal_id"], approver_id="U123")

    # --- code side: applies and verifies
    applied = store.apply(result["proposal_id"])
    assert applied["status"] == "applied" and applied["verified"] is True
