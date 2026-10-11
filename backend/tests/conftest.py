"""Keep test databases in isolated, project-local temporary directories."""

import os
from uuid import uuid4

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    if config.option.basetemp is not None or os.environ.get("PYTEST_DEBUG_TEMPROOT"):
        return

    temporary_root = config.rootpath / ".pytest_cache" / "tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    # pytest clears an explicit base directory. A fresh name prevents parallel
    # runs from clearing each other's databases or touching old restricted dirs.
    config.option.basetemp = str(temporary_root / f"run-{uuid4().hex}")
