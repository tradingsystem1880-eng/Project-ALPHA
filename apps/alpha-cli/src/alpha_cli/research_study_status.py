"""CLI-owned projection of semantic review and existing D1 research authority."""

from __future__ import annotations

from collections.abc import Mapping

from alpha_cli.control_store import ControlStore, research_case_revision
from alpha_core import DataError


def _event_view(event: Mapping[str, object]) -> dict[str, object]:
    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        raise DataError("semantic event payload is corrupt")
    return {
        "event_id": event["event_id"],
        "artifact_id": event["semantic_artifact_id"],
        "receipt_id": event["receipt_id"],
        "actor": event["actor"],
        "reason": event["reason"],
        "recorded_at": event["recorded_at"],
        "payload": dict(payload),
    }


_SEMANTIC_SOURCE_VIEW_FIELDS = (
    "case_contract_id",
    "case_revision",
    "verified_read_sha256",
    "projection_sha256",
    "run_id",
    "cutoff_confirmed_at",
)


def _semantic_view(
    store: ControlStore,
    project_id: str,
    *,
    summary: Mapping[str, object],
) -> dict[str, object]:
    events, head_sha256 = store.read_semantic_state(project_id)
    definition_index = max(
        (index for index, event in enumerate(events) if event.get("event_type") == "definition"),
        default=-1,
    )
    cycle = events[definition_index:] if definition_index >= 0 else []
    definition_source = None if not cycle else cycle[0]
    current_contract_id = summary.get("active_contract_id")
    current_revision = research_case_revision(summary)
    source_state = "not_recorded"
    if definition_source is not None:
        source_state = (
            "current"
            if definition_source.get("case_contract_id") == current_contract_id
            and definition_source.get("case_revision") == current_revision
            else "stale"
        )
    if source_state == "stale":
        cycle = []
    definitions = [event for event in cycle if event.get("event_type") == "definition"]
    reviews = [event for event in cycle if event.get("event_type") == "review"]
    freezes = [event for event in cycle if event.get("event_type") == "freeze"]
    if source_state == "stale":
        state = "stale"
    elif not events or (
        events[-1].get("event_type") == "review" and events[-1].get("review_decision") == "reject"
    ):
        state = "definition_required"
    elif events[-1].get("event_type") == "freeze":
        state = "frozen"
    elif events[-1].get("event_type") == "definition":
        state = "review_required"
    else:
        state = "freeze_required"
    next_actions = {
        "definition_required": "Record a semantic definition with fresh Touch ID.",
        "review_required": "Review the semantic definition with fresh Touch ID.",
        "freeze_required": "Freeze the approved semantic definition with fresh Touch ID.",
        "frozen": "The reviewed semantic definition is frozen; continue through owner CLI.",
        "stale": (
            "The prior semantic cycle is bound to an older case revision; refresh and obtain "
            "owner review before recording another semantic action."
        ),
    }
    source = {
        field: definition_source.get(field) if definition_source is not None else None
        for field in _SEMANTIC_SOURCE_VIEW_FIELDS
    }
    return {
        "state": state,
        "source_state": source_state,
        **source,
        "event_count": len(events),
        "head_sha256": head_sha256,
        "definition": None if not definitions else _event_view(definitions[-1]),
        "review": None if not reviews else _event_view(reviews[-1]),
        "freeze": None if not freezes else _event_view(freezes[-1]),
        "next_owner_action": next_actions[state],
    }


def _d1_status(summary: Mapping[str, object], attempts: list[dict[str, object]]) -> str:
    execution_state = str(summary.get("execution_state", ""))
    checkpoint = summary.get("checkpoint")
    has_d1_context = summary.get("phase") == "deep_research" or (
        isinstance(checkpoint, str) and checkpoint.startswith("d1:")
    )
    if has_d1_context and execution_state in {
        "queued",
        "running",
        "paused",
        "blocked",
        "failed",
    }:
        return execution_state
    return "not_started" if not attempts else str(attempts[-1]["status"])


def research_study_status(
    store: ControlStore,
    project_id: str,
    *,
    summary: Mapping[str, object],
) -> dict[str, object]:
    """Return a non-authoritative view over verified semantic and research records."""

    inputs = store.research_gate_packet_inputs(project_id)
    raw_attempts = inputs.get("attempts")
    attempts = (
        [
            {
                "attempt_id": attempt["attempt_id"],
                "contract_id": attempt["contract_id"],
                "status": attempt["status"],
                "run_id": attempt.get("run_id"),
                "recorded_at": attempt["recorded_at"],
            }
            for attempt in raw_attempts
            if isinstance(attempt, Mapping) and attempt.get("kind") == "d1-deep-research"
        ]
        if isinstance(raw_attempts, list)
        else []
    )
    d1_status = _d1_status(summary, attempts)
    active_contract_id = summary.get("active_contract_id")
    if not isinstance(active_contract_id, str):
        raise DataError("research status has no active contract")
    promotion = store.research_promotion_reference(project_id, active_contract_id)
    return {
        "schema": "ResearchStudyStatusV1",
        "schema_version": 1,
        "authority": "none",
        "project_id": project_id,
        "active_contract_id": active_contract_id,
        "semantic": _semantic_view(store, project_id, summary=summary),
        "d1": {
            "launch_authority": "owner_cli_only",
            "status": d1_status,
            "attempts": attempts,
            "elapsed_budget": summary.get("elapsed_budget", {}),
            "remaining_budget": summary.get("remaining_budget", {}),
        },
        "promotion": {
            "packet_id": None if promotion is None else promotion["packet_id"],
            "readiness": summary.get("promotion_readiness"),
        },
        "next_action": summary.get("next_action"),
        "responsibility": summary.get("responsibility"),
    }
