"""`alpha data ticker` relays one adapter quote as JSON and rejects what it cannot serve."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from alpha_cli import data_cmds
from alpha_cli.main import app
from alpha_core import DataError

_STAMP = datetime(2026, 9, 3, 14, 2, 11, tzinfo=UTC)


class _Adapter:
    name = "ccxt:binance"

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[str] = []

    def ticker(self, symbol: str) -> tuple[float, datetime]:
        self.calls.append(symbol)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        assert isinstance(self.outcome, float)
        return self.outcome, _STAMP


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, adapter: _Adapter, *args: str) -> Result:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(data_cmds, "_adapter", lambda *_a, **_k: adapter)
    return CliRunner().invoke(app, ["data", "ticker", *args])


def test_ticker_json_relays_the_normalised_pair_venue_price_and_stamp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = _Adapter(2.914)
    result = _run(monkeypatch, tmp_path, adapter, "xrp-usdt", "--exchange", "binance", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "symbol": "XRP/USDT",
        "exchange": "binance",
        "last": 2.914,
        "ts": "2026-09-03T14:02:11+00:00",
    }
    assert adapter.calls == ["XRP/USDT"]


def test_ticker_relays_the_adapter_error_as_a_plain_error_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter = _Adapter(DataError("ccxt:binance lists no market XRP/USDT"))
    result = _run(monkeypatch, tmp_path, adapter, "XRP/USDT", "--exchange", "binance", "--json")
    assert result.exit_code != 0
    assert "lists no market XRP/USDT" in result.output


def test_ticker_is_ccxt_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result = _run(monkeypatch, tmp_path, _Adapter(1.0), "AAPL", "--source", "tiingo", "--json")
    assert result.exit_code != 0
    assert "only for --source ccxt" in result.output
