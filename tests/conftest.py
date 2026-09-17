"""Shared pytest hooks."""

import os
from pathlib import Path


def pytest_configure(config) -> None:
    """Keep tmp_path inside the repo so Windows user-temp locks cannot fail setup."""
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
    os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
    if getattr(config.option, "basetemp", None):
        return
    basetemp = Path(__file__).resolve().parent.parent / ".pytest_tmp"
    basetemp.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(basetemp)


def pytest_collection_modifyitems(items) -> None:
    """Mark Redis-backed tests at collection time so ``-m redis`` works."""
    import pytest

    marker = pytest.mark.redis
    for item in items:
        names = set(getattr(item, "fixturenames", ()))
        if "redis_store" in names:
            item.add_marker(marker)
        callspec = getattr(item, "callspec", None)
        if callspec is None:
            continue
        params = callspec.params
        if params.get("store_kind") == "redis" or params.get("kind") == "redis":
            item.add_marker(marker)
