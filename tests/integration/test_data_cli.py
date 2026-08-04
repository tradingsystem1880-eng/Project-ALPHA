import json
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli import data_cmds
from alpha_cli.main import app
from alpha_core import DataError
from alpha_data.adapters.base import FetchResult
from alpha_data.adapters.yfinance_adapter import parse_yfinance_history
from tests.fixtures.yf_fixtures import aapl_like

runner = CliRunner()


class _BlockedAdapter:
    """Stands in for a source whose live endpoint is gated (e.g. Stooq's anti-bot wall)."""

    name = "stooq"
    version = "1"
    parser_version = "1"

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        raise DataError(
            f"Stooq withheld the free CSV for {symbol}: gated behind an anti-bot challenge."
        )


class _FakeAdapter:
    name = "fake"
    version = "1"
    parser_version = "1"

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        return parse_yfinance_history(aapl_like(), symbol)


class _FakeCrypto:
    name = "ccxt"
    version = "1"
    parser_version = "1"

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        from alpha_data.adapters.ccxt_adapter import parse_ccxt_ohlcv
        from tests.fixtures.ccxt_fixtures import ccxt_ohlcv

        return parse_ccxt_ohlcv(ccxt_ohlcv(), symbol)


def test_pull_crypto_slash_symbol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"ccxt": _FakeCrypto})
    r1 = runner.invoke(
        app,
        [
            "data",
            "pull",
            "BTC/USD",
            "--source",
            "ccxt",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-04",
        ],
    )
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(app, ["data", "snapshot", "csnap", "BTC/USD", "--source", "ccxt"])
    assert r2.exit_code == 0, r2.output
    r3 = runner.invoke(app, ["data", "verify", "csnap"])
    assert r3.exit_code == 0, r3.output


def test_pull_then_snapshot_then_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    # inject the fake adapter so the CLI does no network
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"fake": _FakeAdapter})
    r1 = runner.invoke(
        app,
        [
            "data",
            "pull",
            "AAPL",
            "--source",
            "fake",
            "--start",
            "2020-08-28",
            "--end",
            "2020-09-02",
        ],
    )
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(app, ["data", "snapshot", "snap1", "AAPL", "--source", "fake"])
    assert r2.exit_code == 0, r2.output
    r3 = runner.invoke(app, ["data", "verify", "snap1"])
    assert r3.exit_code == 0, r3.output
    assert "ok" in r3.output.lower()

    status = runner.invoke(app, ["data", "source-status", "AAPL", "--json"])
    assert status.exit_code == 0, status.output
    payload = json.loads(status.stdout)
    assert payload["provenance"]["source"] == "fake"
    assert payload["promotion_pending"] is False


def test_pull_fails_loud_on_blocked_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A gated/blocked source raises DataError; the CLI must show a clean message, not a traceback.
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"stooq": _BlockedAdapter})
    r = runner.invoke(
        app,
        [
            "data",
            "pull",
            "spy.us",
            "--source",
            "stooq",
            "--start",
            "2020-01-01",
            "--end",
            "2020-02-01",
        ],
    )
    assert r.exit_code == 2
    assert "anti-bot" in r.output and "Traceback" not in r.output


def test_pull_rejects_malformed_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"fake": _FakeAdapter})
    r = runner.invoke(
        app,
        [
            "data",
            "pull",
            "AAPL",
            "--source",
            "fake",
            "--start",
            "not-a-date",
            "--end",
            "2020-02-01",
        ],
    )
    assert r.exit_code == 2
    assert "YYYY-MM-DD" in r.output and "Traceback" not in r.output


def test_audit_and_explicit_repair_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    quality = tmp_path / "store" / "candidates" / "tiingo" / "receipt" / "quality.json"
    quality.parent.mkdir(parents=True)
    quality.write_text('{"status":"passed","symbol":"SPY"}', encoding="utf-8")
    audited = runner.invoke(app, ["data", "audit", "tiingo", "receipt", "--json"])
    assert audited.exit_code == 0 and json.loads(audited.stdout)["status"] == "passed"

    class Outcome:
        provider = "tiingo"
        receipt_id = "receipt"
        symbol = "SPY"

    monkeypatch.setattr(data_cmds, "promote_quarantined", lambda *args, **kwargs: Outcome())
    repaired = runner.invoke(
        app,
        ["data", "repair", "tiingo", "receipt", "--approve-differences"],
    )
    assert repaired.exit_code == 0 and "promoted reviewed receipt" in repaired.output
    monkeypatch.setattr(
        data_cmds,
        "rollback_interrupted_promotion",
        lambda *args, **kwargs: None,
    )
    rolled_back = runner.invoke(
        app,
        ["data", "rollback-promotion", "SPY", "--acknowledge"],
    )
    assert rolled_back.exit_code == 0 and "restored pre-promotion" in rolled_back.output


def test_snapshot_fails_loud_on_unknown_symbol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Snapshotting a symbol with no bars in the store fails loud as a tidy BadParameter, not a dump.
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"fake": _FakeAdapter})
    r = runner.invoke(app, ["data", "snapshot", "snap1", "NEVER_PULLED", "--source", "fake"])
    assert r.exit_code == 2
    assert "Traceback" not in r.output


def test_verify_fails_loud_on_missing_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    r = runner.invoke(app, ["data", "verify", "no-such-snapshot"])
    assert r.exit_code == 2
    assert "Traceback" not in r.output
