"""Command-layer Monte Carlo calibration policy tests."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from alpha_cli.monte_carlo_cmds import (
    _calibration_assessment,
    _causal_regime_states,
    _path_frame,
    _project_forecast_path,
    _verified_forecast_eval,
    _verified_validation_source,
)
from alpha_core import DataError
from tests.fixtures.forecast_fixtures import daily_bars


def _manifest(**overrides: float | int) -> dict[str, object]:
    summary: dict[str, float | int] = {
        "n_origins": 20,
        "skill_vs_rw": 0.1,
        "skill_vs_bootstrap": 0.05,
        "coverage50": 0.5,
        "coverage80": 0.8,
        "coverage90": 0.9,
    }
    summary.update(overrides)
    return {"summary_post_cutoff": summary}


def test_kronos_calibration_requires_skill_and_empirical_coverage() -> None:
    assert _calibration_assessment(_manifest())["status"] == "adequate"

    weak = _calibration_assessment(_manifest(coverage80=0.95))
    assert weak["status"] == "weak_or_insufficient"
    assert "70%-90%" in str(weak["reasons"])


def test_kronos_calibration_rejects_sparse_or_baseline_losing_evidence() -> None:
    weak = _calibration_assessment(_manifest(n_origins=4, skill_vs_rw=0.0, skill_vs_bootstrap=-0.1))
    assert weak["status"] == "weak_or_insufficient"
    assert len(weak["reasons"]) == 3


def test_run_resolution_and_path_frames_reject_missing_or_malformed_inputs(
    tmp_path: Path,
) -> None:
    with pytest.raises(DataError, match="was not found"):
        _verified_validation_source(tmp_path, "missing")
    with pytest.raises(DataError, match="was not found"):
        _verified_forecast_eval(tmp_path, "missing", source_manifest={})
    with pytest.raises(DataError, match="two-dimensional"):
        _path_frame((("iid_empirical", np.array([0.1, 0.2])),))
    with pytest.raises(DataError, match="at least one"):
        _path_frame(())


def test_causal_regime_classifier_rejects_unfrozen_or_unavailable_history() -> None:
    bars = daily_bars(20)
    with pytest.raises(DataError, match="regime_window"):
        _causal_regime_states(bars, (bars[-1].ts,), train_size=10, window=1)
    with pytest.raises(DataError, match="cannot freeze"):
        _causal_regime_states(bars, (bars[-1].ts,), train_size=4, window=3)
    with pytest.raises(DataError, match="insufficient causal"):
        _causal_regime_states(bars, (bars[-1].ts,), train_size=4, window=2)
    with pytest.raises(DataError, match="absent from source"):
        _causal_regime_states(
            bars,
            (bars[-1].ts + timedelta(days=100),),
            train_size=10,
            window=2,
        )
    with pytest.raises(DataError, match="lacks 2 prior"):
        _causal_regime_states(bars, (bars[1].ts,), train_size=10, window=2)


def test_kronos_projection_rejects_bad_sequences_and_physical_values() -> None:
    timestamp = daily_bars(2)[-1].ts + timedelta(days=1)
    valid = {
        "open": (100.0,),
        "high": (101.0,),
        "low": (99.0,),
        "close": (100.5,),
        "volume": (1_000.0,),
    }
    missing = SimpleNamespace(**{key: value for key, value in valid.items() if key != "volume"})
    with pytest.raises(DataError, match="no valid volume sequence"):
        _project_forecast_path(symbol="SPY", timestamps=(timestamp,), sample=missing, path_index=0)

    non_numeric = SimpleNamespace(**{**valid, "close": (object(),)})
    with pytest.raises(DataError, match="non-numeric"):
        _project_forecast_path(
            symbol="SPY", timestamps=(timestamp,), sample=non_numeric, path_index=1
        )

    bad_price = SimpleNamespace(**{**valid, "open": (0.0,)})
    with pytest.raises(DataError, match="invalid price"):
        _project_forecast_path(
            symbol="SPY", timestamps=(timestamp,), sample=bad_price, path_index=2
        )

    bad_volume = SimpleNamespace(**{**valid, "volume": (-1.0,)})
    with pytest.raises(DataError, match="invalid volume"):
        _project_forecast_path(
            symbol="SPY", timestamps=(timestamp,), sample=bad_volume, path_index=3
        )
