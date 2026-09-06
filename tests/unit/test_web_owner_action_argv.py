"""Owner-action argv for the research lifecycle verbs the terminal offers behind Touch ID."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_web.api.owner_auth import _action_argv


@pytest.mark.parametrize(
    ("action_type", "verb"),
    [("pause_research", "pause"), ("resume_research", "resume"), ("cancel_research", "cancel")],
)
def test_pause_resume_cancel_bind_actor_and_reason(action_type: str, verb: str) -> None:
    argv = _action_argv(
        action_type=action_type, project_id="p1", payload={}, actor="owner", reason="why"
    )
    assert argv == ["research", verb, "p1", "--actor", "owner", "--reason", "why", "--json"]


def test_resume_never_forwards_the_orphan_acknowledgement() -> None:
    argv = _action_argv(
        action_type="resume_research",
        project_id="p1",
        payload={"acknowledge_orphaned_process": True},
        actor="owner",
        reason="why",
    )
    assert "--acknowledge-orphaned-process" not in argv


def test_research_gate_override_stays_cli_only() -> None:
    with pytest.raises(DataError, match="unsupported owner action type"):
        _action_argv(
            action_type="override_research_gate",
            project_id="p1",
            payload={},
            actor="owner",
            reason="why",
        )
