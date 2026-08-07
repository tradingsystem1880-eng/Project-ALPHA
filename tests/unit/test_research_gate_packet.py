"""Deterministic terminal ResearchGatePacket contract."""

from __future__ import annotations

import copy
import json
from typing import cast

import pytest

from alpha_core import DataError
from alpha_research import (
    build_research_gate_packet,
    confirmation_classification_from_evidence,
)


def _contract(
    contract_id: str,
    *,
    scope: str,
    parent_contract_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "ResearchContractV1",
        "thesis": {
            "primary_claims": [
                {"claim": "Confirmed double bottoms predict positive forward returns."}
            ],
            "mechanism": "Forced selling exhausts near the second trough.",
        },
        "protocol": {
            "confounders": ["weekday", "trend", "volatility"],
            "complete_variant_family": {
                "primary_formulations": 1,
                "preregistered_sensitivity_contrasts": 8,
            },
        },
        "budget": {"source_requests": 40, "variants": 64, "wall_seconds": 8_400},
        "source_pack_id": "sp_sources",
    }
    if scope == "confirmation":
        payload["confirmation"] = {
            "variant_count": 9,
            "multiplicity_count": 9,
            "familywise_alpha": 0.05,
            "target_power": 0.90,
            "power_report": {"achieved_power": 0.91},
        }
    return {
        "contract_id": contract_id,
        "project_id": "project-1",
        "scope": scope,
        "parent_contract_id": parent_contract_id,
        "payload": payload,
        "payload_hash": "a" * 64,
        "created_by": "codex",
        "author_kind": "agent",
        "created_at": "2026-08-06T00:00:00.000000Z",
        "review_state": "approved",
        "latest_review": None,
    }


def _inputs(*, include_d0: bool = True) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    if include_d0:
        attempts.append(
            {
                "attempt_id": "ra_d0",
                "project_id": "project-1",
                "contract_id": "rc_explore",
                "phase": "pilot",
                "kind": "d0-synthetic-pilot",
                "status": "completed",
                "config_fingerprint": "cfg:d0",
                "budget_used": {
                    "source_requests": 0,
                    "variants": 3,
                    "wall_seconds": 1,
                },
                "run_id": "0000000000000001",
                "error": None,
                "details": {
                    "evidence_zone": "D0",
                    "real_market_evidence": False,
                    # Even an accidentally supplied D0 evidence summary must not become support.
                    "gate_packet_evidence": {
                        "schema": "ResearchGateEvidenceV1",
                        "evidence_zone": "D0",
                        "primary_result": {
                            "status": "TESTED",
                            "estimate": 99.0,
                        },
                    },
                },
                "recorded_at": "2026-08-06T00:10:00.000000Z",
            }
        )
    return {
        "schema_version": 1,
        "project": {
            "project_id": "project-1",
            "name": "Double bottom study",
            "hypothesis": "Double bottoms precede positive returns.",
            "falsification_criterion": "Reject on a non-positive matched effect.",
            "status": "active",
        },
        "phase": "closed",
        "active_contract_id": "rc_confirm",
        "lineage_contract_ids": ["rc_explore", "rc_confirm"],
        "contracts": [
            _contract("rc_explore", scope="exploration"),
            _contract(
                "rc_confirm",
                scope="confirmation",
                parent_contract_id="rc_explore",
            ),
        ],
        "source_packs": [
            {
                "pack_id": "sp_sources",
                "project_id": "project-1",
                "source_ids": ["rs_paper"],
                "definition": {"frozen": True, "queries": ["double bottom returns"]},
                "pack_hash": "b" * 64,
                "created_at": "2026-08-06T00:01:00.000000Z",
            }
        ],
        "sources": [
            {
                "source_id": "rs_paper",
                "project_id": "project-1",
                "title": "Technical patterns and subsequent returns",
                "locator": "doi:10.0000/example",
                "provider": "crossref",
                "access_mode": "metadata_only",
                "content_hash": None,
                "metadata": {"screening": "include"},
                "created_at": "2026-08-06T00:00:30.000000Z",
            }
        ],
        "attempts": attempts,
        "phase_events": [
            {
                "sequence": 1,
                "project_id": "project-1",
                "contract_id": "rc_explore",
                "phase": "captured",
                "actor": "codex",
                "occurred_at": "2026-08-06T00:00:00.000000Z",
                "reason": "Captured.",
            },
            {
                "sequence": 2,
                "project_id": "project-1",
                "contract_id": "rc_confirm",
                "phase": "closed",
                "actor": "codex",
                "occurred_at": "2026-08-06T00:20:00.000000Z",
                "reason": "Closed after owner decision.",
            },
        ],
        "review_events": [
            {
                "sequence": 1,
                "project_id": "project-1",
                "contract_id": "rc_explore",
                "scope": "exploration",
                "decision": "approve",
                "actor": "owner",
                "actor_kind": "human",
                "reason": "Approved.",
                "occurred_at": "2026-08-06T00:02:00.000000Z",
            }
        ],
        "execution_events": [],
        "d2_events": [
            {
                "sequence": 1,
                "project_id": "project-1",
                "contract_id": "rc_explore",
                "state": "sealed",
                "boundary_hash": "boundary-v1",
                "actor": "system",
                "reason": "Sealed.",
                "occurred_at": "2026-08-06T00:00:00.000000Z",
            },
            {
                "sequence": 2,
                "project_id": "project-1",
                "contract_id": "rc_confirm",
                "state": "consumed",
                "boundary_hash": "boundary-v1",
                "actor": "system",
                "reason": "Consumed once.",
                "occurred_at": "2026-08-06T00:15:00.000000Z",
            },
        ],
        "decision_events": [
            {
                "sequence": 1,
                "project_id": "project-1",
                "contract_id": "rc_confirm",
                "outcome": "INCONCLUSIVE",
                "disposition": "park",
                "actor": "owner",
                "actor_kind": "human",
                "reason": "Owner accepted the recorded research classification.",
                "occurred_at": "2026-08-06T00:19:00.000000Z",
            }
        ],
    }


