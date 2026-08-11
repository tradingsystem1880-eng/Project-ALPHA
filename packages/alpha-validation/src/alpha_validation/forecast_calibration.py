"""Fold-local convex blending and rolling-origin conformal forecast calibration."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import numpy as np

from alpha_core import DataError
from alpha_validation.forecast_eval import central_coverage, crps_sample, pinball_loss

_CONTRACT_SCHEMA = "ForecastCalibrationContractV1"
_FIT_SCHEMA = "KronosCalibrationFitV1"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise DataError(f"{label} has unexpected or missing fields")


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DataError(f"{label} must be a finite number")
    return float(value)


def _integer(value: object, label: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DataError(f"{label} must be an integer >= {minimum}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DataError(f"{label} must be a non-empty canonical string")
    return value


def _samples(values: Sequence[float], label: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size < 2 or not bool(np.all(np.isfinite(array))):
        raise DataError(f"{label} needs at least two finite samples")
    return array


@dataclass(frozen=True, slots=True)
class ForecastCalibrationContractV1:
    """Preregistered calibration, blend, coverage, edge, and abstention policy."""

    coverage_level: float
    residual_window: int
    blend_weights: tuple[float, ...]
    minimum_validation_origins: int
    minimum_empirical_coverage: float
    minimum_edge: float
    maximum_interval_width: float
    minimum_state_samples: int

    def __post_init__(self) -> None:
        coverage = _number(self.coverage_level, "coverage_level")
        if not 0 < coverage < 1:
            raise DataError("coverage_level must lie in (0, 1)")
        window = _integer(self.residual_window, "residual_window", minimum=3)
        weights = tuple(_number(weight, "blend_weights") for weight in self.blend_weights)
        if (
            len(weights) < 2
            or weights != tuple(sorted(set(weights)))
            or any(not 0 <= weight <= 1 for weight in weights)
        ):
            raise DataError("blend_weights must be unique, sorted, and bounded in [0, 1]")
        if weights[0] != 0.0 or weights[-1] != 1.0:
            raise DataError("blend_weights must include both convex endpoints 0 and 1")
        minimum = _integer(self.minimum_validation_origins, "minimum_validation_origins", minimum=4)
        if minimum < 2 * window:
            raise DataError("minimum_validation_origins must be at least twice residual_window")
        empirical = _number(self.minimum_empirical_coverage, "minimum_empirical_coverage")
        if not 0 <= empirical <= 1:
            raise DataError("minimum_empirical_coverage must lie in [0, 1]")
        if _number(self.minimum_edge, "minimum_edge") < 0:
            raise DataError("minimum_edge cannot be negative")
        if _number(self.maximum_interval_width, "maximum_interval_width") <= 0:
            raise DataError("maximum_interval_width must be positive")
        _integer(self.minimum_state_samples, "minimum_state_samples", minimum=1)

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "schema": _CONTRACT_SCHEMA,
            "schema_version": 1,
            "coverage_level": self.coverage_level,
            "residual_window": self.residual_window,
            "blend_weights": list(self.blend_weights),
            "minimum_validation_origins": self.minimum_validation_origins,
            "minimum_empirical_coverage": self.minimum_empirical_coverage,
            "minimum_edge": self.minimum_edge,
            "maximum_interval_width": self.maximum_interval_width,
            "minimum_state_samples": self.minimum_state_samples,
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self._semantic_dict())

    def to_dict(self) -> dict[str, object]:
        payload = self._semantic_dict()
        payload["contract_sha256"] = self.contract_sha256
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ForecastCalibrationContractV1:
        _exact_keys(
            value,
            {
                "schema",
                "schema_version",
                "coverage_level",
                "residual_window",
                "blend_weights",
                "minimum_validation_origins",
                "minimum_empirical_coverage",
                "minimum_edge",
                "maximum_interval_width",
                "minimum_state_samples",
                "contract_sha256",
            },
            _CONTRACT_SCHEMA,
        )
        if value["schema"] != _CONTRACT_SCHEMA or value["schema_version"] != 1:
            raise DataError("unsupported ForecastCalibrationContractV1 schema")
        weights = value["blend_weights"]
        if not isinstance(weights, list):
            raise DataError("blend_weights must be an array")
        result = cls(
            coverage_level=_number(value["coverage_level"], "coverage_level"),
            residual_window=_integer(value["residual_window"], "residual_window", minimum=3),
            blend_weights=tuple(_number(weight, "blend_weights") for weight in weights),
            minimum_validation_origins=_integer(
                value["minimum_validation_origins"], "minimum_validation_origins", minimum=4
            ),
            minimum_empirical_coverage=_number(
                value["minimum_empirical_coverage"], "minimum_empirical_coverage"
            ),
            minimum_edge=_number(value["minimum_edge"], "minimum_edge"),
            maximum_interval_width=_number(
                value["maximum_interval_width"], "maximum_interval_width"
            ),
            minimum_state_samples=_integer(
                value["minimum_state_samples"], "minimum_state_samples", minimum=1
            ),
        )
        if value["contract_sha256"] != result.contract_sha256:
            raise DataError("ForecastCalibrationContractV1 contract_sha256 does not match")
        return result


@dataclass(frozen=True, slots=True)
class ForecastCalibrationOriginV1:
    """One close-stamped validation origin; no fitting split is inferred from its contents."""

    origin_id: str
    model_end_returns: tuple[float, ...]
    random_walk_end_returns: tuple[float, ...]
    observed_end_return: float
    state_key: str

    def __post_init__(self) -> None:
        _text(self.origin_id, "origin_id")
        model = _samples(self.model_end_returns, "model_end_returns")
        baseline = _samples(self.random_walk_end_returns, "random_walk_end_returns")
        if model.size != baseline.size:
            raise DataError("model and random-walk sample counts must match")
        _number(self.observed_end_return, "observed_end_return")
        _text(self.state_key, "state_key")


@dataclass(frozen=True, slots=True)
class ForecastCalibrationMetricsV1:
    evaluated_origins: int
    raw_crps: float
    calibrated_crps: float
    raw_pinball: float
    calibrated_pinball: float
    raw_coverage: float
    calibrated_coverage: float

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluated_origins": self.evaluated_origins,
            "raw_crps": self.raw_crps,
            "calibrated_crps": self.calibrated_crps,
            "raw_pinball": self.raw_pinball,
            "calibrated_pinball": self.calibrated_pinball,
            "raw_coverage": self.raw_coverage,
            "calibrated_coverage": self.calibrated_coverage,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ForecastCalibrationMetricsV1:
        expected = {
            "evaluated_origins",
            "raw_crps",
            "calibrated_crps",
            "raw_pinball",
            "calibrated_pinball",
            "raw_coverage",
            "calibrated_coverage",
        }
        _exact_keys(value, expected, "ForecastCalibrationMetricsV1")
        return cls(
            evaluated_origins=_integer(value["evaluated_origins"], "evaluated_origins", minimum=1),
            raw_crps=_number(value["raw_crps"], "raw_crps"),
            calibrated_crps=_number(value["calibrated_crps"], "calibrated_crps"),
            raw_pinball=_number(value["raw_pinball"], "raw_pinball"),
            calibrated_pinball=_number(value["calibrated_pinball"], "calibrated_pinball"),
            raw_coverage=_number(value["raw_coverage"], "raw_coverage"),
            calibrated_coverage=_number(value["calibrated_coverage"], "calibrated_coverage"),
        )


@dataclass(frozen=True, slots=True)
class ForecastStateDiagnosticV1:
    state_key: str
    sample_count: int
    minimum_samples: int
    used_pooled_fallback: bool
    evaluated_count: int
    raw_crps: float
    calibrated_crps: float
    calibrated_coverage: float

    def to_dict(self) -> dict[str, object]:
        return {
            "state_key": self.state_key,
            "sample_count": self.sample_count,
            "minimum_samples": self.minimum_samples,
            "used_pooled_fallback": self.used_pooled_fallback,
            "evaluated_count": self.evaluated_count,
            "raw_crps": self.raw_crps,
            "calibrated_crps": self.calibrated_crps,
            "calibrated_coverage": self.calibrated_coverage,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ForecastStateDiagnosticV1:
        expected = {
            "state_key",
            "sample_count",
            "minimum_samples",
            "used_pooled_fallback",
            "evaluated_count",
            "raw_crps",
            "calibrated_crps",
            "calibrated_coverage",
        }
        _exact_keys(value, expected, "ForecastStateDiagnosticV1")
        fallback = value["used_pooled_fallback"]
        if not isinstance(fallback, bool):
            raise DataError("used_pooled_fallback must be boolean")
        return cls(
            state_key=_text(value["state_key"], "state_key"),
            sample_count=_integer(value["sample_count"], "sample_count", minimum=1),
            minimum_samples=_integer(value["minimum_samples"], "minimum_samples", minimum=1),
            used_pooled_fallback=fallback,
            evaluated_count=_integer(value["evaluated_count"], "evaluated_count", minimum=1),
            raw_crps=_number(value["raw_crps"], "raw_crps"),
            calibrated_crps=_number(value["calibrated_crps"], "calibrated_crps"),
            calibrated_coverage=_number(value["calibrated_coverage"], "calibrated_coverage"),
        )


@dataclass(frozen=True, slots=True)
class ForecastCalibrationFitV1:
    """Frozen validation-only fit used unchanged for later OOS and holdout origins."""

    contract: ForecastCalibrationContractV1
    selected_model_weight: float
    conformal_radius: float
    validation_origin_ids: tuple[str, ...]
    validation_metrics: ForecastCalibrationMetricsV1
    state_diagnostics: tuple[ForecastStateDiagnosticV1, ...]

    def _semantic_dict(self) -> dict[str, object]:
        return {
            "schema": _FIT_SCHEMA,
            "schema_version": 1,
            "contract": self.contract.to_dict(),
            "selected_model_weight": self.selected_model_weight,
            "conformal_radius": self.conformal_radius,
            "validation_origin_ids": list(self.validation_origin_ids),
            "validation_metrics": self.validation_metrics.to_dict(),
            "state_diagnostics": [row.to_dict() for row in self.state_diagnostics],
        }

    @property
    def fit_sha256(self) -> str:
        return _canonical_sha256(self._semantic_dict())

    def to_dict(self) -> dict[str, object]:
        payload = self._semantic_dict()
        payload["fit_sha256"] = self.fit_sha256
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ForecastCalibrationFitV1:
        _exact_keys(
            value,
            {
                "schema",
                "schema_version",
                "contract",
                "selected_model_weight",
                "conformal_radius",
                "validation_origin_ids",
                "validation_metrics",
                "state_diagnostics",
                "fit_sha256",
            },
            _FIT_SCHEMA,
        )
        if value["schema"] != _FIT_SCHEMA or value["schema_version"] != 1:
            raise DataError("unsupported KronosCalibrationFitV1 schema")
        contract = value["contract"]
        metrics = value["validation_metrics"]
        diagnostics = value["state_diagnostics"]
        ids = value["validation_origin_ids"]
        if not isinstance(contract, Mapping) or not isinstance(metrics, Mapping):
            raise DataError("KronosCalibrationFitV1 contract and metrics must be objects")
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            raise DataError("validation_origin_ids must be a string array")
        if not isinstance(diagnostics, list) or any(
            not isinstance(item, Mapping) for item in diagnostics
        ):
            raise DataError("state_diagnostics must be an object array")
        result = cls(
            contract=ForecastCalibrationContractV1.from_dict(cast(Mapping[str, object], contract)),
            selected_model_weight=_number(value["selected_model_weight"], "selected_model_weight"),
            conformal_radius=_number(value["conformal_radius"], "conformal_radius"),
            validation_origin_ids=tuple(ids),
            validation_metrics=ForecastCalibrationMetricsV1.from_dict(
                cast(Mapping[str, object], metrics)
            ),
            state_diagnostics=tuple(
                ForecastStateDiagnosticV1.from_dict(cast(Mapping[str, object], item))
                for item in diagnostics
            ),
        )
        if value["fit_sha256"] != result.fit_sha256:
            raise DataError("KronosCalibrationFitV1 fit_sha256 does not match its content")
        return result


def _blend(origin: ForecastCalibrationOriginV1, model_weight: float) -> np.ndarray:
    model = _samples(origin.model_end_returns, "model_end_returns")
    baseline = _samples(origin.random_walk_end_returns, "random_walk_end_returns")
    if model.size != baseline.size:
        raise DataError("model and random-walk sample counts must match")
    return model_weight * model + (1.0 - model_weight) * baseline


def _select_model_weight(
    origins: Sequence[ForecastCalibrationOriginV1], weights: Sequence[float]
) -> float:
    losses = {
        weight: float(
            np.mean(
                [
                    crps_sample(_blend(origin, weight), origin.observed_end_return)
                    for origin in origins
                ]
            )
        )
        for weight in weights
    }
    return min(weights, key=lambda weight: (losses[weight], -weight))


def _absolute_residuals(
    origins: Sequence[ForecastCalibrationOriginV1], model_weight: float
) -> tuple[float, ...]:
    return tuple(
        abs(origin.observed_end_return - float(np.median(_blend(origin, model_weight))))
        for origin in origins
    )


def _conformal_radius(residuals: Sequence[float], coverage_level: float) -> float:
    values = np.asarray(residuals, dtype=np.float64)
    corrected = min(1.0, math.ceil((values.size + 1) * coverage_level) / values.size)
    return float(np.quantile(values, corrected, method="higher"))


def _calibrate_samples(
    samples: np.ndarray, *, coverage_level: float, conformal_radius: float
) -> np.ndarray:
    median = float(np.median(samples))
    tail = (1.0 - coverage_level) / 2.0
    low, high = np.quantile(samples, [tail, 1.0 - tail])
    half_width = float(high - low) / 2.0
    if half_width <= np.finfo(float).eps:
        return np.linspace(median - conformal_radius, median + conformal_radius, samples.size)
    return median + (samples - median) * (conformal_radius / half_width)


@dataclass(frozen=True, slots=True)
class _ScoredOrigin:
    state_key: str
    raw_crps: float
    calibrated_crps: float
    raw_pinball: float
    calibrated_pinball: float
    raw_covered: bool
    calibrated_covered: bool


def _metrics(rows: Sequence[_ScoredOrigin]) -> ForecastCalibrationMetricsV1:
    if not rows:
        raise DataError("calibration metrics require at least one scored origin")
    return ForecastCalibrationMetricsV1(
        evaluated_origins=len(rows),
        raw_crps=float(np.mean([row.raw_crps for row in rows])),
        calibrated_crps=float(np.mean([row.calibrated_crps for row in rows])),
        raw_pinball=float(np.mean([row.raw_pinball for row in rows])),
        calibrated_pinball=float(np.mean([row.calibrated_pinball for row in rows])),
        raw_coverage=float(np.mean([row.raw_covered for row in rows])),
        calibrated_coverage=float(np.mean([row.calibrated_covered for row in rows])),
    )


def fit_rolling_conformal_blend(
    contract: ForecastCalibrationContractV1,
    validation_origins: Sequence[ForecastCalibrationOriginV1],
) -> ForecastCalibrationFitV1:
    """Fit a preregistered convex blend and conformal radius on validation origins only."""
    origins = tuple(validation_origins)
    if len(origins) < contract.minimum_validation_origins:
        raise DataError(
            "insufficient validation origins for frozen calibration: "
            f"{len(origins)} < {contract.minimum_validation_origins}"
        )
    if len({origin.origin_id for origin in origins}) != len(origins):
        raise DataError("calibration validation origin ids must be unique")
    scored: list[_ScoredOrigin] = []
    for index in range(contract.residual_window, len(origins)):
        prior_origins = origins[:index]
        rolling_weight = _select_model_weight(prior_origins, contract.blend_weights)
        residuals = _absolute_residuals(prior_origins, rolling_weight)
        radius = _conformal_radius(residuals[-contract.residual_window :], contract.coverage_level)
        raw = _blend(origins[index], rolling_weight)
        calibrated = _calibrate_samples(
            raw, coverage_level=contract.coverage_level, conformal_radius=radius
        )
        observed = origins[index].observed_end_return
        scored.append(
            _ScoredOrigin(
                state_key=origins[index].state_key,
                raw_crps=crps_sample(raw, observed),
                calibrated_crps=crps_sample(calibrated, observed),
                raw_pinball=(pinball_loss(raw, observed, 0.25) + pinball_loss(raw, observed, 0.75))
                / 2.0,
                calibrated_pinball=(
                    pinball_loss(calibrated, observed, 0.25)
                    + pinball_loss(calibrated, observed, 0.75)
                )
                / 2.0,
                raw_covered=central_coverage(raw, observed, contract.coverage_level),
                calibrated_covered=central_coverage(calibrated, observed, contract.coverage_level),
            )
        )
    pooled_metrics = _metrics(scored)
    grouped: dict[str, list[_ScoredOrigin]] = {}
    for row in scored:
        grouped.setdefault(row.state_key, []).append(row)
    diagnostics: list[ForecastStateDiagnosticV1] = []
    for state_key in sorted(grouped):
        state_rows = grouped[state_key]
        fallback = len(state_rows) < contract.minimum_state_samples
        selected_rows = scored if fallback else state_rows
        state_metrics = _metrics(selected_rows)
        diagnostics.append(
            ForecastStateDiagnosticV1(
                state_key=state_key,
                sample_count=len(state_rows),
                minimum_samples=contract.minimum_state_samples,
                used_pooled_fallback=fallback,
                evaluated_count=state_metrics.evaluated_origins,
                raw_crps=state_metrics.raw_crps,
                calibrated_crps=state_metrics.calibrated_crps,
                calibrated_coverage=state_metrics.calibrated_coverage,
            )
        )
    selected_weight = _select_model_weight(origins, contract.blend_weights)
    residuals = _absolute_residuals(origins, selected_weight)
    final_radius = _conformal_radius(
        residuals[-contract.residual_window :], contract.coverage_level
    )
    return ForecastCalibrationFitV1(
        contract=contract,
        selected_model_weight=selected_weight,
        conformal_radius=final_radius,
        validation_origin_ids=tuple(origin.origin_id for origin in origins),
        validation_metrics=pooled_metrics,
        state_diagnostics=tuple(diagnostics),
    )


@dataclass(frozen=True, slots=True)
class KronosCalibratedAssessmentV1:
    ready: bool
    candidate: str | None
    signal: int | None
    blocker_codes: tuple[str, ...]
    median_end_return: float
    interval_low: float
    interval_high: float
    interval_width: float
    calibration_fit_sha256: str


@dataclass(frozen=True, slots=True)
class ForecastCalibratedOriginEvaluationV1:
    """One OOS origin scored with a calibration fit frozen on earlier validation data."""

    origin_id: str
    state_key: str
    market_state_eligible: bool
    raw_crps: float
    calibrated_crps: float
    raw_pinball: float
    calibrated_pinball: float
    raw_covered: bool
    calibrated_covered: bool
    assessment: KronosCalibratedAssessmentV1


def assess_kronos_calibrated_candidate(
    fit: ForecastCalibrationFitV1,
    *,
    model_end_returns: Sequence[float],
    random_walk_end_returns: Sequence[float],
    market_state_eligible: bool,
) -> KronosCalibratedAssessmentV1:
    """Emit ``kronos_calibrated`` only when all frozen admission rules pass."""
    origin = ForecastCalibrationOriginV1(
        origin_id="candidate",
        model_end_returns=tuple(model_end_returns),
        random_walk_end_returns=tuple(random_walk_end_returns),
        observed_end_return=0.0,
        state_key="candidate",
    )
    blended = _blend(origin, fit.selected_model_weight)
    calibrated = _calibrate_samples(
        blended,
        coverage_level=fit.contract.coverage_level,
        conformal_radius=fit.conformal_radius,
    )
    tail = (1.0 - fit.contract.coverage_level) / 2.0
    interval_low, interval_high = (
        float(value) for value in np.quantile(calibrated, [tail, 1.0 - tail])
    )
    median = float(np.median(calibrated))
    width = interval_high - interval_low
    blockers: list[str] = []
    if fit.validation_metrics.calibrated_coverage < fit.contract.minimum_empirical_coverage:
        blockers.append("CALIBRATION_COVERAGE_BELOW_FLOOR")
    if width > fit.contract.maximum_interval_width:
        blockers.append("CALIBRATED_UNCERTAINTY_TOO_WIDE")
    if not market_state_eligible:
        blockers.append("MARKET_STATE_UNAVAILABLE")
    signal: int | None = None
    if interval_low >= fit.contract.minimum_edge:
        signal = 1
    elif interval_high <= -fit.contract.minimum_edge:
        signal = -1
    else:
        blockers.append("CALIBRATED_EDGE_BELOW_FLOOR")
    ready = not blockers
    return KronosCalibratedAssessmentV1(
        ready=ready,
        candidate="kronos_calibrated" if ready else None,
        signal=signal if ready else None,
        blocker_codes=tuple(blockers),
        median_end_return=median,
        interval_low=interval_low,
        interval_high=interval_high,
        interval_width=width,
        calibration_fit_sha256=fit.fit_sha256,
    )


def evaluate_frozen_calibration(
    fit: ForecastCalibrationFitV1,
    origins: Sequence[ForecastCalibrationOriginV1],
    *,
    market_state_eligibility: Mapping[str, bool],
) -> tuple[ForecastCalibratedOriginEvaluationV1, ...]:
    """Score later origins without changing the validation-fitted blend or conformal radius."""
    validation_ids = set(fit.validation_origin_ids)
    results: list[ForecastCalibratedOriginEvaluationV1] = []
    for origin in origins:
        if origin.origin_id in validation_ids:
            raise DataError("OOS calibration origins overlap the frozen validation fit")
        if origin.origin_id not in market_state_eligibility:
            raise DataError(f"market-state eligibility is missing for origin {origin.origin_id!r}")
        raw = _blend(origin, fit.selected_model_weight)
        calibrated = _calibrate_samples(
            raw,
            coverage_level=fit.contract.coverage_level,
            conformal_radius=fit.conformal_radius,
        )
        observed = origin.observed_end_return
        eligible = market_state_eligibility[origin.origin_id]
        if not isinstance(eligible, bool):
            raise DataError("market-state eligibility values must be boolean")
        results.append(
            ForecastCalibratedOriginEvaluationV1(
                origin_id=origin.origin_id,
                state_key=origin.state_key,
                market_state_eligible=eligible,
                raw_crps=crps_sample(raw, observed),
                calibrated_crps=crps_sample(calibrated, observed),
                raw_pinball=(pinball_loss(raw, observed, 0.25) + pinball_loss(raw, observed, 0.75))
                / 2.0,
                calibrated_pinball=(
                    pinball_loss(calibrated, observed, 0.25)
                    + pinball_loss(calibrated, observed, 0.75)
                )
                / 2.0,
                raw_covered=central_coverage(raw, observed, fit.contract.coverage_level),
                calibrated_covered=central_coverage(
                    calibrated, observed, fit.contract.coverage_level
                ),
                assessment=assess_kronos_calibrated_candidate(
                    fit,
                    model_end_returns=origin.model_end_returns,
                    random_walk_end_returns=origin.random_walk_end_returns,
                    market_state_eligible=eligible,
                ),
            )
        )
    if not results:
        raise DataError("frozen calibration evaluation requires at least one OOS origin")
    return tuple(results)


__all__ = [
    "ForecastCalibrationContractV1",
    "ForecastCalibratedOriginEvaluationV1",
    "ForecastCalibrationFitV1",
    "ForecastCalibrationMetricsV1",
    "ForecastCalibrationOriginV1",
    "ForecastStateDiagnosticV1",
    "KronosCalibratedAssessmentV1",
    "assess_kronos_calibrated_candidate",
    "evaluate_frozen_calibration",
    "fit_rolling_conformal_blend",
]
