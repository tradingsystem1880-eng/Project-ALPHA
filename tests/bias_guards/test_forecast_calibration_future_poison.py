"""Fold-local guard for frozen Kronos calibration."""

from __future__ import annotations

import pytest

from alpha_validation.forecast_calibration import (
    ForecastCalibrationContractV1,
    ForecastCalibrationOriginV1,
    assess_kronos_calibrated_candidate,
    fit_rolling_conformal_blend,
)


def _contract() -> ForecastCalibrationContractV1:
    return ForecastCalibrationContractV1(
        coverage_level=0.8,
        residual_window=4,
        blend_weights=(0.0, 0.5, 1.0),
        minimum_validation_origins=8,
        minimum_empirical_coverage=0.5,
        minimum_edge=0.01,
        maximum_interval_width=0.25,
        minimum_state_samples=3,
    )


def _origin(index: int, *, poison: bool = False) -> ForecastCalibrationOriginV1:
    observed = 50.0 if poison else -0.03 + index * 0.006
    return ForecastCalibrationOriginV1(
        origin_id=f"origin-{index:02d}",
        model_end_returns=(observed - 0.01, observed, observed + 0.01),
        random_walk_end_returns=(0.15, 0.20, 0.25),
        observed_end_return=observed,
        state_key="poison" if poison else "validation",
    )


@pytest.mark.bias_guard
def test_oos_and_holdout_poison_cannot_change_frozen_calibration() -> None:
    validation = tuple(_origin(index) for index in range(12))
    fit_before = fit_rolling_conformal_blend(_contract(), validation)
    poisoned_future = tuple(_origin(index, poison=True) for index in range(12, 20))
    for origin in poisoned_future:
        assess_kronos_calibrated_candidate(
            fit_before,
            model_end_returns=origin.model_end_returns,
            random_walk_end_returns=origin.random_walk_end_returns,
            market_state_eligible=True,
        )
    fit_after = fit_rolling_conformal_blend(_contract(), validation)
    assert fit_after == fit_before
    assert fit_after.fit_sha256 == fit_before.fit_sha256
