"""Shared pytest hooks."""

from pathlib import Path


def pytest_configure(config) -> None:
    """Keep tmp_path inside the repo so Windows user-temp locks cannot fail setup."""
    if getattr(config.option, "basetemp", None):
        return
    basetemp = Path(__file__).resolve().parent.parent / ".pytest_tmp"
    basetemp.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(basetemp)
