"""CLI-owned research projections (gate packet, backlog rows) over public store reads."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Protocol

from alpha_cli.research_readiness import derive_research_readiness
from alpha_core import DataError
from alpha_research import build_research_gate_packet


class ResearchPacketStore(Protocol):
    def research_case_summary(self, project_id: str) -> dict[str, object]: ...

    def research_gate_packet_inputs(
        self, project_id: str, *, ledger_limit: int = 10_000
    ) -> dict[str, object]: ...

    def list_research_datasets(
        self, *, instrument: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, object]]: ...

    def list_source_claims(
        self,
        project_id: str,
        *,
        include_history: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, object]]: ...


def _case_datasets(
    store: ResearchPacketStore, payload: Mapping[str, object]
) -> list[dict[str, object]]:
    """Registered datasets bound to the contract's instrument (none while unresolved)."""
    instrument = _mapping(payload.get("chart_fingerprint")).get("instrument")
    if not isinstance(instrument, str) or not instrument:
        return []
    try:
        return store.list_research_datasets(instrument=instrument)
    except DataError:
        # Synthetic fixture instruments are not registrable symbols; no datasets exist.
        return []


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
        return value
    return {}


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def _budget_minutes(case: Mapping[str, object]) -> dict[str, object]:
    """Project the wall-clock budget in minutes; other native units are never summed in."""
    elapsed_seconds = _finite_number(_mapping(case.get("elapsed_budget")).get("wall_seconds"))
    remaining_seconds = _finite_number(_mapping(case.get("remaining_budget")).get("wall_seconds"))
    return {
        "approved_units": (elapsed_seconds + remaining_seconds) / 60.0,
        "consumed_units": elapsed_seconds / 60.0,
        "unit": "minutes",
    }


# Mirror of ``research_cmds._require_resolved_material``: text carrying one of these markers
# is a live placeholder, so the card reports the field as partial, never as complete.
_UNRESOLVED_MARKERS = ("unresolved", "placeholder", "selection_required", "provider_required")


def _has_unresolved_marker(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in _UNRESOLVED_MARKERS)


def _card_field(
    field_id: str, label: str, value: str | None, *, partial: bool = False
) -> dict[str, object]:
    if value is None or not value.strip():
        return {"field_id": field_id, "label": label, "value": None, "status": "missing"}
    status = "partial" if partial or _has_unresolved_marker(value) else "complete"
    return {"field_id": field_id, "label": label, "value": value, "status": status}


