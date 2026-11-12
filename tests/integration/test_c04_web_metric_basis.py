"""Real web-to-CLI metadata consumption over synthetic stored equity; no fits."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from fastapi.testclient import TestClient

from alpha_cli import _artifacts, _runner
from alpha_web import _catalog, _risk
from alpha_web.api.models import ApiErrorV1
from alpha_web.app import create_app


def seed_run(tmp_path: Path, wealth: tuple[float, ...] = (900, 950, 1000)) -> str:
    identity = _runner.run_identity_for({"command": "c04_web_fixture", "wealth": wealth})
    directory = tmp_path / "runs" / identity.run_id
    directory.mkdir(parents=True)
    frame = pl.DataFrame(
        {
            "ts": [datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(3)],
            "equity": wealth,
        },
        schema={"ts": pl.Datetime("us", "UTC"), "equity": pl.Float64()},
    )
    _artifacts.publish_artifact(directory / "equity_curve.parquet", frame.write_parquet)
    _artifacts.write_manifest(
        directory,
        {
            "run_id": identity.run_id,
            "command": "c04_web_fixture",
            "metadata": {"starting_cash": 1000.0},
            **identity.manifest_fields(),
        },
    )
    return identity.run_id


def test_real_http_cli_and_serialization_preserve_basis_and_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = seed_run(tmp_path)
    original = _catalog._run_json
    calls: list[tuple[list[str], Any]] = []

    def capture(args: list[str], *, data_dir: Path) -> Any:
        result = original(args, data_dir=data_dir)  # execute the real CLI subprocess
        calls.append((args, deepcopy(result)))
        return result

    monkeypatch.setattr(_risk, "_run_json", capture)
    client = TestClient(create_app())
    legacy = client.get("/api/risk/scenario", params={"run_id": run_id})
    disclosed = client.get(
        "/api/risk/scenario", params={"run_id": run_id, "include_metric_basis": True}
    )
    assert legacy.status_code == 200, legacy.text
    assert disclosed.status_code == 200, disclosed.text
    before, after = legacy.json(), disclosed.json()
    assert before == calls[0][1]
    assert after == calls[1][1]  # serialization does not strip or invent metadata
    assert "--include-metric-basis" not in calls[0][0]
    assert "--include-metric-basis" in calls[1][0]
    assert "metric_basis" not in before["provenance"]
    basis = after["provenance"].pop("metric_basis")
    assert after == before
    assert basis["schema_version"] == 1
    assert basis["anchor_value"] == pytest.approx(900, abs=1e-12, rel=0)
    assert basis["anchor_kind"] == "first_recorded_equity"
    assert basis["initial_capital_status"] == basis["external_cash_flow_status"] == "unknown"
    base = next(row for row in after["scenarios"] if row["name"] == "base")
    assert base["max_drawdown"] == pytest.approx(0, abs=1e-12, rel=0)
    assert base["total_return"] == pytest.approx(1 / 9, abs=1e-12, rel=0)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("schema_version", True),
        ("initial_capital_status", "verified"),
        ("external_cash_flow_status", "verified"),
        ("anchor_value", float("nan")),
        ("anchor_value", -1),
        ("anchor_value", True),
        ("anchor_ts", "not a timestamp"),
        ("return_accumulation", "sum"),
        ("drawdown_convention", "qlib_sum"),
        ("invented_verification", "SYNTHETIC PRIVATE CANARY"),
    ],
)
def test_malformed_basis_is_rejected_without_leaking_raw_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = seed_run(tmp_path)
    client = TestClient(create_app())
    valid = client.get(
        "/api/risk/scenario", params={"run_id": run_id, "include_metric_basis": True}
    )
    assert valid.status_code == 200, valid.text
    malformed = deepcopy(valid.json())
    malformed["provenance"]["metric_basis"][field] = value
    monkeypatch.setattr("alpha_web.api.risk._risk.scenario", lambda **kwargs: malformed)
    response = client.get(
        "/api/risk/scenario", params={"run_id": run_id, "include_metric_basis": True}
    )
    assert response.status_code == 422
    error = ApiErrorV1.model_validate(response.json())
    assert error.code == "request_invalid"
    assert error.message == "Risk scenario response is invalid"
    assert error.field_errors == []  # invalid upstream values are not echoed


@pytest.mark.parametrize("explicit_null", [False, True])
def test_legacy_absent_metadata_is_preserved_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit_null: bool
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = seed_run(tmp_path)
    client = TestClient(create_app())
    legacy = client.get("/api/risk/scenario", params={"run_id": run_id}).json()
    if explicit_null:
        legacy["provenance"]["metric_basis"] = None
    monkeypatch.setattr("alpha_web.api.risk._risk.scenario", lambda **kwargs: legacy)
    response = client.get(
        "/api/risk/scenario", params={"run_id": run_id, "include_metric_basis": True}
    )
    assert response.status_code == 200
    assert response.json() == legacy
