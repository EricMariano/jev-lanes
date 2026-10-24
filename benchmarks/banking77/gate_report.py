"""Replay recorded Jev answers through the confidence gate and write a Markdown report.

    python benchmarks/banking77/gate_report.py --first test --clarify clarify-test \
        --out benchmarks/results/banking77/gate-report.md

Policies, all deciding with the same Jev answers (nothing is called here):

- always act: do what Jev's route says, whatever the confidence.
- gate, no questions: act only if confidence >= threshold, otherwise decline.
- gate + k questions: below the threshold ask the (simulated) customer, classify the
  conversation again, and act as soon as confidence reaches the threshold, up to k times.

"Act" means running the tool of the classified route. The primary threshold is frozen in
config.py; the sweep over other thresholds is descriptive.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from config import CLARIFY_QUESTION, CLARIFY_ROUNDS, GATE_GRID, PRIMARY_THRESHOLD
from report import frac

RESULTS = Path(__file__).resolve().parents[1] / "results" / "banking77"


def load_jsonl(name: str) -> list[dict]:
    path = RESULTS / f"{name}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def decide(row: dict, clar: dict | None, threshold: float, rounds: int) -> tuple[str | None, int]:
    """Return (route acted on or None if declined, questions asked)."""
    if row["jev_confidence"] >= threshold:
        return row["jev_route"], 0
    for asked in range(1, rounds + 1):
        if clar is None:
            break
        if clar[f"r{asked}_confidence"] >= threshold:
            return clar[f"r{asked}_route"], asked
    return None, rounds if clar is not None else 0


def score(rows: list[dict], clars: dict[str, dict], threshold: float, rounds: int) -> dict:
    out = dict(
        n=len(rows),
        acted=0,
        correct=0,
        wrong=0,
        unsupported=0,
        declined_in=0,
        declined_out=0,
        questions=0,
        asked=0,
        late_acts=0,
        late_correct=0,
        late_wrong=0,
        late_unsupported=0,
    )
    for row in rows:
        route, asked = decide(row, clars.get(row["id"]), threshold, rounds)
        out["questions"] += asked
        out["asked"] += asked > 0
        if route is None:
            out["declined_in" if row["route"] else "declined_out"] += 1
            continue
        out["acted"] += 1
        good = row["route"] is not None and route == row["route"]
        out["correct"] += good
        out["wrong"] += row["route"] is not None and not good
        out["unsupported"] += row["route"] is None
        if asked:  # acted only after the customer was asked
            out["late_acts"] += 1
            out["late_correct"] += good
            out["late_wrong"] += row["route"] is not None and not good
            out["late_unsupported"] += row["route"] is None
    out["harm"] = out["wrong"] + out["unsupported"]
    return out


def outcome(row: dict, clars: dict[str, dict], threshold: float, rounds: int) -> tuple[int, int]:
    """(served correctly, harmful act) for one case, as 0/1."""
    route, _ = decide(row, clars.get(row["id"]), threshold, rounds)
    if route is None:
        return 0, 0
    good = row["route"] is not None and route == row["route"]
    return int(good), int(not good)


def harm_matched_baseline(rows: list[dict], clars: dict[str, dict], budget: int) -> float:
    """Threshold of the no-question gate that serves most customers with harm <= budget.

    Searches every distinct first-pass confidence, so it is the best a plain gate can do by
    lowering its threshold; ties go to the higher threshold.
    """
    best = (-1, 0.0)
    for threshold in sorted({r["jev_confidence"] for r in rows}):
        s = score(rows, clars, threshold, 0)
        if s["harm"] <= budget:
            best = max(best, (s["correct"], threshold))
    return best[1] if best[0] >= 0 else 1.0


def paired_bootstrap(
    rows: list[dict],
    clars: dict[str, dict],
    a: tuple[float, int],
    b: tuple[float, int],
    *,
    draws: int = 2000,
    seed: int = 0,
) -> dict:
    """95% interval of (A - B) in served-correctly and harmful acts, resampling cases.

    Policies are fixed beforehand (threshold, questions), so the interval does not include
    the uncertainty of having chosen B's threshold on the same data.
    """
    pa = [outcome(r, clars, *a) for r in rows]
    pb = [outcome(r, clars, *b) for r in rows]
    rng = random.Random(seed)
    n = len(rows)
    served, harm = [], []
    for _ in range(draws):
        picks = [rng.randrange(n) for _ in range(n)]
        served.append(sum(pa[i][0] - pb[i][0] for i in picks))
        harm.append(sum(pa[i][1] - pb[i][1] for i in picks))
    served.sort()
    harm.sort()
    low, high = int(0.025 * draws), int(0.975 * draws) - 1
    return dict(
        served=(sum(x[0] for x in pa) - sum(x[0] for x in pb), served[low], served[high]),
        harm=(sum(x[1] for x in pa) - sum(x[1] for x in pb), harm[low], harm[high]),
    )


def table_row(label: str, s: dict) -> str:
    return (
        f"| {label} | {s['correct']} | {s['harm']} ({s['wrong']} + {s['unsupported']}) | "
        f"{s['declined_in']} | {s['declined_out']} | "
        f"{s['asked']} ({100 * s['asked'] / s['n']:.1f}%) | {s['questions']} |"
    )


HEADER = (
    "| Policy | Served correctly | Harmful acts (wrong route + unsupported) | "
    "Declined in-scope | Declined held-out | Customers asked | Questions asked |\n"
    "|---|---|---|---|---|---|---|"
)


def build(first_name: str, clarify_name: str) -> str:
    first = [r for r in load_jsonl(first_name) if not r["jev_error"]]
    clar_all = load_jsonl(clarify_name)
    clars = {
        r["id"]: r
        for r in clar_all
        if not any(r[f"r{k}_error"] for k in range(1, CLARIFY_ROUNDS + 1))
    }
    needs = [r for r in first if r["jev_confidence"] < 1.0]
    # A case that could need a question but has no clean clarification record is left out of
    # every policy, so all policies are compared on the same cases.
    rows = [r for r in first if r["jev_confidence"] >= 1.0 or r["id"] in clars]
    missing = len(first) - len(rows)
    in_scope = sum(bool(r["route"]) for r in rows)
    L: list[str] = []
    add = L.append

    add("# Confidence gate on Banking77")
    add("")
    add(
        "Replays recorded Jev answers through the gate policy of `GatedAgent`. Public data "
        "(Banking77, PolyAI, CC BY 4.0), routes and held-out intents fixed in `config.py`. "
        "**The simulated customer is optimistic; read the limitations before quoting a number.**"
    )
    add("")
    add("## Setup")
    add("")
    add(
        f"- Cases: {len(rows)} ({in_scope} in-scope, {len(rows) - in_scope} held-out with no correct route)."
    )
    add(
        f"- Cases below confidence 1.0 (could need a question): {len(needs)}; left out because a "
        f"clarification call failed or is missing: {missing} (the same cases are left out of every policy)."
    )
    add(f"- The agent's question is always: “{CLARIFY_QUESTION}”")
    add(
        "- The simulated reply is another Banking77 train message of the same intent, so it "
        "restates the problem in new words instead of answering the question. Jev then classifies "
        "the whole conversation (customer and assistant turns)."
    )
    add(
        f"- Questions are limited to {CLARIFY_ROUNDS} per case; a case still below the threshold is declined."
    )
    add(
        f"- Primary threshold, frozen in `config.py` before any clarification call: {PRIMARY_THRESHOLD}."
    )
    add("- A harmful act is an action on the wrong route, or any action on a held-out message.")
    add("")

    add(f"## Primary comparison at threshold {PRIMARY_THRESHOLD}")
    add("")
    add(HEADER)
    always = score(rows, clars, 0.0, 0)
    add(table_row("always act", always))
    base = score(rows, clars, PRIMARY_THRESHOLD, 0)
    add(table_row("gate, no questions", base))
    one = score(rows, clars, PRIMARY_THRESHOLD, 1)
    add(table_row("gate + 1 question", one))
    two = score(rows, clars, PRIMARY_THRESHOLD, CLARIFY_ROUNDS)
    add(table_row(f"gate + {CLARIFY_ROUNDS} questions", two))
    add("")
    add(
        "“Served correctly” counts in-scope messages whose classified route is the right one. "
        "Declining a held-out message is the right outcome; declining an in-scope one is a "
        "customer who was not served."
    )
    add("")

    add("### What the questions bought")
    add("")
    for label, s in (("1 question", one), (f"{CLARIFY_ROUNDS} questions", two)):
        gained = s["correct"] - base["correct"]
        extra_harm = s["harm"] - base["harm"]
        add(
            f"- With {label}: {s['late_acts']} cases were acted on only after being asked; "
            f"{frac(s['late_correct'], s['late_acts'])} of those were the right action "
            f"(+{gained} served correctly, {extra_harm:+d} harmful acts, "
            f"{s['questions']} questions in total)."
        )
    first_pass = base["acted"]
    add(
        f"- For comparison, the first-pass acts (no question needed): "
        f"{frac(base['correct'], first_pass)} right."
    )
    add(
        f"- Of the {two['late_acts']} cases acted on after questions: {two['late_correct']} "
        f"right, {two['late_wrong']} on the wrong route, {two['late_unsupported']} on "
        f"held-out messages (nothing correct to do)."
    )
    add("")

    add("### Is asking better than lowering the threshold?")
    add("")
    add(
        "*Added after the first replay, as a control; not part of the frozen design.* A plain "
        "gate can also serve more customers by lowering its threshold, at the price of more "
        "harmful acts. For each gate that asks (2 questions), the table gives the plain gate "
        "with the highest served count whose harmful acts do not exceed it. Intervals come "
        "from resampling cases (2000 draws) with both policies fixed beforehand."
    )
    add("")
    add(
        "| Asking gate (threshold, 2 q) | Served / harm | Plain gate at the same harm budget "
        "(threshold) | Served / harm | Δ served (95% CI) | Δ harm (95% CI) |"
    )
    add("|---|---|---|---|---|---|")
    for threshold in GATE_GRID:
        ask = score(rows, clars, threshold, CLARIFY_ROUNDS)
        match = harm_matched_baseline(rows, clars, ask["harm"])
        plain = score(rows, clars, match, 0)
        ci = paired_bootstrap(rows, clars, (threshold, CLARIFY_ROUNDS), (match, 0))
        (ds, dsl, dsh), (dh, dhl, dhh) = ci["served"], ci["harm"]
        marker = " (primary)" if threshold == PRIMARY_THRESHOLD else ""
        add(
            f"| {threshold}{marker} | {ask['correct']} / {ask['harm']} | {match} | "
            f"{plain['correct']} / {plain['harm']} | {ds:+d} ({dsl:+d} to {dsh:+d}) | "
            f"{dh:+d} ({dhl:+d} to {dhh:+d}) |"
        )
    add("")

    add("## Sweep over thresholds (descriptive, not used for selection)")
    add("")
    add(
        "For each threshold: served correctly / harmful acts. The gate only helps if asking moves "
        "a row toward more served at the same or fewer harmful acts."
    )
    add("")
    add("| Threshold | No questions | 1 question | 2 questions | Customers asked (2 q) |")
    add("|---|---|---|---|---|")
    for threshold in GATE_GRID:
        cells = [score(rows, clars, threshold, k) for k in (0, 1, CLARIFY_ROUNDS)]
        add(
            f"| {threshold} | "
            + " | ".join(f"{c['correct']} / {c['harm']}" for c in cells)
            + f" | {cells[2]['asked']} |"
        )
    add("")
    add(f"Always act: {always['correct']} served correctly / {always['harm']} harmful acts.")
    add("")

    add("## Limitations")
    add("")
    add(
        "- **The customer is simulated and helpful.** Real replies to a question may add nothing, "
        "go off topic or not come at all; here every reply is a fluent message of the right "
        "intent. Treat the gain as an upper bound."
    )
    add(
        "- **Part of the gain may be a second look, not a better question.** Jev sees one more "
        "message of the same intent; no control separates the value of asking from the value "
        "of more text."
    )
    add(
        "- **Only the gate is evaluated.** The agent's language model (which tool it proposes, "
        "its question wording, its use of the answer) is not in the loop, and no tool runs."
    )
    add(
        "- One dataset, English only, one run, one simulated reply per case and round, no repeated draws."
    )
    add(
        "- Held-out messages stand for requests the desk cannot serve; their share "
        f"({100 * (len(rows) - in_scope) / len(rows):.0f}%) is a design choice."
    )
    add("- Banking77 labels are ambiguous in places; a “wrong route” may be a defensible one.")
    add("- Confidence is a distribution statistic, not an accuracy guarantee.")
    add("")
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--first", default="test")
    parser.add_argument("--clarify", default="clarify-test")
    parser.add_argument("--out", default=str(RESULTS / "gate-report.md"))
    args = parser.parse_args()
    Path(args.out).write_text(build(args.first, args.clarify) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
