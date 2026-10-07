"""Suite-wide terminal determinism for CLI assertions, plus the alpha/platform tier marker.

``typer.rich_utils`` forces a colour terminal at import time whenever ``GITHUB_ACTIONS``,
``FORCE_COLOR`` or ``PY_COLORS`` is set (it does not honour ``NO_COLOR``), so on GitHub
runners help and error panels carry ANSI sequences and plain-token assertions fail
CI-only. This conftest runs before any test module imports typer: it strips the forcing
variables and sets ``NO_COLOR`` so the suite renders identically on every terminal.

``pytest_collection_modifyitems`` applies the ``platform`` marker from ``tests/_tiers.py`` so the
fast gate can run ``-m "not platform"`` (the alpha tier) without touching any test file.
"""

import os
from pathlib import Path

import pytest

from tests._tiers import classify_platform

os.environ["NO_COLOR"] = "1"
for _name in ("GITHUB_ACTIONS", "FORCE_COLOR", "PY_COLORS"):
    os.environ.pop(_name, None)

_ROOT = Path(__file__).resolve().parent.parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        rel = Path(str(item.fspath)).resolve().relative_to(_ROOT).as_posix()
        if classify_platform(rel):
            item.add_marker(pytest.mark.platform)
