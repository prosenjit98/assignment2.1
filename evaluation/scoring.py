"""Scoring for the evaluation harness. Pure functions, no API calls.

An expected value can be a single label or a list of acceptable labels (used only
where two answers are genuinely defensible; see the notes in data/test_cases.json).
"""

from __future__ import annotations

import statistics

PRIORITY_ORDER = ["Critical", "High", "Medium", "Low"]
SCORE_FIELDS = ["category", "subcategory", "priority", "priority_within_one", "clarification", "full_match"]

# USD per million tokens, keyed by the model ID the server reports. "cached_input" is
# optional and defaults to the input price. Models not listed here report cost as n/a
# (a local server costs nothing per token).
#   "provider/model-name": {"input": 1.00, "output": 4.00, "cached_input": 0.25},
PRICING: dict[str, dict[str, float]] = {}


def accepted(value) -> list:
    return value if isinstance(value, list) else [value]


def score_case(expected: dict, actual: dict | None) -> dict:
    if actual is None:
        return {field: False for field in SCORE_FIELDS}

    category_ok = actual["category"] in accepted(expected["category"])
    # Hierarchical: the subcategory only counts if the category is also right.
    subcategory_ok = category_ok and actual["subcategory"] in accepted(expected["subcategory"])
    priority_ok = actual["priority"] in accepted(expected["priority"])
    distance = min(
        abs(PRIORITY_ORDER.index(actual["priority"]) - PRIORITY_ORDER.index(p))
        for p in accepted(expected["priority"])
    )
    clarification_ok = actual["needs_clarification"] in accepted(expected["needs_clarification"])
    return {
        "category": category_ok,
        "subcategory": subcategory_ok,
        "priority": priority_ok,
        "priority_within_one": distance <= 1,
        "clarification": clarification_ok,
        "full_match": category_ok and subcategory_ok and priority_ok and clarification_ok,
    }


def _rate(rows: list[dict], field: str) -> float | None:
    return sum(r["scores"][field] for r in rows) / len(rows) if rows else None


def aggregate(rows: list[dict]) -> dict:
    groups = {
        "all": rows,
        "standard": [r for r in rows if r["type"] == "standard"],
        "ambiguous_edge": [r for r in rows if r["type"] != "standard"],
    }
    metrics = {
        name: {"cases": len(group), **{field: _rate(group, field) for field in SCORE_FIELDS}}
        for name, group in groups.items()
    }

    completed = [r for r in rows if r["actual"] is not None]
    llm_rows = [r for r in completed if r["actual"]["meta"]["source"] == "llm"]
    latencies = sorted(r["actual"]["meta"]["latency_ms"] for r in llm_rows)

    return {
        "accuracy": metrics,
        "errors": len(rows) - len(completed),
        "json_valid_rate": len(completed) / len(rows) if rows else None,
        "clarification_detection": _clarification_detection(completed),
        "human_review_rate": (
            sum(r["actual"]["needs_human_review"] for r in completed) / len(completed) if completed else None
        ),
        "latency_ms": {
            "mean": round(statistics.mean(latencies)) if latencies else None,
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
        },
        "usage": _usage_and_cost(llm_rows),
        "category_confusion": _confusion(completed),
    }


def _clarification_detection(rows: list[dict]) -> dict:
    """Precision/recall for flagging needs_clarification, over cases with a single expected value."""
    tp = fp = fn = 0
    for r in rows:
        expected = r["expected"]["needs_clarification"]
        if isinstance(expected, list):
            continue
        predicted = r["actual"]["needs_clarification"]
        tp += expected and predicted
        fp += predicted and not expected
        fn += expected and not predicted
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"true_positives": tp, "false_positives": fp, "false_negatives": fn, "precision": precision, "recall": recall}


def _percentile(sorted_values: list[float], pct: int) -> int | None:
    if not sorted_values:
        return None
    index = round((pct / 100) * (len(sorted_values) - 1))
    return round(sorted_values[index])


def _usage_and_cost(llm_rows: list[dict]) -> dict:
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    cost = 0.0
    priced = True
    for r in llm_rows:
        usage = r["actual"]["meta"]["usage"]
        for key in totals:
            totals[key] += usage[key]
        price = PRICING.get(r["actual"]["meta"]["model"])
        if price is None:
            priced = False
            continue
        # input_tokens includes the cached ones.
        cached = usage["cached_input_tokens"]
        cost += (
            (usage["input_tokens"] - cached) * price["input"]
            + cached * price.get("cached_input", price["input"])
            + usage["output_tokens"] * price["output"]
        ) / 1_000_000
    return {**totals, "estimated_cost_usd": round(cost, 4) if priced else None}


def _confusion(rows: list[dict]) -> dict:
    """expected -> actual -> count. When several categories were acceptable and the
    model chose one of them, that counts as on the diagonal."""
    matrix: dict[str, dict[str, int]] = {}
    for r in rows:
        actual = r["actual"]["category"]
        options = accepted(r["expected"]["category"])
        expected = actual if actual in options else options[0]
        matrix.setdefault(expected, {}).setdefault(actual, 0)
        matrix[expected][actual] += 1
    return matrix
