# Contributing

This project is in early development. Discuss changes to routing semantics before
expanding the public API; accepted architecture decisions live in `docs/adr/`.

## Local workflow

Use Python 3.10+ and uv:

```bash
uv sync --locked --dev
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
uv run --offline --no-sync pytest
uv build
```

Commit `uv.lock` when changing development dependencies. Keep code and public
examples in English, with type annotations compatible with Python 3.10.

## Tests and evidence

The default test suite must run without credentials, provider calls or network
access. Add behavior tests for policy changes and resume/error handling. Dataset
evaluation belongs outside that suite and must report its methodology.

Do not infer accuracy from a confidence threshold or claim savings based only on
synthetic tests. Distinguish implemented APIs from design proposals in documentation.