def _d2_evidence() -> dict[str, object]:
    return {
        "schema": "ResearchGateEvidenceV1",
        "evidence_zone": "D2",
        "confirmation_classification": "SUPPORTED",
        "confirmation_claim": {
            "direction": "positive",
            "minimum_effect": 0.0025,
            "adjusted_p_value": 0.011,
            "alpha": 0.05,
        },
        "confirmation_checks": {
            "corrected_primary_test_passed": True,
            "interval_registered_direction": True,
            "economic_hurdle_cleared": True,
            "interval_wholly_against_direction": False,
        },
        "primary_result": {
            "status": "TESTED",
            "estimate": 0.0051,
            "unit": "return",
            "sample_size": 61,
            "effective_sample_size": 43.5,
            "uncertainty": {
                "lower": 0.0028,
                "upper": 0.0074,
                "level": 0.95,
                "method": "cluster bootstrap",
            },
            "practical_magnitude": {
                "status": "CLEARS_HURDLE",
                "value": 0.0051,
                "unit": "return",
                "interpretation": "The interval clears the registered 25 bp hurdle.",
            },
        },
        "mechanism": {
            "status": "INCONCLUSIVE",
            "summary": "Predictive association survived matching; mechanism was not identified.",
        },
        "strongest_support": "The D2 matched-control interval remained above zero.",
        "strongest_contradiction": "The effect weakened in high-volatility observations.",
        "confounders": {
            "resolved": ["weekday", "trend"],
            "unresolved": ["volatility term structure"],
        },
        "stability": {
            "parameter": {"status": "STABLE", "summary": "Adjacent definitions agreed."},
            "temporal": {"status": "INCONCLUSIVE", "summary": "One D2 era only."},
            "transportability": {
                "status": "NOT_TESTED",
                "summary": "Independent replication was unavailable.",
            },
        },
        "multiplicity": {
            "status": "PASSED",
            "summary": "The registered primary family cleared Holm correction.",
        },
        "power": {
            "status": "PASSED",
            "summary": "Prospective power was 91% at the registered effect.",
        },
        "negative_controls": {
            "status": "PASSED",
            "summary": "Weekday-only and pseudo-pattern controls were null.",
        },
        "untested_work": ["Non-overlapping future replication"],
        "what_would_change_conclusion": ["A future registered replication interval crossing zero."],
        "artifact_links": [
            {
                "run_id": "0000000000000002",
                "artifact_id": "primary-effect",
                "content_sha256": "c" * 64,
                "media_type": "application/json",
            }
        ],
    }


