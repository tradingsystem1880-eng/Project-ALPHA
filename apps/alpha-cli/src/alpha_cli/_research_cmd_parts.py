"""Independent contract projections and durable research-command bookkeeping."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal, NamedTuple, cast

from alpha_cli._cli_json import emit as _emit
from alpha_cli.control_store import ControlStore, ResearchPhase, ResearchResponsibility
from alpha_cli.research_crypto_binding import CryptoEmpiricalDataset
from alpha_cli.research_d1 import D1_ANALYSES_ARTIFACT, D1_EVIDENCE_ARTIFACT
from alpha_cli.research_d2 import D2_EVIDENCE_ARTIFACT
from alpha_cli.research_readiness import ReadinessProjection, derive_research_readiness
from alpha_cli.research_runtime import registered_d0_material_choices, registered_d0_operator
from alpha_core import DataError
from alpha_research import (
    EqualDurationResearchBars,
    ResearchChartFingerprintV1,
    ResearchD2BoundaryV2,
)


def _sha_json(value: object) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as exc:
        raise DataError("research fingerprint input must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _manifest_artifact_sha256(manifest: Mapping[str, object], artifact: str) -> str:
    artifacts = manifest.get("artifacts")
    metadata = None if not isinstance(artifacts, Mapping) else artifacts.get(artifact)
    digest = None if not isinstance(metadata, Mapping) else metadata.get("sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise DataError(f"research run has no valid {artifact!r} artifact digest")
    return digest


def _require_resolved_material(value: object, label: str) -> None:
    """Reject approval-ready material fields that still contain sentinel placeholders."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            _require_resolved_material(item, f"{label}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _require_resolved_material(item, f"{label}[{index}]")
        return
    if isinstance(value, str) and any(
        marker in value.casefold()
        for marker in ("unresolved", "placeholder", "selection_required", "provider_required")
    ):
        raise DataError(f"approval-ready {label} contains unresolved material semantics")


_EMPIRICAL_CHART_CHOICES: Final = frozenset(
    {"tiingo_daily_fallback", "bybit_btcusdt_linear_hourly"}
)


class _EmpiricalDataset(NamedTuple):
    """One registered research dataset resolved to its exact loaded research bars."""

    ref: dict[str, object]
    bars: EqualDurationResearchBars


def _case_payload(
    store: ControlStore, project_id: str
) -> tuple[dict[str, object], dict[str, object]]:
    summary = store.research_case_summary(project_id)
    active = summary.get("active_contract")
    if not isinstance(active, dict):
        raise DataError("research case has no active contract projection")
    payload = active.get("payload")
    if not isinstance(payload, dict):
        raise DataError("research case has no active contract payload")
    return cast(dict[str, object], payload), summary


def _post_d0_route(
    payload: Mapping[str, object],
) -> tuple[ResearchPhase, str, ResearchResponsibility]:
    """Route an analysis-plan case to D1; retain the legacy no-plan exit."""
    if isinstance(payload.get("analysis_plan"), Mapping):
        return (
            "deep_research",
            "Launch `alpha research run deep` to execute the frozen analysis plan on D1.",
            "codex",
        )
    return (
        "research_decision",
        "Owner records INCONCLUSIVE with revise, park, or reject; empirical D1 is "
        "unavailable in Gate 1.",
        "owner",
    )


_D1_NEXT_ACTION_AFTER = (
    "Owner reviews the D1 evidence, then drafts a confirmation contract or records an "
    "early decision."
)


def _failure_text(error: BaseException) -> str:
    return (str(error).strip() or type(error).__name__)[:8192]


