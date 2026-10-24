"""ARCHIVED: reproduces the three-lane fallback evaluation and needs jev-lanes at commit 8d07291 (JevRouter, Lanes and
LangChainFallback were removed afterwards). Its recorded results remain valid history.

Run TypeSafe (Jev) and the fallback model on a stratified Banking77 sample.

    uv sync --locked --dev --group live
    uv run --env-file .env --no-sync python benchmarks/banking77/run.py \
        --split test --per-intent 10 --limit 50 --name pilot

Both providers answer EVERY sampled case, so one run yields the Jev-only, fallback-only and
three-lane results by replaying the recorded answers (report.py). The fallback never sees
Jev's answer, so replaying it for the llm lane is equivalent to calling it there.

Calls real services with your own keys and costs money. Results are appended to
`benchmarks/results/banking77/<name>.jsonl`, and a finished case is skipped on re-run.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from importlib import metadata
from pathlib import Path

from config import HELD_OUT, INTENT_TO_ROUTE, ROUTES, SEED
from langchain_core.callbacks import get_usage_metadata_callback
from langchain_typesafe import TypeSafeClassifier

from jev_lanes.adapters import JevClassifier, LangChainFallback

BENCH = Path(__file__).resolve().parents[1]
DATA = BENCH / "data" / "banking77"
OUT = BENCH / "results" / "banking77"
DEFAULT_MODEL = "openai:gpt-5-nano"
DEFAULT_PER_INTENT = {"calibration": 3, "test": 10}


def load_cases(split: str, per_intent: int, seed: int) -> list[dict]:
    """Stratified sample: ``per_intent`` messages per intent, in a seeded random order."""
    csv_name = "train.csv" if split == "calibration" else "test.csv"
    with open(DATA / csv_name, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_intent: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_intent[row["category"]].append(index)
    unknown = set(by_intent) - set(INTENT_TO_ROUTE) - set(HELD_OUT)
    if unknown:
        raise SystemExit(f"intents missing from config.py: {sorted(unknown)}")
    cases = []
    for intent in sorted(by_intent):
        picked = random.Random(f"{seed}-{split}-{intent}").sample(by_intent[intent], per_intent)
        for index in picked:
            cases.append(
                {
                    "id": f"{split}-{index}",
                    "text": rows[index]["text"],
                    "intent": intent,
                    "route": INTENT_TO_ROUTE.get(intent),  # None for held-out intents
                }
            )
    random.Random(f"{seed}-{split}-order").shuffle(cases)
    return cases


class UsageClient:
    """Wraps TypeSafeClassifier to remember the token usage of each thread's last call."""

    def __init__(self, client: TypeSafeClassifier) -> None:
        self.client = client
        self._local = threading.local()

    def invoke(self, request):
        response = self.client.invoke(request)
        self._local.usage = response.usage
        return response

    @property
    def last_usage(self):
        return getattr(self._local, "usage", None)


def timed(fn, *args):
    start = time.perf_counter()
    try:
        return fn(*args), None, round(time.perf_counter() - start, 3)
    except Exception as error:  # recorded in the results, never hidden
        message = f"{type(error).__name__}: {error}"[:300]
        return None, message, round(time.perf_counter() - start, 3)


def evaluate(case: dict, classifier: JevClassifier, usage: UsageClient, fallback) -> dict:
    jev, jev_error, jev_seconds = timed(classifier.classify, case["text"], ROUTES)
    jev_usage = usage.last_usage if jev else None
    with get_usage_metadata_callback() as callback:
        answer, llm_error, llm_seconds = timed(fallback.decide, case["text"], ROUTES)
    totals = defaultdict(int)
    for model_usage in callback.usage_metadata.values():
        totals["input"] += model_usage.get("input_tokens", 0)
        totals["output"] += model_usage.get("output_tokens", 0)
        details = model_usage.get("output_token_details") or {}
        totals["reasoning"] += details.get("reasoning", 0)
    return {
        **case,
        "jev_route": jev.route if jev else None,
        "jev_confidence": jev.confidence if jev else None,
        "jev_input_tokens": getattr(jev_usage, "input_tokens", None),
        "jev_output_tokens": getattr(jev_usage, "output_tokens", None),
        "jev_seconds": jev_seconds,
        "jev_error": jev_error,
        "llm_answer": answer,
        "llm_input_tokens": totals["input"],
        "llm_output_tokens": totals["output"],
        "llm_reasoning_tokens": totals["reasoning"],
        "llm_seconds": llm_seconds,
        "llm_error": llm_error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--split", choices=["calibration", "test"], required=True)
    parser.add_argument("--per-intent", type=int)
    parser.add_argument("--limit", type=int, help="run only the first N shuffled cases (pilot)")
    parser.add_argument("--name", help="output name; defaults to the split")
    parser.add_argument("--model", default=os.environ.get("JEV_LIVE_FALLBACK_MODEL", DEFAULT_MODEL))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("TYPESAFE_API_KEY is not set; use `uv run --env-file .env`", file=sys.stderr)
        return 2
    if not (DATA / "train.csv").exists():
        print(f"missing data; see benchmarks/banking77/README.md ({DATA})", file=sys.stderr)
        return 2

    per_intent = args.per_intent or DEFAULT_PER_INTENT[args.split]
    cases = load_cases(args.split, per_intent, args.seed)[: args.limit]
    name = args.name or args.split
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(line)["id"] for line in path.read_text().splitlines() if line}
    todo = [case for case in cases if case["id"] not in done]

    typesafe = TypeSafeClassifier()
    usage = UsageClient(typesafe)
    classifier = JevClassifier(client=usage)
    fallback = LangChainFallback(args.model)
    (OUT / f"{name}.meta.json").write_text(
        json.dumps(
            {
                "date": str(date.today()),
                "split": args.split,
                "per_intent": per_intent,
                "limit": args.limit,
                "seed": args.seed,
                "cases": len(cases),
                "fallback_model": args.model,
                "typesafe_model": typesafe.model,
                "langchain_typesafe": metadata.version("langchain-typesafe"),
                "jev_lanes": metadata.version("jev-lanes"),
                "routes": ROUTES,
                "workers": args.workers,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"{len(cases)} cases, {len(done)} already done, running {len(todo)}", flush=True)

    lock = threading.Lock()
    finished = 0

    def work(case: dict) -> None:
        nonlocal finished
        row = evaluate(case, classifier, usage, fallback)
        with lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            finished += 1
            if finished % 10 == 0 or finished == len(todo):
                print(f"  {finished}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, todo))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