def _inputs_with_evidence(
    evidence: dict[str, object] | None = None,
    *,
    phase: str = "sealed_confirmation",
    contract_id: str = "rc_confirm",
    status: str = "completed",
    run_id: str | None = "0000000000000002",
) -> tuple[dict[str, object], dict[str, object]]:
    inputs = _inputs(include_d0=False)
    attempt: dict[str, object] = {
        "attempt_id": "ra_d2",
        "project_id": "project-1",
        "contract_id": contract_id,
        "phase": phase,
        "kind": "d2-confirmation",
        "status": status,
        "config_fingerprint": "cfg:d2",
        "budget_used": {"source_requests": 1, "variants": 9, "wall_seconds": 90},
        "run_id": run_id,
        "error": None,
        "details": {
            "gate_packet_evidence": _d2_evidence() if evidence is None else evidence,
            "gate_packet_evidence_ref": {
                "artifact": "research_gate_evidence.json",
                "content_sha256": "d" * 64,
            },
        },
        "recorded_at": "2026-08-06T00:16:00.000000Z",
    }
    cast(list[dict[str, object]], inputs["attempts"]).append(attempt)
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision.update(outcome="SUPPORTED", disposition="advance_to_strategy")
    return inputs, attempt


def test_closed_packet_is_content_addressed_complete_and_d0_honest() -> None:
    inputs = _inputs()
    packet = build_research_gate_packet(inputs)
    again = build_research_gate_packet(copy.deepcopy(inputs))

    assert packet.to_dict() == again.to_dict()
    assert packet.to_json_bytes() == again.to_json_bytes()
    row = packet.to_dict()
    assert row["report_schema"] == "ResearchGatePacketV1"
    assert row["terminal"] is True
    assert row["packet_id"] == f"rgp_{row['packet_hash']}"
    assert len(cast(str, row["packet_hash"])) == 64
    json.loads(packet.to_json_bytes())

    layers = cast(dict[str, object], row["layers"])
    assert set(layers) == {"conclusion_90_seconds", "guided_evidence", "technical_appendix"}
    conclusion = cast(dict[str, object], layers["conclusion_90_seconds"])
    guided = cast(dict[str, object], layers["guided_evidence"])
    primary = cast(dict[str, object], guided["primary_result"])
    assert conclusion["scientific_outcome"] == "INCONCLUSIVE"
    assert conclusion["recommended_disposition"] == "park"
    assert conclusion["evidence_basis"] == "NO_TYPED_NON_SYNTHETIC_EVIDENCE"
    assert primary == {
        "effective_sample_size": None,
        "estimate": None,
        "practical_magnitude": {
            "interpretation": "No typed D1 or D2 empirical result is present.",
            "status": "NOT_TESTED",
            "unit": None,
            "value": None,
        },
        "sample_size": None,
        "status": "NOT_TESTED",
        "uncertainty": None,
        "unit": None,
    }
    assert cast(dict[str, object], guided["mechanism"])["status"] == "NOT_TESTED"
    assert "D0" in cast(str, conclusion["strongest_caveat"])

    appendix = cast(dict[str, object], layers["technical_appendix"])
    assert len(cast(list[object], appendix["source_ledger"])) == 1
    assert len(cast(list[object], appendix["source_pack_ledger"])) == 1
    assert len(cast(list[object], appendix["variant_ledger"])) == 2
    assert len(cast(list[object], appendix["attempt_ledger"])) == 1
    assert len(cast(list[object], appendix["budget_ledger"])) == 2
    audit = cast(dict[str, object], appendix["phase_review_d2_ledgers"])
    assert len(cast(list[object], audit["phase_events"])) == 2
    assert len(cast(list[object], audit["review_events"])) == 1
    assert len(cast(list[object], audit["d2_events"])) == 2
    links = cast(list[dict[str, object]], appendix["immutable_artifact_links"])
    assert links[0]["run_id"] == "0000000000000001"
    assert links[0]["evidence_zone"] == "D0"


def test_packet_rejects_contradicted_without_typed_non_synthetic_evidence() -> None:
    inputs = _inputs()
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision.update(outcome="CONTRADICTED", disposition="reject")

    with pytest.raises(DataError, match="lineage-bound typed non-synthetic"):
        build_research_gate_packet(inputs)


def test_typed_d2_evidence_is_exposed_without_changing_owner_decision() -> None:
    inputs, _ = _inputs_with_evidence()

    row = build_research_gate_packet(inputs).to_dict()
    layers = cast(dict[str, object], row["layers"])
    conclusion = cast(dict[str, object], layers["conclusion_90_seconds"])
    guided = cast(dict[str, object], layers["guided_evidence"])
    primary = cast(dict[str, object], guided["primary_result"])
    assert conclusion["evidence_basis"] == "SEALED_D2"
    assert primary["estimate"] == 0.0051
    assert primary["effective_sample_size"] == 43.5
    assert cast(dict[str, object], primary["uncertainty"])["lower"] == 0.0028
    assert cast(dict[str, object], primary["practical_magnitude"])["status"] == ("CLEARS_HURDLE")
    assert cast(dict[str, object], guided["confounders"])["resolved"] == [
        "weekday",
        "trend",
    ]


