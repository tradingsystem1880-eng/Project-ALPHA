"""Process cleanup must start without importing the unused research analysis stack."""

import json
import subprocess
import sys


def test_run_child_import_skips_analysis_stack() -> None:
    probe = """
import json, sys
from alpha_cli.research_execution import run_child
heavy = [name for name in ("alpha_cli._artifacts", "alpha_cli._runner",
                           "alpha_cli.research_execution_digest", "numpy", "scipy",
                           "polars", "alpha_validation") if name in sys.modules]
print(json.dumps(heavy))
"""
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=120, check=True
    )
    assert json.loads(result.stdout) == []