def _checkpoint_failed_research_run(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    *,
    run_error: BaseException,
    kind: str,
    config_fingerprint: str,
    attempt_number: int,
    evidence_zone: str,
    finding: str,
    stage: str,
    reason: str,
    retry_action: str,
    retry_recovery: str,
    job_id: str | None = None,
    launch_reservation_id: str | None = None,
    details: Mapping[str, object] | None = None,
) -> str:
    """Best-effort terminal bookkeeping shared by D0, D1, and D2 failures."""
    error_text = _failure_text(run_error)
    retries_exhausted = attempt_number >= 3
    checkpoint_errors: list[str] = []
    attempt_details: dict[str, object] = {
        "attempt_number": attempt_number,
        "evidence_zone": evidence_zone,
        "finding": finding,
        **dict(details or {}),
    }
    try:
        store.record_research_attempt(
            project_id,
            contract_id,
            kind=kind,
            status="failed",
            config_fingerprint=config_fingerprint,
            budget_used={},
            details=attempt_details,
            error=error_text,
            launch_reservation_id=launch_reservation_id,
        )
    except Exception as terminal_error:
        checkpoint_errors.append(f"terminal attempt: {terminal_error}")
    if job_id is not None:
        try:
            cancelled = store.job_cancellation_requested(job_id)
            store.set_job_status(
                job_id,
                "cancelled" if cancelled else "failed",
                terminal_error=None if cancelled else error_text,
            )
        except Exception as job_error:
            checkpoint_errors.append(f"job terminalization: {job_error}")
    try:
        store.transition_research_execution(
            project_id,
            to_state="blocked" if retries_exhausted else "failed",
            contract_id=contract_id,
            actor="system",
            reason=reason,
            next_action=(
                "Owner revises, parks, or rejects the case; the safe retry limit is exhausted."
                if retries_exhausted
                else retry_action
            ),
            responsibility="owner" if retries_exhausted else "codex",
            checkpoint=f"{stage}:failed:{attempt_number}",
            blocker=error_text,
            recovery=(
                "Change the approved contract only through owner-directed revision."
                if retries_exhausted
                else retry_recovery
            ),
        )
    except Exception as execution_error:
        checkpoint_errors.append(f"execution checkpoint: {execution_error}")
    if checkpoint_errors:
        return error_text + "; checkpoint errors: " + "; ".join(checkpoint_errors)
    return error_text


_D2_NEXT_ACTION_AFTER = "Owner accepts, rejects, or revises the research conclusion."


_D2_NEXT_ACTION_DURING = "Execute the frozen primary exactly once on the sealed D2 share."


def _approval_boundary_dataset(
    result: dict[str, object],
    empirical_dataset: _EmpiricalDataset | CryptoEmpiricalDataset | None,
    chart: ResearchChartFingerprintV1,
) -> tuple[tuple[str, ...], str, dict[str, object], dict[str, object] | None]:
    boundary_authority: dict[str, object] = {
        "kind": "synthetic_acceptance_fixture",
        "real_market_evidence": False,
        "empirical_confirmation_authorized": False,
    }
    empirical_section: dict[str, object] | None = None
    if isinstance(empirical_dataset, CryptoEmpiricalDataset):
        ref = empirical_dataset.ref
        eligible_groups = tuple(
            observation.funding_time.isoformat() for observation in empirical_dataset.observations
        )
        if len(set(eligible_groups)) != len(eligible_groups):
            raise DataError("crypto crowding snapshot produced duplicate funding groups")
        dataset_fingerprint = empirical_dataset.snapshot_id
        boundary_authority = {
            "kind": "empirical_dataset",
            "real_market_evidence": True,
            "empirical_confirmation_authorized": True,
        }
        hashes = cast(dict[str, object], result["hashes"])
        hashes["data"] = dataset_fingerprint
        empirical_section = {
            "ref_id": str(ref.get("ref_id", "")),
            "content_sha256": dataset_fingerprint,
            "instrument": "BTCUSDT",
            "provider": "bybit",
            "session_group_count": len(eligible_groups),
            "start_ts": eligible_groups[0],
            "end_ts": eligible_groups[-1],
            "snapshot_id": empirical_dataset.snapshot_id,
            "snapshot_hash": empirical_dataset.snapshot_hash,
            "operator_fingerprint": empirical_dataset.operator_fingerprint,
            "asset_master_version": empirical_dataset.asset_master_version,
            "qualification_versions": list(empirical_dataset.qualification_versions),
        }
    elif isinstance(empirical_dataset, _EmpiricalDataset):
        ref, bars = empirical_dataset
        ref_instrument = str(ref.get("instrument", ""))
        ref_provider = str(ref.get("provider", ""))
        if ref_instrument != chart.instrument:
            raise DataError(
                f"registered dataset instrument {ref_instrument!r} does not match the "
                f"chart instrument {chart.instrument!r}"
            )
        if ref_provider != chart.provider:
            raise DataError(
                f"registered dataset provider {ref_provider!r} does not match the "
                f"chart provider {chart.provider!r}"
            )
        eligible_groups = tuple(bar.start.date().isoformat() for bar in bars.bars)
        if len(set(eligible_groups)) != len(eligible_groups):
            raise DataError("registered daily dataset produced duplicate session groups")
        dataset_fingerprint = bars.dataset.content_sha256
        boundary_authority = {
            "kind": "empirical_dataset",
            "real_market_evidence": True,
            "empirical_confirmation_authorized": True,
        }
        hashes = cast(dict[str, object], result["hashes"])
        hashes["data"] = dataset_fingerprint
        empirical_section = {
            "ref_id": str(ref.get("ref_id", "")),
            "content_sha256": dataset_fingerprint,
            "instrument": ref_instrument,
            "provider": ref_provider,
            "session_group_count": len(eligible_groups),
            "start_ts": str(ref.get("start_ts", "")),
            "end_ts": str(ref.get("end_ts", "")),
        }
    else:
        eligible_groups = tuple(
            f"synthetic-acceptance-session-{index:03d}" for index in range(1, 11)
        )
        dataset_fingerprint = _sha_json(
            {
                "schema": "AlphaSyntheticResearchAcceptanceDatasetV1",
                "generator": "d0-synthetic-v1",
                "chart_fingerprint": chart.to_dict(),
                "eligible_groups": list(eligible_groups),
            }
        )

    return eligible_groups, dataset_fingerprint, boundary_authority, empirical_section