def test_packet_requires_closed_owner_decision_and_matching_lineage() -> None:
    inputs = _inputs()
    inputs["phase"] = "research_decision"
    with pytest.raises(DataError, match="closed"):
        build_research_gate_packet(inputs)

    inputs = _inputs()
    inputs["decision_events"] = []
    with pytest.raises(DataError, match="owner decision"):
        build_research_gate_packet(inputs)

    inputs = _inputs()
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision["actor_kind"] = "agent"
    with pytest.raises(DataError, match="human owner"):
        build_research_gate_packet(inputs)

    inputs = _inputs()
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision["contract_id"] = "rc_unknown"
    with pytest.raises(DataError, match="active contract"):
        build_research_gate_packet(inputs)


def test_packet_rejects_malformed_non_synthetic_evidence_and_non_finite_json() -> None:
    inputs, attempt = _inputs_with_evidence()
    evidence = cast(
        dict[str, object],
        cast(dict[str, object], attempt["details"])["gate_packet_evidence"],
    )
    primary = cast(dict[str, object], evidence["primary_result"])
    primary["estimate"] = float("nan")
    with pytest.raises(DataError, match="finite"):
        build_research_gate_packet(inputs)

    inputs = _inputs()
    cast(dict[str, object], inputs["project"])["unexpected"] = {"bad": object()}
    with pytest.raises(DataError, match="JSON-compatible"):
        build_research_gate_packet(inputs)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("bad_input_schema", "schema_version"),
        ("lineage_not_array", "lineage_contract_ids"),
        ("duplicate_lineage", "active contract"),
        ("contract_lineage_mismatch", "exactly match"),
        ("foreign_contract", "another project"),
        ("sources_not_array", "sources must be a JSON array"),
        ("source_not_object", r"sources\[0\] must be an object"),
        ("too_many_sources", "row bound"),
        ("duplicate_source", "duplicate research source_id"),
        ("foreign_source", "another project"),
        ("foreign_decision", "another project"),
        ("bad_outcome", "outcome is unsupported"),
        ("bad_disposition", "disposition is unsupported"),
        ("bad_advance", "only a SUPPORTED"),
        ("empty_owner_reason", "decision reason"),
        ("duplicate_attempt", "duplicate research attempt_id"),
        ("foreign_attempt_project", "belongs to another project"),
        ("foreign_attempt_contract", "outside the active lineage"),
        ("bad_attempt_status", "status is unsupported"),
        ("negative_attempt_budget", "must be non-negative"),
        ("undeclared_budget", "undeclared budget dimension"),
        ("over_budget", "exceeds approved"),
        ("negative_contract_budget", "budget values must be non-negative"),
        ("bad_contract_scope", "scope is unsupported"),
        ("bad_evidence_schema", "ResearchGateEvidenceV1"),
        ("bad_evidence_zone", "identify D1 or D2"),
        ("bad_primary_status", "TESTED or NOT_TESTED"),
        ("zero_sample", "integer >= 1"),
        ("excess_effective_sample", "effective_sample_size"),
        ("reversed_interval", "lower cannot exceed"),
        ("bad_interval_level", "level must be"),
        ("bad_magnitude_status", "magnitude.status"),
        ("bad_artifact_hash", "SHA-256"),
        ("missing_evidence_ref", "immutable artifact selector"),
        ("conflicting_outer_zone", "conflicting evidence-zone"),
        ("incomplete_evidence_attempt", "completed immutable run"),
        ("wrong_d2_phase", "sealed_confirmation"),
        ("wrong_d1_phase", "pilot or deep_research"),
        ("artifact_run_mismatch", "bind its attempt run_id"),
        ("duplicate_d2_evidence", "only one typed D2"),
        ("non_boolean_market_flag", "must be boolean"),
        ("d2_wrong_contract", "active confirmation contract"),
        ("bad_finding_status", "status is unsupported"),
        ("missing_finding_summary", "summary is required"),
        ("not_tested_with_value", "cannot carry empirical values"),
        ("evidence_unknown_field", "unsupported fields"),
        ("evidence_missing_primary", "missing required fields"),
        ("missing_confirmation_classification", "confirmation_classification"),
        ("classification_mismatch", "does not match the owner outcome"),
        ("supported_check_failure", "confirmation_checks disagree with the numeric evidence"),
    ],
)
def test_strict_packet_validation_rejects_corrupt_authority_inputs(
    case: str,
    message: str,
) -> None:
    inputs = _inputs()
    if case == "bad_input_schema":
        inputs["schema_version"] = 2
    elif case == "lineage_not_array":
        inputs["lineage_contract_ids"] = "rc_confirm"
    elif case == "duplicate_lineage":
        inputs["lineage_contract_ids"] = ["rc_confirm", "rc_confirm"]
    elif case == "contract_lineage_mismatch":
        inputs["lineage_contract_ids"] = ["rc_confirm", "rc_explore"]
    elif case == "foreign_contract":
        cast(list[dict[str, object]], inputs["contracts"])[0]["project_id"] = "other"
    elif case == "sources_not_array":
        inputs["sources"] = {}
    elif case == "source_not_object":
        inputs["sources"] = ["bad"]
    elif case == "too_many_sources":
        inputs["sources"] = [{} for _ in range(10_001)]
    elif case == "duplicate_source":
        sources = cast(list[dict[str, object]], inputs["sources"])
        sources.append(copy.deepcopy(sources[0]))
    elif case == "foreign_source":
        cast(list[dict[str, object]], inputs["sources"])[0]["project_id"] = "other"
    elif case == "foreign_decision":
        cast(list[dict[str, object]], inputs["decision_events"])[0]["project_id"] = "other"
    elif case == "bad_outcome":
        cast(list[dict[str, object]], inputs["decision_events"])[0]["outcome"] = "MAYBE"
    elif case == "bad_disposition":
        cast(list[dict[str, object]], inputs["decision_events"])[0]["disposition"] = "trade"
    elif case == "bad_advance":
        cast(list[dict[str, object]], inputs["decision_events"])[0]["disposition"] = (
            "advance_to_strategy"
        )
    elif case == "empty_owner_reason":
        cast(list[dict[str, object]], inputs["decision_events"])[0]["reason"] = ""
    elif case == "duplicate_attempt":
        attempts = cast(list[dict[str, object]], inputs["attempts"])
        attempts.append(copy.deepcopy(attempts[0]))
    elif case == "foreign_attempt_project":
        cast(list[dict[str, object]], inputs["attempts"])[0]["project_id"] = "other"
    elif case == "foreign_attempt_contract":
        cast(list[dict[str, object]], inputs["attempts"])[0]["contract_id"] = "rc_other"
    elif case == "bad_attempt_status":
        cast(list[dict[str, object]], inputs["attempts"])[0]["status"] = "unknown"
    elif case == "negative_attempt_budget":
        budget = cast(
            dict[str, object], cast(list[dict[str, object]], inputs["attempts"])[0]["budget_used"]
        )
        budget["variants"] = -1
    elif case in {"undeclared_budget", "over_budget"}:
        budget = cast(
            dict[str, object], cast(list[dict[str, object]], inputs["attempts"])[0]["budget_used"]
        )
        if case == "undeclared_budget":
            budget["gpu_seconds"] = 1
        else:
            budget["variants"] = 65
    elif case == "negative_contract_budget":
        contracts = cast(list[dict[str, object]], inputs["contracts"])
        payload = cast(dict[str, object], contracts[0]["payload"])
        cast(dict[str, object], payload["budget"])["variants"] = -1
    elif case == "bad_contract_scope":
        cast(list[dict[str, object]], inputs["contracts"])[0]["scope"] = "draft"
    else:
        if case == "non_boolean_market_flag":
            details = cast(
                dict[str, object], cast(list[dict[str, object]], inputs["attempts"])[0]["details"]
            )
            details["real_market_evidence"] = "no"
        else:
            inputs, attempt = _inputs_with_evidence()
            details = cast(dict[str, object], attempt["details"])
            evidence = cast(dict[str, object], details["gate_packet_evidence"])
            primary = cast(dict[str, object], evidence.get("primary_result", {}))
            if case == "bad_evidence_schema":
                evidence["schema"] = "ResearchGateEvidenceV2"
            elif case == "bad_evidence_zone":
                evidence["evidence_zone"] = "D3"
            elif case == "bad_primary_status":
                primary["status"] = "UNKNOWN"
            elif case == "zero_sample":
                primary["sample_size"] = 0
            elif case == "excess_effective_sample":
                primary["effective_sample_size"] = 62
            elif case == "reversed_interval":
                cast(dict[str, object], primary["uncertainty"])["lower"] = 0.01
            elif case == "bad_interval_level":
                cast(dict[str, object], primary["uncertainty"])["level"] = 1.0
            elif case == "bad_magnitude_status":
                cast(dict[str, object], primary["practical_magnitude"])["status"] = "PROFITABLE"
            elif case == "bad_artifact_hash":
                cast(list[dict[str, object]], evidence["artifact_links"])[0]["content_sha256"] = (
                    "bad"
                )
            elif case == "missing_evidence_ref":
                details.pop("gate_packet_evidence_ref")
            elif case == "conflicting_outer_zone":
                details["evidence_zone"] = "D1"
            elif case == "incomplete_evidence_attempt":
                attempt["status"] = "failed"
            elif case == "wrong_d2_phase":
                attempt["phase"] = "deep_research"
            elif case == "wrong_d1_phase":
                evidence["evidence_zone"] = "D1"
                evidence.pop("confirmation_classification")
                evidence.pop("confirmation_claim")
                evidence.pop("confirmation_checks")
                attempt["phase"] = "sealed_confirmation"
            elif case == "artifact_run_mismatch":
                cast(list[dict[str, object]], evidence["artifact_links"])[0]["run_id"] = "other"
            elif case == "duplicate_d2_evidence":
                duplicate = copy.deepcopy(attempt)
                duplicate["attempt_id"] = "ra_d2_second"
                duplicate["run_id"] = "0000000000000003"
                duplicate_details = cast(dict[str, object], duplicate["details"])
                duplicate_evidence = cast(
                    dict[str, object], duplicate_details["gate_packet_evidence"]
                )
                cast(list[dict[str, object]], duplicate_evidence["artifact_links"])[0]["run_id"] = (
                    "0000000000000003"
                )
                cast(list[dict[str, object]], inputs["attempts"]).append(duplicate)
            elif case == "d2_wrong_contract":
                attempt["contract_id"] = "rc_explore"
            elif case == "bad_finding_status":
                cast(dict[str, object], evidence["mechanism"])["status"] = "PROVEN"
            elif case == "missing_finding_summary":
                cast(dict[str, object], evidence["mechanism"])["summary"] = None
            elif case == "not_tested_with_value":
                evidence["primary_result"] = {"status": "NOT_TESTED", "estimate": 1.0}
            elif case == "evidence_unknown_field":
                evidence["secret"] = "unsupported"
            elif case == "evidence_missing_primary":
                evidence.pop("primary_result")
            elif case == "missing_confirmation_classification":
                evidence.pop("confirmation_classification")
            elif case == "classification_mismatch":
                # Numerically coherent CONTRADICTED evidence, so the surviving failure is
                # the owner-outcome binding, not the numeric recomputation.
                evidence["confirmation_classification"] = "CONTRADICTED"
                cast(dict[str, object], evidence["confirmation_claim"])["adjusted_p_value"] = 0.62
                checks = cast(dict[str, object], evidence["confirmation_checks"])
                checks.update(
                    corrected_primary_test_passed=False,
                    interval_registered_direction=False,
                    economic_hurdle_cleared=False,
                    interval_wholly_against_direction=True,
                )
                primary["estimate"] = -0.0031
                uncertainty = cast(dict[str, object], primary["uncertainty"])
                uncertainty.update(lower=-0.0074, upper=-0.0008)
                magnitude = cast(dict[str, object], primary["practical_magnitude"])
                magnitude.update(status="BELOW_HURDLE", value=-0.0031)
            elif case == "supported_check_failure":
                cast(dict[str, object], evidence["confirmation_checks"])[
                    "economic_hurdle_cleared"
                ] = False
            else:  # pragma: no cover - parametrization exhausts cases.
                raise AssertionError(case)
    with pytest.raises(DataError, match=message):
        build_research_gate_packet(inputs)


