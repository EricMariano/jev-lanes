# Contributing

This project is in early development. Discuss changes to the gate semantics (what a
tool needs before it runs, what happens when it is blocked) before expanding the public API.

## Local workflow

Use Python 3.10+ and uv:

```bash
uv sync --locked --dev
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
uv run --offline --no-sync mypy
uv run --offline --no-sync pytest
uv build
```

CI also runs the offline customer-service demo (`examples/atendimento/demo.py`).

Commit `uv.lock` when changing development dependencies. Keep code and public
examples in English, with type annotations compatible with Python 3.10.

## Live tests (optional, your own keys)

`tests/live/` calls TypeSafe and may cost money, so it is skipped unless `JEV_RUN_LIVE=1`.
Put `TYPESAFE_API_KEY` in a git-ignored `.env` and run:

```bash
uv sync --locked --dev
JEV_RUN_LIVE=1 uv run --env-file .env --no-sync pytest tests/live -s
```

These are smoke tests on unambiguous cases: they check the integration, not decision
quality. The bring-your-own-keys chat (`examples/atendimento/byok.py`) also needs
`uv sync --locked --dev --group live` and your chat model's key.

## Tests and evidence

The default test suite must run without credentials, provider calls or network
access. Add behavior tests for policy changes and resume/error handling. Dataset
evaluation belongs outside that suite and must report its methodology.

Keep real-data evaluation out of that suite; see `benchmarks/README.md`. The replay logic
of an evaluation does belong in tests, because it decides what the report concludes.

Do not infer accuracy from a confidence threshold or claim savings based only on
synthetic tests. A simulated customer favours asking: say so wherever its results are used.
Distinguish implemented APIs from design proposals in documentation.
