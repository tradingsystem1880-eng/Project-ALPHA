"""`/api/ideas` relays `alpha idea list --json`; the relay is faked here."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from alpha_web.api import ideas as ideas_api
from alpha_web.app import create_app

LISTED: dict[str, Any] = {
    "cards": [
        {"id": "7634f180ca16", "claim": "Gaps close", "tested": True, "not_stated": ["held_for"]},
        {"id": "aaaaaaaaaaaa", "claim": None, "tested": False, "not_stated": [], "extra": 1},
    ]
}


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relay: Any) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ideas_api, "_run_json", relay)
    return TestClient(create_app())


def test_relays_the_command_and_drops_unknown_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def relay(args: list[str], **kwargs: Any) -> Any:
        calls.append(args)
        assert kwargs["timeout_seconds"] > 0
        return LISTED

    body = _client(tmp_path, monkeypatch, relay).get("/api/ideas").json()
    assert calls == [["idea", "list", "--json"]]
    assert [card["id"] for card in body["cards"]] == ["7634f180ca16", "aaaaaaaaaaaa"]
    assert "extra" not in body["cards"][1]


@pytest.mark.parametrize(("message", "status"), [("boom", 409), ("command timed out", 504)])
def test_a_command_failure_is_a_409_and_a_timeout_a_504(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str, status: int
) -> None:
    def relay(args: list[str], **kwargs: Any) -> Any:
        raise RuntimeError(message)

    response = _client(tmp_path, monkeypatch, relay).get("/api/ideas")
    assert response.status_code == status
