"""Classify again after simulated clarification, for every case below confidence 1.0.

    uv run --env-file .env --no-sync python benchmarks/banking77/clarify.py \
        --source test --limit 50 --name clarify-pilot   # pilot first

For each case the first Jev answer is already recorded in `<source>.jsonl` (run.py). Here the
agent's question (config.CLARIFY_QUESTION) is answered with another Banking77 TRAIN message of
the same intent, and Jev classifies the whole conversation, exactly as the GatedAgent would
send it (customer and assistant turns, as LangChain messages). A second round adds a second
answer. Both rounds are recorded for every case so gate_report.py can replay any threshold.

Only Jev is called (no LLM). Calls a real service with your own key and costs money. Results
go to `benchmarks/results/banking77/<name>.jsonl`; a finished case is skipped on re-run.
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

from config import CLARIFY_QUESTION, CLARIFY_ROUNDS, ROUTES, SEED
from langchain_core.messages import AIMessage, HumanMessage
from langchain_typesafe import TypeSafeClassifier

from jev_lanes.adapters import JevClassifier

BENCH = Path(__file__).resolve().parents[1]
DATA = BENCH / "data" / "banking77"
OUT = BENCH / "results" / "banking77"


def train_by_intent() -> dict[str, list[str]]:
    with open(DATA / "train.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_intent: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_intent[row["category"]].append(row["text"])
    return by_intent


def answers_for(case: dict, pool: dict[str, list[str]], seed: int) -> list[str]:
    """Two distinct train messages of the case's intent, never the case's own text."""
    options = [text for text in pool[case["intent"]] if text != case["text"]]
    return random.Random(f"{seed}-clarify-{case['id']}").sample(options, CLARIFY_ROUNDS)


def conversation(text: str, answers: list[str]) -> list:
    messages: list = [HumanMessage(text)]
    for answer in answers:
        messages += [AIMessage(CLARIFY_QUESTION), HumanMessage(answer)]
    return messages


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


def evaluate(case: dict, answers: list[str], classifier: JevClassifier, usage: UsageClient) -> dict:
    row = {"id": case["id"], "intent": case["intent"], "route": case["route"], "answers": answers}
    for round_number in range(1, CLARIFY_ROUNDS + 1):
        start = time.perf_counter()
        try:
            result = classifier.classify(conversation(case["text"], answers[:round_number]), ROUTES)
            error = None
        except Exception as exc:  # recorded in the results, never hidden
            result, error = None, f"{type(exc).__name__}: {exc}"[:300]
        used = usage.last_usage if result else None
        row[f"r{round_number}_route"] = result.route if result else None
        row[f"r{round_number}_confidence"] = result.confidence if result else None
        row[f"r{round_number}_input_tokens"] = getattr(used, "input_tokens", None)
        row[f"r{round_number}_seconds"] = round(time.perf_counter() - start, 3)
        row[f"r{round_number}_error"] = error
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", default="test", help="results file with the first answers")
    parser.add_argument("--limit", type=int, help="first N eligible cases only (pilot)")
    parser.add_argument("--name", help="output name; defaults to clarify-<source>")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("TYPESAFE_API_KEY is not set; use `uv run --env-file .env`", file=sys.stderr)
        return 2
    if not (DATA / "train.csv").exists():
        print(f"missing data; see benchmarks/banking77/README.md ({DATA})", file=sys.stderr)
        return 2

    source = [
        json.loads(line) for line in (OUT / f"{args.source}.jsonl").read_text().splitlines() if line
    ]
    eligible = [r for r in source if not r["jev_error"] and r["jev_confidence"] < 1.0]
    eligible = eligible[: args.limit]
    name = args.name or f"clarify-{args.source}"
    path = OUT / f"{name}.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(line)["id"] for line in path.read_text().splitlines() if line}
    todo = [r for r in eligible if r["id"] not in done]

    pool = train_by_intent()
    typesafe = TypeSafeClassifier()
    usage = UsageClient(typesafe)
    classifier = JevClassifier(client=usage)  # same default instructions as the first answers
    (OUT / f"{name}.meta.json").write_text(
        json.dumps(
            {
                "date": str(date.today()),
                "source": args.source,
                "eligible": len(eligible),
                "limit": args.limit,
                "seed": args.seed,
                "question": CLARIFY_QUESTION,
                "rounds": CLARIFY_ROUNDS,
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
    print(f"{len(eligible)} eligible, {len(done)} already done, running {len(todo)}", flush=True)

    lock = threading.Lock()
    finished = 0

    def work(case: dict) -> None:
        nonlocal finished
        row = evaluate(case, answers_for(case, pool, args.seed), classifier, usage)
        with lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            finished += 1
            if finished % 20 == 0 or finished == len(todo):
                print(f"  {finished}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool_executor:
        list(pool_executor.map(work, todo))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
