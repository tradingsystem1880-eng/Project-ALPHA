"""Provider/system control-plane CLI and CCXT venue provenance."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_data.adapters.ccxt_adapter import CCXTAdapter
from alpha_data.store import ParquetStore
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()


def test_info_providers_json_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "provider-secret-must-not-leak"
    monkeypatch.setenv("ALPHA_FINNHUB_API_KEY", secret)

    result = runner.invoke(app, ["info", "providers", "--json"])

    assert result.exit_code == 0, result.output
    providers = {provider["id"]: provider for provider in json.loads(result.stdout)}
    assert {"yfinance", "ccxt", "stooq", "finnhub", "binance"} == set(providers)
    assert providers["finnhub"]["configured"] is True
    assert providers["ccxt"]["options"]["exchange"]["choices"] == ["coinbase", "binance"]
    assert secret not in result.stdout


def test_info_system_reports_local_readiness_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_FORECAST_HUB_CACHE", str(tmp_path / "models"))
    seed_store(tmp_path, symbol="SPY")
    completed = tmp_path / "snapshots" / "complete"
    completed.mkdir(parents=True)
    (completed / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "snapshots" / ".partial.tmp").mkdir()

    result = runner.invoke(app, ["info", "system", "--json"])

    assert result.exit_code == 0, result.output
    status = json.loads(result.stdout)
    assert status["data_dir"]["path"] == str(tmp_path)
    assert status["data_dir"]["readable"] is True
    assert status["data_dir"]["writable"] is True
    assert status["data_dir"]["free_bytes"] > 0
    assert status["counts"] == {"symbols": 1, "snapshots": 1}
    assert status["nautilus"]["pinned_version"] == "1.228.0"
    assert status["kronos_cache"]["configured"] is True
    assert status["paper_enabled"] is True


def test_info_control_plane_has_human_readable_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))

    providers = runner.invoke(app, ["info", "providers"])
    system = runner.invoke(app, ["info", "system"])

    assert providers.exit_code == 0, providers.output
    assert "ccxt: configured (historical_bars)" in providers.stdout
    assert "binance: configured (live_bars, live_quotes, sandbox_paper)" in providers.stdout
    assert system.exit_code == 0, system.output
    assert f"data_dir={tmp_path}" in system.stdout
    assert "symbols=0 snapshots=0" in system.stdout
    assert "nautilus=1.228.0 (pinned 1.228.0)" in system.stdout
    assert "paper_enabled=False" in system.stdout


def test_ccxt_snapshot_provenance_includes_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="BTC/USDT")
    adapter = CCXTAdapter(exchange="binance")
    ParquetStore(tmp_path / "store").write_provenance(
        "BTC/USDT",
        source=adapter.name,
        adapter_version=adapter.version,
        parser_version=adapter.parser_version,
    )

    result = runner.invoke(
        app,
        [
            "data",
            "snapshot",
            "binance-history",
            "BTC/USDT",
            "--source",
            "ccxt",
            "--exchange",
            "binance",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads(
        (tmp_path / "snapshots" / "binance-history" / "manifest.json").read_text()
    )
    assert manifest["source"] == "ccxt:binance"
    assert manifest["symbols"]["BTC/USDT"]["provenance_sha256"]


def test_ccxt_snapshot_rejects_relabelled_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="BTC/USDT")
    coinbase = CCXTAdapter(exchange="coinbase")
    ParquetStore(tmp_path / "store").write_provenance(
        "BTC/USDT",
        source=coinbase.name,
        adapter_version=coinbase.version,
        parser_version=coinbase.parser_version,
    )

    result = runner.invoke(
        app,
        [
            "data",
            "snapshot",
            "relabeled",
            "BTC/USDT",
            "--source",
            "ccxt",
            "--exchange",
            "binance",
        ],
    )

    assert result.exit_code != 0
    assert "stored pull" in result.output and "provenance is 'ccxt:coinbase'" in result.output
    assert not (tmp_path / "snapshots" / "relabeled").exists()


def test_ccxt_exchange_is_validated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "data",
            "pull",
            "BTC/USDT",
            "--source",
            "ccxt",
            "--exchange",
            "kraken",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-02",
        ],
    )

    assert result.exit_code == 2
    assert "coinbase" in result.output and "binance" in result.output
    assert "Traceback" not in result.output


def test_paper_enabled_defaults_false(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.startswith("ALPHA_"):
            monkeypatch.delenv(name, raising=False)

    result = runner.invoke(app, ["info", "system", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["paper_enabled"] is False


def test_malformed_paper_enabled_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "sometimes")

    result = runner.invoke(app, ["info", "system", "--json"])

    assert result.exit_code != 0