def test_exploratory_evidence_is_reported_but_never_treated_as_confirmation() -> None:
    evidence = _d2_evidence()
    evidence["evidence_zone"] = "D1"
    evidence.pop("confirmation_classification")
    evidence.pop("confirmation_claim")
    evidence.pop("confirmation_checks")
    inputs, _ = _inputs_with_evidence(
        evidence,
        phase="deep_research",
        contract_id="rc_explore",
    )
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision.update(
        contract_id="rc_confirm",
        outcome="INCONCLUSIVE",
        disposition="park",
    )
    row = build_research_gate_packet(inputs).to_dict()
    layers = cast(dict[str, object], row["layers"])
    conclusion = cast(dict[str, object], layers["conclusion_90_seconds"])
    guided = cast(dict[str, object], layers["guided_evidence"])
    assert conclusion["evidence_basis"] == "EXPLORATORY_D1"
    assert "cannot confirm" in cast(str, conclusion["strongest_caveat"])
    assert "Sealed D2 confirmation" in cast(list[str], guided["untested_work"])


def test_not_tested_evidence_and_contract_fallbacks_are_explicit() -> None:
    evidence = _d2_evidence()
    evidence["primary_result"] = {"status": "NOT_TESTED"}
    evidence["confirmation_classification"] = "INCONCLUSIVE"
    evidence.pop("confirmation_claim")
    cast(dict[str, object], evidence["confirmation_checks"]).update(
        corrected_primary_test_passed=False,
        interval_registered_direction=False,
        economic_hurdle_cleared=False,
        interval_wholly_against_direction=False,
    )
    for key in (
        "mechanism",
        "strongest_support",
        "strongest_contradiction",
        "confounders",
        "stability",
        "multiplicity",
        "power",
        "negative_controls",
        "untested_work",
        "what_would_change_conclusion",
        "artifact_links",
    ):
        evidence.pop(key)
    inputs, _ = _inputs_with_evidence(evidence)
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision.update(outcome="INCONCLUSIVE", disposition="park")
    active = cast(list[dict[str, object]], inputs["contracts"])[1]
    payload = cast(dict[str, object], active["payload"])
    payload.pop("thesis")
    payload["mechanism"] = "A contract-level proposed mechanism."
    row = build_research_gate_packet(inputs).to_dict()
    layers = cast(dict[str, object], row["layers"])
    conclusion = cast(dict[str, object], layers["conclusion_90_seconds"])
    guided = cast(dict[str, object], layers["guided_evidence"])
    assert conclusion["thesis"] == "Double bottoms precede positive returns."
    assert cast(dict[str, object], guided["primary_result"])["status"] == "NOT_TESTED"
    assert cast(dict[str, object], guided["mechanism"])["status"] == "NOT_TESTED"