def _complete_approval_payload(
    result: dict[str, object],
    primary_claim: dict[str, object],
    empirical_dataset: _EmpiricalDataset | CryptoEmpiricalDataset | None,
    d2_relation_to_prior: str | None,
) -> dict[str, object]:
    resolved_choices = result.get("resolved_material_choices")
    chart_choice = (
        resolved_choices.get("chart_construction")
        if isinstance(resolved_choices, Mapping)
        else None
    )
    empirical_lane = chart_choice in _EMPIRICAL_CHART_CHOICES
    if empirical_dataset is not None and not empirical_lane:
        raise DataError(
            "a registered research dataset can bind only a registered empirical lane; "
            "synthetic-boundary lanes must not carry one"
        )
    if empirical_lane and empirical_dataset is None and result.get("approval_ready") is True:
        raise DataError(
            "the selected empirical lane requires a registered compatible research dataset "
            "bound at draft time; pass --dataset rd_<sha256>"
        )
    chart_value = result.get("chart_fingerprint")
    event_value = result.get("event_definition")
    if not isinstance(chart_value, dict) or not isinstance(event_value, dict):
        raise DataError("approval-ready research contract requires chart and event definitions")
    if result.get("approval_ready") is True:
        _require_resolved_material(chart_value, "chart_fingerprint")
        _require_resolved_material(event_value, "event_definition")
        _require_resolved_material(primary_claim, "primary_claim")
    duration_minutes = chart_value.get("bar_duration_minutes")
    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or duration_minutes < 1
    ):
        raise DataError("approval-ready chart requires a positive fixed bar duration")
    pattern_window = chart_value.get("pattern_window_trading_minutes")
    if pattern_window is not None:
        bar_construction = (
            f"fixed_{duration_minutes}_trading_minute_bars_with_"
            f"{pattern_window}_trading_minute_pattern_window"
        )
    elif duration_minutes == 1_440:
        bar_construction = "fixed_session_daily_bars"
    else:
        bar_construction = f"fixed_{duration_minutes}_elapsed_minute_bars"
    chart = ResearchChartFingerprintV1(
        instrument=str(chart_value.get("instrument", "")),
        provider=str(chart_value.get("provider", "")),
        venue=str(chart_value.get("venue", "")),
        timezone=str(chart_value.get("timezone", "")),
        session=str(chart_value.get("session", "")),
        bar_construction=bar_construction,
        bar_duration_seconds=duration_minutes * 60,
        anchor=str(chart_value.get("anchor", "")),
        adjustment_basis=str(chart_value.get("adjustment_basis", "")),
        timestamp_semantics=str(chart_value.get("timestamp_semantics", "")),
    )
    endpoint = primary_claim.get("estimand", primary_claim.get("endpoint"))
    horizon = primary_claim.get("horizon_trading_minutes", primary_claim.get("horizon"))
    if not isinstance(endpoint, str) or not endpoint or not isinstance(horizon, str | int):
        raise DataError("approval-ready primary claim requires an exact endpoint and horizon")
    event_formula = json.dumps(event_value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    eligible_groups, dataset_fingerprint, boundary_authority, empirical_section = (
        _approval_boundary_dataset(result, empirical_dataset, chart)
    )
    return _approval_protocol(
        result,
        primary_claim,
        chart,
        event_value,
        endpoint,
        horizon,
        event_formula,
        eligible_groups,
        dataset_fingerprint,
        boundary_authority,
        empirical_section,
        d2_relation_to_prior,
    )


def _approval_protocol(
    result: dict[str, object],
    primary_claim: dict[str, object],
    chart: ResearchChartFingerprintV1,
    event_value: dict[str, object],
    endpoint: str,
    horizon: str | int,
    event_formula: str,
    eligible_groups: tuple[str, ...],
    dataset_fingerprint: str,
    boundary_authority: dict[str, object],
    empirical_section: dict[str, object] | None,
    d2_relation_to_prior: str | None,
) -> dict[str, object]:
    boundary = ResearchD2BoundaryV2.from_eligible_groups(
        dataset_fingerprint=dataset_fingerprint,
        eligible_groups=eligible_groups,
        chart_fingerprint=chart,
        event_formula=event_formula,
        event_availability_timestamp=str(event_value.get("availability", "")),
        primary_endpoint=endpoint,
        primary_horizon=str(horizon),
        outcome_overlap_embargo_groups=1,
    )
    d2_definition: dict[str, object] = {
        "purpose": "research_confirmation",
        "share": 0.20,
        "state": "sealed",
        "boundary_hash": boundary.boundary_sha256,
    }
    if d2_relation_to_prior is not None:
        d2_definition["relation_to_prior"] = d2_relation_to_prior
    result["protocol"] = {
        "chart_fingerprint": chart.to_dict(),
        "event_definition": result.get("event_definition"),
        "primary_claims": [primary_claim],
        "primary_claim_count": 1,
        "boundary_authority": boundary_authority,
        "evidence_topology": {
            "boundary": boundary.to_dict(),
            "D0": {"purpose": "synthetic_validation", "share": 0.0},
            "D1": {"purpose": "discovery", "share": 0.60},
            "D2": d2_definition,
            "D3": {"purpose": "final_strategy_holdout", "share": 0.20, "state": "sealed"},
        },
        "statistical_policy": result.get("statistical_policy"),
        "required_falsifiers": result.get("required_falsifiers"),
        "confounders": result.get("confounders"),
        "complete_variant_family": {
            "primary_formulations": 1,
            "preregistered_sensitivity_contrasts": 8,
            "maximum_declared_grid_cells": 64,
        },
    }
    protocol = cast(dict[str, object], result["protocol"])
    if empirical_section is not None:
        protocol["empirical_dataset"] = empirical_section
    resolved = result.get("resolved_material_choices")
    if (
        isinstance(resolved, Mapping)
        and result.get("approval_ready") is True
        and event_value.get("name") == "double_bottom"
        and event_value.get("availability") == "second_trough_confirmable"
        and (resolved.get("chart_construction"), resolved.get("primary_outcome"))
        in registered_d0_material_choices()
    ):
        protocol["d0_operator"] = registered_d0_operator(result)
    elif (
        isinstance(resolved, Mapping)
        and result.get("approval_ready") is True
        and result.get("answer_bundle_id") == "bybit_btcusdt_crowding_reversal_v1"
        and event_value.get("name") == "bybit_btcusdt_crowding_reversal"
        and event_value.get("availability") == "bybit_funding_event_point_in_time"
    ):
        from alpha_cli.research_crypto_runtime import registered_crypto_d0_operator

        protocol["d0_operator"] = registered_crypto_d0_operator()
    return result


def _attach_exploration_draft(
    store: ControlStore,
    project_id: str,
    contract: Mapping[str, object],
    payload: Mapping[str, object],
    created_by: str,
) -> dict[str, object]:
    selected = store.research_case_summary(project_id)
    if selected["phase"] == "captured":
        store.transition_research_phase(
            project_id,
            to_phase="triage",
            contract_id=str(contract["contract_id"]),
            actor=created_by,
            reason="attached the complete draft to the legally migrated research case",
            next_action="Codex verifies the frozen source pack and material resolutions.",
            responsibility="codex",
        )
        selected = store.research_case_summary(project_id)
    if selected["phase"] == "triage":
        approval_ready = payload.get("approval_ready") is True
        store.transition_research_phase(
            project_id,
            to_phase="exploration_review",
            contract_id=str(contract["contract_id"]),
            actor=created_by,
            reason="complete exploration contract and immutable source pack are ready",
            next_action=(
                "Owner approves or rejects the exact exploration contract."
                if approval_ready
                else (
                    "Owner rejects and closes the Gate-1-unavailable proposal or waits for "
                    "its registered operator to be implemented."
                )
            ),
            responsibility="owner",
            blocker=(
                None
                if approval_ready
                else "Gate 1 has no registered operator for this exact contract."
            ),
            recovery=(
                None
                if approval_ready
                else (
                    "Reject and close the proposal, or wait for the operator to be added "
                    "through normal repository implementation and review."
                )
            ),
        )
    elif selected["phase"] != "exploration_review":
        raise DataError("research draft can attach only to captured, triage, or exploration review")
    case = store.research_case_summary(project_id)

    return case


def _confirmation_readiness(
    payload: Mapping[str, object], evidence: dict[str, Any], analyses: dict[str, Any]
) -> ReadinessProjection:
    analysis_measurements = analyses.get("measurements")
    skipped_rows = (
        analysis_measurements.get("skipped_families", [])
        if isinstance(analysis_measurements, Mapping)
        else []
    )
    skipped_families = (
        [
            str(item["family"])
            for item in skipped_rows
            if isinstance(item, Mapping) and isinstance(item.get("family"), str)
        ]
        if isinstance(skipped_rows, list)
        else []
    )
    analysis_plan = payload.get("analysis_plan")
    family_rows = analysis_plan.get("families", []) if isinstance(analysis_plan, Mapping) else []
    required_families = (
        [
            str(item["family"])
            for item in family_rows
            if isinstance(item, Mapping) and isinstance(item.get("family"), str)
        ]
        if isinstance(family_rows, list)
        else []
    )
    required_falsifiers = (
        [
            str(item["family"])
            for item in family_rows
            if isinstance(item, Mapping)
            and isinstance(item.get("family"), str)
            and item.get("multiplicity") == "falsification"
        ]
        if isinstance(family_rows, list)
        else []
    )
    readiness = derive_research_readiness(
        evidence,
        required_falsifiers=required_falsifiers,
        skipped_required_families=[
            family for family in skipped_families if family in required_families
        ],
    )["confirmation_readiness"]

    return readiness


def _recover_completed_d1(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    payload: Mapping[str, object],
    case: Mapping[str, object],
    execution_state: str,
    *,
    json_out: bool,
) -> bool:
    latest_attempt_id = case.get("latest_attempt_id")
    if isinstance(latest_attempt_id, str) and isinstance(case.get("latest_run_id"), str):
        recovered = store.verified_research_attempt(project_id, latest_attempt_id)
        recovered_attempt = cast(dict[str, object], recovered["attempt"])
        recovered_manifest = cast(dict[str, object], recovered["manifest"])
        if (
            recovered_attempt.get("status") == "completed"
            and recovered_attempt.get("kind") == "d1-deep-research"
            and recovered_attempt.get("phase") == "deep_research"
            and recovered_attempt.get("contract_id") == contract_id
            and recovered_manifest.get("evidence_zone") == "D1"
        ):
            if execution_state in {"queued", "running"}:
                active_job_id = case.get("active_job_id")
                if isinstance(active_job_id, str):
                    active_job = store.get_job(active_job_id)
                    if active_job.get("status") in {"queued", "running"}:
                        raise DataError(
                            "completed D1 attempt is awaiting durable job reconciliation; "
                            "its owner host is unverified"
                        )
                store.transition_research_execution(
                    project_id,
                    to_state="idle",
                    contract_id=contract_id,
                    actor="system",
                    reason="recovered the completed immutable D1 run after interruption",
                    next_action=_D1_NEXT_ACTION_AFTER,
                    responsibility="owner",
                    checkpoint="d1:complete",
                )
            recovered_case = store.research_case_summary(project_id)
            _emit(
                {
                    "manifest": recovered_manifest,
                    "attempt": recovered_attempt,
                    "case": recovered_case,
                },
                json_out=json_out,
                fallback=(
                    f"recovered D1 run {recovered_manifest['run_id']}; owner review required"
                ),
            )
            return True

    return False


def _recover_completed_d2(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    payload: Mapping[str, object],
    case: Mapping[str, object],
    execution_state: str,
    *,
    json_out: bool,
) -> bool:
    phase = str(case["phase"])
    latest_attempt_id = case.get("latest_attempt_id")
    if isinstance(latest_attempt_id, str) and isinstance(case.get("latest_run_id"), str):
        recovered = store.verified_research_attempt(project_id, latest_attempt_id)
        recovered_attempt = cast(dict[str, object], recovered["attempt"])
        recovered_manifest = cast(dict[str, object], recovered["manifest"])
        if (
            recovered_attempt.get("status") == "completed"
            and recovered_attempt.get("kind") == "sealed-confirmation"
            and recovered_attempt.get("phase") == "sealed_confirmation"
            and recovered_attempt.get("contract_id") == contract_id
            and recovered_manifest.get("evidence_zone") == "D2"
        ):
            # Finish the interrupted tail exactly once: consume -> owner decision ->
            # idle. Each step is skipped when the crash already got past it.
            if case.get("d2_state") == "authorized":
                store.transition_research_d2_state(
                    project_id,
                    contract_id,
                    to_state="consumed",
                    actor="system",
                    reason="recovered the completed immutable one-shot confirmation",
                )
            if phase == "sealed_confirmation":
                store.transition_research_phase(
                    project_id,
                    to_phase="research_decision",
                    contract_id=contract_id,
                    actor="system",
                    reason=(
                        "the one-shot D2 confirmation completed with mechanically verified evidence"
                    ),
                    next_action=_D2_NEXT_ACTION_AFTER,
                    responsibility="owner",
                )
            if execution_state in {"queued", "running"}:
                store.transition_research_execution(
                    project_id,
                    to_state="idle",
                    contract_id=contract_id,
                    actor="system",
                    reason="recovered the completed immutable D2 run after interruption",
                    next_action=_D2_NEXT_ACTION_AFTER,
                    responsibility="owner",
                    checkpoint="d2:complete",
                )
            recovered_case = store.research_case_summary(project_id)
            _emit(
                {
                    "manifest": recovered_manifest,
                    "attempt": recovered_attempt,
                    "case": recovered_case,
                },
                json_out=json_out,
                fallback=(
                    f"recovered D2 confirmation run {recovered_manifest['run_id']}; "
                    "owner decision required"
                ),
            )
            return True

    return False


def _recover_completed_d0(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    payload: Mapping[str, object],
    case: Mapping[str, object],
    execution_state: str,
    *,
    json_out: bool,
) -> bool:
    latest_attempt_id = case.get("latest_attempt_id")
    if (
        execution_state in {"idle", "queued"}
        and isinstance(latest_attempt_id, str)
        and isinstance(case.get("latest_run_id"), str)
    ):
        recovered = store.verified_research_attempt(project_id, latest_attempt_id)
        recovered_attempt = cast(dict[str, object], recovered["attempt"])
        recovered_manifest = cast(dict[str, object], recovered["manifest"])
        if (
            recovered_attempt.get("status") == "completed"
            and recovered_attempt.get("kind") == "d0-synthetic-pilot"
            and recovered_attempt.get("phase") == "pilot"
            and recovered_attempt.get("contract_id") == contract_id
            and recovered_manifest.get("evidence_zone") == "D0"
        ):
            next_phase, next_action, responsibility = _post_d0_route(payload)
            if execution_state == "queued":
                store.transition_research_execution(
                    project_id,
                    to_state="idle",
                    contract_id=contract_id,
                    actor="system",
                    reason="recovered the completed immutable D0 run after interruption",
                    next_action=next_action,
                    responsibility=responsibility,
                    checkpoint="d0:complete",
                )
            store.transition_research_phase(
                project_id,
                to_phase=next_phase,
                contract_id=contract_id,
                actor="system",
                reason="recovered the verified completed D0 attempt after interruption",
                next_action=next_action,
                responsibility=responsibility,
            )
            recovered_case = store.research_case_summary(project_id)
            _emit(
                {
                    "manifest": recovered_manifest,
                    "attempt": recovered_attempt,
                    "case": recovered_case,
                },
                json_out=json_out,
                fallback=(
                    f"recovered D0 pilot {recovered_manifest['run_id']}; owner disposition required"
                ),
            )
            return True

    return False


def _record_completed_d1(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    manifest: Mapping[str, Any],
    attempt_number: int,
    job_id: str,
    *,
    data_dir: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    # The run is published and immutable. As with D0, a store write failure past this
    # point must never fabricate a failed attempt.
    run_id = str(manifest["run_id"])
    run_dir = data_dir / "runs" / run_id
    analyses = json.loads((run_dir / D1_ANALYSES_ARTIFACT).read_text(encoding="utf-8"))
    variants_used = int(analyses["measurements"]["budget"]["variants_used"])
    try:
        attempt = store.record_research_attempt(
            project_id,
            contract_id,
            kind="d1-deep-research",
            status="completed",
            config_fingerprint=str(manifest["execution_fingerprint"]),
            budget_used={"variants": variants_used},
            details={
                "attempt_number": attempt_number,
                "evidence_zone": "D1",
                "finding": (
                    "The frozen analysis plan executed on the discovery share; findings "
                    "were mechanically re-verified from raw measurements."
                ),
                "gate_packet_evidence_ref": {
                    "artifact": D1_EVIDENCE_ARTIFACT,
                    "content_sha256": _manifest_artifact_sha256(manifest, D1_EVIDENCE_ARTIFACT),
                },
            },
            run_id=run_id,
        )
    except Exception as record_error:
        raise DataError(
            f"the D1 deep run completed and published immutable run {run_id}, but "
            "recording its completed attempt failed; no failed attempt was fabricated. "
            "Inspect the control store, then re-run deep research: the identical run "
            f"republishes idempotently: {record_error}"
        ) from record_error
    store.append_job_result(job_id, {"run_id": run_id})
    store.set_job_status(job_id, "succeeded", result_run_id=run_id)
    store.transition_research_execution(
        project_id,
        to_state="idle",
        contract_id=contract_id,
        actor="system",
        reason="the D1 deep run completed and its immutable evidence was recorded",
        next_action=_D1_NEXT_ACTION_AFTER,
        responsibility="owner",
        checkpoint="d1:complete",
    )
    case = store.research_case_summary(project_id)

    return attempt, case


def _record_completed_d2(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    manifest: Mapping[str, Any],
    attempt_number: int,
    job_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    # The run is published and immutable. As with D0/D1, a store write failure past
    # this point must never fabricate a failed attempt.
    run_id = str(manifest["run_id"])
    try:
        attempt = store.record_research_attempt(
            project_id,
            contract_id,
            kind="sealed-confirmation",
            status="completed",
            config_fingerprint=str(manifest["execution_fingerprint"]),
            budget_used={"variants": 1},
            details={
                "attempt_number": attempt_number,
                "evidence_zone": "D2",
                "real_market_evidence": True,
                "finding": (
                    "The frozen primary executed exactly once on the sealed "
                    "confirmation share; the classification was mechanically "
                    "re-verified from raw measurements."
                ),
                "gate_packet_evidence_ref": {
                    "artifact": D2_EVIDENCE_ARTIFACT,
                    "content_sha256": _manifest_artifact_sha256(manifest, D2_EVIDENCE_ARTIFACT),
                },
            },
            run_id=run_id,
        )
    except Exception as record_error:
        raise DataError(
            f"the one-shot confirmation completed and published immutable run {run_id}, "
            "but recording its completed attempt failed; no failed attempt was "
            "fabricated. Inspect the control store, then re-run confirmation: the "
            f"identical run republishes idempotently: {record_error}"
        ) from record_error
    store.transition_research_d2_state(
        project_id,
        contract_id,
        to_state="consumed",
        actor="system",
        reason="the sealed confirmation share was read exactly once by the frozen primary",
    )
    store.transition_research_phase(
        project_id,
        to_phase="research_decision",
        contract_id=contract_id,
        actor="system",
        reason="the one-shot D2 confirmation completed with mechanically verified evidence",
        next_action=_D2_NEXT_ACTION_AFTER,
        responsibility="owner",
    )
    store.append_job_result(job_id, {"run_id": run_id})
    store.set_job_status(job_id, "succeeded", result_run_id=run_id)
    store.transition_research_execution(
        project_id,
        to_state="idle",
        contract_id=contract_id,
        actor="system",
        reason="the one-shot confirmation completed and its immutable evidence was recorded",
        next_action=_D2_NEXT_ACTION_AFTER,
        responsibility="owner",
        checkpoint="d2:complete",
    )
    case = store.research_case_summary(project_id)

    return attempt, case


def _record_completed_d0(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    manifest: Mapping[str, Any],
    attempt_number: int,
    payload: Mapping[str, object],
    reservation_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    # The pilot succeeded and its immutable run is published. From here on, a store
    # write failure must never be recorded as a pilot failure: fabricating a terminal
    # 'failed' attempt would falsify the append-only ledger and mis-checkpoint the case.
    try:
        attempt = store.record_research_attempt(
            project_id,
            contract_id,
            kind="d0-synthetic-pilot",
            status="completed",
            config_fingerprint=str(manifest["execution_fingerprint"]),
            budget_used={},
            details={
                "attempt_number": attempt_number,
                "evidence_zone": "D0",
                "finding": (
                    "D0 detector, point-in-time timing, null, and power fixtures passed; this "
                    "is not real-market evidence."
                ),
                "d0_acceptance_ref": {
                    "artifact": "d0_acceptance.json",
                    "content_sha256": _manifest_artifact_sha256(manifest, "d0_acceptance.json"),
                },
            },
            run_id=str(manifest["run_id"]),
            launch_reservation_id=reservation_id,
        )
    except Exception as record_error:
        raise DataError(
            f"the D0 pilot completed and published immutable run {manifest['run_id']}, but "
            "recording its completed attempt failed; no failed attempt was fabricated. "
            "Inspect the control store, then `alpha research resume` and re-run the pilot: "
            "the identical run republishes idempotently and the attempt is recorded on "
            f"success: {record_error}"
        ) from record_error
    next_phase, next_action, responsibility = _post_d0_route(payload)
    store.transition_research_execution(
        project_id,
        to_state="idle",
        contract_id=contract_id,
        actor="system",
        reason="the D0 pilot completed and its immutable run was recorded",
        next_action=next_action,
        responsibility=responsibility,
        checkpoint="d0:complete",
    )
    store.transition_research_phase(
        project_id,
        to_phase=next_phase,
        contract_id=contract_id,
        actor="codex",
        reason="D0 detector, null, topology, and power fixtures passed",
        next_action=next_action,
        responsibility=responsibility,
    )
    case = store.research_case_summary(project_id)

    return attempt, case


def _validate_research_stage_phase(
    case: Mapping[str, object], *, stage: Literal["d1", "d2"]
) -> None:
    if stage == "d1":
        if case["phase"] != "deep_research":
            raise DataError("deep research requires the deep_research phase (complete D0 first)")
    elif str(case["phase"]) not in {"sealed_confirmation", "research_decision"}:
        raise DataError(
            "one-shot confirmation requires the sealed_confirmation phase (owner "
            "approval of the exact confirmation contract seals it)"
        )


def _start_research_stage_job(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    execution_state: str,
    attempt_number: int,
    *,
    stage: Literal["d1", "d2"],
) -> str:
    deep = stage == "d1"
    operation = "deep research" if deep else "one-shot confirmation"
    next_action = (
        "Execute the registered analysis families on the D1 share."
        if deep
        else _D2_NEXT_ACTION_DURING
    )
    if execution_state == "idle":
        store.transition_research_execution(
            project_id,
            to_state="queued",
            contract_id=contract_id,
            actor="codex",
            reason=(
                "the frozen analysis plan is queued for deep research"
                if deep
                else "the approved one-shot confirmation is queued"
            ),
            next_action=next_action,
            responsibility="codex",
            checkpoint=f"{stage}:queued",
        )
    elif execution_state != "queued":
        raise DataError(f"{operation} must be idle or explicitly queued for resume")
    job = store.create_research_job(
        project_id,
        contract_id=contract_id,
        request={
            "stage": "deep" if deep else "confirm",
            "contract_id": contract_id,
            "attempt_number": attempt_number,
        },
    )
    job_id = str(job["job_id"])
    store.set_job_status(job_id, "running")
    store.transition_research_execution(
        project_id,
        to_state="running",
        contract_id=contract_id,
        actor="system",
        reason=(
            "the deep-research job started under governed heavyweight capacity"
            if deep
            else "the one-shot confirmation job started under governed heavyweight capacity"
        ),
        next_action=next_action,
        responsibility="codex",
        active_job_id=job_id,
        checkpoint=f"{stage}:running:{attempt_number}",
    )
    return job_id


def _checkpoint_stage_failure(
    store: ControlStore,
    project_id: str,
    contract_id: str,
    *,
    run_error: Exception,
    config_fingerprint: str,
    attempt_number: int,
    job_id: str,
    stage: Literal["d1", "d2"],
) -> str:
    deep = stage == "d1"
    return _checkpoint_failed_research_run(
        store,
        project_id,
        contract_id,
        run_error=run_error,
        kind="d1-deep-research" if deep else "sealed-confirmation",
        config_fingerprint=config_fingerprint,
        attempt_number=attempt_number,
        evidence_zone="D1" if deep else "D2",
        finding=(
            "The D1 deep run failed; no empirical conclusion was produced."
            if deep
            else "The one-shot D2 run failed; no confirmatory conclusion was produced and "
            "the sealed share granted no authority."
        ),
        stage=stage,
        reason=(
            "the D1 deep run stopped at a durable checkpoint"
            if deep
            else "the one-shot D2 run stopped at a durable checkpoint"
        ),
        retry_action=(
            "Inspect the failure, resume the case, and re-run deep research."
            if deep
            else "Inspect the failure, resume the case, and re-run confirmation."
        ),
        retry_recovery="Re-execution is exact: the identical run republishes idempotently.",
        job_id=job_id,
    )


def _emit_stage_result(
    manifest: Mapping[str, object],
    attempt: Mapping[str, object],
    case: Mapping[str, object],
    *,
    stage: Literal["d1", "d2"],
    json_out: bool,
) -> None:
    _emit(
        {"manifest": manifest, "attempt": attempt, "case": case},
        json_out=json_out,
        fallback=(
            f"D1 deep run {manifest['run_id']} completed; owner review required"
            if stage == "d1"
            else (
                f"one-shot D2 confirmation run {manifest['run_id']} completed; "
                "owner decision required"
            )
        ),
    )
