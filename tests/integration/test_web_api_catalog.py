"""The workstation catalog endpoints (FastAPI TestClient; real ``alpha`` subprocess, offline).

``/api/strategies`` and ``/api/commands`` project the CLI's catalogs; ``/api/symbols`` reads the
store. These subprocess the real ``alpha`` binary so the workstation and the CLI can never drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app
from tests.fixtures.cli_fixtures import seed_store


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_strategies_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    by_name = {s["name"]: s for s in _client(tmp_path, monkeypatch).get("/api/strategies").json()}
    assert "ma_crossover" in by_name
    assert any(p["name"] == "fast" for p in by_name["ma_crossover"]["params"])
    assert by_name["kronos_forecast"]["has_tier1_surrogate"] is False


def test_commands_endpoint_annotates_run_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    by_id = {c["id"]: c for c in _client(tmp_path, monkeypatch).get("/api/commands").json()}
    assert by_id["backtest run"]["run_type"] == "runs"
    assert by_id["optim grid"]["run_type"] == "optim"
    assert by_id["data pull"]["run_type"] is None  # persists no manifest


def test_symbols_endpoint_reads_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_store(tmp_path, symbol="QQQ")
    assert _client(tmp_path, monkeypatch).get("/api/symbols").json() == {"symbols": ["QQQ"]}