def test_supported_or_advance_requires_exact_sealed_d2_evidence() -> None:
    inputs = _inputs()
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision.update(outcome="SUPPORTED", disposition="advance_to_strategy")
    with pytest.raises(DataError, match="requires one typed SEALED_D2"):
        build_research_gate_packet(inputs)

    evidence = _d2_evidence()
    evidence["evidence_zone"] = "D1"
    evidence.pop("confirmation_classification")
    evidence.pop("confirmation_claim")
    evidence.pop("confirmation_checks")
    inputs, _ = _inputs_with_evidence(
        evidence,
        phase="deep_research",
        contract_id="rc_explore",
    )
    with pytest.raises(DataError, match="requires one typed SEALED_D2"):
        build_research_gate_packet(inputs)


def test_public_confirmation_classifier_is_the_single_mechanical_rule_seam() -> None:
    evidence = _d2_evidence()
    assert confirmation_classification_from_evidence(evidence) == "SUPPORTED"

    evidence["evidence_zone"] = "D1"
    evidence.pop("confirmation_classification")
    evidence.pop("confirmation_claim")
    evidence.pop("confirmation_checks")
    with pytest.raises(DataError, match="requires D2 evidence"):
        confirmation_classification_from_evidence(evidence)

    contradicted = _d2_evidence()
    contradicted["confirmation_classification"] = "CONTRADICTED"
    cast(dict[str, object], contradicted["confirmation_claim"])["adjusted_p_value"] = 0.62
    cast(dict[str, object], contradicted["confirmation_checks"]).update(
        corrected_primary_test_passed=False,
        interval_registered_direction=False,
        economic_hurdle_cleared=False,
        interval_wholly_against_direction=True,
    )
    primary = cast(dict[str, object], contradicted["primary_result"])
    primary["estimate"] = -0.0031
    cast(dict[str, object], primary["uncertainty"]).update(lower=-0.0074, upper=-0.0008)
    magnitude = cast(dict[str, object], primary["practical_magnitude"])
    magnitude.update(status="BELOW_HURDLE", value=-0.0031)
    assert confirmation_classification_from_evidence(contradicted) == "CONTRADICTED"

    cast(dict[str, object], primary["practical_magnitude"])["status"] = "CLEARS_HURDLE"
    with pytest.raises(DataError, match="CONTRADICTED classification checks"):
        confirmation_classification_from_evidence(contradicted)


