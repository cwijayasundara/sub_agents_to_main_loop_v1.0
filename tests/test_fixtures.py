import datetime as dt

from pmf_evals.fixtures import (
    SHIPPED_ANCHOR,
    anchor,
    load_dataset,
    platform_names,
    shift_dataset,
    window_totals,
)


def test_load_dataset_is_deterministic_and_complete():
    a = load_dataset()
    b = load_dataset()
    assert a == b  # no randomness across calls
    assert set(platform_names()) == {"google_ads", "meta_ads", "reddit_ads"}
    for platform, rows in a.items():
        assert len(rows) >= 42  # >= 6 weeks of daily rows
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates)
        assert dates[-1] == SHIPPED_ANCHOR
        for r in rows:
            assert r["spend"] > 0 and r["conversions"] >= 0 and r["clicks"] > 0


def test_shift_dataset_moves_dates_and_preserves_totals():
    ds = load_dataset()
    offset = dt.timedelta(days=37)
    shifted = shift_dataset(ds, offset)
    for platform in ds:
        assert shifted[platform][0]["date"] == ds[platform][0]["date"] + offset
        total_before = sum(r["spend"] for r in ds[platform])
        total_after = sum(r["spend"] for r in shifted[platform])
        assert total_before == total_after


def test_window_totals_exact():
    ds = load_dataset()
    window = (dt.date(2026, 8, 24), dt.date(2026, 8, 30))
    totals = window_totals(ds, "google_ads", window)
    manual = sum(
        r["spend"]
        for r in ds["google_ads"]
        if window[0] <= r["date"] <= window[1]
    )
    assert totals["spend"] == manual
    assert totals["cpa"] == round(totals["spend"] / totals["conversions"], 2)


def test_anchor_env_override(monkeypatch):
    monkeypatch.setenv("PMF_FIXTURE_ANCHOR", "2026-11-01")
    assert anchor() == dt.date(2026, 11, 1)
    monkeypatch.delenv("PMF_FIXTURE_ANCHOR")
    assert anchor() == dt.date.today() - dt.timedelta(days=2)


def test_shape_has_movers():
    """One platform spikes in the last week, one dips — grader scenarios need movers."""
    ds = load_dataset()
    # windows end at the anchor so both weeks are fully covered
    last = (SHIPPED_ANCHOR - dt.timedelta(days=6), SHIPPED_ANCHOR)
    prior = (SHIPPED_ANCHOR - dt.timedelta(days=13), SHIPPED_ANCHOR - dt.timedelta(days=7))
    g_last = window_totals(ds, "google_ads", last)["spend"]
    g_prior = window_totals(ds, "google_ads", prior)["spend"]
    m_last = window_totals(ds, "meta_ads", last)["spend"]
    m_prior = window_totals(ds, "meta_ads", prior)["spend"]
    assert g_last > g_prior * 1.15  # google spikes
    assert m_last < m_prior  # meta dips
