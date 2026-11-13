"""Workflow 3, statistical validation: gauntlet -> verdict on disk -> a second process reads it."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.smoke._harness import alpha
from tests.smoke.conftest import SNAPSHOT, STRATEGY, copy_home

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

# Small gauntlet sizes, as in tests/integration/test_validate_determinism.py.
_GAUNTLET = (
    "--train-size", "120", "--test-size", "40", "--embargo", "2", "--tier1-paths", "20",
    "--tier2-paths", "4", "--tier3-paths", "4", "--n-resamples", "50", "--seed", "7",
    "--max-workers", "1",
)  # fmt: skip
_VERDICT_LINE = re.compile(r"-> run ([0-9a-f]{16}): (PASS|FAIL) \(Verdict ([A-F])\b")


def test_validation_verdict_is_stored_and_read_back(data_home: Path, tmp_path: Path) -> None:
    home = copy_home(data_home, tmp_path)
    ran = alpha(home, "validate", "SPY", *STRATEGY, *_GAUNTLET, "--snapshot", SNAPSHOT)
    match = _VERDICT_LINE.search(ran.stdout)
    assert match, ran.report()
    run_id, verdict, grade = match.groups()

    run_dir = home / "data" / "runs" / run_id
    for artefact in ("manifest.json", "nulls.parquet", "tearsheet.html", "equity_curve.parquet"):
        assert (run_dir / artefact).is_file(), artefact
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["command"] == "validate"
    assert manifest["passed"] is (verdict == "PASS")
    assert manifest["verdict"]["overall"] == grade

    report = alpha(home, "report", run_id).stdout
    assert f"run {run_id}  validate  [SPY]" in report
    assert f"verdict: {verdict}" in report
    assert f"grade: {grade} " in report
    assert "gate[walk_forward_oos]:" in report
