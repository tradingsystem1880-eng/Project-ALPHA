"""`/api/ideas` and `/api/ideas/{card}` relay the CLI; the relay is faked but for the last test."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from alpha_web.api import ideas as ideas_api
from alpha_web.app import create_app
from tests.unit import test_idea_file as idea_fixture

CARD = "0f1aabc8218c"


class Relay:
    def __init__(self, answer: Any = None, error: str | None = None) -> None:
        self.calls: list[list[str]] = []
        self.answer, self.error = answer, error

    def __call__(self, args: list[str], **kwargs: Any) -> Any:
        self.calls.append(args)
        assert kwargs["timeout_seconds"] > 0
        if self.error:
            raise RuntimeError(self.error)
        return self.answer


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relay: Relay) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ideas_api, "_run_json", relay)
    return TestClient(create_app())


def _row(n: int, saved: str) -> dict[str, Any]:
    return {
        "id": f"{n:012x}",
        "claim": f"idea {n}",
        "tested": False,
        "not_stated": [],
        "tests_linked": 0,
        "saved_at": saved,
    }


def test_list_is_newest_first_and_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_row(n, f"2026-11-{1 + n % 28:02d}T00:00:00+00:00") for n in range(520)]
    relay = Relay({"cards": rows})
    body = _client(tmp_path, monkeypatch, relay).get("/api/ideas").json()
    assert relay.calls == [["idea", "list", "--json"]]
    assert body["total"] == 520 and body["truncated"] is True and len(body["cards"]) == 500
    stamps = [c["saved_at"] for c in body["cards"]]
    assert stamps == sorted(stamps, reverse=True)


def test_empty_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = _client(tmp_path, monkeypatch, Relay({"cards": []})).get("/api/ideas").json()
    assert body == {"cards": [], "total": 0, "truncated": False}


def _file(readings: int) -> dict[str, Any]:
    return {
        "card": {"id": CARD, "claim": "c"},
        "map": [{"step": "card written", "state": "done", "evidence": [CARD], "note": ""}],
        "follows": [],
        "readings": [{"kind": "rule test", "id": f"{n:016x}"} for n in range(readings)],
        "counts": {},
        "open_points": {},
        "secret_extra": "dropped",
    }


def test_file_keeps_the_newest_readings_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relay = Relay(_file(230))
    body = _client(tmp_path, monkeypatch, relay).get(f"/api/ideas/{CARD}").json()
    assert relay.calls == [["idea", "file", CARD, "--json"]]
    assert len(body["readings"]) == 200 and body["readings_total"] == 230
    assert body["readings_shown_from"] == 30 and body["readings"][-1]["id"] == f"{229:016x}"
    assert "secret_extra" not in body


def test_unknown_card_is_404_with_the_cli_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = "There is no idea card with the id 'deadbeef0000'. Run `alpha idea list`."
    res = _client(tmp_path, monkeypatch, Relay(error=text)).get("/api/ideas/deadbeef0000")
    assert res.status_code == 404 and "no idea card" in res.json()["message"]


def test_other_failures_and_bad_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch, Relay(error="More than one idea card starts with 'ab'"))
    assert client.get("/api/ideas/abcd").status_code == 409
    assert client.get("/api/ideas/not-hex").status_code == 422
    assert client.get("/api/ideas/..%2Fx").status_code in {404, 422}
    slow = _client(tmp_path, monkeypatch, Relay(error="alpha idea file timed out after 30 seconds"))
    assert slow.get(f"/api/ideas/{CARD}").status_code == 504


def test_the_real_cli_answers_the_models_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = idea_fixture.synthetic_home(tmp_path)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    listing = client.get("/api/ideas").json()
    assert [c["id"] for c in listing["cards"]] == [card] and listing["cards"][0][
        "tests_linked"
    ] == 2
    body = client.get(f"/api/ideas/{card}").json()
    assert body["card"]["claim"].startswith("Quiet weeks")
    assert body["readings"][0]["reading"]["evidence"]["word"] == "too little to read"
    assert body["readings"][0]["aim"]["observed"] == 0.75
    assert body["readings"][0]["reading"]["aim"]["source"] == "default"
    assert body["readings"][0]["reading"]["counts"]["family_id"] == "spine:ma_cross"
    assert body["readings"][0]["checks"][0]["tool"] == "costs.break_even"
    assert client.get("/api/ideas/ffffffffffff").status_code == 404
