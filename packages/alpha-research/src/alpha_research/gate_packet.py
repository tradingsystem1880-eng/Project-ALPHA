"""Deterministic terminal ResearchGatePacket projection.

The packet is a pure projection over already-bounded control-plane inputs.  It never reads storage,
opens evidence, or upgrades synthetic D0 fixtures into empirical support.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast

from alpha_core import DataError
from alpha_research.confirmation import (
    ClaimDirection,
    ConfirmationEvidence,
    classify_confirmation,
)

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | Sequence[JsonValue] | Mapping[str, JsonValue]
type ResearchOutcome = Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"]
type ResearchDisposition = Literal["advance_to_strategy", "revise", "park", "reject"]

_MAX_LEDGER_ROWS: Final = 10_000
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_OUTCOMES: Final = frozenset({"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"})
_DISPOSITIONS: Final = frozenset({"advance_to_strategy", "revise", "park", "reject"})
_ATTEMPT_STATUSES: Final = frozenset(
    {
        "queued",
        "running",
        "completed",
        "passed",
        "warning",
        "failed",
        "pruned",
        "rejected",
        "cancelled",
    }
)
_FINDING_STATUSES: Final = frozenset(
    {
        "PASSED",
        "FAILED",
        "STABLE",
        "UNSTABLE",
        "SUPPORTED",
        "CONTRADICTED",
        "INCONCLUSIVE",
        "NOT_TESTED",
    }
)


def _json_value(value: object, label: str) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DataError(f"{label} must contain only finite JSON numbers")
        return value
    if isinstance(value, list):
        return [_json_value(item, f"{label}[]") for item in value]
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DataError(f"{label} must use string JSON object keys")
            result[key] = _json_value(item, f"{label}.{key}")
        return result
    raise DataError(f"{label} must be JSON-compatible")


def _object(value: object, label: str) -> dict[str, JsonValue]:
    normalized = _json_value(value, label)
    if not isinstance(normalized, dict):
        raise DataError(f"{label} must be a JSON object")
    return normalized


def _array(value: object, label: str) -> list[JsonValue]:
    normalized = _json_value(value, label)
    if not isinstance(normalized, list):
        raise DataError(f"{label} must be a JSON array")
    return normalized


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"{label} must be non-empty text")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise DataError(f"{label} must be a finite number")
    return result


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DataError(f"{label} must be an integer >= 1")
    return value


def _text_list(value: object, label: str) -> list[str]:
    raw = _array(value, label)
    return [_text(item, f"{label}[]") for item in raw]


def _canonical_json_bytes(value: object) -> bytes:
    normalized = _json_value(value, "research gate packet")
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _strict_keys(
    value: dict[str, JsonValue],
    *,
    label: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise DataError(f"{label} is missing required fields: {', '.join(sorted(missing))}")
    if unknown:
        raise DataError(f"{label} has unsupported fields: {', '.join(sorted(unknown))}")


def _ledger(inputs: dict[str, JsonValue], key: str) -> list[dict[str, JsonValue]]:
    raw = inputs.get(key)
    if not isinstance(raw, list):
        raise DataError(f"research gate packet {key} must be a JSON array")
    if len(raw) > _MAX_LEDGER_ROWS:
        raise DataError(f"research gate packet {key} exceeds the {_MAX_LEDGER_ROWS}-row bound")
    result: list[dict[str, JsonValue]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise DataError(f"research gate packet {key}[{index}] must be an object")
        result.append(item)
    return result


def _claim(payload: dict[str, JsonValue], project: dict[str, JsonValue]) -> str:
    thesis = payload.get("thesis")
    if isinstance(thesis, dict):
        claims = thesis.get("primary_claims")
        if isinstance(claims, list) and len(claims) == 1 and isinstance(claims[0], dict):
            claim = claims[0]
            for key in ("claim", "statement", "prediction"):
                if isinstance(claim.get(key), str) and str(claim[key]).strip():
                    return str(claim[key])
            return _canonical_json_bytes(claim).decode("utf-8")
    hypothesis = project.get("hypothesis")
    return _text(hypothesis, "research project hypothesis")


def _proposed_mechanism(payload: dict[str, JsonValue]) -> str | None:
    thesis = payload.get("thesis")
    if isinstance(thesis, dict):
        mechanism = thesis.get("mechanism")
        if isinstance(mechanism, str) and mechanism.strip():
            return mechanism
    mechanism = payload.get("mechanism")
    if isinstance(mechanism, str) and mechanism.strip():
        return mechanism
    return None


def _not_tested_finding(summary: str | None = None) -> dict[str, JsonValue]:
    return {"status": "NOT_TESTED", "summary": summary}


def _not_tested_primary() -> dict[str, JsonValue]:
    return {
        "status": "NOT_TESTED",
        "estimate": None,
        "unit": None,
        "sample_size": None,
        "effective_sample_size": None,
        "uncertainty": None,
        "practical_magnitude": {
            "status": "NOT_TESTED",
            "value": None,
            "unit": None,
            "interpretation": "No typed D1 or D2 empirical result is present.",
        },
    }


def _finding(value: object, label: str) -> dict[str, JsonValue]:
    raw = _object(value, label)
    _strict_keys(
        raw,
        label=label,
        required=frozenset({"status", "summary"}),
    )
    status = _text(raw["status"], f"{label}.status")
    if status not in _FINDING_STATUSES:
        raise DataError(f"{label}.status is unsupported")
    summary = _optional_text(raw["summary"], f"{label}.summary")
    if status != "NOT_TESTED" and summary is None:
        raise DataError(f"{label}.summary is required when the result was tested")
    return {"status": status, "summary": summary}


def _primary_result(value: object) -> dict[str, JsonValue]:
    raw = _object(value, "gate evidence primary_result")
    status = _text(raw.get("status"), "gate evidence primary_result.status")
    if status == "NOT_TESTED":
        _strict_keys(
            raw,
            label="gate evidence primary_result",
            required=frozenset({"status"}),
            optional=frozenset(
                {
                    "estimate",
                    "unit",
                    "sample_size",
                    "effective_sample_size",
                    "uncertainty",
                    "practical_magnitude",
                }
            ),
        )
        if any(raw.get(key) is not None for key in raw if key != "status"):
            raise DataError("NOT_TESTED primary_result cannot carry empirical values")
        return _not_tested_primary()
    if status != "TESTED":
        raise DataError("gate evidence primary_result.status must be TESTED or NOT_TESTED")
    _strict_keys(
        raw,
        label="gate evidence primary_result",
        required=frozenset(
            {
                "status",
                "estimate",
                "unit",
                "sample_size",
                "effective_sample_size",
                "uncertainty",
                "practical_magnitude",
            }
        ),
    )
    sample_size = _positive_int(raw["sample_size"], "gate evidence sample_size")
    effective_sample_size = _number(
        raw["effective_sample_size"], "gate evidence effective_sample_size"
    )
    if not 0.0 < effective_sample_size <= sample_size:
        raise DataError("gate evidence effective_sample_size must be in (0, sample_size]")
    uncertainty = _object(raw["uncertainty"], "gate evidence uncertainty")
    _strict_keys(
        uncertainty,
        label="gate evidence uncertainty",
        required=frozenset({"lower", "upper", "level", "method"}),
    )
    lower = _number(uncertainty["lower"], "gate evidence uncertainty.lower")
    upper = _number(uncertainty["upper"], "gate evidence uncertainty.upper")
    level = _number(uncertainty["level"], "gate evidence uncertainty.level")
    if lower > upper:
        raise DataError("gate evidence uncertainty lower cannot exceed upper")
    if not 0.0 < level < 1.0:
        raise DataError("gate evidence uncertainty level must be in (0, 1)")
    magnitude = _object(raw["practical_magnitude"], "gate evidence practical_magnitude")
    _strict_keys(
        magnitude,
        label="gate evidence practical_magnitude",
        required=frozenset({"status", "value", "unit", "interpretation"}),
    )
    magnitude_status = _text(magnitude["status"], "gate evidence practical_magnitude.status")
    if magnitude_status not in {"CLEARS_HURDLE", "BELOW_HURDLE", "INCONCLUSIVE"}:
        raise DataError("gate evidence practical_magnitude.status is unsupported")
    return {
        "status": "TESTED",
        "estimate": _number(raw["estimate"], "gate evidence estimate"),
        "unit": _text(raw["unit"], "gate evidence unit"),
        "sample_size": sample_size,
        "effective_sample_size": effective_sample_size,
        "uncertainty": {
            "lower": lower,
            "upper": upper,
            "level": level,
            "method": _text(uncertainty["method"], "gate evidence uncertainty.method"),
        },
        "practical_magnitude": {
            "status": magnitude_status,
            "value": _number(magnitude["value"], "gate evidence practical_magnitude.value"),
            "unit": _text(magnitude["unit"], "gate evidence practical_magnitude.unit"),
            "interpretation": _text(
                magnitude["interpretation"],
                "gate evidence practical_magnitude.interpretation",
            ),
        },
    }


def _artifact_link(value: object, label: str) -> dict[str, JsonValue]:
    raw = _object(value, label)
    _strict_keys(
        raw,
        label=label,
        required=frozenset({"run_id", "artifact_id", "content_sha256", "media_type"}),
    )
    digest = _text(raw["content_sha256"], f"{label}.content_sha256")
    if _SHA256.fullmatch(digest) is None:
        raise DataError(f"{label}.content_sha256 must be a lowercase SHA-256 digest")
    return {
        "run_id": _text(raw["run_id"], f"{label}.run_id"),
        "artifact_id": _text(raw["artifact_id"], f"{label}.artifact_id"),
        "content_sha256": digest,
        "media_type": _text(raw["media_type"], f"{label}.media_type"),
    }


def _evidence_artifact_reference(value: object, label: str) -> dict[str, JsonValue]:
    raw = _object(value, label)
    _strict_keys(
        raw,
        label=label,
        required=frozenset({"artifact", "content_sha256"}),
    )
    if raw["artifact"] != "research_gate_evidence.json":
        raise DataError(f"{label}.artifact must be research_gate_evidence.json")
    digest = _text(raw["content_sha256"], f"{label}.content_sha256")
    if _SHA256.fullmatch(digest) is None:
        raise DataError(f"{label}.content_sha256 must be a lowercase SHA-256 digest")
    return {"artifact": "research_gate_evidence.json", "content_sha256": digest}


def _confirmation_claim(
    raw: dict[str, JsonValue],
    primary: dict[str, JsonValue],
    classification: str,
    checks: dict[str, JsonValue],
) -> dict[str, JsonValue] | None:
    """Bind the D2 classification and check booleans to the numeric evidence.

    The producer supplies the registered claim context (direction, minimum effect, frozen
    alpha, adjusted p, and an optional invalid reason); the classification is then
    RECOMPUTED via :func:`classify_confirmation` and every check boolean is compared to
    its numeric fact.  Producer attestations that disagree with the numbers fail loud.
    A NOT_TESTED primary result has no numbers to bind, so it must not carry a claim.
    """

    if primary["status"] != "TESTED":
        if raw.get("confirmation_claim") is not None:
            raise DataError("a NOT_TESTED primary_result cannot carry a confirmation_claim")
        return None
    claim = _object(raw.get("confirmation_claim"), "D2 gate evidence confirmation_claim")
    _strict_keys(
        claim,
        label="D2 gate evidence confirmation_claim",
        required=frozenset({"direction", "minimum_effect", "adjusted_p_value", "alpha"}),
        optional=frozenset({"invalid_reason"}),
    )
    direction_text = _text(claim["direction"], "D2 confirmation_claim.direction")
    if direction_text not in {"positive", "negative"}:
        raise DataError("D2 confirmation_claim.direction must be positive or negative")
    invalid_reason = _optional_text(
        claim.get("invalid_reason"), "D2 confirmation_claim.invalid_reason"
    )
    uncertainty = cast(dict[str, JsonValue], primary["uncertainty"])
    numeric = ConfirmationEvidence(
        direction=ClaimDirection(direction_text),
        estimate=_number(primary["estimate"], "D2 confirmation_claim estimate"),
        ci_lower=_number(uncertainty["lower"], "D2 confirmation_claim ci_lower"),
        ci_upper=_number(uncertainty["upper"], "D2 confirmation_claim ci_upper"),
        adjusted_p_value=_number(
            claim["adjusted_p_value"], "D2 confirmation_claim.adjusted_p_value"
        ),
        alpha=_number(claim["alpha"], "D2 confirmation_claim.alpha"),
        minimum_effect=_number(claim["minimum_effect"], "D2 confirmation_claim.minimum_effect"),
        invalid_reason=invalid_reason,
    )
    recomputed = classify_confirmation(numeric).status.name
    if classification != recomputed:
        raise DataError(
            f"D2 confirmation_classification {classification} disagrees with the mechanical "
            f"numeric classification {recomputed}"
        )
    positive = numeric.direction is ClaimDirection.POSITIVE
    expected_booleans = {
        "corrected_primary_test_passed": numeric.adjusted_p_value <= numeric.alpha,
        "interval_registered_direction": (
            numeric.ci_lower > 0.0 if positive else numeric.ci_upper < 0.0
        ),
        "economic_hurdle_cleared": (
            numeric.ci_lower > numeric.minimum_effect
            if positive
            else numeric.ci_upper < -numeric.minimum_effect
        ),
        "interval_wholly_against_direction": (
            numeric.ci_upper < 0.0 if positive else numeric.ci_lower > 0.0
        ),
    }
    disagreements = sorted(
        name for name, expected in expected_booleans.items() if checks[name] is not expected
    )
    if disagreements:
        raise DataError(
            "D2 confirmation_checks disagree with the numeric evidence: " + ", ".join(disagreements)
        )
    return {
        "direction": direction_text,
        "minimum_effect": numeric.minimum_effect,
        "adjusted_p_value": numeric.adjusted_p_value,
        "alpha": numeric.alpha,
        "invalid_reason": invalid_reason,
    }


def _gate_evidence(value: object) -> dict[str, JsonValue]:
    raw = _object(value, "gate packet evidence")
    _strict_keys(
        raw,
        label="gate packet evidence",
        required=frozenset({"schema", "evidence_zone", "primary_result"}),
        optional=frozenset(
            {
                "confirmation_classification",
                "confirmation_claim",
                "confirmation_checks",
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
            }
        ),
    )
    if raw["schema"] != "ResearchGateEvidenceV1":
        raise DataError("gate packet evidence requires schema ResearchGateEvidenceV1")
    zone = _text(raw["evidence_zone"], "gate packet evidence.evidence_zone")
    if zone not in {"D1", "D2"}:
        raise DataError("non-synthetic gate packet evidence must identify D1 or D2")
    primary = _primary_result(raw["primary_result"])
    classification: str | None = None
    checks: dict[str, JsonValue] | None = None
    claim: dict[str, JsonValue] | None = None
    if zone == "D2":
        classification = _text(
            raw.get("confirmation_classification"),
            "D2 gate evidence confirmation_classification",
        )
        if classification not in _OUTCOMES:
            raise DataError("D2 gate evidence confirmation_classification is unsupported")
        checks_raw = _object(
            raw.get("confirmation_checks"),
            "D2 gate evidence confirmation_checks",
        )
        _strict_keys(
            checks_raw,
            label="D2 gate evidence confirmation_checks",
            required=frozenset(
                {
                    "corrected_primary_test_passed",
                    "interval_registered_direction",
                    "economic_hurdle_cleared",
                    "interval_wholly_against_direction",
                }
            ),
        )
        if not all(isinstance(value, bool) for value in checks_raw.values()):
            raise DataError("D2 gate evidence confirmation_checks must be booleans")
        checks = checks_raw
        claim = _confirmation_claim(raw, primary, classification, checks)
        supports = (
            checks["corrected_primary_test_passed"] is True
            and checks["interval_registered_direction"] is True
            and checks["economic_hurdle_cleared"] is True
            and checks["interval_wholly_against_direction"] is False
            and primary["status"] == "TESTED"
            and cast(dict[str, JsonValue], primary["practical_magnitude"])["status"]
            == "CLEARS_HURDLE"
        )
        contradicts = (
            checks["interval_wholly_against_direction"] is True
            and checks["interval_registered_direction"] is False
            and checks["economic_hurdle_cleared"] is False
            and primary["status"] == "TESTED"
            and cast(dict[str, JsonValue], primary["practical_magnitude"])["status"]
            != "CLEARS_HURDLE"
        )
        if classification == "SUPPORTED" and not supports:
            raise DataError("D2 SUPPORTED classification checks are inconsistent")
        if classification == "CONTRADICTED" and not contradicts:
            raise DataError("D2 CONTRADICTED classification checks are inconsistent")
        if classification == "INCONCLUSIVE" and (supports or contradicts):
            raise DataError("D2 INCONCLUSIVE classification checks are inconsistent")
    elif (
        "confirmation_classification" in raw
        or "confirmation_checks" in raw
        or "confirmation_claim" in raw
    ):
        raise DataError("D1 evidence cannot carry D2 confirmation classification")
    confounders = _object(raw.get("confounders", {}), "gate evidence confounders")
    _strict_keys(
        confounders,
        label="gate evidence confounders",
        required=frozenset(),
        optional=frozenset({"resolved", "unresolved"}),
    )
    stability = _object(raw.get("stability", {}), "gate evidence stability")
    _strict_keys(
        stability,
        label="gate evidence stability",
        required=frozenset(),
        optional=frozenset({"parameter", "temporal", "transportability"}),
    )
    links_raw = _array(raw.get("artifact_links", []), "gate evidence artifact_links")
    return {
        "schema": "ResearchGateEvidenceV1",
        "evidence_zone": zone,
        "confirmation_classification": classification,
        "confirmation_claim": claim,
        "confirmation_checks": checks,
        "primary_result": primary,
        "mechanism": (
            _not_tested_finding()
            if "mechanism" not in raw
            else _finding(raw["mechanism"], "gate evidence mechanism")
        ),
        "strongest_support": _optional_text(
            raw.get("strongest_support"), "gate evidence strongest_support"
        ),
        "strongest_contradiction": _optional_text(
            raw.get("strongest_contradiction"), "gate evidence strongest_contradiction"
        ),
        "confounders": {
            "resolved": _text_list(
                confounders.get("resolved", []), "gate evidence confounders.resolved"
            ),
            "unresolved": _text_list(
                confounders.get("unresolved", []), "gate evidence confounders.unresolved"
            ),
        },
        "stability": {
            key: (
                _not_tested_finding()
                if key not in stability
                else _finding(stability[key], f"gate evidence stability.{key}")
            )
            for key in ("parameter", "temporal", "transportability")
        },
        "multiplicity": (
            _not_tested_finding()
            if "multiplicity" not in raw
            else _finding(raw["multiplicity"], "gate evidence multiplicity")
        ),
        "power": (
            _not_tested_finding()
            if "power" not in raw
            else _finding(raw["power"], "gate evidence power")
        ),
        "negative_controls": (
            _not_tested_finding()
            if "negative_controls" not in raw
            else _finding(raw["negative_controls"], "gate evidence negative_controls")
        ),
        "untested_work": _text_list(raw.get("untested_work", []), "gate evidence untested_work"),
        "what_would_change_conclusion": _text_list(
            raw.get("what_would_change_conclusion", []),
            "gate evidence what_would_change_conclusion",
        ),
        "artifact_links": [
            _artifact_link(item, f"gate evidence artifact_links[{index}]")
            for index, item in enumerate(links_raw)
        ],
    }


def confirmation_classification_from_evidence(
    evidence: Mapping[str, object],
) -> ResearchOutcome:
    """Validate one exact D2 evidence summary and return its mechanical classification."""
    parsed = _gate_evidence(evidence)
    if parsed["evidence_zone"] != "D2":
        raise DataError("confirmation classification requires D2 evidence")
    return cast(ResearchOutcome, parsed["confirmation_classification"])


def _validated_attempts(
    attempts: list[dict[str, JsonValue]],
    *,
    project_id: str,
    lineage_ids: list[str],
) -> tuple[list[dict[str, JsonValue]], list[tuple[dict[str, JsonValue], dict[str, JsonValue]]]]:
    seen: set[str] = set()
    evidence: list[tuple[dict[str, JsonValue], dict[str, JsonValue]]] = []
    for index, attempt in enumerate(attempts):
        label = f"research attempt ledger[{index}]"
        attempt_id = _text(attempt.get("attempt_id"), f"{label}.attempt_id")
        if attempt_id in seen:
            raise DataError(f"duplicate research attempt_id {attempt_id!r}")
        seen.add(attempt_id)
        if attempt.get("project_id") != project_id:
            raise DataError(f"{label} belongs to another project")
        contract_id = _text(attempt.get("contract_id"), f"{label}.contract_id")
        if contract_id not in lineage_ids:
            raise DataError(f"{label} belongs to a contract outside the active lineage")
        status = _text(attempt.get("status"), f"{label}.status")
        if status not in _ATTEMPT_STATUSES:
            raise DataError(f"{label}.status is unsupported")
        _text(attempt.get("phase"), f"{label}.phase")
        _text(attempt.get("kind"), f"{label}.kind")
        _text(attempt.get("config_fingerprint"), f"{label}.config_fingerprint")
        budget = _object(attempt.get("budget_used"), f"{label}.budget_used")
        for key, value in budget.items():
            amount = _number(value, f"{label}.budget_used.{key}")
            if amount < 0:
                raise DataError(f"{label}.budget_used.{key} must be non-negative")
        details = _object(attempt.get("details"), f"{label}.details")
        raw_evidence = details.get("gate_packet_evidence")
        if raw_evidence is None:
            continue
        candidate = _object(raw_evidence, f"{label}.details.gate_packet_evidence")
        inner_zone = candidate.get("evidence_zone")
        outer_zone = details.get("evidence_zone")
        if inner_zone == "D0" or outer_zone == "D0":
            if outer_zone not in {None, "D0"} or inner_zone != "D0":
                raise DataError(f"{label} has conflicting evidence-zone labels")
            continue
        parsed = _gate_evidence(candidate)
        zone = cast(str, parsed["evidence_zone"])
        reference = details.get("gate_packet_evidence_ref")
        if reference is None:
            raise DataError(f"{label} empirical evidence requires an immutable artifact selector")
        _evidence_artifact_reference(reference, f"{label}.details.gate_packet_evidence_ref")
        if outer_zone is not None and outer_zone != zone:
            raise DataError(f"{label} has conflicting evidence-zone labels")
        if status != "completed" or attempt.get("run_id") is None:
            raise DataError(f"{label} empirical packet evidence requires a completed immutable run")
        phase = cast(str, attempt["phase"])
        if zone == "D2" and phase != "sealed_confirmation":
            raise DataError("D2 packet evidence must come from sealed_confirmation")
        if zone == "D1" and phase not in {"pilot", "deep_research"}:
            raise DataError("D1 packet evidence must come from pilot or deep_research")
        for link in cast(list[dict[str, JsonValue]], parsed["artifact_links"]):
            if link["run_id"] != attempt["run_id"]:
                raise DataError("gate evidence artifact link must bind its attempt run_id")
        evidence.append((attempt, parsed))
    if sum(1 for _, item in evidence if item["evidence_zone"] == "D2") > 1:
        raise DataError("ResearchGatePacket permits only one typed D2 evidence result")
    return attempts, evidence


def _validated_launch_ledger(
    reservations: list[dict[str, JsonValue]],
    links: list[dict[str, JsonValue]],
    attempts: list[dict[str, JsonValue]],
    *,
    project_id: str,
    lineage_ids: list[str],
) -> tuple[list[dict[str, JsonValue]], list[dict[str, JsonValue]]]:
    reservation_ids: set[str] = set()
    for index, reservation in enumerate(reservations):
        label = f"research launch reservation ledger[{index}]"
        reservation_id = _text(reservation.get("reservation_id"), f"{label}.reservation_id")
        if reservation_id in reservation_ids:
            raise DataError(f"duplicate research reservation_id {reservation_id!r}")
        reservation_ids.add(reservation_id)
        if reservation.get("project_id") != project_id:
            raise DataError(f"{label} belongs to another project")
        contract_id = _text(reservation.get("contract_id"), f"{label}.contract_id")
        if contract_id not in lineage_ids:
            raise DataError(f"{label} belongs to a contract outside the active lineage")
        _text(reservation.get("phase"), f"{label}.phase")
        _text(reservation.get("kind"), f"{label}.kind")
        _text(reservation.get("config_fingerprint"), f"{label}.config_fingerprint")
        _positive_int(reservation.get("launch_number"), f"{label}.launch_number")
        _positive_int(reservation.get("execution_sequence"), f"{label}.execution_sequence")
        budget = _object(reservation.get("budget_reserved"), f"{label}.budget_reserved")
        for key, value in budget.items():
            if _number(value, f"{label}.budget_reserved.{key}") < 0:
                raise DataError(f"{label}.budget_reserved.{key} must be non-negative")

    attempt_by_id = {
        _text(attempt.get("attempt_id"), "research attempt ledger attempt_id"): attempt
        for attempt in attempts
    }
    linked_reservations: set[str] = set()
    linked_attempts: set[str] = set()
    for index, link in enumerate(links):
        label = f"research launch terminal-link ledger[{index}]"
        reservation_id = _text(link.get("reservation_id"), f"{label}.reservation_id")
        attempt_id = _text(link.get("attempt_id"), f"{label}.attempt_id")
        if reservation_id not in reservation_ids or attempt_id not in attempt_by_id:
            raise DataError(f"{label} references a launch or attempt outside the packet")
        if reservation_id in linked_reservations or attempt_id in linked_attempts:
            raise DataError(f"{label} violates one-to-one terminal launch linkage")
        linked_reservations.add(reservation_id)
        linked_attempts.add(attempt_id)
        if attempt_by_id[attempt_id].get("launch_reservation_id") != reservation_id:
            raise DataError(f"{label} disagrees with its terminal attempt")
    for attempt_id, attempt in attempt_by_id.items():
        attempt_reservation_id = attempt.get("launch_reservation_id")
        if attempt_reservation_id is not None and not isinstance(attempt_reservation_id, str):
            raise DataError("research attempt launch_reservation_id must be text")
        if attempt_reservation_id is not None and attempt_id not in linked_attempts:
            raise DataError("research attempt declares a missing launch terminal link")
    return reservations, links


def _budget(
    contracts: list[dict[str, JsonValue]],
    attempts: list[dict[str, JsonValue]],
    reservations: list[dict[str, JsonValue]],
) -> list[dict[str, JsonValue]]:
    result: list[dict[str, JsonValue]] = []
    for index, contract in enumerate(contracts):
        contract_id = _text(contract.get("contract_id"), f"research contract[{index}].contract_id")
        payload = _object(contract.get("payload"), f"research contract[{index}].payload")
        approved = _object(payload.get("budget", {}), f"research contract[{index}].budget")
        approved_numbers: dict[str, float | int] = {}
        used_numbers: dict[str, float | int] = {}
        for key, value in approved.items():
            amount = _number(value, f"research contract[{index}].budget.{key}")
            if amount < 0:
                raise DataError("research contract budget values must be non-negative")
            approved_numbers[key] = cast(float | int, value)
            used_numbers[key] = 0
        for reservation in reservations:
            if reservation["contract_id"] != contract_id:
                continue
            reserved_budget = cast(dict[str, JsonValue], reservation["budget_reserved"])
            for key, value in reserved_budget.items():
                if key not in approved_numbers:
                    raise DataError(f"research launch uses undeclared budget dimension {key!r}")
                used_numbers[key] += cast(float | int, value)
        for attempt in attempts:
            if attempt["contract_id"] != contract_id:
                continue
            if attempt.get("launch_reservation_id") is not None:
                continue
            attempt_budget = cast(dict[str, JsonValue], attempt["budget_used"])
            for key, value in attempt_budget.items():
                if key not in approved_numbers:
                    raise DataError(f"research attempt uses undeclared budget dimension {key!r}")
                used_numbers[key] += cast(float | int, value)
        remaining: dict[str, float | int] = {}
        for key, limit in approved_numbers.items():
            used = used_numbers[key]
            if used > limit:
                raise DataError(f"research attempt ledger exceeds approved {key!r} budget")
            remaining[key] = limit - used
        result.append(
            {
                "contract_id": contract_id,
                "approved": dict(sorted(approved_numbers.items())),
                "used": dict(sorted(used_numbers.items())),
                "remaining": dict(sorted(remaining.items())),
                "status": "WITHIN_BUDGET",
            }
        )
    return result


def _variants(
    contracts: list[dict[str, JsonValue]], attempts: list[dict[str, JsonValue]]
) -> list[dict[str, JsonValue]]:
    result: list[dict[str, JsonValue]] = []
    for index, contract in enumerate(contracts):
        contract_id = _text(contract.get("contract_id"), f"research contract[{index}].contract_id")
        scope = _text(contract.get("scope"), f"research contract[{index}].scope")
        if scope not in {"exploration", "confirmation"}:
            raise DataError(f"research contract[{index}].scope is unsupported")
        payload = _object(contract.get("payload"), f"research contract[{index}].payload")
        protocol = payload.get("protocol")
        family: JsonValue = None
        if isinstance(protocol, dict):
            family = protocol.get("complete_variant_family")
        confirmation = payload.get("confirmation")
        result.append(
            {
                "contract_id": contract_id,
                "scope": scope,
                "declared_family_status": (
                    "DECLARED" if isinstance(family, dict) else "NOT_DECLARED"
                ),
                "declared_family": family if isinstance(family, dict) else None,
                "confirmation_family": confirmation if isinstance(confirmation, dict) else None,
                "attempted_config_fingerprints": [
                    cast(str, attempt["config_fingerprint"])
                    for attempt in attempts
                    if attempt["contract_id"] == contract_id
                ],
            }
        )
    return result


def _contract_confounders(payload: dict[str, JsonValue]) -> list[str]:
    protocol = payload.get("protocol")
    if not isinstance(protocol, dict):
        return []
    raw = protocol.get("confounders", [])
    return _text_list(raw, "research contract protocol.confounders")


def _artifact_links(
    attempts: list[dict[str, JsonValue]],
    evidence: list[tuple[dict[str, JsonValue], dict[str, JsonValue]]],
) -> list[dict[str, JsonValue]]:
    result: list[dict[str, JsonValue]] = []
    for attempt in attempts:
        run_id = attempt.get("run_id")
        if run_id is None:
            continue
        details = cast(dict[str, JsonValue], attempt["details"])
        zone = details.get("evidence_zone")
        real_market = details.get("real_market_evidence")
        if real_market is not None and not isinstance(real_market, bool):
            raise DataError("research attempt real_market_evidence must be boolean when present")
        result.append(
            {
                "attempt_id": attempt["attempt_id"],
                "run_id": _text(run_id, "research attempt run_id"),
                "artifact_id": None,
                "content_sha256": None,
                "media_type": None,
                "contract_id": attempt["contract_id"],
                "phase": attempt["phase"],
                "kind": attempt["kind"],
                "status": attempt["status"],
                "evidence_zone": zone if isinstance(zone, str) else None,
                "real_market_evidence": real_market,
                "selector_status": "IMMUTABLE_RUN_ID",
            }
        )
        reference = details.get("gate_packet_evidence_ref")
        if reference is not None:
            parsed_reference = _evidence_artifact_reference(
                reference,
                "research attempt gate_packet_evidence_ref",
            )
            result.append(
                {
                    "attempt_id": attempt["attempt_id"],
                    "run_id": _text(run_id, "research attempt run_id"),
                    "artifact_id": parsed_reference["artifact"],
                    "content_sha256": parsed_reference["content_sha256"],
                    "media_type": "application/json",
                    "contract_id": attempt["contract_id"],
                    "phase": attempt["phase"],
                    "kind": attempt["kind"],
                    "status": attempt["status"],
                    "evidence_zone": zone if isinstance(zone, str) else None,
                    "real_market_evidence": real_market,
                    "selector_status": "CONTENT_HASHED_RESULT_ARTIFACT",
                }
            )
    for attempt, item in evidence:
        for link in cast(list[dict[str, JsonValue]], item["artifact_links"]):
            result.append(
                {
                    "attempt_id": attempt["attempt_id"],
                    **link,
                    "contract_id": attempt["contract_id"],
                    "phase": attempt["phase"],
                    "kind": attempt["kind"],
                    "status": attempt["status"],
                    "evidence_zone": item["evidence_zone"],
                    "real_market_evidence": True,
                    "selector_status": "CONTENT_HASHED_ARTIFACT",
                }
            )
    return result


def _outcome_answer(outcome: str) -> str:
    return {
        "SUPPORTED": "The owner-recorded outcome supports the exact frozen predictive claim.",
        "CONTRADICTED": "The owner-recorded outcome contradicts the exact frozen predictive claim.",
        "INCONCLUSIVE": (
            "The owner-recorded outcome does not resolve the exact frozen predictive claim."
        ),
        "INVALID": "The owner-recorded outcome says this lineage cannot answer the frozen claim.",
    }[outcome]


@dataclass(frozen=True, slots=True)
class ResearchGatePacket:
    """Immutable content-addressed terminal packet."""

    _body_json: bytes
    packet_hash: str

    @property
    def packet_id(self) -> str:
        return f"rgp_{self.packet_hash}"

    def to_dict(self) -> dict[str, object]:
        body = cast(dict[str, object], json.loads(self._body_json))
        return {
            "packet_id": self.packet_id,
            "packet_hash": self.packet_hash,
            **body,
        }

    def to_json_bytes(self) -> bytes:
        return _canonical_json_bytes(self.to_dict())


def build_research_gate_packet(inputs: Mapping[str, object]) -> ResearchGatePacket:
    """Validate bounded authority inputs and build a deterministic terminal packet."""
    root = _object(inputs, "research gate packet inputs")
    if root.get("schema_version") != 1:
        raise DataError("research gate packet inputs require schema_version 1")
    if root.get("phase") != "closed":
        raise DataError("ResearchGatePacket can only be emitted for a closed research case")

    project = _object(root.get("project"), "research gate packet project")
    project_id = _text(project.get("project_id"), "research gate packet project_id")
    project_name = _text(project.get("name"), "research gate packet project name")
    active_contract_id = _text(
        root.get("active_contract_id"), "research gate packet active_contract_id"
    )
    lineage_ids = _text_list(
        root.get("lineage_contract_ids"), "research gate packet lineage_contract_ids"
    )
    if len(lineage_ids) != len(set(lineage_ids)) or active_contract_id not in lineage_ids:
        raise DataError("research gate packet active contract must appear once in its lineage")

    contracts = _ledger(root, "contracts")
    contract_ids = [
        _text(item.get("contract_id"), f"research contract[{index}].contract_id")
        for index, item in enumerate(contracts)
    ]
    if contract_ids != lineage_ids:
        raise DataError("research gate packet contracts must exactly match lineage_contract_ids")
    for index, contract in enumerate(contracts):
        if contract.get("project_id") != project_id:
            raise DataError(f"research contract[{index}] belongs to another project")
    active_contract = contracts[contract_ids.index(active_contract_id)]
    active_payload = _object(active_contract.get("payload"), "active research contract payload")

    sources = _ledger(root, "sources")
    source_packs = _ledger(root, "source_packs")
    attempts = _ledger(root, "attempts")
    launch_reservations = (
        [] if root.get("launch_reservations") is None else _ledger(root, "launch_reservations")
    )
    launch_attempt_links = (
        [] if root.get("launch_attempt_links") is None else _ledger(root, "launch_attempt_links")
    )
    phase_events = _ledger(root, "phase_events")
    review_events = _ledger(root, "review_events")
    execution_events = _ledger(root, "execution_events")
    d2_events = _ledger(root, "d2_events")
    decision_events = _ledger(root, "decision_events")
    if not decision_events:
        raise DataError("closed ResearchGatePacket requires an owner decision")
    decision = decision_events[-1]
    if decision.get("actor_kind") != "human":
        raise DataError("closed ResearchGatePacket requires a human owner decision")
    if decision.get("contract_id") != active_contract_id:
        raise DataError("closed ResearchGatePacket owner decision must bind the active contract")
    if decision.get("project_id") != project_id:
        raise DataError("closed ResearchGatePacket owner decision belongs to another project")
    outcome = _text(decision.get("outcome"), "research decision outcome")
    disposition = _text(decision.get("disposition"), "research decision disposition")
    if outcome not in _OUTCOMES:
        raise DataError("research decision outcome is unsupported")
    if disposition not in _DISPOSITIONS:
        raise DataError("research decision disposition is unsupported")
    if disposition == "advance_to_strategy" and outcome != "SUPPORTED":
        raise DataError("only a SUPPORTED outcome may recommend advance_to_strategy")
    owner_reason = _text(decision.get("reason"), "research decision reason")

    for label, rows, id_key in (
        ("source", sources, "source_id"),
        ("source pack", source_packs, "pack_id"),
    ):
        seen: set[str] = set()
        for index, item in enumerate(rows):
            identifier = _text(item.get(id_key), f"research {label}[{index}].{id_key}")
            if identifier in seen:
                raise DataError(f"duplicate research {id_key} {identifier!r}")
            seen.add(identifier)
            if item.get("project_id") != project_id:
                raise DataError(f"research {label}[{index}] belongs to another project")

    attempts, evidence_records = _validated_attempts(
        attempts,
        project_id=project_id,
        lineage_ids=lineage_ids,
    )
    launch_reservations, launch_attempt_links = _validated_launch_ledger(
        launch_reservations,
        launch_attempt_links,
        attempts,
        project_id=project_id,
        lineage_ids=lineage_ids,
    )
    selected: dict[str, JsonValue] | None = None
    selected_attempt: dict[str, JsonValue] | None = None
    d2_evidence = [
        (attempt, item) for attempt, item in evidence_records if item["evidence_zone"] == "D2"
    ]
    d1_evidence = [
        (attempt, item) for attempt, item in evidence_records if item["evidence_zone"] == "D1"
    ]
    if d2_evidence:
        selected_attempt, selected = d2_evidence[-1]
        if selected_attempt["contract_id"] != active_contract_id:
            raise DataError("D2 packet evidence must bind the active confirmation contract")
        if (
            not d2_events
            or d2_events[-1].get("state") != "consumed"
            or d2_events[-1].get("contract_id") != active_contract_id
        ):
            raise DataError("SEALED_D2 packet evidence requires consumed active-contract D2 state")
        if selected["confirmation_classification"] != outcome:
            raise DataError("D2 confirmation classification does not match the owner outcome")
        evidence_basis = "SEALED_D2"
    elif d1_evidence:
        selected_attempt, selected = d1_evidence[-1]
        evidence_basis = "EXPLORATORY_D1"
    else:
        evidence_basis = "NO_TYPED_NON_SYNTHETIC_EVIDENCE"
    if (outcome == "SUPPORTED" or disposition == "advance_to_strategy") and (
        evidence_basis != "SEALED_D2"
    ):
        raise DataError(
            "SUPPORTED or advance_to_strategy requires one typed SEALED_D2 evidence result"
        )
    if outcome == "CONTRADICTED" and evidence_basis == "NO_TYPED_NON_SYNTHETIC_EVIDENCE":
        raise DataError(
            "CONTRADICTED requires a lineage-bound typed non-synthetic falsifier or result"
        )

    primary = (
        _not_tested_primary()
        if selected is None
        else cast(dict[str, JsonValue], selected["primary_result"])
    )
    proposed_mechanism = _proposed_mechanism(active_payload)
    mechanism = (
        _not_tested_finding(
            None if proposed_mechanism is None else f"Proposed mechanism only: {proposed_mechanism}"
        )
        if selected is None
        else cast(dict[str, JsonValue], selected["mechanism"])
    )
    confounders: dict[str, JsonValue]
    stability: dict[str, JsonValue]
    if selected is None:
        strongest_support = _not_tested_finding()
        strongest_contradiction = _not_tested_finding()
        confounders = {
            "resolved": [],
            "unresolved": _contract_confounders(active_payload),
        }
        stability = {
            "parameter": _not_tested_finding(),
            "temporal": _not_tested_finding(),
            "transportability": _not_tested_finding(),
        }
        multiplicity = _not_tested_finding()
        power = _not_tested_finding()
        negative_controls = _not_tested_finding()
        untested_work = ["No typed D1 or D2 empirical result is present."]
        what_changes: list[str] = []
    else:
        support = cast(str | None, selected["strongest_support"])
        contradiction = cast(str | None, selected["strongest_contradiction"])
        strongest_support = (
            _not_tested_finding() if support is None else {"status": "OBSERVED", "summary": support}
        )
        strongest_contradiction = (
            _not_tested_finding()
            if contradiction is None
            else {"status": "OBSERVED", "summary": contradiction}
        )
        confounders = cast(dict[str, JsonValue], selected["confounders"])
        stability = cast(dict[str, JsonValue], selected["stability"])
        multiplicity = cast(dict[str, JsonValue], selected["multiplicity"])
        power = cast(dict[str, JsonValue], selected["power"])
        negative_controls = cast(dict[str, JsonValue], selected["negative_controls"])
        untested_work = cast(list[str], selected["untested_work"])
        what_changes = cast(list[str], selected["what_would_change_conclusion"])

    has_d0 = any(
        isinstance(attempt.get("details"), dict)
        and cast(dict[str, JsonValue], attempt["details"]).get("evidence_zone") == "D0"
        for attempt in attempts
    )
    if evidence_basis == "NO_TYPED_NON_SYNTHETIC_EVIDENCE":
        caveat = (
            "D0 validates implementation only; it is synthetic and cannot support a market "
            "claim. No typed D1 or D2 empirical result is present."
            if has_d0
            else "No typed D1 or D2 empirical result is present; the recorded outcome is not "
            "independently reconstructed by this packet."
        )
    elif evidence_basis == "EXPLORATORY_D1":
        caveat = "D1 is exploratory and cannot confirm the claim or authorize strategy advancement."
        if "Sealed D2 confirmation" not in untested_work:
            untested_work.append("Sealed D2 confirmation")
    else:
        caveat = (
            "This is point-in-time predictive-association evidence, not causal proof and not a "
            "validated, paper-ready, or profitable strategy."
        )
    if not what_changes:
        falsifier = project.get("falsification_criterion")
        if isinstance(falsifier, str) and falsifier.strip():
            what_changes.append(falsifier)
        what_changes.append(
            "A preregistered non-overlapping future or defensibly independent replication that "
            "conflicts with the recorded outcome."
        )

    artifact_links = _artifact_links(attempts, evidence_records)
    variant_ledger = _variants(contracts, attempts)
    budget_ledger = _budget(contracts, attempts, launch_reservations)
    claim = _claim(active_payload, project)
    practical = cast(dict[str, JsonValue], primary["practical_magnitude"])
    body: dict[str, JsonValue] = {
        "report_schema": "ResearchGatePacketV1",
        "schema_version": 1,
        "terminal": True,
        "project_id": project_id,
        "active_contract_id": active_contract_id,
        "scientific_outcome": outcome,
        "recommended_disposition": disposition,
        "authority": {
            "evidence_claim": "point-in-time-valid predictive association",
            "strategy_validated": False,
            "paper_ready": False,
            "places_orders": False,
            "uses_final_strategy_holdout": False,
        },
        "layers": {
            "conclusion_90_seconds": {
                "project_name": project_name,
                "thesis": claim,
                "thesis_answer": _outcome_answer(outcome),
                "scientific_outcome": outcome,
                "recommended_disposition": disposition,
                "owner_decision_reason": owner_reason,
                "evidence_basis": evidence_basis,
                "primary_estimate": primary["estimate"],
                "uncertainty": primary["uncertainty"],
                "effective_sample_size": primary["effective_sample_size"],
                "practical_magnitude": practical,
                "strongest_caveat": caveat,
            },
            "guided_evidence": {
                "primary_result": primary,
                "mechanism": mechanism,
                "strongest_support": strongest_support,
                "strongest_contradiction": strongest_contradiction,
                "confounders": confounders,
                "stability": stability,
                "multiplicity": multiplicity,
                "power": power,
                "negative_controls": negative_controls,
                "confirmation_classification": (
                    None if selected is None else selected["confirmation_classification"]
                ),
                "confirmation_checks": (
                    None if selected is None else selected["confirmation_checks"]
                ),
                "untested_work": untested_work,
                "what_would_change_conclusion": what_changes,
                "teaching_note": caveat,
            },
            "technical_appendix": {
                "project": project,
                "contract_lineage": contracts,
                "source_pack_ledger": source_packs,
                "source_ledger": sources,
                "variant_ledger": variant_ledger,
                "attempt_ledger": attempts,
                "launch_reservation_ledger": launch_reservations,
                "launch_attempt_link_ledger": launch_attempt_links,
                "budget_ledger": budget_ledger,
                "phase_review_d2_ledgers": {
                    "phase_events": phase_events,
                    "review_events": review_events,
                    "execution_events": execution_events,
                    "d2_events": d2_events,
                    "decision_events": decision_events,
                },
                "immutable_artifact_links": artifact_links,
                "selected_evidence": (
                    None
                    if selected is None or selected_attempt is None
                    else {
                        "attempt_id": selected_attempt["attempt_id"],
                        "run_id": selected_attempt["run_id"],
                        "contract_id": selected_attempt["contract_id"],
                        "evidence_zone": selected["evidence_zone"],
                    }
                ),
                "ledger_bounds": {
                    "maximum_rows_per_input_ledger": _MAX_LEDGER_ROWS,
                    "truncated": False,
                    "counts": {
                        "contracts": len(contracts),
                        "source_packs": len(source_packs),
                        "sources": len(sources),
                        "attempts": len(attempts),
                        "launch_reservations": len(launch_reservations),
                        "launch_attempt_links": len(launch_attempt_links),
                        "phase_events": len(phase_events),
                        "review_events": len(review_events),
                        "execution_events": len(execution_events),
                        "d2_events": len(d2_events),
                        "decision_events": len(decision_events),
                        "artifact_links": len(artifact_links),
                    },
                },
            },
        },
    }
    body_json = _canonical_json_bytes(body)
    return ResearchGatePacket(
        _body_json=body_json,
        packet_hash=hashlib.sha256(body_json).hexdigest(),
    )


__all__ = [
    "ResearchDisposition",
    "ResearchGatePacket",
    "ResearchOutcome",
    "build_research_gate_packet",
    "confirmation_classification_from_evidence",
]
