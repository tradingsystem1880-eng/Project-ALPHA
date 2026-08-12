"""Trusted CLI is the only entry point for enrollment and recovery ceremonies."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from alpha_cli import owner_auth_cmds
from alpha_cli.main import app
from alpha_core import DataError


@pytest.mark.parametrize(
    ("command", "replaces"),
    [(["enroll"], False), (["recover"], True)],
)
def test_owner_auth_cli_issues_short_lived_local_url(
    monkeypatch: pytest.MonkeyPatch, command: list[str], replaces: bool
) -> None:
    captured: dict[str, object] = {}

    def issue(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "request_id": "request-1",
            "expires_at": "2026-08-13T02:05:00Z",
            "url": "http://localhost:8801/owner-auth/enroll#token=fragment-only",
        }

    monkeypatch.setattr(owner_auth_cmds, "issue_enrollment", issue)
    result = CliRunner().invoke(
        app,
        ["owner-auth", *command, "--reason", "trusted local ceremony", "--json"],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["url"].startswith("http://localhost:8801/")
    assert captured["reason"] == "trusted local ceremony"
    assert captured["replace_existing"] is replaces


def test_owner_auth_human_output_and_safe_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        owner_auth_cmds,
        "issue_enrollment",
        lambda **_: {
            "expires_at": "2026-08-13T02:05:00Z",
            "url": "http://localhost:8801/owner-auth/enroll#token=fragment-only",
        },
    )
    shown = CliRunner().invoke(app, ["owner-auth", "enroll", "--reason", "trusted local ceremony"])
    assert shown.exit_code == 0
    assert "Open this short-lived local URL" in shown.stdout
    assert "http://localhost:8801/" in shown.stdout

    def fail(**_: object) -> dict[str, object]:
        raise DataError("an enrollment request is already active")

    monkeypatch.setattr(owner_auth_cmds, "issue_enrollment", fail)
    denied = CliRunner().invoke(app, ["owner-auth", "recover", "--reason", "trusted recovery"])
    assert denied.exit_code != 0
    assert "already active" in denied.output
