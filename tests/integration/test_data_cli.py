import json
from datetime import UTC, date, datetime
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


def test_snapshots_lists_manifest_summaries_deterministically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"fake": _FakeAdapter})
    empty = runner.invoke(app, ["data", "snapshots", "--json"])
    assert empty.exit_code == 0, empty.output
    assert json.loads(empty.stdout) == {"snapshots": []}

    pull = runner.invoke(
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
    assert pull.exit_code == 0, pull.output
    for snapshot_id in ("snap-b", "snap-a"):
        created = runner.invoke(app, ["data", "snapshot", snapshot_id, "AAPL", "--source", "fake"])
        assert created.exit_code == 0, created.output

    listed = runner.invoke(app, ["data", "snapshots", "--json"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.stdout)
    rows = payload["snapshots"]
    # Deterministic order: snapshot id ascending, independent of creation order.
    assert [row["snapshot_id"] for row in rows] == ["snap-a", "snap-b"]
    for row in rows:
        assert set(row) == {
            "snapshot_id",
            "created_at",
            "source",
            "adapter_version",
            "parser_version",
            "symbols",
            "manifest_sha256",
        }
        assert row["source"] == "fake"
        assert row["symbols"] == ["AAPL"]
        assert len(row["manifest_sha256"]) == 64

    fallback = runner.invoke(app, ["data", "snapshots"])
    assert fallback.exit_code == 0
    assert "snap-a" in fallback.output and "snap-b" in fallback.output


class _RecordingCrypto(_FakeCrypto):
    seen: list[str] = []

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult:
        _RecordingCrypto.seen.append(symbol)
        return super().fetch(symbol, start, end)


def test_pull_normalises_symbol_before_fetch_and_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"ccxt": _RecordingCrypto})
    _RecordingCrypto.seen.clear()
    r = runner.invoke(
        app,
        [
            "data",
            "pull",
            "xrp-usdt",
            "--source",
            "ccxt",
            "--exchange",
            "binance",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-03",
        ],
    )
    assert r.exit_code == 0, r.output
    assert _RecordingCrypto.seen == ["XRP/USDT"]
    assert "pulled XRP/USDT" in r.output
    assert data_cmds._store().list_symbols() == ["XRP/USDT"]


def test_pull_rejects_end_before_start_without_calling_the_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"ccxt": _RecordingCrypto})
    _RecordingCrypto.seen.clear()
    r = runner.invoke(
        app,
        [
            "data",
            "pull",
            "XRP/USDT",
            "--source",
            "ccxt",
            "--exchange",
            "binance",
            "--start",
            "2024-02-01",
            "--end",
            "2024-01-01",
        ],
    )
    assert r.exit_code == 2
    assert "2024-01-01" in r.output and "2024-02-01" in r.output and "Traceback" not in r.output
    assert _RecordingCrypto.seen == []


def test_pull_rejects_impossible_calendar_date_naming_the_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"ccxt": _RecordingCrypto})
    r = runner.invoke(
        app,
        [
            "data",
            "pull",
            "XRP/USDT",
            "--source",
            "ccxt",
            "--exchange",
            "binance",
            "--start",
            "2015-01-01",
            "--end",
            "2026-06-31",
        ],
    )
    assert r.exit_code == 2
    assert "YYYY-MM-DD" in r.output and "out of range" in r.output


class _ListedCrypto(_RecordingCrypto):
    """A ccxt-like adapter whose pair was first listed on 2019-04-30."""

    probed: list[str] = []

    def first_bar(self, symbol: str, *, timeframe: str = "1d") -> datetime:
        _ListedCrypto.probed.append(symbol)
        return datetime(2019, 4, 30, tzinfo=UTC)


def test_first_bar_json_projection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"ccxt": _ListedCrypto})
    r = runner.invoke(
        app,
        ["data", "first-bar", "xrp-usdt", "--source", "ccxt", "--exchange", "binance", "--json"],
    )
    assert r.exit_code == 0, r.output
    assert json.loads(r.output) == {
        "symbol": "XRP/USDT",
        "exchange": "binance",
        "first_bar_ts": "2019-04-30T00:00:00+00:00",
        "timeframe": "1d",
    }
    other = runner.invoke(app, ["data", "first-bar", "AAPL", "--source", "yfinance"])
    assert other.exit_code == 2 and "ccxt" in other.output


def test_pull_before_first_bar_fails_with_first_listed_date_and_start_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"ccxt": _ListedCrypto})
    _ListedCrypto.seen.clear()
    r = runner.invoke(
        app,
        [
            "data",
            "pull",
            "XRP/USDT",
            "--source",
            "ccxt",
            "--exchange",
            "binance",
            "--start",
            "2015-01-01",
            "--end",
            "2020-01-01",
        ],
    )
    assert r.exit_code == 2
    assert "2019-04-30" in r.output and "Start there" in r.output
    assert _ListedCrypto.seen == []
    assert data_cmds._store().list_symbols() == []


def test_pull_starting_exactly_at_first_bar_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("alpha_cli.data_cmds._ADAPTERS", {"ccxt": _ListedCrypto})
    _ListedCrypto.seen.clear()
    r = runner.invoke(
        app,
        [
            "data",
            "pull",
            "XRP/USDT",
            "--source",
            "ccxt",
            "--exchange",
            "binance",
            "--start",
            "2019-04-30",
            "--end",
            "2019-05-02",
        ],
    )
    assert r.exit_code == 0, r.output
    assert _ListedCrypto.seen == ["XRP/USDT"]


def test_pull_non_ccxt_source_skips_the_first_bar_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
            "2015-01-01",
            "--end",
            "2020-01-01",
        ],
    )
    assert r.exit_code == 0, r.output
