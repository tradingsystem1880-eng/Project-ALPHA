"""Closed subprocess relay for advisory recorded-run investigations."""

from pathlib import Path
from typing import Any

from alpha_web._catalog import _run_json


def project(args: list[str], *, data_dir: Path) -> Any:
    return _run_json(["research", "investigations", *args], data_dir=data_dir)
