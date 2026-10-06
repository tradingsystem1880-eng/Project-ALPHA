"""Shared suite vocabulary preserves wire values without importing orchestration."""

import json
import subprocess
import sys
from pathlib import Path

from pydantic import TypeAdapter

from alpha_cli.suite_catalog import SUITE_ACTIONS, SuiteActionValue


def test_suite_schema_preserves_committed_openapi_vocabulary() -> None:
    root = Path(__file__).resolve().parents[2]
    openapi = json.loads((root / "apps/alpha-web/frontend/openapi.json").read_text())
    expected = openapi["components"]["schemas"]["SuiteActionValue"]
    assert TypeAdapter(SuiteActionValue).json_schema() == expected
    assert set(expected["enum"]) == SUITE_ACTIONS


def test_suite_catalog_import_does_not_load_orchestration() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import alpha_cli.suite_catalog; "
            "assert not any(name in sys.modules for name in "
            "('alpha_cli._suite', 'alpha_cli.control_store', 'numpy', 'nautilus_trader'))",
        ],
        check=True,
    )
