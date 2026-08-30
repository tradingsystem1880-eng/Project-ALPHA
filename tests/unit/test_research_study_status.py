from __future__ import annotations

from typing import cast

import pytest

from alpha_cli.control_store import ControlStore, research_case_revision
from alpha_cli.research_study_status import _d1_status, _semantic_view

PROJECT_ID = "00000000-0000-4000-8000-000000000001"
CONTRACT_ID = f"rc_{'a' * 64}"


def _summary(**updates: object) -> dict[str, object]:
    summary: dict[str, object] = {
        "project_id": PROJECT_ID,
        "active_contract_id": CONTRACT_ID,
        "phase": "deep_research",
        "execution_state": "idle",
        "source_pack_id": None,
        "checkpoint": "d1:complete",
    }
    summary.update(updates)
    return summary


def _event(sequence: int, kind: str, decision: str | None = None) -> dict[str, object]:
    suffix = f"{sequence:064x}"
    return {
        "event_id": f"se_{suffix}",
        "event_sha256": suffix,
        "event_type": kind,
        "semantic_artifact_id": f"s{kind[0]}_{suffix}",
        "receipt_id": f"receipt-{sequence}",
        "actor": "owner",
        "reason": f"record {kind}",
        "recorded_at": f"2026-08-30T00:00:0{sequence}Z",
        "review_decision": decision,
        "payload": {"event_type": kind},
        "case_contract_id": CONTRACT_ID,
        "case_revision": research_case_revision(_summary()),
        "verified_read_sha256": "b" * 64,
        "projection_sha256": "c" * 64,
        "run_id": "0123456789abcdef",
        "cutoff_confirmed_at": "2026-08-30T00:00:00Z",
    }


class _Store:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self.events = events

    def read_semantic_state(self, _project_id: str) -> tuple[list[dict[str, object]], str]:
        head_sha256 = "0" * 64 if not self.events else str(self.events[-1]["event_sha256"])
        return self.events, head_sha256


def test_semantic_state_tracks_only_the_current_definition_cycle() -> None:
    old_definition = _event(1, "definition")
    old_review = _event(2, "review", "approve")
    old_freeze = _event(3, "freeze")
    new_definition = _event(4, "definition")
    store = cast(ControlStore, _Store([old_definition, old_review, old_freeze, new_definition]))

    view = _semantic_view(store, PROJECT_ID, summary=_summary())

    assert view["state"] == "review_required"
    assert view["event_count"] == 4
    assert view["definition"] == {
        "event_id": new_definition["event_id"],
        "artifact_id": new_definition["semantic_artifact_id"],
        "receipt_id": new_definition["receipt_id"],
        "actor": "owner",
        "reason": "record definition",
        "recorded_at": new_definition["recorded_at"],
        "payload": {"event_type": "definition"},
    }
    assert view["review"] is None
    assert view["freeze"] is None


def test_rejected_review_requires_a_new_definition_and_never_projects_old_freeze() -> None:
    events = [
        _event(1, "definition"),
        _event(2, "review", "approve"),
        _event(3, "freeze"),
        _event(4, "definition"),
        _event(5, "review", "reject"),
    ]
    store = cast(ControlStore, _Store(events))

    view = _semantic_view(store, PROJECT_ID, summary=_summary())

    assert view["state"] == "definition_required"
    assert view["definition"] is not None
    assert view["review"] is not None
    assert view["freeze"] is None


def test_semantic_state_never_projects_a_cycle_from_an_older_case_revision() -> None:
    frozen = [_event(1, "definition"), _event(2, "review", "approve"), _event(3, "freeze")]
    store = cast(ControlStore, _Store(frozen))

    view = _semantic_view(
        store,
        PROJECT_ID,
        summary=_summary(execution_state="running", checkpoint="d1:running:1"),
    )

    assert view["state"] == "stale"
    assert view["source_state"] == "stale"
    assert view["definition"] is None
    assert view["review"] is None
    assert view["freeze"] is None
    assert view["verified_read_sha256"] == "b" * 64


@pytest.mark.parametrize("state", ["queued", "running", "paused"])
def test_d1_status_projects_active_execution_before_a_terminal_attempt(state: str) -> None:
    assert _d1_status(_summary(execution_state=state, checkpoint=f"d1:{state}"), []) == state


def test_d1_status_projects_an_interrupted_run_as_failed_even_after_an_older_attempt() -> None:
    attempts: list[dict[str, object]] = [{"status": "completed"}]
    assert (
        _d1_status(_summary(execution_state="failed", checkpoint="d1:failed:2"), attempts)
        == "failed"
    )
