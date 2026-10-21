# Banking77 evaluation

A reproducible evaluation of the three-lane policy on a public dataset with labels made
by third parties. It follows the protocol in [`../README.md`](../README.md). Results are
written to `../results/banking77/`; nothing here is a claim until a report is published
there with its limitations.

## Data

[Banking77](https://huggingface.co/datasets/PolyAI/banking77) (PolyAI, CC BY 4.0): 77 banking
intents, 10,003 training and 3,080 test messages, English. The files are not stored in Git.

```bash
mkdir -p benchmarks/data/banking77 && cd benchmarks/data/banking77
base=https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data
curl -sLO $base/train.csv && curl -sLO $base/test.csv
shasum -a 256 train.csv test.csv
# b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b  train.csv
# d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d  test.csv
```

## Design (frozen in `config.py` before any run)

- 66 intents grouped into four routes: `cards`, `payments`, `transfers`, `account`.
- 11 intents held out as unsupported (currency exchange and general product information).
  A message from one of them has **no correct route**: the right outcome is human review.
  Several sit next to in-scope intents, so this is a hard test for the human lane.
- No catch-all `other` route, because the synthetic battery showed that a catch-all
  absorbs vague input at confidence 1.0.
- Calibration set: 3 messages per intent from the train file (231). Test set: 10 per
  intent from the test file (770, of which 110 held-out). Seeded, stratified sampling.
- Thresholds are chosen **only on calibration** by a frozen rule (highest automatic
  coverage with automatic accuracy ≥ 95%, held-out messages routed automatically count as
  errors) and then applied once to the test set.

## Running (spends money on your own keys)

```bash
uv sync --locked --dev --group live
# pilot: 50 cases, a few cents; check for errors and cost first
uv run --env-file .env --no-sync python benchmarks/banking77/run.py \
    --split test --per-intent 10 --limit 50 --name pilot
# full runs
uv run --env-file .env --no-sync python benchmarks/banking77/run.py --split calibration
uv run --env-file .env --no-sync python benchmarks/banking77/run.py --split test
uv run --no-sync python benchmarks/banking77/report.py
```

Both providers answer every sampled case, so one run yields Jev alone, the fallback alone
and the three-lane policy by replaying the recorded answers (the fallback never sees Jev's
answer). A finished case is skipped on re-run. The report on a pilot is a smoke check only:
pass the pilot as both calibration and test and do not quote the numbers.

## Not covered

English only; one fallback model; no repeated runs; humans are not simulated; Banking77 has
ambiguous and noisy labels. See the limitations section of each report.
