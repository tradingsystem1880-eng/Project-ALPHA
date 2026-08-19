"""Immutable deterministic runtime for the sandbox-only hedged-basis candidate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

import numpy as np
import polars as pl

from alpha_cli import _artifacts, _runner
from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_core import DataError
from alpha_strategies.hedged_basis import (
    HedgedBasisEvaluationV1,
    HedgedBasisObservationV1,
    evaluate_hedged_basis,
    registered_hedged_basis_plan,
)
from alpha_validation import (
    annualized_volatility,
    empirical_return_paths,
    regime_switching_return_paths,
    sharpe_ratio,
    student_t_return_paths,
    summarize_path_family,
)

_COMMANDS: Final = {
    "baseline": "candidate_baseline",
    "inner_oos": "candidate_oos",
    "null_bootstrap": "candidate_null_bootstrap",
    "null_student_t": "candidate_null_student_t",
    "null_garch": "candidate_null_garch",
    "monte_carlo_classical": "candidate_monte_carlo_classical",
    "monte_carlo_kronos_fixture": "candidate_monte_carlo_kronos",
    "optimize_cost_sensitivity": "candidate_optim",
    "portfolio_concentration": "candidate_portfolio",
    "cross_asset_scope": "candidate_cross_asset",
    "fixed_stress": "candidate_fixed_stress",
    "qlib_fixture": "candidate_qlib",
    "kronos_forecast_fixture": "candidate_kronos_forecast",
    "kronos_eval_fixture": "candidate_kronos_eval",
    "holdout": "candidate_holdout",
}
_ANALYSES: Final = frozenset(_COMMANDS)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _source_fingerprint(observations: tuple[HedgedBasisObservationV1, ...]) -> str:
    digest = hashlib.sha256()
    digest.update(b"project-alpha-hedged-basis-observations-v1\0")
    for observation in observations:
        digest.update(bytes.fromhex(observation.observation_id))
    return digest.hexdigest()


def _admit(
    observations: tuple[HedgedBasisObservationV1, ...], *, as_of: datetime | None
) -> tuple[HedgedBasisObservationV1, ...]:
    cutoff = None if as_of is None else as_of.astimezone(UTC)
    admitted = tuple(
        observation
        for observation in observations
        if cutoff is None or observation.exit_available_at <= cutoff
    )
    if not admitted:
        raise DataError("hedged basis candidate has no causally available admitted events")
    return admitted


def _payloads(
    observations: tuple[HedgedBasisObservationV1, ...],
) -> tuple[dict[str, object], pl.DataFrame, HedgedBasisEvaluationV1]:
    result = evaluate_hedged_basis(observations)
    returns = np.asarray([trade.net_return for trade in result.trades], dtype=np.float64)
    volatility = (
        annualized_volatility(returns, periods_per_year=result.periods_per_year)
        if returns.size >= 2
        else None
    )
    sharpe = (
        sharpe_ratio(returns, periods_per_year=result.periods_per_year)
        if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0
        else None
    )
    equity = np.cumprod(1.0 + returns)
    peaks = np.maximum.accumulate(np.concatenate(([1.0], equity)))
    curve = np.concatenate(([1.0], equity))
    drawdown = curve / peaks - 1.0
    evaluation = {
        "schema": "HedgedBasisCandidateEvaluationV1",
        "schema_version": 1,
        "strategy_name": "hedged_basis_crowding_v1",
        "deployment_scope": "sandbox_only",
        "places_orders": False,
        "event_count": len(result.trades),
        "periods_per_year": result.periods_per_year,
        "total_round_trip_cost_bps": result.total_round_trip_cost_bps,
        "cumulative_return": result.cumulative_return,
        "annualized_volatility": volatility,
        "annualized_sharpe": sharpe,
        "maximum_drawdown": float(drawdown.min()),
        "plan_fingerprint": result.plan_fingerprint,
        "event_operator_fingerprint": result.event_operator_fingerprint,
        "input_sha256": [list(item) for item in result.input_sha256],
    }
    rows: list[dict[str, object]] = []
    running = 1.0
    for trade in result.trades:
        running *= 1.0 + trade.net_return
        rows.append(
            {
                **asdict(trade),
                "equity": running,
                "deployment_scope": "sandbox_only",
            }
        )
    return evaluation, pl.DataFrame(rows), result


def _causal_return_regimes(returns: np.ndarray) -> np.ndarray:
    """Label each event from only the magnitude history available before that event."""
    labels = np.zeros(returns.size, dtype=np.int8)
    for index in range(1, returns.size):
        prior = np.abs(returns[:index])
        labels[index] = int(abs(float(returns[index - 1])) >= float(np.median(prior)))
    return labels


def _family_payload(family: str, paths: np.ndarray) -> dict[str, object]:
    summary = summarize_path_family(family, paths)
    payload: object = json.loads(_canonical(asdict(summary)))
    if not isinstance(payload, dict):  # pragma: no cover - dataclass serialization is an object.
        raise DataError("candidate Monte Carlo family summary is invalid")
    return payload


def _classical_path_risk(returns: np.ndarray) -> tuple[dict[str, object], bool]:
    paths = 2048
    iid = empirical_return_paths(returns, n_paths=paths, seed=9413)
    student = student_t_return_paths(returns, n_paths=paths, seed=9421)
    families = [_family_payload("iid_empirical", iid)]
    try:
        regime = regime_switching_return_paths(
            returns,
            _causal_return_regimes(returns),
            n_paths=paths,
            min_state_observations=10,
            min_state_transitions=5,
            seed=9417,
        )
        regime_payload = _family_payload("regime_switching", regime.paths)
        regime_payload.update(
            {
                "state_observations": list(regime.state_observations),
                "state_transitions": list(regime.state_transitions),
            }
        )
    except DataError as exc:
        regime_payload = {
            "family": "regime_switching",
            "status": "not_estimable",
            "reason": str(exc),
        }
    families.append(regime_payload)
    families.append(_family_payload("student_t", student))
    status = "clear" if all(row.get("status") == "clear" for row in families) else "warning"
    return {
        "method": "three_classical_path_risk_families_v1",
        "model": "classical_three_family",
        "paths_per_family": paths,
        "semantic_seeds": {"iid_empirical": 9413, "regime_switching": 9417, "student_t": 9421},
        "causal_regime_labels": "prior_event_absolute_return_expanding_median_v1",
        "families": families,
        "status": status,
        "scenario_risk_only": True,
        "edge_or_authority_claim": False,
    }, status == "clear"


def _analysis_result(
    analysis: str, result: HedgedBasisEvaluationV1
) -> tuple[dict[str, object], bool]:
    returns = np.asarray([trade.net_return for trade in result.trades], dtype=np.float64)
    if analysis == "baseline":
        passed = bool(returns.size and float(np.mean(returns)) > 0.0)
        return {"method": "full_registered_event_replay_v1"}, passed
    if analysis == "holdout":
        passed = bool(returns.size and float(np.mean(returns)) > 0.0)
        return {
            "method": "one_shot_locked_event_window_v1",
            "event_count": int(returns.size),
            "mean_net_return": float(np.mean(returns)),
        }, passed
    if analysis == "inner_oos":
        start = max(0, int(np.floor(returns.size * 0.8)))
        selected = returns[start:]
        passed = bool(selected.size and float(np.mean(selected)) > 0.0)
        return {
            "method": "ordered_last_20_percent_event_groups_v1",
            "event_count": int(selected.size),
            "mean_net_return": float(np.mean(selected)),
        }, passed

    if analysis in {"monte_carlo_classical", "monte_carlo_kronos_fixture"}:
        if analysis == "monte_carlo_classical":
            return _classical_path_risk(returns)
        paths = 2048
        rng = np.random.default_rng(9419)
        # The deterministic acceptance fixture deliberately does not claim a
        # downloaded Kronos model. It exercises the model-family boundary with
        # a disclosed AR(1) generator calibrated only on the admitted returns.
        lag = returns[:-1]
        lead = returns[1:]
        denominator = float(np.dot(lag, lag)) if lag.size else 0.0
        phi = (
            0.0
            if denominator == 0.0
            else float(np.clip(np.dot(lag, lead) / denominator, -0.95, 0.95))
        )
        residuals = lead - phi * lag if lead.size else returns
        scale = float(np.std(residuals, ddof=1)) if residuals.size >= 2 else 0.0
        simulated = np.empty((paths, returns.size), dtype=np.float64)
        simulated[:, 0] = rng.choice(returns, size=paths)
        for index in range(1, returns.size):
            simulated[:, index] = phi * simulated[:, index - 1] + rng.normal(0.0, scale, size=paths)
        method = "disclosed_fake_ar1_generator_v1"
        model = "fake"
        terminal = np.prod(1.0 + simulated, axis=1) - 1.0
        loss_probability = float(np.mean(terminal <= 0.0))
        status = "clear" if loss_probability <= 0.25 else "warning"
        return {
            "method": method,
            "model": model,
            "paths": paths,
            "seed": 9419,
            "loss_probability": loss_probability,
            "terminal_return_p05": float(np.quantile(terminal, 0.05)),
            "status": status,
        }, status == "clear"
    if analysis == "optimize_cost_sensitivity":
        gross = returns + 0.004
        trials = [
            {
                "trial": index,
                "total_round_trip_cost_bps": cost,
                "mean_net_return": float(np.mean(gross - cost / 10_000.0)),
                "selected": cost == 40,
            }
            for index, cost in enumerate((20, 40, 60))
        ]
        passed = bool(trials[1]["mean_net_return"] > 0.0)
        return {
            "method": "frozen_cost_sensitivity_no_adaptive_selection_v1",
            "registered_cost_bps": 40,
            "trials": trials,
        }, passed
    if analysis == "portfolio_concentration":
        return {
            "method": "single_candidate_concentration_diagnostic_v1",
            "candidate_count": 1,
            "gross_exposure_legs": 2,
            "venues": ["bybit", "binance"],
            "concentration_warning": "single_registered_asset",
        }, True
    if analysis == "cross_asset_scope":
        return {
            "method": "registered_universe_scope_check_v1",
            "status": "completed_not_applicable_single_registered_asset",
            "eligible_cross_assets": [],
            "reason": "ADR-0033 registers BTCUSDT only; no second asset may be invented.",
        }, True
    if analysis == "fixed_stress":
        scenarios = [
            ("cost_plus_20_bps", -0.002),
            ("perp_gap_minus_1_percent", -0.010),
            ("funding_removed", -0.001),
            ("combined_adverse", -0.013),
        ]
        return {
            "method": "fixed_additive_return_stress_v1",
            "scenarios": [
                {
                    "name": name,
                    "return_adjustment": adjustment,
                    "cumulative_return": float(np.prod(1.0 + returns + adjustment) - 1.0),
                }
                for name, adjustment in scenarios
            ],
            "governing_null_test": False,
        }, True
    if analysis == "qlib_fixture":
        lagged = returns[:-1]
        outcomes = returns[1:]
        directional_accuracy = (
            None if outcomes.size == 0 else float(np.mean(np.sign(lagged) == np.sign(outcomes)))
        )
        return {
            "method": "qlib_contract_temporal_fixture_v1",
            "model": "lag_sign_baseline",
            "external_qlib_model_loaded": False,
            "promotion_authority": False,
            "directional_accuracy": directional_accuracy,
        }, True
    if analysis in {"kronos_forecast_fixture", "kronos_eval_fixture"}:
        return {
            "method": (
                "disclosed_fake_last_return_forecast_v1"
                if analysis == "kronos_forecast_fixture"
                else "disclosed_fake_rolling_error_evaluation_v1"
            ),
            "model": "fake",
            "real_kronos_weights_loaded": False,
            "promotion_authority": False,
            "mean_absolute_error": (
                None if returns.size < 2 else float(np.mean(np.abs(returns[1:] - returns[:-1])))
            ),
        }, True

    centered = returns - float(np.mean(returns))
    observed = abs(float(np.mean(returns)))
    rng = np.random.default_rng(7331)
    paths = 4096
    null_model = analysis.removeprefix("null_")
    if null_model == "bootstrap":
        signs = rng.choice(np.asarray((-1.0, 1.0)), size=(paths, returns.size))
        null_returns = signs * centered
        method = "deterministic_centered_sign_randomization_v1"
        parameters: dict[str, object] = {}
    elif null_model == "student_t":
        degrees_of_freedom = 5
        scale = float(np.std(centered, ddof=1)) if returns.size >= 2 else 0.0
        scale /= float(np.sqrt(degrees_of_freedom / (degrees_of_freedom - 2)))
        null_returns = rng.standard_t(degrees_of_freedom, size=(paths, returns.size)) * scale
        method = "deterministic_student_t_location_null_v1"
        parameters = {"degrees_of_freedom": degrees_of_freedom}
    else:
        alpha, beta = 0.10, 0.85
        variance = float(np.var(centered, ddof=1)) if returns.size >= 2 else 0.0
        omega = max(variance * (1.0 - alpha - beta), np.finfo(np.float64).eps)
        null_returns = np.empty((paths, returns.size), dtype=np.float64)
        conditional_variance = np.full(paths, max(variance, omega), dtype=np.float64)
        prior_shock = np.zeros(paths, dtype=np.float64)
        for index in range(returns.size):
            conditional_variance = omega + alpha * prior_shock**2 + beta * conditional_variance
            prior_shock = rng.normal(size=paths) * np.sqrt(conditional_variance)
            null_returns[:, index] = prior_shock
        method = "deterministic_garch_1_1_location_null_v1"
        parameters = {"alpha": alpha, "beta": beta, "omega": omega}
    null_means = np.abs(np.mean(null_returns, axis=1))
    p_value = float((np.count_nonzero(null_means >= observed) + 1) / (paths + 1))
    passed = p_value <= 0.05
    return {
        "method": method,
        "null_model": null_model,
        "paths": paths,
        "seed": 7331,
        "two_sided_p_value": p_value,
        "parameters": parameters,
    }, passed


def run_hedged_basis_candidate(
    data_dir: Path,
    *,
    snapshot_id: str,
    snapshot_hash: str,
    research_contract_id: str,
    observations: tuple[HedgedBasisObservationV1, ...],
    analysis: str,
    source_run_id: str | None = None,
    holdout_start: date | None = None,
    holdout_end: date | None = None,
    holdout_spec_hash: str | None = None,
    research_cutoff: str | None,
    as_of: datetime | None,
) -> dict[str, Any]:
    """Publish one candidate analysis without constructing an execution adapter."""
    if analysis not in _ANALYSES:
        raise DataError(f"unsupported hedged basis analysis {analysis!r}")
    if len(snapshot_id) != 64 or len(snapshot_hash) != 64:
        raise DataError("hedged basis run requires exact snapshot identities")
    if not research_contract_id.startswith("rc_") or len(research_contract_id) != 67:
        raise DataError("hedged basis run requires its promoted research contract")
    admitted = _admit(observations, as_of=as_of)
    if analysis == "holdout":
        if (
            holdout_start is None
            or holdout_end is None
            or holdout_end < holdout_start
            or holdout_spec_hash is None
            or len(holdout_spec_hash) != 64
        ):
            raise DataError("candidate holdout requires its exact sealed window and hash")
        admitted = tuple(
            observation
            for observation in admitted
            if holdout_start <= observation.event_time.date() <= holdout_end
        )
        if not admitted:
            raise DataError("candidate holdout has no events inside the sealed window")
    source = _source_fingerprint(admitted)
    command = _COMMANDS[analysis]
    identity_payload = {
        "command": command,
        "strategy_name": "hedged_basis_crowding_v1",
        "snapshot_id": snapshot_id,
        "research_cutoff": research_cutoff,
        "research_inheritance": {"contract_id": research_contract_id},
        "candidate_plan": registered_hedged_basis_plan().to_dict(),
    }
    if analysis.startswith("monte_carlo_"):
        if source_run_id is None or len(source_run_id) != 16:
            raise DataError("candidate Monte Carlo requires its exact source validation run")
        identity_payload["source_run_id"] = source_run_id
    if analysis == "holdout":
        assert holdout_start is not None
        assert holdout_end is not None
        identity_payload.update(
            {
                "holdout_start": holdout_start.isoformat(),
                "holdout_end": holdout_end.isoformat(),
                "holdout_spec_hash": holdout_spec_hash,
            }
        )
    identity = _runner.run_identity_for(
        identity_payload,
        source_fingerprint=source,
        snapshot_hash=snapshot_hash,
    )
    run_dir = _artifacts.run_dir(data_dir, identity.run_id)
    evaluation, frame, result = _payloads(admitted)
    analysis_result, passed = _analysis_result(analysis, result)
    _artifacts.publish_artifact(
        run_dir / "candidate_evaluation.json",
        lambda target: target.write_text(_canonical(evaluation), encoding="utf-8"),
    )
    _artifacts.publish_artifact(run_dir / "returns.parquet", frame.write_parquet)
    _artifacts.publish_artifact(
        run_dir / "candidate_analysis.json",
        lambda target: target.write_text(_canonical(analysis_result), encoding="utf-8"),
    )
    _artifacts.publish_artifact(
        run_dir / "report.md",
        lambda target: target.write_text(
            "# Hedged Basis Candidate\n\n"
            "**SANDBOX ONLY — TWO-LEG RETURN REPLAY — NO PAPER OR ORDER AUTHORITY**\n\n"
            f"Evaluated {evaluation['event_count']} registered events net of "
            f"{evaluation['total_round_trip_cost_bps']} bp total round-trip cost.\n",
            encoding="utf-8",
        ),
    )
    manifest: dict[str, Any] = {
        **identity_payload,
        **identity.manifest_fields(),
        "run_id": identity.run_id,
        "kind": "strategy_candidate",
        "snapshot_hash": snapshot_hash,
        "deployment_scope": "sandbox_only",
        "execution_model": "two_leg_return_replay",
        "places_orders": False,
        "paper_eligible": False,
        "broker_connection_attempted": False,
        "event_count": len(admitted),
        "passed": passed,
        "metadata": analysis_result,
        "candidate_evaluation_artifact": "candidate_evaluation.json",
        "candidate_analysis_artifact": "candidate_analysis.json",
        "returns_artifact": "returns.parquet",
    }
    if analysis.startswith("monte_carlo_"):
        manifest["source_run_id"] = source_run_id
        manifest["status"] = analysis_result["status"]
    if analysis == "holdout":
        assert holdout_start is not None
        assert holdout_end is not None
        manifest["holdout_spec_hash"] = holdout_spec_hash
        manifest["holdout_start"] = holdout_start.isoformat()
        manifest["holdout_end"] = holdout_end.isoformat()
    _artifacts.write_manifest(run_dir, manifest)
    return _artifacts.read_manifest(run_dir)


def validate_hedged_basis_candidate_artifacts(
    run_dir: Path,
    manifest: dict[str, object],
    *,
    observations: tuple[HedgedBasisObservationV1, ...],
    as_of: datetime | None,
) -> dict[str, object]:
    """Recompute the exact candidate result from typed frozen observations."""
    verify_manifest_artifacts(run_dir, manifest)
    analysis = next(
        (name for name, command in _COMMANDS.items() if command == manifest.get("command")), None
    )
    if analysis is None or manifest.get("deployment_scope") != "sandbox_only":
        raise DataError("hedged basis manifest is not a registered sandbox candidate run")
    admitted = _admit(observations, as_of=as_of)
    if analysis == "holdout":
        try:
            holdout_start = date.fromisoformat(str(manifest["holdout_start"]))
            holdout_end = date.fromisoformat(str(manifest["holdout_end"]))
        except (KeyError, ValueError) as exc:
            raise DataError("hedged basis holdout window is invalid") from exc
        admitted = tuple(
            observation
            for observation in admitted
            if holdout_start <= observation.event_time.date() <= holdout_end
        )
        if not admitted:
            raise DataError("hedged basis holdout window contains no events")
    expected_payload: dict[str, object] = {
        "command": _COMMANDS[analysis],
        "strategy_name": "hedged_basis_crowding_v1",
        "snapshot_id": manifest.get("snapshot_id"),
        "research_cutoff": manifest.get("research_cutoff"),
        "research_inheritance": manifest.get("research_inheritance"),
        "candidate_plan": registered_hedged_basis_plan().to_dict(),
    }
    if analysis.startswith("monte_carlo_"):
        expected_payload["source_run_id"] = manifest.get("source_run_id")
    if analysis == "holdout":
        expected_payload.update(
            {
                "holdout_start": manifest.get("holdout_start"),
                "holdout_end": manifest.get("holdout_end"),
                "holdout_spec_hash": manifest.get("holdout_spec_hash"),
            }
        )
    expected_identity = _runner.run_identity_for(
        expected_payload,
        source_fingerprint=_source_fingerprint(admitted),
        snapshot_hash=str(manifest.get("snapshot_hash")),
    )
    if manifest.get("run_id") != expected_identity.run_id or any(
        manifest.get(field) != value for field, value in expected_identity.manifest_fields().items()
    ):
        raise DataError("hedged basis manifest does not bind the frozen candidate execution")
    expected, _, result = _payloads(admitted)
    expected_analysis, expected_passed = _analysis_result(analysis, result)
    try:
        actual: object = json.loads(
            (run_dir / "candidate_evaluation.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("hedged basis candidate evaluation is unreadable") from exc
    if _canonical(actual) != _canonical(expected):
        raise DataError("hedged basis candidate evaluation fails exact recomputation")
    try:
        actual_analysis: object = json.loads(
            (run_dir / "candidate_analysis.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("hedged basis candidate analysis is unreadable") from exc
    if (
        _canonical(actual_analysis) != _canonical(expected_analysis)
        or manifest.get("metadata") != expected_analysis
        or manifest.get("passed") is not expected_passed
    ):
        raise DataError("hedged basis candidate analysis fails exact recomputation")
    return expected


__all__ = [
    "run_hedged_basis_candidate",
    "validate_hedged_basis_candidate_artifacts",
]
