"""The web-safe caller of `alpha data run-price` trusts only a well-formed, available reply."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import run_price

BAR = {"t": 1.0, "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 10.0}


def _reply(monkeypatch: pytest.MonkeyPatch, stdout: str, code: int = 0) -> list[Any]:
    calls: list[Any] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, code, stdout=stdout, stderr="")

    monkeypatch.setattr("alpha_cli.run_price.subprocess.run", run)
    return calls


def test_an_available_reply_returns_its_bars_and_forwards_no_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "secret")
    calls = _reply(monkeypatch, json.dumps({"status": "available", "bars": [BAR]}))
    assert run_price.verified_bars("a" * 16, data_dir=tmp_path) == ("available", [BAR])
    command, kwargs = calls[0]
    assert command[1:4] == ["data", "run-price", "a" * 16]
    assert kwargs["env"]["ALPHA_DATA_DIR"] == str(tmp_path)
    assert "ALPHA_TIINGO_API_KEY" not in kwargs["env"]


def test_a_refusal_status_carries_no_bars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _reply(monkeypatch, json.dumps({"status": "bars_changed_since_run", "bars": [BAR]}))
    assert run_price.verified_bars("a" * 16, data_dir=tmp_path) == ("bars_changed_since_run", [])


@pytest.mark.parametrize(
    "stdout",
    [
        "not json",
        json.dumps([]),
        json.dumps({"status": "available", "bars": "x"}),
        json.dumps({"status": "available", "bars": [{**BAR, "c": None}]}),
        json.dumps({"status": "available", "bars": [{**BAR, "c": True}]}),
    ],
)
def test_a_malformed_reply_is_unavailable(
    stdout: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reply(monkeypatch, stdout)
    assert run_price.verified_bars("a" * 16, data_dir=tmp_path) == ("price_unavailable", [])


def test_a_failed_command_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _reply(monkeypatch, "", code=2)
    assert run_price.verified_bars("a" * 16, data_dir=tmp_path) == ("price_unavailable", [])
