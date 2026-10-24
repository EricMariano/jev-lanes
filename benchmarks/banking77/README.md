# Banking77 evaluation

A reproducible evaluation of the three-lane policy on a public dataset with labels made
by third parties. It follows the protocol in [`../README.md`](../README.md). Results are
written to `../results/banking77/`; nothing here is a claim until a report is published
there with its limitations.

## Data

[Banking77](https://huggingface.co/datasets/PolyAI/banking77) (PolyAI, CC BY 4.0): 77 banking
intents, 10,003 training and 3,080 test messages, English. The original CSV files are not
stored in Git; see [Attribution](#attribution) for what the result files contain.

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

## Gate evaluation (`GatedAgent`)

Replays the confidence gate of `GatedAgent` on the same test sample: act only when Jev is
confident enough, otherwise ask the customer and classify the conversation again. It reuses
the first Jev answers in `../results/banking77/test.jsonl` and needs only Jev, no LLM. The
design is frozen in `config.py` (question, number of rounds, primary threshold).

```bash
# pilot: 50 cases, ~100 Jev calls
uv run --env-file .env --no-sync python benchmarks/banking77/clarify.py \
    --source test --limit 50 --name clarify-pilot
# full: every test case with first confidence < 1.0 (327), two rounds each
uv run --env-file .env --no-sync python benchmarks/banking77/clarify.py --source test
uv run --no-sync python benchmarks/banking77/gate_report.py   # offline replay
```

The simulated reply to the question is another Banking77 **train** message of the same intent,
so it restates the problem in new words. This favours asking: read the limitations in
[`../results/banking77/gate-report.md`](../results/banking77/gate-report.md). The pilot file
is a smoke check and is not used by the report.

`run.py` and `../smoke_battery.py` are archived: they reproduce the earlier three-lane
evaluation and need the commit named in their docstrings. Their recorded results stay valid.

## Attribution

The evaluation uses **Banking77**, released by PolyAI under the
[Creative Commons Attribution 4.0 International license](https://creativecommons.org/licenses/by/4.0/):

> Iñigo Casanueva, Tadas Temčinas, Daniela Gerz, Matthew Henderson and Ivan Vulić.
> *Efficient Intent Detection with Dual Sentence Encoders.* 2020.
> [arXiv:2003.04807](https://arxiv.org/abs/2003.04807). Data:
> [PolyAI-LDN/task-specific-datasets](https://github.com/PolyAI-LDN/task-specific-datasets).

Changes made by this project: we sampled subsets of the train and test files (seeded and
stratified, see `run.py`), grouped intents into four routes and held out 11 intents (see
`config.py`). The files in `../results/banking77/` (`*.jsonl`) contain the text of the
sampled messages (and, in `clarify-*.jsonl`, the train messages used as simulated replies)
together with their original intent labels and the answers of the models under test. They are shared under the same license, and the dataset authors are not
responsible for the models' outputs or for our grouping. This is an independent project and
is not endorsed by PolyAI or the dataset authors.

## Not covered

English only; one fallback model; no repeated runs; humans are not simulated; Banking77 has
ambiguous and noisy labels. See the limitations section of each report.