def test_packet_hash_changes_when_an_authoritative_ledger_changes() -> None:
    inputs = _inputs()
    first = build_research_gate_packet(inputs)
    changed = copy.deepcopy(inputs)
    decision = cast(list[dict[str, object]], changed["decision_events"])[0]
    decision["reason"] = "Owner changed the recorded rationale."
    second = build_research_gate_packet(changed)
    assert first.packet_hash != second.packet_hash
    assert first.packet_id != second.packet_id


def test_early_inconclusive_closure_emits_negative_knowledge_with_d2_sealed() -> None:
    inputs = _inputs()
    inputs["active_contract_id"] = "rc_explore"
    inputs["lineage_contract_ids"] = ["rc_explore"]
    inputs["contracts"] = cast(list[dict[str, object]], inputs["contracts"])[:1]
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision.update(
        contract_id="rc_explore",
        outcome="INCONCLUSIVE",
        disposition="park",
        reason="The registered minimum effective sample could not be reached.",
    )
    inputs["d2_events"] = cast(list[dict[str, object]], inputs["d2_events"])[:1]

    row = build_research_gate_packet(inputs).to_dict()
    assert row["scientific_outcome"] == "INCONCLUSIVE"
    assert row["recommended_disposition"] == "park"
    layers = cast(dict[str, object], row["layers"])
    appendix = cast(dict[str, object], layers["technical_appendix"])
    ledgers = cast(dict[str, object], appendix["phase_review_d2_ledgers"])
    assert cast(list[dict[str, object]], ledgers["d2_events"])[-1]["state"] == "sealed"


