"""Opt-in feature identity, portable readers and unchanged default wire format."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_cli.ml_contract import (
    MLContractError,
    _validate_recipe_objects,
    canonical_json_bytes,
    compute_config_hash,
    prepare_exchange,
    validate_result_bundle,
)
from alpha_cli.ml_input import _draft_spec
from alpha_core import DataError
from alpha_web.api.ml import MlDiagnosticFeatureRecipe, MlFeatureRecipe
from tests.unit.test_ml_contract import _draft, _panel, _prediction_frame, _sessions, _write_result


def experiment() -> dict[str, Any]:
    return {
        "universe": [f"S{i:02d}" for i in range(20)],
        "split_policy": {"train": 504, "test": 63, "purge": 5, "embargo": 5},
        "stage_config": {"ml": {"validation_sessions": 120}},
        "costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
        "seeds": {"master": 7},
    }


def draft(experiment_value: dict[str, Any]) -> dict[str, object]:
    return _draft_spec(
        experiment=experiment_value,
        sessions=_sessions(),
        snapshot_hash="a" * 64,
        worker_lock_hash="b" * 64,
    )


def test_default_and_explicit_v1_are_identical_without_mutating_experiment() -> None:
    original = experiment()
    frozen = copy.deepcopy(original)
    default = draft(original)
    explicit = copy.deepcopy(original)
    explicit["stage_config"]["ml"]["feature_recipe_version"] = 1
    assert canonical_json_bytes(default) == canonical_json_bytes(draft(explicit))
    assert compute_config_hash(default) == compute_config_hash(draft(explicit))
    assert original == frozen
    # Hash recorded from the predecessor's actual _draft_spec on this fixture.
    assert (
        hashlib.sha256(canonical_json_bytes(default)).hexdigest()
        == "6e179f10ce73b1d08c9befd3b5ba24255b567a4cf9763fd5ee20abd4d5e9d443"
    )
    assert "feature_recipe_version" not in default


@pytest.mark.parametrize("version", [0, 4, True, 1.0, "2", "3", None])
def test_explicit_invalid_stage_feature_version_fails(version: object) -> None:
    value = experiment()
    value["stage_config"]["ml"]["feature_recipe_version"] = version
    with pytest.raises(DataError, match="feature_recipe_version"):
        draft(value)


def test_explicit_v2_changes_only_feature_version_and_digest() -> None:
    value = experiment()
    legacy = draft(value)
    value["stage_config"]["ml"]["feature_recipe_version"] = 2
    corrected = draft(value)
    expected = copy.deepcopy(legacy)
    expected_recipe = expected["feature_recipe"]
    assert isinstance(expected_recipe, dict)
    expected_recipe["version"] = 2
    assert corrected == expected
    assert compute_config_hash(corrected) != compute_config_hash(legacy)


@pytest.mark.parametrize(
    "envelope,model", [(1, "lightgbm"), (2, "rank_ensemble_v1"), (3, "linear")]
)
def test_all_portable_feature_versions_validate(envelope: int, model: str) -> None:
    for version in (1, 2, 3):
        request = _draft()
        request["schema_version"] = envelope
        request["model"] = {"name": model, "parameters": {}}
        request["feature_recipe"]["version"] = version
        _validate_recipe_objects(request)
        assert MlFeatureRecipe.model_validate(request["feature_recipe"]).version == version


@pytest.mark.parametrize("version", [0, 4, True, 1.0, "2", 3.0])
def test_portable_validator_rejects_unsupported_feature_versions(version: object) -> None:
    request = _draft()
    request["feature_recipe"]["version"] = version
    with pytest.raises(MLContractError, match="feature_recipe"):
        _validate_recipe_objects(request)


def test_v2_result_cannot_reuse_v1_prediction_lineage(tmp_path: Path) -> None:
    raw = _panel()
    panel_path, spec_path = tmp_path / "panel.parquet", tmp_path / "spec.json"
    raw.write_parquet(panel_path)
    legacy = _draft()
    spec_path.write_text(json.dumps(legacy))
    old = prepare_exchange(spec_path, panel_path, tmp_path / "old")
    legacy["feature_recipe"]["version"] = 2
    spec_path.write_text(json.dumps(legacy))
    current = prepare_exchange(spec_path, panel_path, tmp_path / "current")
    assert current["config_hash"] != old["config_hash"]
    predictions = _prediction_frame(old, raw)
    _write_result(tmp_path / "current", current, predictions)
    with pytest.raises(MLContractError, match="config_hash"):
        validate_result_bundle(tmp_path / "current")
    # New request-linked predictions pass. This is fabricated transport, not feature inference.
    predictions = predictions.with_columns(pl.lit(current["config_hash"]).alias("config_hash"))
    _write_result(tmp_path / "current", current, predictions)
    assert (
        validate_result_bundle(tmp_path / "current").request.request["feature_recipe"]["version"]
        == 2
    )


def test_request_descriptors_allow_only_three_explicit_recipe_versions() -> None:
    directory = Path(__file__).parents[2] / "workers/qlib/src/alpha_qlib_worker/schemas"
    for name in ("request.schema.json", "request-v2.schema.json", "request-v3.schema.json"):
        recipe = json.loads((directory / name).read_text())["properties"]["feature_recipe"]
        assert recipe["properties"]["version"] == {"type": "integer", "enum": [1, 2, 3]}
        assert recipe["properties"]["parameters"]["maxProperties"] == 0


def test_legacy_diagnostic_projection_still_accepts_old_shape() -> None:
    value = {
        "name": "Alpha158-style",
        "feature_count": 158,
        "names": [],
        "vwap_source": "causal_typical_price_proxy_not_vendor_vwap",
    }
    projection = MlDiagnosticFeatureRecipe.model_validate(value)
    assert projection.versioned_correction is None
    assert projection.model_dump(mode="json") == value


def test_explicit_v3_changes_only_feature_version_and_digest() -> None:
    value = experiment()
    legacy = draft(value)
    value["stage_config"]["ml"]["feature_recipe_version"] = 3
    upstream = draft(value)
    expected = copy.deepcopy(legacy)
    expected_recipe = expected["feature_recipe"]
    assert isinstance(expected_recipe, dict)
    expected_recipe["version"] = 3
    assert upstream == expected
    assert compute_config_hash(upstream) != compute_config_hash(legacy)


STORED = Path(__file__).parents[1] / "fixtures" / "ml_exchanges"


@pytest.mark.parametrize("version", [1, 2])
def test_stored_legacy_exchanges_still_validate(tmp_path: Path, version: int) -> None:
    """Exchanges published by the pre-v3 CLI and fake worker (598fd98b), byte for byte."""
    import shutil

    exchange = Path(shutil.copytree(STORED / f"feature-v{version}", tmp_path / "exchange"))
    validated = validate_result_bundle(exchange)
    assert validated.request.request["feature_recipe"] == {
        "name": "alpha158",
        "version": version,
        "parameters": {},
    }
    assert validated.result["config_hash"] == validated.request.request["config_hash"]
    assert compute_config_hash(validated.request.request) == validated.result["config_hash"]
    assert validated.predictions.height == 2420
    assert MlFeatureRecipe.model_validate(validated.request.request["feature_recipe"])


def test_v3_diagnostic_projection_accepts_upstream_metadata() -> None:
    names = [f"F{i}" for i in range(158)]
    value = {
        "name": "Alpha158 v3 (upstream Qlib expressions and processors)",
        "feature_count": 158,
        "names": names,
        "vwap_source": "causal_typical_price_proxy_not_vendor_vwap",
        "upstream_alpha158": {
            "name": "alpha158",
            "version": 3,
            "scope": "upstream_alpha158_all_158_columns",
            "upstream_columns": 158,
            "legacy_columns": 0,
            "feature_config": "qlib.contrib.data.handler.Alpha158.get_feature_config",
            "expression_engine": "qlib.utils.parse_field + qlib.data.ops.OpsList",
            "precision": "float32",
            "calendar": "panel sessions",
            "vwap": {"source": "causal_typical_price_proxy_not_vendor_vwap"},
            "processors": {"process_type": "append"},
            "warmup": "Qlib partial windows",
            "nonfinite": "upstream",
            "input": "validated ALPHA OHLCV panel only",
            "upstream": {"versions": {"pyqlib": "0.9.7"}},
            "source_sha256": {"upstream_alpha158.py": "0" * 64},
            "compatibility_key": "config_hash + worker_lock_hash + model_hash",
        },
    }
    projection = MlDiagnosticFeatureRecipe.model_validate(value)
    assert projection.upstream_alpha158 is not None
    assert projection.versioned_correction is None
    assert projection.model_dump(mode="json") == value
