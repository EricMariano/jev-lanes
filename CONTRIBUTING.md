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

## Live tests (optional, your own keys)

`tests/live/` calls TypeSafe and an OpenAI model and may cost money, so it is skipped
unless `JEV_RUN_LIVE=1`. Put `TYPESAFE_API_KEY` and `OPENAI_API_KEY` in a git-ignored
`.env` and run:

```bash
uv sync --locked --dev --group live
JEV_RUN_LIVE=1 uv run --env-file .env --no-sync pytest tests/live -s
```

The default fallback model is `openai:gpt-5-nano`; set `JEV_LIVE_FALLBACK_MODEL` to use
another `init_chat_model` string. These are smoke tests on unambiguous cases: they check
the integration, not decision quality.

## Tests and evidence

The default test suite must run without credentials, provider calls or network
access. Add behavior tests for policy changes and resume/error handling. Dataset
evaluation belongs outside that suite and must report its methodology.

Do not infer accuracy from a confidence threshold or claim savings based only on
synthetic tests. Distinguish implemented APIs from design proposals in documentation.