def test_numeric_interval_that_cannot_support_the_claim_is_rejected() -> None:
    """Producer booleans alone cannot mint SUPPORTED when the interval disagrees."""
    evidence = _d2_evidence()
    primary = cast(dict[str, object], evidence["primary_result"])
    uncertainty = cast(dict[str, object], primary["uncertainty"])
    # Below the registered 25 bp minimum effect: mechanically INCONCLUSIVE, never SUPPORTED.
    uncertainty["lower"] = 0.0008
    with pytest.raises(DataError, match="disagrees with the mechanical numeric classification"):
        confirmation_classification_from_evidence(evidence)


def test_confirmation_booleans_must_match_the_numeric_evidence() -> None:
    """Each check boolean is bound to its numeric fact, not producer attestation."""
    evidence = _d2_evidence()
    evidence["confirmation_classification"] = "INCONCLUSIVE"
    claim = cast(dict[str, object], evidence["confirmation_claim"])
    claim["adjusted_p_value"] = 0.2  # numerically fails the frozen alpha
    with pytest.raises(
        DataError, match="confirmation_checks disagree.*corrected_primary_test_passed"
    ):
        confirmation_classification_from_evidence(evidence)


def test_d1_evidence_cannot_carry_a_confirmation_claim() -> None:
    evidence = _d2_evidence()
    evidence["evidence_zone"] = "D1"
    evidence.pop("confirmation_classification")
    evidence.pop("confirmation_checks")
    inputs, _ = _inputs_with_evidence(evidence, phase="deep_research", contract_id="rc_explore")
    decision = cast(list[dict[str, object]], inputs["decision_events"])[0]
    decision.update(contract_id="rc_confirm", outcome="INCONCLUSIVE", disposition="park")
    with pytest.raises(DataError, match="D1 evidence cannot carry"):
        build_research_gate_packet(inputs)


def test_not_tested_primary_cannot_carry_a_confirmation_claim() -> None:
    evidence = _d2_evidence()
    evidence["primary_result"] = {"status": "NOT_TESTED"}
    evidence["confirmation_classification"] = "INCONCLUSIVE"
    cast(dict[str, object], evidence["confirmation_checks"]).update(
        corrected_primary_test_passed=False,
        interval_registered_direction=False,
        economic_hurdle_cleared=False,
        interval_wholly_against_direction=False,
    )
    with pytest.raises(DataError, match="cannot carry a confirmation_claim"):
        confirmation_classification_from_evidence(evidence)


def test_invalid_classification_requires_a_stated_invalid_reason() -> None:
    evidence = _d2_evidence()
    evidence["confirmation_classification"] = "INVALID"
    with pytest.raises(DataError, match="disagrees with the mechanical numeric classification"):
        confirmation_classification_from_evidence(evidence)

    claim = cast(dict[str, object], evidence["confirmation_claim"])
    claim["invalid_reason"] = "The evaluator violated the frozen protocol mid-run."
    assert confirmation_classification_from_evidence(evidence) == "INVALID"
