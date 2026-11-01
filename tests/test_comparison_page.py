import pytest


def test_build_html_contains_both_architectures_and_diagrams():
    from pmf_evals.comparison_page import build_html

    html = build_html()
    assert "Folded single loop" in html
    assert "Parent + per-platform subagents" in html
    assert "<svg" in html  # diagrams are inline SVG
    assert html.count("<svg") >= 2  # one diagram per architecture


def test_build_html_embeds_measured_numbers_from_results():
    import json as _json

    from pmf_evals.comparison_page import RESULTS_DIR, build_html
    from pmf_evals.grader import grade_result
    from pmf_evals.scenarios import GOLDEN_PATH, load_scenarios

    # independently recompute the hier pass rate from the raw rows
    scenarios = load_scenarios(GOLDEN_PATH)
    rows = [_json.loads(l) for l in (RESULTS_DIR / "fw-hier.jsonl").read_text().splitlines()]
    expected_pass = sum(
        1
        for r in rows
        if grade_result(r, scenarios, arch="hierarchical")["verdict"]
        in ("pass", "figures_only")
    )
    html = build_html()
    assert f"{expected_pass}/15" in html
    assert "15/15" in html  # folded side
    # flip findings present
    assert "q08_slack_reddit_conversions" in html


def test_open_page_writes_file_and_opens_browser(tmp_path, monkeypatch):
    import pmf_evals.comparison_page as cp

    opened = {}
    monkeypatch.setattr("webbrowser.open", lambda url: opened.setdefault("url", url))
    monkeypatch.setattr(cp, "PAGE_PATH", tmp_path / "comparison.html")
    cp.open_page()
    assert (tmp_path / "comparison.html").exists()
    assert opened["url"].endswith("comparison.html")


def test_browser_suppressed_by_env(tmp_path, monkeypatch):
    import pmf_evals.comparison_page as cp

    opened = {}
    monkeypatch.setenv("PMF_NO_BROWSER", "1")
    monkeypatch.setattr("webbrowser.open", lambda url: opened.setdefault("url", url))
    monkeypatch.setattr(cp, "PAGE_PATH", tmp_path / "comparison.html")
    cp.open_page()
    assert "url" not in opened  # file written, browser not popped


def test_zz_popup_on_test_run(tmp_path, monkeypatch):
    """THE popup: a plain `pytest` run opens the comparison page.

    This test must sort last (zz prefix) so the page pops after the suite.
    Disable with PMF_NO_BROWSER=1.
    """
    import os

    from pmf_evals.comparison_page import PAGE_PATH, open_page

    if os.environ.get("PMF_NO_BROWSER"):
        pytest.skip("PMF_NO_BROWSER=1 - popup suppressed")
    monkeypatch.setattr("pmf_evals.comparison_page.PAGE_PATH", PAGE_PATH)  # real path
    written = open_page()
    assert written.name == "comparison.html"
