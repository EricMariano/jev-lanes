# Release process

The checkout is prepared as `0.1.0rc1`. Building a distribution does not publish it.
The name `jev-lanes` is provisional until PyPI accepts the first upload. The package
remains experimental: a release candidate is not a decision-quality guarantee.

## Verify the candidate

```bash
uv sync --locked --dev --group notebook
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
uv run --offline --no-sync pytest
uv run --offline --no-sync python examples/policy.py
uv run --offline --no-sync python examples/router_offline.py
uv run --offline --no-sync python examples/atendimento/demo.py
uv run --offline --no-sync python examples/manual_routing.py
uv run --offline --no-sync python examples/execute_notebook.py
uv build --out-dir build/release
uvx --from 'twine>=7,<8' twine check --strict build/release/*
```

The separate output folder avoids uploading stale distributions from `dist/`. Install
the wheel in a clean environment and run the offline examples before creating a release.
GitHub CI must pass on Python 3.10–3.14 and the notebook job. Live tests remain opt-in;
their keys never belong in repository files, release artifacts or CI logs.

## Configure publication once

1. Confirm the final package name and repository URLs in `pyproject.toml`.
2. In GitHub, create an environment named `pypi`, require a maintainer review, and
   restrict deployments to release tags.
3. In the PyPI account, add a pending Trusted Publisher for project `jev-lanes`,
   owner `EricMariano`, repository `jev-lanes`, workflow `release.yml`, environment
   `pypi`. If the project already exists, its owner must configure the publisher.
4. Confirm that the PyPI account can create or maintain the project. This is an
   account-side step; a public 404 does not reserve the name.

The release workflow uses OIDC, with `id-token: write` limited to the publication job.
It does not need a long-lived PyPI API token. The environment's reviewer is the final
approval before an upload; configure that protection before publishing a GitHub release.

## Publish a reviewed version

Update the version, changelog and `uv.lock` together, then commit and push the reviewed
changes. After CI succeeds, create a tag matching the metadata (for this candidate,
`v0.1.0rc1`) and publish a GitHub prerelease for that tag. The workflow independently
checks the tag/version match, lint, tests, examples, notebook and distributions before
requesting approval in the `pypi` environment. Approving that job uploads to PyPI.

For a final `0.1.0`, update metadata and lockfile first and use `v0.1.0`. Check the
installed package and project description after upload. PyPI versions cannot be reused;
fixes require a new version.

## Evidence and remaining validation

The repository includes deterministic behavior tests and a historical synthetic smoke
battery. A real-data evaluation still requires anonymized cases, independent labels,
separate calibration/test splits and a target error/coverage objective. Follow the
protocol in `benchmarks/README.md`; do not describe the synthetic results as production
accuracy, calibrated thresholds, or proof that fallback reduces error or cost.

Sources: [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/),
[pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/),
[PyPA publishing action](https://github.com/pypa/gh-action-pypi-publish).
