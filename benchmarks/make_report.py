"""ARCHIVED: reports the synthetic smoke battery of the earlier three-lane design (see
smoke_battery.py).

Turn a battery JSON into a Markdown report.

    uv run --no-sync python benchmarks/make_report.py benchmarks/results/<date>-battery.json \
        [--offline path/to/offline-summary.txt] [--notes path/to/notes.md]
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

LABELED = ("clear", "ambiguous", "out_of_scope", "portuguese", "injection")


def hit(row: dict, route: str | None) -> bool:
    return route is not None and route in row["accept"]


def pct(part: int, whole: int) -> str:
    return f"{part}/{whole} ({100 * part / whole:.0f}%)" if whole else "n/a"


def simulate(row: dict, routes: dict) -> tuple[str, str | None]:
    """Apply the policy to recorded answers: returns (lane, decided route or None)."""
    if row["lane"] == "auto":
        return "auto", row["jev_route"]
    if row["lane"] == "llm":
        answer = row["llm_answer"]
        if answer in routes:
            return "llm", answer
        return "human", None  # abstention or unknown route escalates to human review
    return "human", None


def build(data: dict, offline: str | None, notes: str | None) -> str:
    rows, routes = data["rows"], data["routes"]
    lines: list[str] = []
    add = lines.append
    add(f"# Test battery — {data['date']}")
    add("")
    add(
        "Two parts: the offline suite on the Python versions available on the maintainer's "
        "machine, and a small live battery against TypeSafe and "
        f"`{data['fallback_model']}`. **The live battery is not a benchmark**: "
        f"{len(rows)} synthetic cases written by the maintainers, one run, "
        "labels chosen by the maintainers, thresholds not tuned."
    )
    add("")
    add("## 1. Offline suite")
    add("")
    if offline:
        add("```text")
        add(offline.strip())
        add("```")
    else:
        add("_Not included in this report._")
    add("")
    add("## 2. Live battery")
    add("")
    add(
        f"- Fallback model: `{data['fallback_model']}`; lanes: auto ≥ {data['lanes']['auto']}, "
        f"llm ≥ {data['lanes']['llm']}, otherwise human."
    )
    add(f"- Routes: {', '.join(f'`{r}`' for r in routes)}.")
    errors = [r for r in rows if r["jev_error"] or r["llm_error"]]
    add(f"- Calls that raised an error: {len(errors)} of {len(rows)} cases.")
    for r in errors:
        add(f"  - case {r['id']}: {r['jev_error'] or r['llm_error']}")
    add("")

    add("### Jev (TypeSafe) by category")
    add("")
    add("| Category | Cases | Route accepted | Confidence min / mean / max | auto | llm | human |")
    add("|---|---|---|---|---|---|---|")
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    for cat, items in by_cat.items():
        conf = [r["jev_confidence"] for r in items if r["jev_confidence"] is not None]
        lanes = Counter(r["lane"] for r in items)
        accepted = (
            pct(sum(hit(r, r["jev_route"]) for r in items), len(items))
            if r_labeled(cat)
            else "no right answer"
        )
        add(
            f"| {cat} | {len(items)} | {accepted} | "
            f"{min(conf):.2f} / {statistics.mean(conf):.2f} / {max(conf):.2f} | "
            f"{lanes['auto']} | {lanes['llm']} | {lanes['human']} |"
        )
    labeled = [r for r in rows if r["category"] in LABELED]
    add("")
    add(
        f"Jev route accepted on labeled cases: {pct(sum(hit(r, r['jev_route']) for r in labeled), len(labeled))}."
    )
    auto = [r for r in labeled if r["lane"] == "auto"]
    add(
        f"Inside the auto lane: {pct(sum(hit(r, r['jev_route']) for r in auto), len(auto))} accepted."
    )
    wrong_auto = [r for r in auto if not hit(r, r["jev_route"])]
    for r in wrong_auto:
        add(
            f"- Wrong in auto lane — case {r['id']}: `{r['jev_route']}` @ {r['jev_confidence']}, "
            f"accepted {r['accept']}: “{r['text']}”"
        )
    add("")

    add("### Fallback model")
    add("")
    answered = [r for r in rows if r["llm_answer"] is not None]
    abstained = [r for r in rows if r["llm_answer"] is None and not r["llm_error"]]
    unknown = [r for r in answered if r["llm_answer"] not in routes]
    add(
        f"- Answered with a route: {len(answered)}; abstained: {len(abstained)}; "
        f"unknown route: {len(unknown)}."
    )
    lab_answered = [r for r in labeled if r["llm_answer"] is not None]
    add(
        f"- Accepted on labeled cases it answered: "
        f"{pct(sum(hit(r, r['llm_answer']) for r in lab_answered), len(lab_answered))}."
    )
    both = [r for r in rows if r["llm_answer"] is not None and r["jev_route"] is not None]
    agree = [r for r in both if r["llm_answer"] == r["jev_route"]]
    add(
        f"- Agreement with Jev when both answered: {pct(len(agree), len(both))}. "
        "Agreement is not accuracy: both can be wrong in the same way."
    )
    for r in both:
        if r["llm_answer"] != r["jev_route"]:
            add(
                f"  - case {r['id']} disagrees: Jev `{r['jev_route']}` @ {r['jev_confidence']}, "
                f"fallback `{r['llm_answer']}`: “{r['text']}”"
            )
    for r in abstained:
        add(
            f"  - case {r['id']} abstained (Jev `{r['jev_route']}` @ {r['jev_confidence']}, "
            f"lane {r['lane']}): “{r['text']}”"
        )
    add("")

    add("### Policy simulated on the recorded answers")
    add("")
    add(
        "The fallback is applied only to cases in the llm lane; abstentions and unknown routes "
        "go to human review. Human decisions are not simulated: those cases are counted as escalated."
    )
    add("")
    sims = [(r, *simulate(r, routes)) for r in rows]
    decided = [(r, lane, route) for r, lane, route in sims if route is not None]
    escalated = [(r, lane) for r, lane, route in sims if route is None]
    lab_decided = [(r, route) for r, _, route in decided if r["category"] in LABELED]
    add(
        f"- Decided automatically: {len(decided)} of {len(rows)} cases "
        f"({', '.join(f'{k}: {v}' for k, v in Counter(lane for _, lane, _ in decided).items())})."
    )
    add(
        f"- Escalated to human review: {len(escalated)} "
        f"(case ids: {', '.join(str(r['id']) for r, _ in escalated) or 'none'})."
    )
    add(
        f"- Accepted among labeled automatic decisions: "
        f"{pct(sum(hit(r, route) for r, route in lab_decided), len(lab_decided))}."
    )
    add(
        f"- For comparison, Jev alone on labeled cases: "
        f"{pct(sum(hit(r, r['jev_route']) for r in labeled), len(labeled))}; "
        f"fallback alone on labeled cases (abstentions counted as misses): "
        f"{pct(sum(hit(r, r['llm_answer']) for r in labeled), len(labeled))}."
    )
    add("")

    add("### Latency (seconds, single sequential run)")
    add("")
    for name, key in (("Jev (TypeSafe)", "jev_seconds"), ("Fallback model", "llm_seconds")):
        values = [r[key] for r in rows]
        add(f"- {name}: median {statistics.median(values):.2f}, max {max(values):.2f}.")
    add("")

    add("### What this does and does not show")
    add("")
    add("- It shows that both adapters work end to end and which behaviors appear on these cases.")
    add(
        "- It does not estimate accuracy, calibrate thresholds or show that the fallback improves "
        "decisions: the sample is tiny, hand-written, labeled by the maintainers and run once."
    )
    add("")

    if notes:
        add(notes.strip())
        add("")

    add("## Appendix: every case")
    add("")
    add("| # | Category | Text | Jev | Conf. | Lane | Fallback | Accepted |")
    add("|---|---|---|---|---|---|---|---|")
    for r in rows:
        text = r["text"].replace("|", "\\|")
        accepted = ", ".join(r["accept"]) or "—"
        add(
            f"| {r['id']} | {r['category']} | {text} | {r['jev_route']} | "
            f"{r['jev_confidence']:.2f} | {r['lane']} | {r['llm_answer'] or 'ABSTAIN'} | {accepted} |"
        )
    add("")
    return "\n".join(lines)


def r_labeled(category: str) -> bool:
    return category in LABELED


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("battery", type=Path)
    parser.add_argument("--offline", type=Path)
    parser.add_argument("--notes", type=Path)
    args = parser.parse_args()
    data = json.loads(args.battery.read_text())
    offline = args.offline.read_text() if args.offline else None
    out = args.battery.with_suffix(".md")
    notes = args.notes.read_text() if args.notes else None
    out.write_text(build(data, offline, notes))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
