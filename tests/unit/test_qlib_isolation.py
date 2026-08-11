"""The optional Qlib stack must never enter ALPHA's root dependency/import graph."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_root_workspace_and_lock_exclude_qlib_worker_dependencies() -> None:
    repo = Path(__file__).parents[2]
    root_project = (repo / "pyproject.toml").read_text(encoding="utf-8").lower()
    root_lock = (repo / "uv.lock").read_text(encoding="utf-8").lower()
    worker_lock = (repo / "workers/qlib/uv.lock").read_text(encoding="utf-8").lower()
    assert "workers/qlib" not in root_project
    assert "pyqlib" not in root_project
    assert "lightgbm" not in root_project
    assert 'name = "alpha-qlib-worker"' not in root_lock
    assert 'name = "pyqlib"' not in root_lock
    assert 'name = "lightgbm"' not in root_lock
    assert 'name = "alpha-qlib-worker"' in worker_lock
    assert 'name = "pyqlib"' in worker_lock
    assert 'name = "lightgbm"' in worker_lock
    assert 'name = "alpha-cli"' not in worker_lock


def test_importing_ml_contract_does_not_import_worker_or_model_stack() -> None:
    code = (
        "import sys; import alpha_cli.ml_contract; "
        "bad={'qlib','lightgbm','alpha_qlib_worker'} & set(sys.modules); "
        "raise SystemExit(','.join(sorted(bad)) if bad else 0)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
