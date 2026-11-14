"""Offline Alpaca pulls through the real CLI, receipt pipeline and PIT reader."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest
from typer.testing import CliRunner, Result

from alpha_cli import data_cmds, provider_readiness
from alpha_cli.main import app
from alpha_data.adapters.alpaca_adapter import AlpacaAdapter
from alpha_data.store import ParquetStore

runner = CliRunner()
NOW = datetime(2024, 5, 1, 12, tzinfo=UTC)


def fake_transport(
    url: str, headers: Mapping[str, str], timeout: float
) -> tuple[int, dict[str, str], bytes]:
    query = parse_qs(urlsplit(url).query)
    if urlsplit(url).path == "/v1/corporate-actions":
        body = {
            "corporate_actions": {
                "forward_splits": [
                    {"symbol": "SPY", "ex_date": "2024-01-04", "old_rate": 1, "new_rate": 2}
                ],
                "cash_dividends": [{"symbol": "SPY", "ex_date": "2024-01-02", "rate": 0.5}],
            },
            "next_page_token": None,
        }
    else:
        prices = [100, 102, 52] if query["adjustment"] == ["raw"] else [50, 51, 52]
        body = {
            "bars": {
                "SPY": [
                    dict(
                        t=f"2024-01-{day:02d}T05:00:00Z", o=price, h=price, l=price, c=price, v=100
                    )
                    for day, price in zip((2, 3, 4), prices, strict=True)
                ]
            },
            "next_page_token": None,
        }
    return 200, {}, json.dumps(body).encode()


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ParquetStore:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))

    def factory(**kwargs: Any) -> AlpacaAdapter:
        return AlpacaAdapter(
            **kwargs,
            api_key_id="sentinel-key",
            api_secret_key="sentinel-secret",
            transport=fake_transport,
            sleep=lambda _: None,
            clock=lambda: NOW,
        )

    monkeypatch.setattr(data_cmds, "_ADAPTERS", {"alpaca": factory})
    return ParquetStore(tmp_path / "store")


def pull(end: str = "2024-01-04") -> Result:
    return runner.invoke(
        app,
        [
            "data",
            "pull",
            "SPY",
            "--source",
            "alpaca",
            "--asset-class",
            "etf",
            "--start",
            "2024-01-02",
            "--end",
            end,
        ],
    )


def test_promotes_receipt_raw_prices_actions_and_asof_candles(store: ParquetStore) -> None:
    result = pull()
    assert result.exit_code == 0, result.output
    assert "not yet confirmed" in result.output
    assert store.read_bars("SPY")["close"].to_list() == [100.0, 102.0, 52.0]
    assert len(store.read_actions("SPY")) == 2
    provenance: Any = store.read_provenance("SPY")
    assert provenance is not None
    assert provenance["source"] == "alpaca"
    assert provenance["dataset"]["asset_class"] == "etf"
    response = (
        store.root / "receipts" / "alpaca" / provenance["receipt"]["receipt_id"] / "response.bin"
    )
    assert json.loads(response.read_bytes())["schema"] == "alpha.alpaca.daily.v1"
    for cutoff, prices in (("2024-01-03", [100.0, 102.0]), ("2024-01-04", [50.0, 51.0, 52.0])):
        candles = runner.invoke(app, ["data", "candles", "SPY", "--end", cutoff, "--json"])
        assert candles.exit_code == 0, candles.output
        assert [bar["c"] for bar in json.loads(candles.output)["bars"]] == prices


def test_missing_keys_fail_before_request(
    store: ParquetStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    transport = Mock(side_effect=AssertionError("must not call transport"))
    monkeypatch.setattr(
        data_cmds, "_ADAPTERS", {"alpaca": lambda **kw: AlpacaAdapter(transport=transport, **kw)}
    )
    result = pull()
    assert result.exit_code == 2
    assert "APCA_API_KEY_ID" in result.output and "APCA_API_SECRET_KEY" in result.output
    transport.assert_not_called()
    assert store.list_symbols() == []


def test_receipt_pull_cannot_replace_tiingo_and_changes_no_store_bytes(store: ParquetStore) -> None:
    assert pull().exit_code == 0
    store.write_provenance("SPY", source="tiingo", adapter_version="1", parser_version="1")
    before = {
        path.relative_to(store.root): path.read_bytes()
        for path in store.root.rglob("*")
        if path.is_file()
    }
    result = pull()
    assert result.exit_code == 2, result.output
    # Rich may wrap the error inside a bordered panel; retain every word when comparing.
    message = " ".join(result.output.replace("│", " ").split())
    assert "canonical Tiingo data" in message and "cannot be silently replaced" in message
    after = {
        path.relative_to(store.root): path.read_bytes()
        for path in store.root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_calendar_gap_quarantines_without_canonical_publication(store: ParquetStore) -> None:
    result = pull("2024-01-05")
    assert result.exit_code == 2, result.output
    assert "quarantined" in result.output and "calendar_gap:2024-01-05" in result.output
    assert store.list_symbols() == []
    reports = list((store.root / "quarantine" / "alpaca").glob("*/quality.json"))
    assert len(reports) == 1
    assert json.loads(reports[0].read_text())["status"] == "quarantined"


def test_alpaca_readiness_fetches_spy_etf_and_classifies_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from alpha_core import DataError

    fetch = Mock(return_value=Mock(bars=Mock(height=10)))
    factory = Mock(return_value=Mock(fetch=fetch))
    monkeypatch.setattr(provider_readiness, "AlpacaAdapter", factory)
    result = provider_readiness.run_explicit_check(tmp_path, "alpaca")
    assert result["verification_state"] == "verified"
    factory.assert_called_once_with(asset_class="etf")
    symbol, start, end = fetch.call_args.args
    assert symbol == "SPY" and start == end - timedelta(days=14)
    assert end == datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1)
    for code, state in (
        (401, "authentication_failed"),
        (403, "entitlement_denied"),
        (429, "rate_limited"),
    ):
        fetch.side_effect = DataError(f"Alpaca HTTP {code}")
        assert (
            provider_readiness.run_explicit_check(tmp_path, "alpaca")["verification_state"] == state
        )


def test_alpaca_never_merges_into_a_series_held_from_another_source(store: ParquetStore) -> None:
    assert pull().exit_code == 0
    store.write_provenance("SPY", source="yfinance", adapter_version="1", parser_version="2")
    before = store.read_bars("SPY")
    result = pull()
    assert result.exit_code == 2, result.output
    message = " ".join(result.output.replace("│", " ").split())
    assert "already holds yfinance data" in message and "separate ALPHA_DATA_DIR" in message
    assert store.read_bars("SPY").equals(before)
    provenance = store.read_provenance("SPY")
    assert provenance is not None and provenance["source"] == "yfinance"