def _text_of(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def research_hypothesis_card(payload: Mapping[str, object]) -> dict[str, object]:
    """Render the immutable contract in the formal hypothesis vocabulary (spec §5.1).

    Pure projection: per-field ``complete | partial | missing`` honesty, no inference of
    empirical results, and no mutation of the hash-pinned contract payload.
    """
    thesis = _mapping(payload.get("thesis"))
    fingerprint = _mapping(payload.get("chart_fingerprint"))
    event = _mapping(payload.get("event_definition"))
    claim = _mapping(payload.get("primary_claim"))
    policy = _mapping(payload.get("statistical_policy"))
    raw_idea = _text_of(payload.get("raw_idea"))
    mechanism = _text_of(thesis.get("mechanism"))
    prediction = _text_of(thesis.get("prediction"))
    interpretation = _text_of(thesis.get("interpretation"))

    population_parts = [
        _text_of(fingerprint.get("instrument")),
        _text_of(fingerprint.get("venue")),
        _text_of(fingerprint.get("session")),
    ]
    duration = fingerprint.get("bar_duration_minutes")
    if isinstance(duration, int | float) and not isinstance(duration, bool):
        population_parts.append(f"{duration:g}m bars")
    else:
        population_parts.append(None)
    present_parts = [part for part in population_parts if part is not None]
    population = " · ".join(present_parts) if present_parts else None
    population_partial = bool(present_parts) and len(present_parts) < len(population_parts)

    event_name = _text_of(event.get("name"))
    availability = _text_of(event.get("availability"))
    if event_name is not None and availability is not None:
        condition: str | None = f"{event_name} ({availability})"
        condition_partial = False
    else:
        condition = event_name
        condition_partial = event_name is not None

    endpoint = _text_of(claim.get("endpoint"))
    estimand = _text_of(claim.get("estimand")) or endpoint
    horizon_minutes = claim.get("horizon_trading_minutes")
    if isinstance(horizon_minutes, int | float) and not isinstance(horizon_minutes, bool):
        horizon: str | None = f"{horizon_minutes:g} trading minutes"
    else:
        horizon = _text_of(claim.get("horizon"))
    direction = _text_of(claim.get("direction"))

    alpha = policy.get("familywise_alpha")
    alpha_value = alpha if isinstance(alpha, int | float) and not isinstance(alpha, bool) else None
    power = policy.get("prospective_power")
    power_value = power if isinstance(power, int | float) and not isinstance(power, bool) else None
    effect = claim.get("minimum_effect_return")
    effect_value = (
        effect if isinstance(effect, int | float) and not isinstance(effect, bool) else None
    )

    if alpha_value is not None and endpoint is not None:
        null_hypothesis: str | None = (
            f"No association between the registered event and {endpoint} at familywise "
            f"α={alpha_value:g} after the registered controls."
        )
        null_partial = False
    elif alpha_value is not None:
        null_hypothesis = (
            f"No association at familywise α={alpha_value:g} after the registered controls."
        )
        null_partial = True
    else:
        null_hypothesis = None
        null_partial = False

    baseline = (
        "Matched pre-event controls (registered)"
        if estimand is not None and "matched_control" in estimand
        else None
    )

    confounders_raw = payload.get("confounders")
    confounders = (
        [item for item in confounders_raw if isinstance(item, str) and item.strip()]
        if isinstance(confounders_raw, list)
        else []
    )
    falsifiers_raw = payload.get("required_falsifiers")
    falsifiers = (
        [item for item in falsifiers_raw if isinstance(item, str) and item.strip()]
        if isinstance(falsifiers_raw, list)
        else []
    )
    stop_rules_raw = payload.get("stop_rules")
    stop_rule_count = len(stop_rules_raw) if isinstance(stop_rules_raw, list) else 0

    success_parts: list[str] = []
    if alpha_value is not None:
        success_parts.append(f"familywise α={alpha_value:g}")
    if power_value is not None:
        success_parts.append(f"prospective power ≥{power_value:g}")
    if effect_value is not None:
        success_parts.append(f"minimum effect {effect_value:g}")
    success = " · ".join(success_parts) if success_parts else None
    success_partial = 0 < len(success_parts) < 3

    fields = [
        _card_field("research_question", "Research question", prediction),
        _card_field(
            "phenomenon", "Phenomenon", raw_idea, partial=raw_idea is not None and mechanism is None
        ),
        _card_field("population", "Population / universe", population, partial=population_partial),
        _card_field("condition_event", "Condition / event", condition, partial=condition_partial),
        _card_field("dependent_variable", "Dependent variable", estimand),
        _card_field("horizon", "Horizon", horizon),
        _card_field("expected_direction", "Expected direction", direction),
        _card_field(
            "economic_mechanism",
            "Economic mechanism",
            mechanism,
            partial=mechanism is not None and interpretation is None,
        ),
        _card_field("null_hypothesis", "Null hypothesis", null_hypothesis, partial=null_partial),
        _card_field("alternative_hypothesis", "Alternative hypothesis", prediction),
        _card_field("baseline", "Baseline", baseline),
        _card_field(
            "confounders",
            "Confounders",
            "; ".join(confounders) if confounders else None,
            partial=0 < len(confounders) < 6,
        ),
        _card_field(
            "falsification_criteria",
            "Falsification criteria",
            (
                f"{len(falsifiers)} required falsifiers · {stop_rule_count} stop rules"
                if falsifiers
                else None
            ),
            partial=0 < len(falsifiers) < 5,
        ),
        _card_field("success_criteria", "Success criteria", success, partial=success_partial),
    ]
    plan_families = _mapping(payload.get("analysis_plan")).get("families")
    plan_rows = [
        {
            "family": str(_mapping(entry).get("family", "")),
            "multiplicity": str(_mapping(entry).get("multiplicity", "")),
        }
        for entry in (plan_families if isinstance(plan_families, list) else [])
        if _mapping(entry)
    ]
    return {
        "card_schema": "HypothesisCardV1",
        "fields": fields,
        "complete_fields": sum(1 for field in fields if field["status"] == "complete"),
        "total_fields": len(fields),
        "analysis_plan": (
            {"family_count": len(plan_rows), "families": plan_rows} if plan_rows else None
        ),
    }


def _json_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def build_strategy_promotion_payload(
    *,
    project: Mapping[str, object],
    decision: Mapping[str, object],
    contract_payload: Mapping[str, object],
    gate_packet: Mapping[str, object],
    datasets: Sequence[Mapping[str, object]],
    datasets_truncated: bool,
    claims: Sequence[Mapping[str, object]],
    claims_truncated: bool,
    chart_references: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Assemble the lossless spec-§11 promotion dossier from authoritative records only.

    Pure projection over the just-recorded owner decision, the deterministic terminal
    gate packet, the immutable contract payload, and the store's registered dataset,
    screened-claim, and verified chart-artifact rows. Nothing is computed or inferred;
    negative attempts stay visible and honest empty sections stay empty.
    """
    packet_id = gate_packet.get("packet_id")
    packet_hash = gate_packet.get("packet_hash")
    if not isinstance(packet_id, str) or not isinstance(packet_hash, str):
        raise DataError("strategy promotion requires the terminal gate packet identity")
    layers = _mapping(gate_packet.get("layers"))
    guided = _mapping(layers.get("guided_evidence"))
    conclusion = _mapping(layers.get("conclusion_90_seconds"))
    appendix = _mapping(layers.get("technical_appendix"))
    attempt_ledger = appendix.get("attempt_ledger")
    attempts = [
        _mapping(attempt)
        for attempt in (attempt_ledger if isinstance(attempt_ledger, list) else [])
    ]
    by_status: dict[str, int] = {}
    non_completed: list[str] = []
    for attempt in attempts:
        status = str(attempt.get("status", ""))
        by_status[status] = by_status.get(status, 0) + 1
        if status not in {"completed", "passed"}:
            non_completed.append(str(attempt.get("attempt_id", "")))
    confounders = _mapping(guided.get("confounders"))
    stability = dict(_mapping(guided.get("stability")))
    negative_controls = dict(_mapping(guided.get("negative_controls")))
    multiplicity = dict(_mapping(guided.get("multiplicity")))
    authority = dict(_mapping(gate_packet.get("authority")))
    return {
        "packet_schema": "StrategyPromotionPacketV1",
        "project_id": str(project.get("project_id", "")),
        "project_name": project.get("name"),
        "decision": dict(decision),
        "hypothesis_card": research_hypothesis_card(contract_payload),
        "gate_packet_reference": {"packet_id": packet_id, "packet_hash": packet_hash},
        "registered_datasets": [dict(dataset) for dataset in datasets],
        "registered_datasets_truncated": datasets_truncated,
        "screened_source_claims": [dict(claim) for claim in claims],
        "screened_source_claims_truncated": claims_truncated,
        "confounder_ledger": {
            "registered": _string_list(contract_payload.get("confounders")),
            "resolved": _string_list(confounders.get("resolved")),
            "unresolved": _string_list(confounders.get("unresolved")),
        },
        "falsification": {
            "required_falsifiers": _json_list(contract_payload.get("required_falsifiers")),
            "stop_rules": _json_list(contract_payload.get("stop_rules")),
            "negative_controls": negative_controls or None,
            "multiplicity": multiplicity or None,
        },
        "stability_findings": stability or None,
        "known_failure_conditions": _string_list(guided.get("what_would_change_conclusion")),
        "assumptions_limitations": {
            "strongest_caveat": _optional_text(conclusion.get("strongest_caveat")),
            "authority": authority or None,
        },
        "headline_chart_references": [dict(reference) for reference in chart_references],
        "negative_attempt_summary": {
            "total_attempts": len(attempts),
            "by_status": {status: by_status[status] for status in sorted(by_status)},
            "non_completed_attempt_ids": non_completed,
        },
        "open_questions": {
            "blocking_questions": _question_texts(contract_payload.get("blocking_questions")),
            "untested_work": _string_list(guided.get("untested_work")),
        },
    }


def _finding_status(value: object) -> str:
    finding = _mapping(value)
    status = finding.get("status")
    return status if isinstance(status, str) and status else "NOT_TESTED"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _question_texts(value: object) -> list[str]:
    """Blocking questions are structured objects; project their question text."""
    if not isinstance(value, list):
        return []
    texts: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            texts.append(item)
            continue
        mapping = _mapping(item)
        question = mapping.get("prompt", mapping.get("question"))
        if isinstance(question, str) and question.strip():
            texts.append(question)
    return texts


def research_scorecard_inputs(
    summary: Mapping[str, object],
    payload: Mapping[str, object],
    *,
    packet: Mapping[str, object] | None = None,
    datasets: Sequence[Mapping[str, object]] = (),
    claims: Sequence[Mapping[str, object]] = (),
    live_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Assemble the compact, TS-twinnable inputs for the readiness scorecard.

    Everything comes from already-authoritative records: the case summary, the immutable
    contract payload, the deterministic terminal gate packet for closed cases, or — for
    open cases with admitted D1 evidence — the store-verified typed evidence of the
    latest completed deep-research attempt (``live_evidence``). The assembler never
    computes evidence; it only relays recorded statuses.
    """
    card = research_hypothesis_card(payload)
    fields = card["fields"]
    if not isinstance(fields, list):  # pragma: no cover - card invariant above.
        raise DataError("hypothesis card projection is corrupt")
    statuses = [str(_mapping(field).get("status")) for field in fields]
    decision = _mapping(summary.get("research_decision"))

    guided = _mapping(_mapping(_mapping(packet).get("layers")).get("guided_evidence"))
    if packet is None and live_evidence is not None:
        # The typed D1 evidence artifact shares the guided-evidence field vocabulary.
        guided = _mapping(live_evidence)
    primary = _mapping(guided.get("primary_result"))
    stability = _mapping(guided.get("stability"))
    packet_confounders = _mapping(guided.get("confounders"))
    classification = guided.get("confirmation_classification")
    mechanical_readiness = derive_research_readiness(guided)
    confirmation_readiness = _mapping(guided.get("confirmation_readiness"))
    promotion_readiness = _mapping(guided.get("promotion_readiness"))

    confounders_registered = _string_list(payload.get("confounders"))
    confounders_resolved = _string_list(packet_confounders.get("resolved"))
    confounders_unresolved = (
        _string_list(packet_confounders.get("unresolved")) if guided else confounders_registered
    )

    attempt_count = summary.get("attempt_count")
    return {
        "inputs_schema": "ResearchScorecardInputsV1",
        "phase": str(summary.get("phase", "")),
        "outcome": _optional_text(decision.get("outcome")),
        "disposition": _optional_text(decision.get("disposition")),
        "d2_state": str(summary.get("d2_state", "")),
        "hypothesis_complete_fields": statuses.count("complete"),
        "hypothesis_partial_fields": statuses.count("partial"),
        "hypothesis_total_fields": len(statuses),
        "registered_dataset_count": len(datasets),
        "audited_dataset_count": sum(
            1 for dataset in datasets if _mapping(dataset.get("latest_audit"))
        ),
        "audit_blocking_count": sum(
            int(
                _finite_number(
                    _mapping(_mapping(dataset.get("latest_audit")).get("summary")).get(
                        "blocking_count"
                    )
                )
            )
            for dataset in datasets
        ),
        "audit_limiting_count": sum(
            int(
                _finite_number(
                    _mapping(_mapping(dataset.get("latest_audit")).get("summary")).get(
                        "limiting_count"
                    )
                )
            )
            for dataset in datasets
        ),
        "screened_claim_count": sum(1 for claim in claims if claim.get("status") == "screened"),
        "screened_supporting_count": sum(
            1
            for claim in claims
            if claim.get("status") == "screened" and claim.get("direction") == "supports"
        ),
        "screened_contradicting_count": sum(
            1
            for claim in claims
            if claim.get("status") == "screened" and claim.get("direction") == "contradicts"
        ),
        "blocking_questions": _question_texts(payload.get("blocking_questions")),
        "confounders_resolved": confounders_resolved,
        "confounders_unresolved": confounders_unresolved,
        "untested_work": _string_list(guided.get("untested_work")),
        "attempt_count": (
            attempt_count
            if isinstance(attempt_count, int) and not isinstance(attempt_count, bool)
            else 0
        ),
        "primary_result_status": (
            str(primary.get("status")) if isinstance(primary.get("status"), str) else "NOT_TESTED"
        ),
        "practical_magnitude_status": (
            str(_mapping(primary.get("practical_magnitude")).get("status", "NOT_TESTED"))
        ),
        "confirmation_classification": (
            classification if isinstance(classification, str) and classification else None
        ),
        "power_status": _finding_status(guided.get("power")),
        "negative_controls_status": _finding_status(guided.get("negative_controls")),
        "multiplicity_status": _finding_status(guided.get("multiplicity")),
        "mechanism_status": _finding_status(guided.get("mechanism")),
        "stability_parameter_status": _finding_status(stability.get("parameter")),
        "stability_temporal_status": _finding_status(stability.get("temporal")),
        "stability_transportability_status": _finding_status(stability.get("transportability")),
        "confirmation_readiness": (
            dict(confirmation_readiness)
            if confirmation_readiness
            else mechanical_readiness["confirmation_readiness"]
        ),
        "promotion_readiness": (
            dict(promotion_readiness)
            if promotion_readiness
            else mechanical_readiness["promotion_readiness"]
        ),
    }


def _dimension(dimension_id: str, label: str, state: str, basis: str) -> dict[str, object]:
    return {"dimension_id": dimension_id, "label": label, "state": state, "basis": basis}


def derive_research_scorecard(inputs: Mapping[str, object]) -> dict[str, object]:
    """Derive the 13-row readiness scorecard (spec §10.2) from recorded statuses only.

    Enumerated states, transparent bases, and a rule-derived recommendation — never a
    numeric aggregate or a single confidence score. This Python projection is the sole
    readiness authority; clients render it without re-deriving semantics.
    """
    complete = int(_finite_number(inputs.get("hypothesis_complete_fields")))
    partial = int(_finite_number(inputs.get("hypothesis_partial_fields")))
    total = int(_finite_number(inputs.get("hypothesis_total_fields"))) or 14
    if complete == total:
        hypothesis_state = "complete"
    elif complete + partial == 0:
        hypothesis_state = "missing"
    else:
        hypothesis_state = "partial"

    dataset_count = int(_finite_number(inputs.get("registered_dataset_count")))
    audited_count = int(_finite_number(inputs.get("audited_dataset_count")))
    audit_blocking = int(_finite_number(inputs.get("audit_blocking_count")))
    audit_limiting = int(_finite_number(inputs.get("audit_limiting_count")))
    if dataset_count == 0:
        data_quality_state = "not_tested"
        data_quality_basis = "No registered research datasets."
    elif audit_blocking > 0:
        data_quality_state = "blocked"
        data_quality_basis = f"{audit_blocking} blocking data-audit findings."
    elif audited_count == 0:
        data_quality_state = "adequate"
        data_quality_basis = f"{dataset_count} registered datasets; not yet audited."
    elif audit_limiting > 0:
        data_quality_state = "weak"
        data_quality_basis = f"{audit_limiting} limiting data-audit findings."
    else:
        data_quality_state = "strong"
        data_quality_basis = "Every registered dataset audited with no findings."
    claim_count = int(_finite_number(inputs.get("screened_claim_count")))
    supporting_claims = int(_finite_number(inputs.get("screened_supporting_count")))
    contradicting_claims = int(_finite_number(inputs.get("screened_contradicting_count")))
    if claim_count == 0:
        literature_state = "insufficient"
        literature_basis = "No screened claim-level literature evidence."
    elif supporting_claims > 0 and contradicting_claims > 0:
        literature_state = "mixed"
        literature_basis = (
            f"{supporting_claims} supporting vs {contradicting_claims} contradicting "
            "screened claims."
        )
    elif contradicting_claims > 0:
        literature_state = "contradictory"
        literature_basis = f"{contradicting_claims} contradicting screened claims."
    elif supporting_claims > 0:
        literature_state = "supporting"
        literature_basis = f"{supporting_claims} supporting screened claims."
    else:
        literature_state = "insufficient"
        literature_basis = (
            f"{claim_count} screened claims are contextual/method only; no directional evidence."
        )
    classification = _optional_text(inputs.get("confirmation_classification"))
    primary_status = str(inputs.get("primary_result_status", "NOT_TESTED"))
    magnitude = str(inputs.get("practical_magnitude_status", "NOT_TESTED"))
    power = str(inputs.get("power_status", "NOT_TESTED"))
    negative_controls = str(inputs.get("negative_controls_status", "NOT_TESTED"))
    multiplicity = str(inputs.get("multiplicity_status", "NOT_TESTED"))
    mechanism = str(inputs.get("mechanism_status", "NOT_TESTED"))
    temporal = str(inputs.get("stability_temporal_status", "NOT_TESTED"))
    transport = str(inputs.get("stability_transportability_status", "NOT_TESTED"))
    confirmation_readiness = dict(_mapping(inputs.get("confirmation_readiness")))
    promotion_readiness = dict(_mapping(inputs.get("promotion_readiness")))
    if not confirmation_readiness or not promotion_readiness:
        fallback_readiness = derive_research_readiness(
            {
                "primary_result": {
                    "status": primary_status,
                    "practical_magnitude": {"status": magnitude},
                },
                "confirmation_classification": classification,
                "power": {"status": power},
                "multiplicity": {"status": multiplicity},
                "negative_controls": {"status": negative_controls},
            }
        )
        confirmation_readiness = confirmation_readiness or dict(
            fallback_readiness["confirmation_readiness"]
        )
        promotion_readiness = promotion_readiness or dict(fallback_readiness["promotion_readiness"])

    if classification == "SUPPORTED":
        effect_existence = "supported"
        effect_basis = "Sealed confirmation supported the registered claim."
    elif classification == "CONTRADICTED":
        effect_existence = "unsupported"
        effect_basis = "Sealed confirmation contradicted the registered claim."
    elif classification in {"INCONCLUSIVE", "INVALID"}:
        effect_existence = "mixed"
        effect_basis = f"Sealed confirmation classified the claim {classification}."
    elif primary_status == "TESTED":
        effect_existence = "mixed"
        effect_basis = "Exploratory result only; the sealed confirmation has not run."
    else:
        effect_existence = "not_tested"
        effect_basis = "No primary-result evidence has been recorded."

    if magnitude == "CLEARS_HURDLE":
        effect_size, size_basis = "meaningful", "Recorded magnitude clears the registered hurdle."
    elif magnitude == "BELOW_HURDLE":
        effect_size, size_basis = "negligible", "Recorded magnitude is below the registered hurdle."
    elif magnitude == "INCONCLUSIVE":
        effect_size, size_basis = "marginal", "Recorded magnitude is inconclusive at the hurdle."
    else:
        effect_size, size_basis = "not_tested", "No practical-magnitude evidence exists."

    def _stability(state: str) -> str:
        if state == "STABLE":
            return "strong"
        if state == "NOT_TESTED":
            return "not_tested"
        return "weak" if state == "UNSTABLE" else "mixed"

    if power == "PASSED":
        sample_state, sample_basis = "adequate", "The registered power gate passed."
    elif power == "NOT_TESTED":
        sample_state, sample_basis = "not_tested", "No power evidence has been recorded."
    else:
        sample_state, sample_basis = "weak", f"The recorded power finding is {power}."

    if negative_controls == "PASSED":
        falsification_state, falsification_basis = "passed", "Registered negative controls passed."
    elif negative_controls == "FAILED":
        falsification_state, falsification_basis = "failed", "Registered negative controls failed."
    elif negative_controls == "NOT_TESTED":
        falsification_state = "not_tested"
        falsification_basis = "The registered falsifiers have not run."
    else:
        falsification_state = "mixed"
        falsification_basis = f"The negative-control finding is {negative_controls}."

    if mechanism in {"SUPPORTED", "PASSED", "OBSERVED"}:
        mechanism_state, mechanism_basis = (
            "plausible",
            "The recorded mechanism finding supports it.",
        )
    elif mechanism in {"CONTRADICTED", "FAILED"}:
        mechanism_state, mechanism_basis = "unsupported", "The recorded mechanism finding fails."
    elif mechanism == "NOT_TESTED":
        mechanism_state, mechanism_basis = "not_tested", "No mechanism evidence has been recorded."
    else:
        mechanism_state, mechanism_basis = "unclear", f"The mechanism finding is {mechanism}."

    if multiplicity == "PASSED":
        mining_state, mining_basis = "low", "Registered multiplicity accounting passed."
    elif multiplicity == "FAILED":
        mining_state, mining_basis = "high", "Registered multiplicity accounting failed."
    elif multiplicity == "NOT_TESTED":
        mining_state = "low"
        mining_basis = (
            "All analysis families are contract-registered; unregistered attempts are impossible."
        )
    else:
        mining_state, mining_basis = "medium", f"The multiplicity finding is {multiplicity}."

    dimensions = [
        _dimension(
            "hypothesis_definition",
            "Hypothesis definition",
            hypothesis_state,
            f"{complete} of {total} hypothesis-card fields are complete.",
        ),
        _dimension("data_quality", "Data quality", data_quality_state, data_quality_basis),
        _dimension("sample_adequacy", "Sample adequacy", sample_state, sample_basis),
        _dimension("effect_existence", "Effect existence", effect_existence, effect_basis),
        _dimension("effect_size", "Effect size", effect_size, size_basis),
        _dimension(
            "temporal_stability",
            "Temporal stability",
            _stability(temporal),
            f"The recorded temporal-stability finding is {temporal}.",
        ),
        _dimension(
            "cross_asset_stability",
            "Cross-asset stability",
            "strong"
            if transport == "STABLE"
            else ("not_tested" if transport == "NOT_TESTED" else "mixed"),
            f"The recorded transportability finding is {transport}.",
        ),
        _dimension(
            "regime_robustness",
            "Regime robustness",
            "not_tested",
            "No regime-decomposition evidence exists yet.",
        ),
        _dimension("falsification", "Falsification", falsification_state, falsification_basis),
        _dimension("mechanism", "Mechanism", mechanism_state, mechanism_basis),
        _dimension("literature", "Literature", literature_state, literature_basis),
        _dimension("data_mining_risk", "Data-mining risk", mining_state, mining_basis),
    ]

    unresolved_items = [
        *_string_list(inputs.get("blocking_questions")),
        *[
            f"Unresolved confounder: {item}"
            for item in _string_list(inputs.get("confounders_unresolved"))
        ],
        *_string_list(inputs.get("untested_work")),
    ]

    outcome = _optional_text(inputs.get("outcome"))
    if outcome == "CONTRADICTED":
        recommendation = "EVIDENCE DOES NOT SUPPORT CONTINUATION"
        reasons = ["Sealed confirmation contradicted the registered claim."]
    elif outcome == "INVALID":
        recommendation = "REFORMULATE HYPOTHESIS"
        reasons = ["The confirmation run was invalid under the registered protocol."]
    elif outcome == "SUPPORTED" and promotion_readiness.get("state") == "ready":
        recommendation = "READY FOR STRATEGY RESEARCH"
        reasons = [
            "Sealed confirmation supported the registered claim at the frozen alpha and "
            "minimum effect."
        ]
    elif hypothesis_state == "missing":
        recommendation = "REFORMULATE HYPOTHESIS"
        reasons = ["The hypothesis card has no complete or partial fields."]
    else:
        untested = sum(1 for entry in dimensions if entry["state"] == "not_tested")
        recommendation = "MORE RESEARCH REQUIRED"
        reasons = [
            f"{untested} of {len(dimensions)} readiness dimensions are untested.",
            f"{len(unresolved_items)} unresolved questions remain.",
        ]

    return {
        "scorecard_schema": "ResearchReadinessScorecardV1",
        "dimensions": dimensions,
        "unresolved_questions": {"count": len(unresolved_items), "items": unresolved_items},
        "recommendation": {"value": recommendation, "reasons": reasons},
        "confirmation_readiness": confirmation_readiness,
        "promotion_readiness": promotion_readiness,
    }


_LIVE_EVIDENCE_PHASES = frozenset(
    {"deep_research", "confirmation_review", "sealed_confirmation", "research_decision"}
)


def _question(
    question_id: str, number: int, question: str, binding: str, status: str, answer: str
) -> dict[str, object]:
    return {
        "question_id": question_id,
        "number": number,
        "question": question,
        "binding": binding,
        "status": status,
        "answer": answer,
    }


def derive_research_checklist(inputs: Mapping[str, object]) -> dict[str, object]:
    """Derive the 14-question edge-validation checklist (spec §10.1) from recorded statuses.

    Every question is answered by a typed finding status or an explicit ``NOT_TESTED`` —
    never a numeric aggregate or a confidence score. Clients render this Python projection
    without re-deriving semantics.
    """
    classification = _optional_text(inputs.get("confirmation_classification"))
    primary_status = str(inputs.get("primary_result_status", "NOT_TESTED"))
    magnitude = str(inputs.get("practical_magnitude_status", "NOT_TESTED"))
    power = str(inputs.get("power_status", "NOT_TESTED"))
    negative_controls = str(inputs.get("negative_controls_status", "NOT_TESTED"))
    mechanism = str(inputs.get("mechanism_status", "NOT_TESTED"))
    parameter = str(inputs.get("stability_parameter_status", "NOT_TESTED"))
    temporal = str(inputs.get("stability_temporal_status", "NOT_TESTED"))
    transport = str(inputs.get("stability_transportability_status", "NOT_TESTED"))
    dataset_count = int(_finite_number(inputs.get("registered_dataset_count")))
    audited_count = int(_finite_number(inputs.get("audited_dataset_count")))
    audit_blocking = int(_finite_number(inputs.get("audit_blocking_count")))
    audit_limiting = int(_finite_number(inputs.get("audit_limiting_count")))
    supporting_claims = int(_finite_number(inputs.get("screened_supporting_count")))
    contradicting_claims = int(_finite_number(inputs.get("screened_contradicting_count")))

    if classification is not None:
        effect_status = classification
        effect_answer = f"Sealed confirmation classified the registered claim {classification}."
    elif primary_status == "TESTED":
        effect_status = "TESTED"
        effect_answer = "An exploratory primary result exists; the sealed confirmation has not run."
    else:
        effect_status = "NOT_TESTED"
        effect_answer = "No primary-result evidence has been recorded."

    magnitude_answers = {
        "CLEARS_HURDLE": "The recorded magnitude clears the registered minimum effect.",
        "BELOW_HURDLE": "The recorded magnitude is below the registered minimum effect.",
        "NOT_TESTED": "No practical-magnitude evidence exists.",
    }
    if power == "PASSED":
        breadth_answer = (
            "The effective event clusters support the interval beyond one small sample."
        )
    elif power == "NOT_TESTED":
        breadth_answer = "No effective-sample evidence has been recorded."
    else:
        breadth_answer = f"The recorded power finding is {power}."
    falsification_answers = {
        "PASSED": "Registered negative controls passed.",
        "FAILED": "Registered negative controls failed.",
        "NOT_TESTED": "The registered falsifiers have not run.",
    }
    if dataset_count == 0 or audited_count == 0:
        artifact_status, artifact_answer = "NOT_TESTED", "No registered dataset has been audited."
    elif audit_blocking > 0:
        artifact_status = "FAILED"
        artifact_answer = f"{audit_blocking} blocking data-audit findings."
    elif audit_limiting > 0:
        artifact_status = "INCONCLUSIVE"
        artifact_answer = f"{audit_limiting} limiting data-audit findings."
    else:
        artifact_status = "PASSED"
        artifact_answer = "Every registered dataset audited with no findings."
    leakage_answers = {
        "PASSED": "The registered control battery, including the lead-lag leakage screen, passed.",
        "FAILED": "A registered control failed; review the lead-lag leakage screen.",
        "NOT_TESTED": (
            "The lead-lag leakage screen has not run; look-ahead stays structurally "
            "guarded by the point-in-time firewall."
        ),
    }
    if power == "PASSED":
        count_answer = "The effective clusters clear the ten-cluster reliability floor."
    elif power == "INCONCLUSIVE":
        count_answer = "The effective clusters sit below the ten-cluster reliability floor."
    elif power == "NOT_TESTED":
        count_answer = "No power evidence has been recorded."
    else:
        count_answer = f"The recorded power finding is {power}."
    unresolved_count = len(_string_list(inputs.get("blocking_questions"))) + len(
        _string_list(inputs.get("confounders_unresolved"))
    )
    untested_count = len(_string_list(inputs.get("untested_work")))

    questions = [
        _question(
            "effect_exists",
            1,
            "Does the effect exist?",
            "primary result",
            effect_status,
            effect_answer,
        ),
        _question(
            "practical_magnitude",
            2,
            "Is it large enough to matter?",
            "practical magnitude vs registered minimum effect",
            magnitude,
            magnitude_answers.get(magnitude, f"The recorded magnitude finding is {magnitude}."),
        ),
        _question(
            "temporal_stability",
            3,
            "Is it stable through time?",
            "temporal stability",
            temporal,
            f"The recorded temporal-stability finding is {temporal}.",
        ),
        _question(
            "sample_breadth",
            4,
            "Does it exist beyond one small sample?",
            "effective sample and registered subsamples",
            power,
            breadth_answer,
        ),
        _question(
            "transportability",
            5,
            "Does it exist across relevant assets, or only one?",
            "cross-asset transportability",
            transport,
            f"The recorded transportability finding is {transport}.",
        ),
        _question(
            "regime_dependence",
            6,
            "Is it regime-dependent?",
            "regime decomposition",
            "NOT_TESTED",
            "No regime-decomposition evidence exists yet.",
        ),
        _question(
            "parameter_neighborhood",
            7,
            "Does it survive alternative definitions?",
            "parameter neighborhood",
            parameter,
            f"The recorded parameter-neighborhood finding is {parameter}.",
        ),
        _question(
            "falsification",
            8,
            "Does it survive falsification tests?",
            "placebo, negative controls, and registered nulls",
            negative_controls,
            falsification_answers.get(
                negative_controls, f"The negative-control finding is {negative_controls}."
            ),
        ),
        _question(
            "data_artifact",
            9,
            "Is it likely a data artifact?",
            "data-quality audit findings",
            artifact_status,
            artifact_answer,
        ),
        _question(
            "leakage",
            10,
            "Is it likely look-ahead or leakage?",
            "future-poison and lead-lag diagnostics",
            negative_controls,
            leakage_answers.get(
                negative_controls, f"The registered control battery is {negative_controls}."
            ),
        ),
        _question(
            "mechanism",
            11,
            "Is there a plausible mechanism?",
            "mechanism finding and screened claims",
            mechanism,
            (
                f"The recorded mechanism finding is {mechanism}; {supporting_claims} supporting "
                f"and {contradicting_claims} contradicting screened claims."
            ),
        ),
        _question(
            "economic_hurdle",
            12,
            "Could the magnitude survive realistic costs?",
            "economic-hurdle check (last rung)",
            "NOT_TESTED",
            "No economic-hurdle evidence exists; cost realism is the last rung before "
            "strategy work.",
        ),
        _question(
            "observation_count",
            13,
            "Do we have enough observations?",
            "power and the low-cluster floor",
            power,
            count_answer,
        ),
        _question(
            "residual_uncertainty",
            14,
            "How much uncertainty remains?",
            "intervals and untested work",
            "TESTED",
            (
                f"{unresolved_count} unresolved questions and {untested_count} untested "
                "workstreams remain."
            ),
        ),
    ]
    return {"checklist_schema": "ResearchEdgeChecklistV1", "questions": questions}


def _case_scorecard_inputs(
    store: ResearchPacketStore,
    project_id: str,
    case: Mapping[str, object],
) -> tuple[dict[str, object], Mapping[str, object] | None]:
    """Assemble scorecard/checklist inputs and the terminal packet (closed cases only)."""
    payload = _mapping(_mapping(case.get("active_contract")).get("payload"))
    packet: Mapping[str, object] | None = None
    live_evidence: Mapping[str, object] | None = None
    if case.get("phase") == "closed":
        packet = build_research_gate_packet(store.research_gate_packet_inputs(project_id)).to_dict()
    elif str(case.get("phase")) in _LIVE_EVIDENCE_PHASES:
        live_evidence = _latest_live_evidence(store.research_gate_packet_inputs(project_id))
    inputs = research_scorecard_inputs(
        case,
        payload,
        packet=packet,
        datasets=_case_datasets(store, payload),
        claims=store.list_source_claims(project_id),
        live_evidence=live_evidence,
    )
    return inputs, packet


def research_scorecard_projection(
    store: ResearchPacketStore,
    project_id: str,
    *,
    summary: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Project the readiness scorecard for one case from public store reads only."""
    case = store.research_case_summary(project_id) if summary is None else summary
    inputs, _packet = _case_scorecard_inputs(store, project_id, case)
    return derive_research_scorecard(inputs)


class ResearchDecisionViewStore(ResearchPacketStore, Protocol):
    def list_research_decisions(self, project_id: str) -> list[dict[str, object]]: ...


def research_decision_view_projection(
    store: ResearchDecisionViewStore, project_id: str
) -> dict[str, object]:
    """Assemble the owner decision view: checklist, full scorecard, packet, and history.

    Read-only over public store seams. The gate packet appears only for closed cases —
    open cases stay live from admitted evidence; the append-only decision history is
    relayed verbatim.
    """
    case = store.research_case_summary(project_id)
    inputs, packet = _case_scorecard_inputs(store, project_id, case)
    scorecard = derive_research_scorecard(inputs)
    return {
        "view_schema": "ResearchDecisionViewV1",
        "project_id": str(case.get("project_id", project_id)),
        "phase": str(case.get("phase", "")),
        "d2_state": str(case.get("d2_state", "")),
        "next_action": str(case.get("next_action", "")),
        "checklist": derive_research_checklist(inputs),
        "scorecard": scorecard,
        "confirmation_readiness": scorecard["confirmation_readiness"],
        "promotion_readiness": scorecard["promotion_readiness"],
        "gate_packet": None if packet is None else dict(packet),
        "decision_history": store.list_research_decisions(project_id),
    }


_SUPPORTING_FINDING_STATUSES = frozenset({"PASSED", "STABLE", "SUPPORTED"})
_CONTRADICTING_FINDING_STATUSES = frozenset({"FAILED", "UNSTABLE", "CONTRADICTED"})


def _named_findings(guided: Mapping[str, object]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    named: list[tuple[str, object]] = [
        ("mechanism", guided.get("mechanism")),
        ("strongest_support", guided.get("strongest_support")),
        ("strongest_contradiction", guided.get("strongest_contradiction")),
        ("multiplicity", guided.get("multiplicity")),
        ("power", guided.get("power")),
        ("negative_controls", guided.get("negative_controls")),
    ]
    stability = _mapping(guided.get("stability"))
    for axis in ("parameter", "temporal", "transportability"):
        named.append((f"stability_{axis}", stability.get(axis)))
    for finding_id, value in named:
        finding = _mapping(value)
        if not finding:
            continue
        summary = finding.get("summary")
        findings.append(
            {
                "finding_id": finding_id,
                "status": _finding_status(finding),
                "summary": summary if isinstance(summary, str) else None,
            }
        )
    return findings


def _packet_findings(packet: Mapping[str, object] | None) -> list[dict[str, object]]:
    """Flatten the packet's guided evidence into typed findings for partitioning."""
    layers = _mapping(_mapping(packet).get("layers"))
    guided = _mapping(layers.get("guided_evidence"))
    conclusion = _mapping(layers.get("conclusion_90_seconds"))
    findings: list[dict[str, object]] = []
    classification = guided.get("confirmation_classification")
    if isinstance(classification, str) and classification:
        answer = conclusion.get("thesis_answer")
        findings.append(
            {
                "finding_id": "confirmation_classification",
                "status": classification,
                "summary": answer if isinstance(answer, str) else None,
            }
        )
    return [*findings, *_named_findings(guided)]


def _latest_live_evidence(inputs: Mapping[str, object]) -> Mapping[str, object] | None:
    """The newest completed attempt's store-verified typed D1 or D2 evidence, if any."""
    attempts = inputs.get("attempts")
    if not isinstance(attempts, list):
        return None
    live: Mapping[str, object] | None = None
    for attempt in attempts:
        record = _mapping(attempt)
        if record.get("status") != "completed":
            continue
        evidence = _mapping(_mapping(record.get("details")).get("gate_packet_evidence"))
        if evidence.get("schema") == "ResearchGateEvidenceV1" and evidence.get("evidence_zone") in {
            "D1",
            "D2",
        }:
            live = evidence
    return live


def _live_findings(evidence: Mapping[str, object] | None) -> list[dict[str, object]]:
    """Flatten live D1 evidence into typed findings; the strongest lines keep direction."""
    guided = _mapping(evidence)
    if not guided:
        return []
    findings = _named_findings(guided)
    support = guided.get("strongest_support")
    if isinstance(support, str) and support.strip():
        findings.append(
            {"finding_id": "strongest_support", "status": "SUPPORTED", "summary": support}
        )
    contradiction = guided.get("strongest_contradiction")
    if isinstance(contradiction, str) and contradiction.strip():
        findings.append(
            {
                "finding_id": "strongest_contradiction",
                "status": "CONTRADICTED",
                "summary": contradiction,
            }
        )
    return findings


def _bounded_sources(rows: object) -> list[dict[str, object]]:
    """Project bounded source records; screening state comes from recorded metadata."""
    if not isinstance(rows, list):
        return []
    projected: list[dict[str, object]] = []
    for row in rows:
        record = _mapping(row)
        if not record:
            continue
        metadata_raw = record.get("metadata_json")
        screening: str | None = None
        if isinstance(metadata_raw, str):
            try:
                metadata = json.loads(metadata_raw)
            except ValueError:
                metadata = None
            if isinstance(metadata, dict):
                value = metadata.get("screening")
                screening = value if isinstance(value, str) else None
        projected.append(
            {
                "source_id": str(record.get("source_id", "")),
                "title": str(record.get("title", "")),
                "locator": str(record.get("locator", "")),
                "provider": str(record.get("provider", "")),
                "access_mode": str(record.get("access_mode", "")),
                "screening": screening,
            }
        )
    return projected


def _bounded_attempts(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    projected: list[dict[str, object]] = []
    for row in rows:
        record = _mapping(row)
        if not record:
            continue
        run_id = record.get("run_id")
        projected.append(
            {
                "attempt_id": str(record.get("attempt_id", "")),
                "phase": str(record.get("phase", "")),
                "kind": str(record.get("kind", "")),
                "status": str(record.get("status", "")),
                "config_fingerprint": str(record.get("config_fingerprint", "")),
                "run_id": run_id if isinstance(run_id, str) else None,
                "recorded_at": str(record.get("recorded_at", "")),
            }
        )
    return projected


def research_evidence_hub_projection(
    store: ResearchPacketStore, project_id: str
) -> dict[str, object]:
    """Aggregate the eleven Evidence Hub sections (spec §6.2) from public store reads.

    One workflow surface, not eleven dashboards: sections fill as phases progress and
    render honest ``NOT_TESTED`` states before then. Evidence for and evidence against
    are structurally identical so the panel cannot bias their prominence.
    """
    summary = store.research_case_summary(project_id)
    payload = _mapping(_mapping(summary.get("active_contract")).get("payload"))
    inputs = store.research_gate_packet_inputs(project_id)
    packet: Mapping[str, object] | None = None
    if summary.get("phase") == "closed":
        packet = build_research_gate_packet(inputs).to_dict()

    live_evidence = None if packet is not None else _latest_live_evidence(inputs)
    thesis = _mapping(payload.get("thesis"))
    card = research_hypothesis_card(payload)
    datasets = _case_datasets(store, payload)
    claims = store.list_source_claims(project_id)
    scorecard = derive_research_scorecard(
        research_scorecard_inputs(
            summary,
            payload,
            packet=packet,
            datasets=datasets,
            claims=claims,
            live_evidence=live_evidence,
        )
    )
    scorecard_dimensions = scorecard["dimensions"]
    if not isinstance(scorecard_dimensions, list):  # pragma: no cover - deriver invariant.
        raise DataError("research scorecard projection is corrupt")
    data_quality = next(
        (
            _mapping(entry)
            for entry in scorecard_dimensions
            if _mapping(entry).get("dimension_id") == "data_quality"
        ),
        {},
    )
    guided = _mapping(_mapping(_mapping(packet).get("layers")).get("guided_evidence"))
    if packet is None and live_evidence is not None:
        guided = _mapping(live_evidence)
    findings = _packet_findings(packet) if packet is not None else _live_findings(live_evidence)
    packet_confounders = _mapping(guided.get("confounders"))
    registered_confounders = _string_list(payload.get("confounders"))
    if guided:
        confounder_rows = [
            {"text": text, "status": "resolved"}
            for text in _string_list(packet_confounders.get("resolved"))
        ] + [
            {"text": text, "status": "unresolved"}
            for text in _string_list(packet_confounders.get("unresolved"))
        ]
    else:
        confounder_rows = [
            {"text": text, "status": "unresolved"} for text in registered_confounders
        ]
    decision = _mapping(summary.get("research_decision"))
    mechanism = thesis.get("mechanism")
    interpretation = thesis.get("interpretation")
    attempts = _bounded_attempts(inputs.get("attempts"))
    exploration_charts = [
        {
            "run_id": attempt["run_id"],
            "figure_id": "research_discovery_trace",
            "evidence_phase": "exploratory",
            "watermark": "EXPLORATORY",
        }
        for attempt in attempts
        if attempt["kind"] == "d1-deep-research"
        and attempt["status"] == "completed"
        and isinstance(attempt["run_id"], str)
    ]

    sections: dict[str, object] = {
        "overview": {
            "original_idea": str(payload.get("raw_idea", "") or ""),
            "phase": str(summary.get("phase", "")),
            "execution_state": str(summary.get("execution_state", "")),
            "next_action": str(summary.get("next_action", "")),
            "responsibility": str(summary.get("responsibility", "")),
            "latest_finding": _optional_text(summary.get("latest_finding")),
            "outstanding_questions": _question_texts(payload.get("blocking_questions")),
            "hypothesis_card": card,
            "scorecard": scorecard,
        },
        "data": {
            "registered_datasets": [
                {
                    "ref_id": str(dataset.get("ref_id", "")),
                    "dataset_kind": str(dataset.get("dataset_kind", "")),
                    "instrument": str(dataset.get("instrument", "")),
                    "provider": str(dataset.get("provider", "")),
                    "start_ts": str(dataset.get("start_ts", "")),
                    "end_ts": str(dataset.get("end_ts", "")),
                    "latest_audit": _mapping(dataset.get("latest_audit")).get("summary"),
                }
                for dataset in datasets
            ],
            "status": str(data_quality.get("state", "not_tested")).upper(),
            "note": str(data_quality.get("basis", "No registered research datasets.")),
        },
        "literature": {
            "claims": [
                {
                    "claim_id": str(claim.get("claim_id", "")),
                    "direction": str(claim.get("direction", "")),
                    "strength": str(claim.get("strength", "")),
                    "status": str(claim.get("status", "")),
                    "claim_text": str(claim.get("claim_text", "")),
                    "source_id": str(claim.get("source_id", "")),
                    "author_kind": str(claim.get("author_kind", "")),
                    "limitations": str(claim.get("limitations", "")),
                }
                for claim in claims
            ],
            "sources": _bounded_sources(inputs.get("sources")),
            "status": next(
                (
                    str(_mapping(entry).get("state", "insufficient")).upper()
                    for entry in scorecard_dimensions
                    if _mapping(entry).get("dimension_id") == "literature"
                ),
                "INSUFFICIENT",
            ),
        },
        "mechanism": {
            "mechanism": mechanism if isinstance(mechanism, str) else None,
            "interpretation": interpretation if isinstance(interpretation, str) else None,
            "alternatives": _string_list(thesis.get("alternatives")),
            "confounders": confounder_rows,
        },
        "exploration": {
            "charts": exploration_charts,
            "watermark": "EXPLORATORY",
            "status": (
                "TESTED"
                if str(_mapping(guided.get("primary_result")).get("status")) == "TESTED"
                else "NOT_TESTED"
            ),
        },
        "experiments": {"attempts": attempts},
        "evidence_for": {
            "findings": [
                finding for finding in findings if finding["status"] in _SUPPORTING_FINDING_STATUSES
            ]
        },
        "evidence_against": {
            "findings": [
                finding
                for finding in findings
                if finding["status"] in _CONTRADICTING_FINDING_STATUSES
            ]
        },
        "falsification": {
            "falsifiers": [
                {"text": text, "result": "NOT_TESTED"}
                for text in _string_list(payload.get("required_falsifiers"))
            ],
            "stop_rules": _string_list(payload.get("stop_rules")),
        },
        "robustness": {
            "findings": [
                finding
                for finding in findings
                if str(finding["finding_id"]).startswith("stability_")
            ],
            "status": "NOT_TESTED" if not guided else "RECORDED",
        },
        "decision": {
            "outcome": _optional_text(decision.get("outcome")),
            "disposition": _optional_text(decision.get("disposition")),
            "d2_state": str(summary.get("d2_state", "")),
            "d3_state": str(summary.get("d3_state", "")),
            "packet_id": None if packet is None else str(packet.get("packet_id")),
            "packet_hash": None if packet is None else str(packet.get("packet_hash")),
        },
    }
    return {
        "hub_schema": "ResearchEvidenceHubV1",
        "project_id": str(summary.get("project_id", project_id)),
        "sections": sections,
    }


def research_backlog_row(case: Mapping[str, object], updated_at: str) -> dict[str, object]:
    """Project one bounded backlog row from the canonical research case summary."""
    payload = _mapping(_mapping(case.get("active_contract")).get("payload"))
    decision = _mapping(case.get("research_decision"))
    completed = case.get("completed_milestones")
    remaining = case.get("remaining_milestones")
    if not isinstance(completed, list) or not isinstance(remaining, list):
        raise DataError("research case summary has corrupt milestone projections")
    return {
        "case_id": str(case.get("project_id", "")),
        "title": str(case.get("project_name", "")),
        "original_idea": str(payload.get("raw_idea", "") or ""),
        "phase": str(case.get("phase", "")),
        "execution_state": str(case.get("execution_state", "")),
        "outcome": _optional_text(decision.get("outcome")),
        "disposition": _optional_text(decision.get("disposition")),
        "next_action": str(case.get("next_action", "")),
        "responsibility": str(case.get("responsibility", "")),
        "latest_finding": _optional_text(case.get("latest_finding")),
        "blocker": _optional_text(case.get("blocker")),
        "recovery_action": _optional_text(case.get("recovery")),
        "completed_milestones": len(completed),
        "total_milestones": len(completed) + len(remaining),
        # No pinning store and no scored advisory rubric exist yet; the projection reports
        # neutral values instead of inventing priority numbers (spec §2.2: never profit-based).
        "owner_pinned": False,
        "priority": {
            "falsifiability": 0,
            "data_readiness": 0,
            "novelty": 0,
            "information_gain_per_cost": 0,
        },
        "budget": _budget_minutes(case),
        "updated_at": updated_at,
    }


def research_report_projection(store: ResearchPacketStore, project_id: str) -> dict[str, object]:
    """Return the legacy progress report or one strict terminal packet."""
    summary = store.research_case_summary(project_id)
    if summary.get("phase") != "closed":
        return {
            "report_schema": "ResearchProgressReportV1",
            "terminal": False,
            "case": summary,
            "warning": "This is a progress report, not a terminal ResearchGatePacket.",
        }
    return build_research_gate_packet(store.research_gate_packet_inputs(project_id)).to_dict()


__all__ = [
    "ResearchDecisionViewStore",
    "ResearchPacketStore",
    "derive_research_checklist",
    "derive_research_scorecard",
    "research_backlog_row",
    "research_decision_view_projection",
    "research_evidence_hub_projection",
    "research_hypothesis_card",
    "research_report_projection",
    "research_scorecard_inputs",
    "research_scorecard_projection",
]
