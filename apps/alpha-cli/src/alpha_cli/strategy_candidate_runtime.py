"""Immutable deterministic runtime for the sandbox-only hedged-basis candidate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
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
from alpha_validation import annualized_volatility, sharpe_ratio

_ANALYSES: Final = frozenset({"baseline"})
_COMMANDS: Final = {"baseline": "candidate_baseline"}


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


def run_hedged_basis_candidate(
    data_dir: Path,
    *,
    snapshot_id: str,
    snapshot_hash: str,
    research_contract_id: str,
    observations: tuple[HedgedBasisObservationV1, ...],
    analysis: str,
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
    identity = _runner.run_identity_for(
        identity_payload,
        source_fingerprint=source,
        snapshot_hash=snapshot_hash,
    )
    run_dir = _artifacts.run_dir(data_dir, identity.run_id)
    evaluation, frame, _ = _payloads(admitted)
    _artifacts.publish_artifact(
        run_dir / "candidate_evaluation.json",
        lambda target: target.write_text(_canonical(evaluation), encoding="utf-8"),
    )
    _artifacts.publish_artifact(run_dir / "returns.parquet", frame.write_parquet)
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
        "candidate_evaluation_artifact": "candidate_evaluation.json",
        "returns_artifact": "returns.parquet",
    }
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
    expected_identity = _runner.run_identity_for(
        {
            "command": _COMMANDS[analysis],
            "strategy_name": "hedged_basis_crowding_v1",
            "snapshot_id": manifest.get("snapshot_id"),
            "research_cutoff": manifest.get("research_cutoff"),
            "research_inheritance": manifest.get("research_inheritance"),
            "candidate_plan": registered_hedged_basis_plan().to_dict(),
        },
        source_fingerprint=_source_fingerprint(admitted),
        snapshot_hash=str(manifest.get("snapshot_hash")),
    )
    if manifest.get("run_id") != expected_identity.run_id or any(
        manifest.get(field) != value for field, value in expected_identity.manifest_fields().items()
    ):
        raise DataError("hedged basis manifest does not bind the frozen candidate execution")
    expected, _, _ = _payloads(admitted)
    try:
        actual: object = json.loads(
            (run_dir / "candidate_evaluation.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("hedged basis candidate evaluation is unreadable") from exc
    if _canonical(actual) != _canonical(expected):
        raise DataError("hedged basis candidate evaluation fails exact recomputation")
    return expected


__all__ = [
    "run_hedged_basis_candidate",
    "validate_hedged_basis_candidate_artifacts",
]
