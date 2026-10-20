"""Live tests call real services with your own keys and may cost money.

They are skipped unless ``JEV_RUN_LIVE=1`` is set, so exporting keys in your shell never
triggers them by accident:

    JEV_RUN_LIVE=1 uv run --env-file .env pytest tests/live -s
"""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("JEV_RUN_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="live tests need JEV_RUN_LIVE=1 and your own API keys")
    for item in items:
        if "tests/live" in item.nodeid.replace("\\", "/"):
            item.add_marker(skip)
