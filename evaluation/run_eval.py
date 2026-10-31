"""Run the test cases through the live classifier and write expected-vs-actual reports.

    python -m evaluation.run_eval                   # all test cases
    python -m evaluation.run_eval --ids TC01,TC23   # a subset
    python -m evaluation.run_eval --update-readme   # also refresh the summary in README.md

Writes results.json, results.csv, EVALUATION.md and prompt_used.md to evaluation/results/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from classifier import ClassificationError, ConfigurationError, TextClassifier
from classifier.taxonomy import PROJECT_ROOT
from evaluation.scoring import accepted, aggregate, score_case

DEFAULT_CASES = PROJECT_ROOT / "data" / "test_cases.json"
DEFAULT_OUT = PROJECT_ROOT / "evaluation" / "results"
README = PROJECT_ROOT / "README.md"
README_START = "<!-- EVAL-SUMMARY:START -->"
README_END = "<!-- EVAL-SUMMARY:END -->"


def load_cases(path: Path, ids: list[str] | None = None) -> list[dict]:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if ids:
        wanted = set(ids)
        cases = [c for c in cases if c["id"] in wanted]
        missing = wanted - {c["id"] for c in cases}
        if missing:
            raise SystemExit(f"Unknown test case ids: {', '.join(sorted(missing))}")
    return cases


def run_case(classifier: TextClassifier, case: dict) -> dict:
    row = {key: case[key] for key in ("id", "type", "text", "expected", "notes")}
    try:
        row["actual"], row["error"] = classifier.classify(case["text"]), None
    except ConfigurationError:
        raise
    except (ClassificationError, ValueError) as exc:
        row["actual"], row["error"] = None, str(exc)
    row["scores"] = score_case(case["expected"], row["actual"])
    return row


def run_cases(classifier: TextClassifier, cases: list[dict], workers: int) -> list[dict]:
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(lambda case: run_case(classifier, case), cases):
            print(_progress_line(row), flush=True)
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Test case file (JSON)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Directory for the reports")
    parser.add_argument("--ids", help="Comma-separated test case ids to run")
    parser.add_argument("--workers", type=int, default=4, help="Parallel requests (default 4)")
    parser.add_argument("--update-readme", action="store_true", help="Refresh the results summary in README.md")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(PROJECT_ROOT / ".env")

    cases = load_cases(args.cases, args.ids.split(",") if args.ids else None)
    classifier = TextClassifier()
    print(f"Running {len(cases)} test cases against {classifier.model or '(no model set)'} at {classifier.base_url}\n")
    try:
        rows = run_cases(classifier, cases, args.workers)
    except ConfigurationError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 2

    metrics = aggregate(rows)
    run_info = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requested_model": classifier.model,
        "base_url": classifier.base_url,
        "served_models": sorted(
            {r["actual"]["meta"]["model"] for r in rows if r["actual"] and r["actual"]["meta"]["source"] == "llm"}
        ),
        "effort": classifier.effort or "default",
        "response_format": classifier.response_format,
        "prompt_sha256": hashlib.sha256(classifier.system_prompt.encode("utf-8")).hexdigest()[:12],
        "cases_file": _relative(args.cases),
        "cases": len(rows),
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(
        json.dumps({"run": run_info, "metrics": metrics, "results": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_csv(args.out / "results.csv", rows)
    (args.out / "prompt_used.md").write_text(classifier.system_prompt + "\n", encoding="utf-8")
    (args.out / "EVALUATION.md").write_text(
        render_report(run_info, metrics, rows, classifier.taxonomy.category_names), encoding="utf-8"
    )
    if args.update_readme:
        update_readme(run_info, metrics)

    acc = metrics["accuracy"]["all"]
    print(
        f"\nCategory {_pct(acc['category'])} | Subcategory {_pct(acc['subcategory'])} | "
        f"Priority {_pct(acc['priority'])} | All fields {_pct(acc['full_match'])} | Errors {metrics['errors']}"
    )
    print(f"Reports written to {_relative(args.out)}")
    return 0


# ---------------------------------------------------------------- reporting


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _fmt(value) -> str:
    if isinstance(value, list):
        return " or ".join(_fmt(v) for v in value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _cell(text: str, limit: int | None = None) -> str:
    text = " ".join(str(text).split()) or "(empty)"
    if limit and len(text) > limit:
        text = text[: limit - 1] + "…"
    return text.replace("|", "\\|")


def _relative(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _labels(result: dict) -> str:
    return f"{_fmt(result['category'])} / {_fmt(result['subcategory'])} / {_fmt(result['priority'])}"


def _progress_line(row: dict) -> str:
    if row["actual"] is None:
        return f"{row['id']:<5} ERROR {row['error']}"
    status = "PASS" if row["scores"]["full_match"] else "FAIL"
    return f"{row['id']:<5} {status}  {_labels(row['actual'])}   (expected {_labels(row['expected'])})"


def summary_table(metrics: dict) -> str:
    acc = metrics["accuracy"]
    groups = [acc["all"], acc["standard"], acc["ambiguous_edge"]]
    lines = [
        f"| Metric | All ({groups[0]['cases']}) | Standard ({groups[1]['cases']}) | Ambiguous / edge ({groups[2]['cases']}) |",
        "|---|---|---|---|",
    ]
    for label, field in [
        ("Category accuracy", "category"),
        ("Subcategory accuracy (category also correct)", "subcategory"),
        ("Priority, exact match", "priority"),
        ("Priority, within one level", "priority_within_one"),
        ("Clarification flag correct", "clarification"),
        ("**All fields correct**", "full_match"),
    ]:
        lines.append(f"| {label} | " + " | ".join(_pct(g[field]) for g in groups) + " |")

    clar = metrics["clarification_detection"]
    usage = metrics["usage"]
    cost = usage["estimated_cost_usd"]
    lines += [
        "",
        "| Operational metric | Value |",
        "|---|---|",
        f"| Valid structured JSON responses | {_pct(metrics['json_valid_rate'])} ({metrics['errors']} errors) |",
        f"| Clarification detection, precision / recall | {_pct(clar['precision'])} / {_pct(clar['recall'])} |",
        f"| Results flagged for human review | {_pct(metrics['human_review_rate'])} |",
        f"| Latency per message, mean / p50 / p95 | {metrics['latency_ms']['mean']} / {metrics['latency_ms']['p50']} / {metrics['latency_ms']['p95']} ms |",
        f"| Tokens (input, of which cached / output) | {usage['input_tokens']:,}, {usage['cached_input_tokens']:,} / {usage['output_tokens']:,} |",
        f"| Estimated cost for the run | {'n/a' if cost is None else f'${cost:.2f}'} |",
    ]
    return "\n".join(lines)


def render_report(run_info: dict, metrics: dict, rows: list[dict], category_order: list[str]) -> str:
    served = ", ".join(run_info["served_models"]) or "n/a"
    out = [
        "# Evaluation Results",
        "",
        "<!-- Generated by `python -m evaluation.run_eval`. Re-run to refresh. -->",
        "",
        f"- **Run:** {run_info['timestamp']}",
        f"- **Model:** `{run_info['requested_model']}` (served by: {served}), effort `{run_info['effort']}`",
        f"- **Endpoint:** `{run_info.get('base_url', 'n/a')}`, response format `{run_info.get('response_format', 'n/a')}`",
        f"- **Prompt version:** `{run_info['prompt_sha256']}` (SHA-256 prefix of [prompt_used.md](prompt_used.md))",
        f"- **Test cases:** {run_info['cases']} from `{run_info['cases_file']}`",
        "",
        "## Summary",
        "",
        summary_table(metrics),
        "",
        "Scoring: a field is correct when the model's label is one of the expected labels. Most cases have one",
        "expected label; a few accept two where both are defensible (the notes explain why). Subcategory only",
        "counts as correct when the category is also correct.",
        "",
        "## Category confusion matrix",
        "",
        "Rows are the expected category, columns the model's category.",
        "",
    ]
    out += _confusion_table(metrics["category_confusion"], category_order)
    out += [
        "",
        "## Expected vs actual",
        "",
        "| ID | Type | Message | Expected (category / subcategory / priority) | Actual | Cat | Sub | Pri | Clarify | Result |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    tick = {True: "✅", False: "❌"}
    for r in rows:
        s = r["scores"]
        actual = _cell(_labels(r["actual"])) if r["actual"] else f"ERROR: {_cell(r['error'], 60)}"
        if r["actual"] and r["actual"]["needs_clarification"]:
            actual += " (asks to clarify)"
        out.append(
            f"| {r['id']} | {r['type']} | {_cell(r['text'], 70)} | {_cell(_labels(r['expected']))} | {actual} | "
            f"{tick[s['category']]} | {tick[s['subcategory']]} | {tick[s['priority']]} | {tick[s['clarification']]} | "
            f"{'PASS' if s['full_match'] else '**FAIL**'} |"
        )

    out += ["", "## Ambiguous and edge cases: what the model said", ""]
    for r in rows:
        if r["type"] == "standard" or r["actual"] is None:
            continue
        a = r["actual"]
        out += [f"**{r['id']}** ({r['type']}): {_cell(r['text'], 160)}", ""]
        out.append(f"- Result: {_labels(a)}, confidence {a['confidence']}, source `{a['meta']['source']}`")
        if a["secondary_categories"]:
            out.append(f"- Secondary teams: {', '.join(a['secondary_categories'])}")
        if a["clarifying_question"]:
            out.append(f"- Clarifying question: \"{a['clarifying_question']}\"")
        out.append(f"- Rationale: {a['rationale']}")
        out.append(f"- Why this case is in the suite: {r['notes']}")
        out.append("")

    failures = [r for r in rows if not r["scores"]["full_match"]]
    out += ["## Mismatches", ""]
    if not failures:
        out.append("None: every case matched on all fields.")
    for r in failures:
        wrong = [f for f in ("category", "subcategory", "priority", "clarification") if not r["scores"][f]]
        out += [f"### {r['id']}: wrong {', '.join(wrong) or 'n/a'}", "", f"> {_cell(r['text'])}", ""]
        out.append(f"- Expected: {_labels(r['expected'])}, needs clarification: {_fmt(r['expected']['needs_clarification'])}")
        if r["actual"] is None:
            out.append(f"- Error: {r['error']}")
        else:
            a = r["actual"]
            out.append(
                f"- Actual: {_labels(a)}, needs clarification: {_fmt(a['needs_clarification'])}, confidence {a['confidence']}"
            )
            out.append(f"- Model rationale: {a['rationale']}")
        out.append(f"- Test notes: {r['notes']}")
        out.append("")
    return "\n".join(out)


def _confusion_table(matrix: dict, order: list[str]) -> list[str]:
    present = {c for c in matrix} | {a for row in matrix.values() for a in row}
    labels = [c for c in order if c in present]
    lines = ["| Expected \\ Actual | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for expected in labels:
        if expected not in matrix:
            continue
        counts = [str(matrix[expected].get(actual, "")) or "·" for actual in labels]
        lines.append(f"| **{expected}** | " + " | ".join(counts) + " |")
    return lines


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "id", "type", "text",
        "expected_category", "expected_subcategory", "expected_priority", "expected_needs_clarification",
        "actual_category", "actual_subcategory", "actual_priority", "actual_needs_clarification",
        "confidence", "secondary_categories", "clarifying_question", "rationale",
        "category_ok", "subcategory_ok", "priority_ok", "clarification_ok", "full_match",
        "latency_ms", "error",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            e, a, s = r["expected"], r["actual"] or {}, r["scores"]
            writer.writerow({
                "id": r["id"],
                "type": r["type"],
                "text": r["text"],
                **{f"expected_{k}": " | ".join(map(str, accepted(e[k]))) for k in
                   ("category", "subcategory", "priority", "needs_clarification")},
                **{f"actual_{k}": a.get(k, "") for k in ("category", "subcategory", "priority", "needs_clarification")},
                "confidence": a.get("confidence", ""),
                "secondary_categories": ", ".join(a.get("secondary_categories", [])),
                "clarifying_question": a.get("clarifying_question") or "",
                "rationale": a.get("rationale", ""),
                "category_ok": s["category"],
                "subcategory_ok": s["subcategory"],
                "priority_ok": s["priority"],
                "clarification_ok": s["clarification"],
                "full_match": s["full_match"],
                "latency_ms": a.get("meta", {}).get("latency_ms", ""),
                "error": r["error"] or "",
            })


def update_readme(run_info: dict, metrics: dict, readme: Path = README) -> None:
    text = readme.read_text(encoding="utf-8")
    start, end = text.find(README_START), text.find(README_END)
    if start == -1 or end == -1:
        print(f"warning: summary markers not found in {readme.name}; README not updated", file=sys.stderr)
        return
    block = "\n".join([
        README_START,
        f"Last run: {run_info['timestamp']}, model `{run_info['requested_model']}`, effort `{run_info['effort']}`, "
        f"prompt `{run_info['prompt_sha256']}`, {run_info['cases']} test cases.",
        "",
        summary_table(metrics),
        "",
        "Per-case expected vs actual results, the confusion matrix and every mismatch are in "
        "[evaluation/results/EVALUATION.md](evaluation/results/EVALUATION.md).",
    ])
    readme.write_text(text[:start] + block + "\n" + text[end:], encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
