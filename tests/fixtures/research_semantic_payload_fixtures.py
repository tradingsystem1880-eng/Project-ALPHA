"""Shared public semantic-payload constructors with fixed test inputs."""

from __future__ import annotations

PROJECT_ID = "9e4908b1-a9cd-4c13-a47e-740d92175680"


def _semantic_source() -> dict[str, object]:
    return {
        "project_id": PROJECT_ID,
        "case_contract_id": "rc_" + "1" * 64,
        "source_contract_id": "rc_" + "2" * 64,
        "case_revision": "a" * 64,
        "verified_read_sha256": "b" * 64,
        "projection_sha256": "c" * 64,
        "run_id": "0123456789abcdef",
        "cutoff_confirmed_at": "2026-08-13T00:00:00.000000Z",
    }


def _semantic_definition_payload(source: dict[str, object], head: str) -> dict[str, object]:
    return {
        "schema": "SemanticOwnerActionV1",
        "schema_version": 1,
        "event_type": "definition",
        "verified_read_sha256": source["verified_read_sha256"],
        "projection_sha256": source["projection_sha256"],
        "run_id": source["run_id"],
        "cutoff_confirmed_at": source["cutoff_confirmed_at"],
        "expected_semantic_head_sha256": head,
        "definition_label": "Test definition",
        "definition_text": "A bounded semantic definition.",
    }


def _semantic_review_payload(
    source: dict[str, object], head: str, definition_id: str, decision: str
) -> dict[str, object]:
    return {
        "schema": "SemanticOwnerActionV1",
        "schema_version": 1,
        "event_type": "review",
        "verified_read_sha256": source["verified_read_sha256"],
        "projection_sha256": source["projection_sha256"],
        "run_id": source["run_id"],
        "cutoff_confirmed_at": source["cutoff_confirmed_at"],
        "expected_semantic_head_sha256": head,
        "definition_id": definition_id,
        "review_decision": decision,
        "review_text": "Review the bounded semantic definition.",
    }
