"""Replay recorded answers through the lane policy and write a Markdown report.

    python benchmarks/banking77/report.py --calibration calibration --test test \
        --out benchmarks/results/banking77/report.md

Thresholds are chosen on the calibration file only, with the frozen rule below, and then
applied once to the test file. For a smoke check on a pilot, pass the same name twice
(the numbers are then optimistic by construction and must not be quoted).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from config import ROUTES, TARGET_AUTO_ACCURACY

RESULTS = Path(__file__).resolve().parents[1] / "results" / "banking77"
AUTO_GRID = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 1.0]
LLM_GRID = [0.0, 0.2, 0.4, 0.6, 0.8, 0.9]
# OpenAI pricing page, checked 2026-10-20, USD per 1M tokens; used only for gpt-5-nano.
NANO_PRICE = (0.05, 0.40)


def load(name: str) -> tuple[list[dict], dict]:
    rows = [
        json.loads(line) for line in (RESULTS / f"{name}.jsonl").read_text().splitlines() if line
    ]
    meta = json.loads((RESULTS / f"{name}.meta.json").read_text())
    return rows, meta


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)


def frac(k: int, n: int) -> str:
    if n == 0:
        return "n/a (0 cases)"
    low, high = wilson(k, n)
    return f"{100 * k / n:.1f}% ({k}/{n}; 95% CI {100 * low:.1f}–{100 * high:.1f}%)"


def auroc(positive: list[float], negative: list[float]) -> float:
    """P(score of a random positive > score of a random negative); ties count half."""
    if not positive or not negative:
        return math.nan
    wins = 0.0
    for p in positive:
        for n in negative:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return wins / (len(positive) * len(negative))


def sign_test(fixed: int, broken: int) -> float:
    """Exact two-sided p-value for ``fixed`` vs ``broken`` under a fair coin (McNemar)."""
    n = fixed + broken
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(fixed, broken) + 1)) / 2**n
    return min(1.0, 2 * tail)


def fallback_vs_jev(rows: list[dict]) -> dict:
    """Compare Jev and the fallback on the same in-scope rows (held-out rows have no answer)."""
    scope = [r for r in rows if r["route"]]
    jev_ok = [r["jev_route"] == r["route"] for r in scope]
    llm_ok = [r["llm_answer"] == r["route"] for r in scope]
    return dict(
        n=len(scope),
        jev=sum(jev_ok),
        llm=sum(llm_ok),
        fixed=sum(not j and f for j, f in zip(jev_ok, llm_ok, strict=True)),
        broken=sum(j and not f for j, f in zip(jev_ok, llm_ok, strict=True)),
        abstained=sum(r["llm_answer"] is None for r in scope),
    )


def usable(rows: list[dict]) -> list[dict]:
    """Provider failures are operational errors, never counted as escalations or answers."""
    return [r for r in rows if not r["jev_error"] and not r["llm_error"]]


def replay(row: dict, auto: float, llm: float, fallback: bool) -> tuple[str, str | None]:
    """Return (lane, decided route or None). ``fallback=False`` makes the llm lane escalate."""
    conf = row["jev_confidence"]
    if conf >= auto:
        return "auto", row["jev_route"]
    if fallback and conf >= llm:
        answer = row["llm_answer"]
        return ("llm", answer) if answer in ROUTES else ("llm", None)
    return "human", None


def run_policy(rows: list[dict], auto: float, llm: float, fallback: bool = True) -> dict:
    out = dict(
        n=len(rows),
        decided=0,
        correct=0,
        wrong=0,
        unsupported=0,
        esc_in=0,
        esc_out=0,
        fb_calls=0,
        fb_in=0,
        fb_out=0,
        lanes={"auto": 0, "llm": 0, "human": 0},
    )
    for row in rows:
        lane, route = replay(row, auto, llm, fallback)
        out["lanes"][lane] += 1
        if lane == "llm":
            out["fb_calls"] += 1
            out["fb_in"] += row["llm_input_tokens"]
            out["fb_out"] += row["llm_output_tokens"]
        if route is None:
            out["esc_in" if row["route"] else "esc_out"] += 1
            continue
        out["decided"] += 1
        if row["route"] is None:
            out["unsupported"] += 1
        elif route == row["route"]:
            out["correct"] += 1
        else:
            out["wrong"] += 1
    out["coverage"] = out["decided"] / out["n"] if out["n"] else math.nan
    out["accuracy"] = out["correct"] / out["decided"] if out["decided"] else None
    return out


def select(rows: list[dict], fallback: bool) -> tuple[float, float, dict, bool]:
    """Frozen rule: highest coverage with automatic accuracy >= target; ties prefer higher
    thresholds. If no pair reaches the target, take the most accurate (then widest) pair."""
    candidates = []
    for auto in AUTO_GRID:
        for llm in LLM_GRID if fallback else [auto]:
            if llm >= auto and fallback:
                continue
            result = run_policy(rows, auto, llm, fallback)
            candidates.append((auto, llm, result))
    meets = [
        c
        for c in candidates
        if c[2]["accuracy"] is not None and c[2]["accuracy"] >= TARGET_AUTO_ACCURACY
    ]
    if meets:
        best = max(meets, key=lambda c: (c[2]["coverage"], c[0], c[1]))
        return (*best, True)
    scored = [c for c in candidates if c[2]["accuracy"] is not None]
    best = max(scored, key=lambda c: (c[2]["accuracy"], c[2]["coverage"]))
    return (*best, False)


def row_of(label: str, r: dict, price: tuple[float, float] | None) -> str:
    acc = frac(r["correct"], r["decided"]) if r["decided"] else "n/a (nothing automated)"
    cov = frac(r["decided"], r["n"])
    cost = (
        "n/a" if price is None else f"${(r['fb_in'] * price[0] + r['fb_out'] * price[1]) / 1e6:.4f}"
    )
    return (
        f"| {label} | {cov} | {acc} | {r['wrong']} | {r['unsupported']} | "
        f"{r['esc_in']} / {r['esc_out']} | {r['fb_calls']} | {cost} |"
    )


def pct_or_na(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def build(cal_name: str, test_name: str) -> str:
    cal_all, cal_meta = load(cal_name)
    test_all, test_meta = load(test_name)
    cal, test = usable(cal_all), usable(test_all)
    price = NANO_PRICE if test_meta["fallback_model"] == "openai:gpt-5-nano" else None
    L: list[str] = []
    add = L.append

    add("# Banking77 evaluation")
    add("")
    add(
        "Public data (Banking77, PolyAI, CC BY 4.0), labels by the dataset's authors, routes "
        "and held-out intents fixed in `config.py` before any run. English only. "
        "**Read the limitations at the end before quoting any number.**"
    )
    add("")
    add("## Setup")
    add("")
    add(
        f"- Date: {test_meta['date']}; seed {test_meta['seed']}; fallback `{test_meta['fallback_model']}`; "
        f"TypeSafe model `{test_meta['typesafe_model']}`; langchain-typesafe "
        f"{test_meta['langchain_typesafe']}; jev-lanes {test_meta['jev_lanes']}."
    )
    add(
        f"- Calibration: {len(cal)} cases from the train file ({cal_meta['per_intent']} per intent); "
        f"test: {len(test)} cases from the test file ({test_meta['per_intent']} per intent). "
        f"Provider failures excluded: {len(cal_all) - len(cal)} calibration, "
        f"{len(test_all) - len(test)} test (counted as operational errors, not escalations)."
    )
    held = sum(r["route"] is None for r in test)
    add(
        f"- Test mix: {len(test) - held} in-scope, {held} held-out (no correct route; the right "
        "outcome is human review)."
    )
    add(f"- Routes: {', '.join(f'`{r}`' for r in ROUTES)}; no catch-all route.")
    add(
        f"- Selection rule (frozen): highest automatic coverage on the calibration set with "
        f"automatic accuracy ≥ {TARGET_AUTO_ACCURACY:.0%}; a held-out message routed "
        "automatically counts as an error."
    )
    add("- Human reviews are not simulated: escalated cases are reported as escalated.")
    add("")

    ins = [r for r in test if r["route"]]
    out = [r for r in test if not r["route"]]
    add("## Single-model baselines (test)")
    add("")
    jev_ok = sum(r["jev_route"] == r["route"] for r in ins)
    llm_ok = sum(r["llm_answer"] == r["route"] for r in ins)
    abstain = sum(r["llm_answer"] is None for r in test)
    invalid = sum(r["llm_answer"] is not None and r["llm_answer"] not in ROUTES for r in test)
    add(
        f"- Jev alone, in-scope accuracy: {frac(jev_ok, len(ins))}. It always names a route, "
        f"so all {len(out)} held-out messages would be routed."
    )
    add(
        f"- Fallback alone, in-scope accuracy (abstentions count as misses): {frac(llm_ok, len(ins))}."
    )
    add(
        f"- Fallback abstentions: {frac(abstain, len(test))}; unknown routes: {invalid}. "
        f"On held-out messages it abstained on {frac(sum(r['llm_answer'] is None for r in out), len(out))}."
    )
    add("")

    add("## Does Jev's confidence separate right from wrong? (test)")
    add("")
    right = [r["jev_confidence"] for r in ins if r["jev_route"] == r["route"]]
    wrong = [r["jev_confidence"] for r in ins if r["jev_route"] != r["route"]]
    held_conf = [r["jev_confidence"] for r in out]
    add("| Group | n | median | share ≥ 0.95 |")
    add("|---|---|---|---|")
    for label, values in (
        ("in-scope, correct", right),
        ("in-scope, wrong", wrong),
        ("held-out", held_conf),
    ):
        if values:
            add(
                f"| {label} | {len(values)} | {statistics.median(values):.2f} | "
                f"{100 * sum(v >= 0.95 for v in values) / len(values):.0f}% |"
            )
    add("")
    add(f"- AUROC, correct vs wrong among in-scope: {auroc(right, wrong):.3f}.")
    add(f"- AUROC, in-scope correct vs held-out: {auroc(right, held_conf):.3f}.")
    add("- 0.5 means confidence tells nothing; 1.0 means it separates perfectly.")
    add("")

    add("## Thresholds chosen on calibration")
    add("")
    auto3, llm3, cal3, met3 = select(cal, fallback=True)
    auto2, _, cal2, met2 = select(cal, fallback=False)
    add(
        f"- Three lanes: auto ≥ {auto3}, llm ≥ {llm3}. On calibration: coverage "
        f"{100 * cal3['coverage']:.1f}%, automatic accuracy "
        f"{pct_or_na(cal3['accuracy'])}"
        f"{'' if met3 else ' — target NOT reached'}."
    )
    add(
        f"- Two lanes (Jev + human, no fallback): auto ≥ {auto2}. On calibration: coverage "
        f"{100 * cal2['coverage']:.1f}%, automatic accuracy "
        f"{pct_or_na(cal2['accuracy'])}"
        f"{'' if met2 else ' — target NOT reached'}."
    )
    add("")

    add("## Test results at the chosen thresholds")
    add("")
    add(
        "| Configuration | Automated | Accuracy of automated | Wrong route | Held-out routed | "
        "Escalated in-scope / held-out | Fallback calls | Fallback cost |"
    )
    add("|---|---|---|---|---|---|---|---|")
    add(row_of("Jev alone, no escalation", run_policy(test, 0.0, 0.0, False), None))
    add(row_of(f"Jev + human (auto ≥ {auto2})", run_policy(test, auto2, auto2, False), None))
    add(row_of(f"Three lanes (auto ≥ {auto3}, llm ≥ {llm3})", run_policy(test, auto3, llm3), price))
    add("")
    add(
        "The fallback is called only for cases in the llm lane; its recorded answer is used. "
        "Abstentions and unknown routes escalate."
    )
    add("")

    add("## Does the fallback help where it is consulted? (test, in-scope cases)")
    add("")
    add(
        "Jev and the fallback answered the same messages, so they can be compared directly. "
        '"Fixed" means Jev was wrong and the fallback right; "broken" means the opposite. '
        "The fallback only helps if fixed > broken. Abstentions count as misses (the policy "
        "escalates them instead). The p-value is an exact sign test on fixed vs broken."
    )
    add("")
    add(
        "| Jev confidence band | n | Jev correct | Fallback correct | Fixed | Broken | Abstained | p |"
    )
    add("|---|---|---|---|---|---|---|---|")
    bands = (
        (f"llm lane [{llm3}, {auto3})", llm3, auto3),
        (f"below the auto threshold [0, {auto3})", 0.0, auto3),
        (f"[0, {llm3}) (human lane)", 0.0, llm3),
    )
    for label, low, high in bands:
        band = [r for r in test if low <= r["jev_confidence"] < high]
        c = fallback_vs_jev(band)
        if not c["n"]:
            add(f"| {label} | 0 | n/a | n/a | n/a | n/a | n/a | n/a |")
            continue
        add(
            f"| {label} | {c['n']} | {c['jev']} ({100 * c['jev'] / c['n']:.0f}%) | "
            f"{c['llm']} ({100 * c['llm'] / c['n']:.0f}%) | {c['fixed']} | {c['broken']} | "
            f"{c['abstained']} | {sign_test(c['fixed'], c['broken']):.2f} |"
        )
    add("")
    add(
        "Small samples: a difference here is not significant unless p is small, and an equal "
        "split does not show the fallback is harmless either. The bands are not independent "
        "of the thresholds chosen on calibration."
    )
    add("")

    add("## Descriptive sweep on the test set (not used for selection)")
    add("")
    add("| Jev + human, auto ≥ | Automated | Accuracy of automated | Held-out routed |")
    add("|---|---|---|---|")
    for threshold in AUTO_GRID:
        r = run_policy(test, threshold, threshold, False)
        acc = frac(r["correct"], r["decided"]) if r["decided"] else "n/a"
        add(f"| {threshold} | {100 * r['coverage']:.1f}% | {acc} | {r['unsupported']}/{len(out)} |")
    add("")

    add("## Cost and latency")
    add("")
    all_in, all_out = (
        sum(r["llm_input_tokens"] for r in test),
        sum(r["llm_output_tokens"] for r in test),
    )
    reasoning = sum(r["llm_reasoning_tokens"] for r in test)
    add(
        f"- Fallback tokens over all {len(test)} test calls: {all_in} in, {all_out} out "
        f"({reasoning} of them reasoning)."
        + (
            f" At ${price[0]}/${price[1]} per 1M tokens: ${(all_in * price[0] + all_out * price[1]) / 1e6:.4f}."
            if price
            else " No price configured for this model."
        )
    )
    jev_in = sum(r["jev_input_tokens"] or 0 for r in test)
    jev_out = sum(r["jev_output_tokens"] or 0 for r in test)
    add(
        f"- TypeSafe tokens reported: {jev_in} in, {jev_out} out. TypeSafe pricing was not "
        "checked, so no TypeSafe cost is given."
    )
    for label, key in (("TypeSafe", "jev_seconds"), ("Fallback", "llm_seconds")):
        values = [r[key] for r in test]
        add(
            f"- {label} latency: median {statistics.median(values):.2f}s, p95 {quantile(values, 0.95):.2f}s "
            f"({test_meta['workers']} concurrent workers, so under mild load)."
        )
    add("")

    add("## Automatic errors of the three-lane policy (test)")
    add("")
    shown = 0
    for r in test:
        lane, route = replay(r, auto3, llm3, True)
        if route is None or route == r["route"]:
            continue
        kind = "held-out routed" if r["route"] is None else f"wrong (true `{r['route']}`)"
        add(
            f"- `{r['intent']}` → `{route}` via {lane}, Jev `{r['jev_route']}` @ "
            f"{r['jev_confidence']:.2f}, {kind}: “{r['text'][:110]}”"
        )
        shown += 1
        if shown >= 25:
            add("- … (list truncated at 25)")
            break
    if shown == 0:
        add("- None.")
    add("")

    add("## Limitations")
    add("")
    for text in (
        "Banking77 is one domain with fine-grained, partly overlapping intents; some messages "
        '("How long will it take to arrive?") are unanswerable without context, so no model can '
        "reach 100%. Label noise is part of every number here.",
        "Grouping 66 intents into four routes, and choosing 11 intents as unsupported, are our "
        "design decisions. Other groupings would give other numbers.",
        "English only. Nothing here says how Jev or the fallback behave in Portuguese.",
        "One fallback model, one run, non-deterministic fallback: no repetitions, so no variance "
        "estimate. Confidence intervals cover sampling of the test cases only.",
        "Thresholds come from a coarse grid and a few hundred calibration cases.",
        "Escalated cases are not resolved: the cost and accuracy of the human step are unknown.",
        "Public benchmark data may overlap with what the models were trained on.",
    ):
        add(f"- {text}")
    add("")
    return "\n".join(L)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", default="calibration")
    parser.add_argument("--test", default="test")
    parser.add_argument("--out", type=Path, default=RESULTS / "report.md")
    args = parser.parse_args()
    args.out.write_text(build(args.calibration, args.test))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
