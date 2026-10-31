"""Flip report: compare two result sets and surface which tasks flipped.

Per the Anthropic doctrine: don't just compare aggregate scores — look at
which tasks flipped, because a fold can lower latency while silently breaking
a process that was passing.
"""

from __future__ import annotations


def _index(rows: list[dict]) -> dict[str, dict]:
    return {r["scenario_id"]: r for r in rows}


def _summary(rows: list[dict]) -> dict:
    n = len(rows) or 1
    passes = sum(1 for r in rows if r["verdict"] in ("pass", "figures_only"))
    return {
        "pass_rate": passes / n,
        "mean_latency_ms": sum(r["latency_ms"] for r in rows) / n,
        "mean_cost_usd": sum(r["cost_usd"] for r in rows) / n,
    }


def compare(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """Compare two graded result lists. Raises ValueError on scenario mismatch."""
    a, b = _index(rows_a), _index(rows_b)
    if set(a) != set(b):
        missing_a = sorted(set(b) - set(a))
        missing_b = sorted(set(a) - set(b))
        raise ValueError(
            f"scenario mismatch: only-in-b={missing_a} only-in-a={missing_b}"
        )

    flipped = {
        sid: f"{a[sid]['verdict']}->{b[sid]['verdict']}"
        for sid in sorted(a)
        if a[sid]["verdict"] != b[sid]["verdict"]
    }
    return {
        "verdicts": {
            "a": {sid: a[sid]["verdict"] for sid in sorted(a)},
            "b": {sid: b[sid]["verdict"] for sid in sorted(b)},
        },
        "flipped": flipped,
        "summary": {"a": _summary(rows_a), "b": _summary(rows_b)},
    }
