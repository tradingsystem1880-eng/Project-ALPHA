"""Rolling-origin conformal calibration and candidate-admission tests."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_validation.forecast_calibration import (
    ForecastCalibrationContractV1,
    ForecastCalibrationFitV1,
    ForecastCalibrationOriginV1,
    assess_kronos_calibrated_candidate,
    evaluate_frozen_calibration,
    fit_rolling_conformal_blend,
)


def _contract(**overrides: object) -> ForecastCalibrationContractV1:
    values: dict[str, object] = {
        "coverage_level": 0.8,
        "residual_window": 4,
        "blend_weights": (0.0, 0.5, 1.0),
        "minimum_validation_origins": 8,
        "minimum_empirical_coverage": 0.5,
        "minimum_edge": 0.01,
        "maximum_interval_width": 0.20,
        "minimum_state_samples": 3,
    }
    values.update(overrides)
    return ForecastCalibrationContractV1(**values)  # type: ignore[arg-type]


def _origins(count: int = 12) -> tuple[ForecastCalibrationOriginV1, ...]:
    rows = []
    for index in range(count):
        observed = -0.04 + 0.008 * index
        rows.append(
            ForecastCalibrationOriginV1(
                origin_id=f"validation-{index:02d}",
                model_end_returns=(observed - 0.008, observed, observed + 0.008),
                random_walk_end_returns=(0.16, 0.20, 0.24),
                observed_end_return=observed + (0.002 if index % 2 else -0.002),
                state_key="calm" if index < count - 2 else "rare",
            )
        )
    return tuple(rows)


def test_contract_and_fit_round_trip_are_content_addressed_and_deterministic() -> None:
    contract = _contract()
    assert ForecastCalibrationContractV1.from_dict(contract.to_dict()) == contract
    first = fit_rolling_conformal_blend(contract, _origins())
    second = fit_rolling_conformal_blend(contract, _origins())
    assert first == second
    assert first.fit_sha256 == second.fit_sha256
    assert ForecastCalibrationFitV1.from_dict(first.to_dict()) == first
    assert first.selected_model_weight == 1.0
    assert first.validation_metrics.calibrated_coverage >= 0.5
    assert first.validation_metrics.raw_crps >= 0.0
    assert first.validation_metrics.calibrated_crps >= 0.0
    assert first.validation_metrics.raw_pinball >= 0.0
    assert first.validation_metrics.calibrated_pinball >= 0.0


def test_state_diagnostics_use_pooled_fallback_below_frozen_minimum() -> None:
    fit = fit_rolling_conformal_blend(_contract(), _origins())
    diagnostics = {row.state_key: row for row in fit.state_diagnostics}
    assert diagnostics["calm"].used_pooled_fallback is False
    assert diagnostics["rare"].sample_count == 2
    assert diagnostics["rare"].used_pooled_fallback is True
    assert diagnostics["rare"].evaluated_count == fit.validation_metrics.evaluated_origins


def test_candidate_requires_coverage_uncertainty_edge_and_available_state() -> None:
    fit = fit_rolling_conformal_blend(_contract(), _origins())
    ready = assess_kronos_calibrated_candidate(
        fit,
        model_end_returns=(0.05, 0.06, 0.07),
        random_walk_end_returns=(0.01, 0.02, 0.03),
        market_state_eligible=True,
    )
    assert ready.ready is True
    assert ready.candidate == "kronos_calibrated"
    assert ready.signal == 1
    assert ready.blocker_codes == ()

    unavailable = assess_kronos_calibrated_candidate(
        fit,
        model_end_returns=(0.05, 0.06, 0.07),
        random_walk_end_returns=(0.01, 0.02, 0.03),
        market_state_eligible=False,
    )
    assert unavailable.ready is False
    assert unavailable.signal is None
    assert "MARKET_STATE_UNAVAILABLE" in unavailable.blocker_codes

    no_edge = assess_kronos_calibrated_candidate(
        fit,
        model_end_returns=(-0.005, 0.0, 0.005),
        random_walk_end_returns=(-0.005, 0.0, 0.005),
        market_state_eligible=True,
    )
    assert no_edge.ready is False
    assert "CALIBRATED_EDGE_BELOW_FLOOR" in no_edge.blocker_codes


def test_frozen_fit_scores_only_disjoint_oos_origins() -> None:
    fit = fit_rolling_conformal_blend(_contract(), _origins())
    oos = ForecastCalibrationOriginV1(
        origin_id="oos-01",
        model_end_returns=(0.04, 0.05, 0.06),
        random_walk_end_returns=(-0.01, 0.0, 0.01),
        observed_end_return=0.045,
        state_key="calm",
    )

    (evaluated,) = evaluate_frozen_calibration(
        fit, (oos,), market_state_eligibility={"oos-01": True}
    )

    assert evaluated.origin_id == "oos-01"
    assert evaluated.raw_crps >= 0.0
    assert evaluated.calibrated_crps >= 0.0
    assert evaluated.assessment.calibration_fit_sha256 == fit.fit_sha256

    with pytest.raises(DataError, match="overlap"):
        evaluate_frozen_calibration(
            fit,
            (_origins()[0],),
            market_state_eligibility={_origins()[0].origin_id: True},
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"coverage_level": 1.0}, "coverage_level"),
        ({"blend_weights": (0.0, 0.5, 0.5, 1.0)}, "blend_weights"),
        ({"blend_weights": (0.2, 0.8)}, "endpoints"),
        ({"minimum_validation_origins": 3}, "minimum_validation_origins"),
        ({"maximum_interval_width": 0.0}, "maximum_interval_width"),
    ],
)
def test_contract_rejects_unbounded_or_ambiguous_calibration(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(DataError, match=message):
        _contract(**overrides)


def test_fit_rejects_too_few_origins_and_sample_shape_drift() -> None:
    with pytest.raises(DataError, match="validation origins"):
        fit_rolling_conformal_blend(_contract(), _origins(7))
    with pytest.raises(DataError, match="sample counts"):
        ForecastCalibrationOriginV1(
            origin_id="validation-03",
            model_end_returns=(0.0, 0.1),
            random_walk_end_returns=(0.0, 0.1, 0.2),
            observed_end_return=0.05,
            state_key="calm",
        )
