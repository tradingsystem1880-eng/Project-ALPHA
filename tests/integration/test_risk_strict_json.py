"""Real CLI serialization must reject nonfinite legacy provenance, not emit JSON extensions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

RUN_ID = "c040000000000002"


def _run_cli(
    tmp_path: Path,
    manifest: dict[str, object],
    *,
    include_basis: bool,
    extra_args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    run = tmp_path / "runs" / RUN_ID
    run.mkdir(parents=True)
    # Deliberately preserve permissive legacy manifest encoding as the input
    # boundary under test. The emitted report must still be standards JSON.
    (run / "manifest.json").write_text(json.dumps(manifest))
    start = datetime(2024, 1, 1, tzinfo=UTC)
    pl.DataFrame(
        {"ts": [start + timedelta(days=i) for i in range(3)], "equity": [100.0, 95.0, 100.0]}
    ).write_parquet(run / "equity_curve.parquet")
    repository = Path(__file__).resolve().parents[2]
    roots = sorted([*repository.glob("packages/*/src"), *repository.glob("apps/*/src")])
    env = {key: value for key, value in os.environ.items() if not key.startswith("ALPHA_")}
    env.update(
        ALPHA_DATA_DIR=str(tmp_path),
        ALPHA_BULK_DATA_DIR=str(tmp_path / "bulk"),
        PYTHONPATH=os.pathsep.join(str(path) for path in roots),
        NO_COLOR="1",
        TERM="dumb",
    )
    args = [
        str(Path(sys.executable).with_name("alpha")),
        "risk",
        "scenario",
        "--from-run",
        RUN_ID,
        "--json",
    ]
    if include_basis:
        args.append("--include-metric-basis")
    args.extend(extra_args)
    return subprocess.run(
        args, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30, check=False
    )


@pytest.mark.parametrize("field", ["command", "snapshot_id"])
@pytest.mark.parametrize(
    "constant", [float("nan"), float("inf"), -float("inf")], ids=["NaN", "Infinity", "-Infinity"]
)
@pytest.mark.parametrize("include_basis", [False, True], ids=["legacy", "opted"])
def test_real_cli_rejects_nonfinite_manifest_provenance(
    tmp_path: Path, field: str, constant: float, include_basis: bool
) -> None:
    manifest: dict[str, object] = {
        "command": "SYNTHETIC_STRICT_JSON_NO_FIT",
        "snapshot_id": "snapshot",
    }
    manifest[field] = constant
    result = _run_cli(tmp_path, manifest, include_basis=include_basis)
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == ""
    assert "risk report contains non-finite values" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("include_basis", [False, True], ids=["legacy", "opted"])
def test_real_cli_keeps_valid_json_format_and_numeric_contract(
    tmp_path: Path, include_basis: bool
) -> None:
    # A string spelling a JSON extension is an ordinary valid string; it must
    # not be rejected by a textual NaN/Infinity filter.
    manifest: dict[str, object] = {
        "command": "SYNTHETIC_STRICT_JSON_NO_FIT",
        "snapshot_id": "NaN",
    }
    result = _run_cli(tmp_path, manifest, include_basis=include_basis)
    assert result.returncode == 0, result.stderr

    def reject_extension(value: str) -> None:
        raise AssertionError(f"nonstandard JSON constant in successful report: {value}")

    body = json.loads(result.stdout, parse_constant=reject_extension)
    assert result.stdout == json.dumps(body, allow_nan=False) + "\n"
    assert body["provenance"]["source_command"] == manifest["command"]
    assert body["provenance"]["snapshot_id"] == "NaN"
    assert ("metric_basis" in body["provenance"]) == include_basis
    assert body["scenarios"][0]["max_drawdown"] == pytest.approx(-0.05, abs=1e-12, rel=0)
    assert body["scenarios"][0]["total_return"] == pytest.approx(0.0, abs=1e-12, rel=0)


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--confidence", "1", "confidence must be in (0, 1)"),
        ("--periods-per-year", "0", "periods_per_year must be >= 1"),
        (
            "--periods-per-year",
            str(10**309),
            "risk inputs exceed supported numeric range",
        ),
    ],
    ids=["invalid-confidence", "nonpositive-annualization", "overflow-annualization"],
)
@pytest.mark.parametrize("include_basis", [False, True], ids=["legacy", "opted"])
def test_real_cli_numeric_option_errors_are_clean(
    tmp_path: Path, option: str, value: str, message: str, include_basis: bool
) -> None:
    result = _run_cli(
        tmp_path,
        {"command": "SYNTHETIC_STRICT_JSON_NO_FIT"},
        include_basis=include_basis,
        extra_args=(option, value),
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == ""
    assert message in result.stderr
    assert "Traceback" not in result.stderr
