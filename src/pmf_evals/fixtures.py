"""Deterministic synthetic fixture data for the paid media eval harness.

No network, no credentials, synthetic only (adopted from the PMA repo's rule).
Rows are generated against a fixed SHIPPED_ANCHOR; at runtime the dataset is
date-shifted to the current anchor so questions like "last week vs the week
before" always have data. Window totals are shift-invariant, so ground-truth
figures are stable across days.
"""

from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache

SHIPPED_ANCHOR = dt.date(2026, 8, 28)
"""The dataset always ends on this date before shifting."""

PLATFORMS = ("google_ads", "meta_ads", "reddit_ads")

_N_DAYS = 56  # 8 weeks of daily rows

# Per-platform weekly baselines: (spend, clicks, conversions)
_BASELINES = {
    "google_ads": (5000.0, 2200.0, 26.0),
    "meta_ads": (3500.0, 1500.0, 18.0),
    "reddit_ads": (700.0, 350.0, 4.5),
}

# Last-week multipliers that guarantee "movers" for the golden scenarios:
# google spikes hard, meta dips, reddit stays flat.
_LAST_WEEK_MULTIPLIER = {
    "google_ads": 1.45,
    "meta_ads": 0.78,
    "reddit_ads": 1.0,
}

_START = SHIPPED_ANCHOR - dt.timedelta(days=_N_DAYS - 1)  # 2026-07-04
_LAST_WEEK_START = SHIPPED_ANCHOR - dt.timedelta(days=6)  # 2026-08-22


def anchor() -> dt.date:
    """Runtime anchor: PMF_FIXTURE_ANCHOR env (ISO date) or today - 2 days."""
    raw = os.environ.get("PMF_FIXTURE_ANCHOR")
    if raw:
        return dt.date.fromisoformat(raw)
    return dt.date.today() - dt.timedelta(days=2)


def shipped_offset() -> dt.timedelta:
    """Offset to apply to shipped dates so the dataset ends at the runtime anchor."""
    return anchor() - SHIPPED_ANCHOR


def _day_spend(platform: str, day: dt.date) -> float:
    base, _, _ = _BASELINES[platform]
    # deterministic weekday pattern: weekends spend less
    weekday = day.weekday()  # Mon=0 .. Sun=6
    weekend_dip = 0.7 if weekday >= 5 else 1.0
    # slow drift over the 8 weeks so trends exist
    week_index = (day - _START).days // 7
    drift = 1.0 + 0.03 * week_index
    # cheap deterministic jitter (no random module state to keep totals stable)
    jitter = 1.0 + ((day.day * 37 + len(platform) * 11) % 13 - 6) / 100.0
    spend = base / 7.0 * weekend_dip * drift * jitter
    if day >= _LAST_WEEK_START:
        spend *= _LAST_WEEK_MULTIPLIER[platform]
    return round(spend, 2)


def _day_row(platform: str, day: dt.date) -> dict:
    _, clicks_base, conv_base = _BASELINES[platform]
    spend = _day_spend(platform, day)
    scale = spend / (_BASELINES[platform][0] / 7.0)
    clicks = round(clicks_base / 7.0 * scale, 0)
    conversions = round(conv_base / 7.0 * scale, 0)
    return {
        "date": day,
        "spend": spend,
        "clicks": int(clicks),
        "conversions": int(conversions),
    }


@lru_cache(maxsize=1)
def load_dataset() -> dict[str, list[dict]]:
    """Platform -> list of daily rows (ascending by date), ending at SHIPPED_ANCHOR."""
    dataset: dict[str, list[dict]] = {}
    for platform in PLATFORMS:
        dataset[platform] = [
            _day_row(platform, _START + dt.timedelta(days=i)) for i in range(_N_DAYS)
        ]
    return dataset


def platform_names() -> tuple[str, ...]:
    return PLATFORMS


def shift_dataset(
    dataset: dict[str, list[dict]], offset: dt.timedelta
) -> dict[str, list[dict]]:
    """Copy of the dataset with every row date moved by `offset` (totals invariant)."""
    shifted: dict[str, list[dict]] = {}
    for platform, rows in dataset.items():
        shifted[platform] = [{**r, "date": r["date"] + offset} for r in rows]
    return shifted


def window_totals(
    dataset: dict[str, list[dict]], platform: str, window: tuple[dt.date, dt.date]
) -> dict[str, float | None]:
    """Exact spend / conversions / CPA for one platform over one inclusive window."""
    rows = [
        r for r in dataset[platform] if window[0] <= r["date"] <= window[1]
    ]
    spend = round(sum(r["spend"] for r in rows), 2)
    conversions = sum(r["conversions"] for r in rows)
    cpa = round(spend / conversions, 2) if conversions else None
    return {"spend": spend, "conversions": conversions, "cpa": cpa}
