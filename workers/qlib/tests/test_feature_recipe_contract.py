"""Feature recipe selection without native model training or provider initialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_qlib_worker.contract import canonical_json_bytes, compute_config_hash, validate_request
from alpha_qlib_worker.feature_recipes import feature_capabilities

from .test_fake_worker import _exchange


@pytest.mark.parametrize(
    "envelope,model", [(1, "lightgbm"), (2, "rank_ensemble_v1"), (3, "linear")]
)
def test_worker_accepts_explicit_v2_and_binds_config_identity(
    tmp_path: Path, envelope: int, model: str
) -> None:
    exchange = _exchange(tmp_path / "exchange")
    path = exchange / "request.json"
    request = json.loads(path.read_text())
    original = request["config_hash"]
    request["schema_version"], request["model"]["name"] = envelope, model
    request["feature_recipe"]["version"] = 2
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    assert request["config_hash"] != original
    assert validate_request(exchange).payload["feature_recipe"]["version"] == 2


@pytest.mark.parametrize("version", [0, 3, True, 1.0, "2"])
def test_worker_rejects_unknown_and_noninteger_feature_versions(
    tmp_path: Path, version: object
) -> None:
    exchange = _exchange(tmp_path / "exchange")
    path = exchange / "request.json"
    request = json.loads(path.read_text())
    request["feature_recipe"]["version"] = version
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    with pytest.raises(RuntimeError, match="feature recipe"):
        validate_request(exchange)


def test_feature_capabilities_disclose_scope_and_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.metadata

    rows = feature_capabilities()
    assert rows[0]["version"] == 1 and rows[1]["version"] == 2
    assert rows[1]["scope"] == "partial_alpha158_style_40_column_correction"

    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    rows = feature_capabilities()
    assert rows[1]["status"] == "missing_dependency"
    assert rows[0]["status"] == "available"


@pytest.mark.parametrize("version", [1, 2])
def test_real_entry_dispatches_version_then_stops_before_any_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: int
) -> None:
    """Dispatch test only: synthetic feature sentinel stops before folds or model APIs."""
    from types import ModuleType

    import pandas as pd

    from alpha_qlib_worker import real

    exchange = _exchange(tmp_path / "exchange")
    path = exchange / "request.json"
    request = json.loads(path.read_text())
    request["feature_recipe"]["version"] = version
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    calls: list[int] = []
    sentinel = pd.DataFrame({"test": [1.0]})

    def legacy(panel: object) -> pd.DataFrame:
        calls.append(1)
        return sentinel

    def corrected(panel: object, *, version: int) -> pd.DataFrame:
        calls.append(version)
        return sentinel

    def stop(request: object, features: pd.DataFrame) -> None:
        assert features is sentinel
        raise RuntimeError("test stop before model folds")

    monkeypatch.setattr(
        real,
        "require_real_dependencies",
        lambda: (ModuleType("unused_qlib"), ModuleType("unused_lightgbm")),
    )
    monkeypatch.setattr(real, "_official_feature_names", real.alpha158_feature_names)
    monkeypatch.setattr(real, "alpha158_features", legacy)
    monkeypatch.setattr(real, "build_features", corrected)
    monkeypatch.setattr(real, "_sample_table", stop)
    with pytest.raises(RuntimeError, match="test stop before model folds"):
        real.run_real(exchange, worker_lock_path=Path(__file__).parents[1] / "uv.lock")
    assert calls == [version]
    assert not (exchange / "result.json").exists()
    assert not (exchange / "predictions.parquet").exists()
