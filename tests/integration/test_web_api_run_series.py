"""``GET /api/runs/{id}/series``: stored equity, drawdown, trades, bands and verified price."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from fastapi.testclient import TestClient

from alpha_cli import _runner
from alpha_cli.spine import reserve
from alpha_data.store import ParquetStore
from alpha_data.timeframe import DAILY, store_dir
from alpha_web.app import create_app

RUN_ID = "abcd00000000beef"
START = datetime(2020, 1, 1, tzinfo=UTC)
DAYS = 30
EQUITY = [1.0, 1.1, 1.2, 0.9] + [1.0 + 0.01 * i for i in range(DAYS - 4)]


def _days() -> list[datetime]:
    return [START + timedelta(days=i) for i in range(DAYS)]


def _bars(bump: float = 0.0) -> pl.DataFrame:
    prices = [100.0 + i + (bump if i == 5 else 0.0) for i in range(DAYS)]
    return pl.DataFrame(
        {
            "ts": _days(),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [1.0] * DAYS,
        }
    )


def _write_store(home: Path, frame: pl.DataFrame) -> None:
    store = ParquetStore(store_dir(home, DAILY))
    store.write_bars("AAA", frame)
    store.write_provenance("AAA", source="vendor", adapter_version="1", parser_version="1")


def _fingerprint(home: Path) -> str:
    bars, _ = _runner.load_bars("AAA", data_dir=home, as_of=reserve.CUTOFF)
    return _runner.source_fingerprint(bars)


def _run(home: Path, *, fingerprint: str | None, with_benchmark: bool = True) -> None:
    rdir = home / "runs" / RUN_ID
    rdir.mkdir(parents=True)
    days = _days()
    pl.DataFrame(
        {"ts": days, "equity": EQUITY},
        schema={"ts": pl.Datetime("us", "UTC"), "equity": pl.Float64()},
    ).write_parquet(rdir / "equity_curve.parquet")
    pl.DataFrame(
        {
            "instrument_id": ["AAA"],
            "side": ["long"],
            "quantity": [1.0],
            "entry_price": [101.0],
            "exit_price": [109.0],
            "entry_ts": [days[1]],
            "exit_ts": [days[9]],
            "realized_pnl": [8.0],
            "realized_return": [0.0792],
        },
        schema={
            "instrument_id": pl.String(),
            "side": pl.String(),
            "quantity": pl.Float64(),
            "entry_price": pl.Float64(),
            "exit_price": pl.Float64(),
            "entry_ts": pl.Datetime("us", "UTC"),
            "exit_ts": pl.Datetime("us", "UTC"),
            "realized_pnl": pl.Float64(),
            "realized_return": pl.Float64(),
        },
    ).write_parquet(rdir / "trades.parquet")
    if with_benchmark:
        pl.DataFrame(
            {
                "ts": days[2:],
                "strategy_equity": EQUITY[2:],
                "benchmark_equity": [1.0 + 0.02 * i for i in range(DAYS - 2)],
                "strategy_return": [0.0] * (DAYS - 2),
                "benchmark_return": [0.0] * (DAYS - 2),
                "excess_return": [0.0] * (DAYS - 2),
                "available": [True] * (DAYS - 2),
                "benchmark_kind": ["buy_and_hold"] * (DAYS - 2),
                "unavailable_reason": [None] * (DAYS - 2),
            },
            schema_overrides={"unavailable_reason": pl.String()},
        ).write_parquet(rdir / "benchmark_comparison.parquet")
    manifest: dict[str, Any] = {
        "command": "validate",
        "metadata": {"symbol": "AAA"},
        "folds": [
            {
                "index": 0,
                "test_start_ts": days[4].isoformat(),
                "test_end_ts": days[14].isoformat(),
            }
        ],
        "spine": {
            "store": "home",
            "name": "ma_cross-2-5",
            "data_period": {"first_ts": days[0].isoformat(), "last_ts": days[-1].isoformat()},
            "traded_period": {"first_ts": days[3].isoformat(), "last_ts": days[-1].isoformat()},
            "periods": {
                "tradable": {"first_ts": days[2].isoformat(), "last_ts": days[-1].isoformat()},
                "scored": {"first_ts": days[3].isoformat(), "last_ts": days[-1].isoformat()},
            },
        },
    }
    if fingerprint is not None:
        manifest["source_fingerprint"] = fingerprint
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _client(home: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(home))
    return TestClient(create_app())


def _get(client: TestClient, query: str = "") -> dict[str, Any]:
    response = client.get(f"/api/runs/{RUN_ID}/series{query}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_series_relays_stored_curves_trades_bands_and_verified_price(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_store(tmp_path, _bars())
    _run(tmp_path, fingerprint=_fingerprint(tmp_path))
    body = _get(_client(tmp_path, monkeypatch))
    assert len(body["ts"]) == len(body["equity"]) == len(body["drawdown"]) == DAYS
    assert body["equity"] == EQUITY
    assert min(body["drawdown"]) == pytest.approx(0.9 / 1.2 - 1.0)
    assert body["benchmark"][:2] == [None, None]
    assert body["benchmark"][2] == 1.0
    assert body["exposure"] is None
    (trade,) = body["trades"]
    assert trade["side"] == "long"
    assert trade["entry_price"] == 101.0
    assert trade["realized_return"] == 0.0792
    assert trade["exit_ts"] - trade["entry_ts"] == 8 * 86400
    assert body["bounds"]["trades"] == {
        "original": 1,
        "returned": 1,
        "truncated": False,
        "cap": 2000,
    }
    assert body["bands"]["tradable"]["first_ts"].startswith("2020-01-03")
    assert body["bands"]["scored"]["first_ts"].startswith("2020-01-04")
    assert body["bands"]["folds"] == [
        {
            "index": 0,
            "start_ts": "2020-01-05T00:00:00+00:00",
            "end_ts": "2020-01-15T00:00:00+00:00",
        }
    ]
    assert body["price"]["status"] == "available"
    assert len(body["price"]["ts"]) == len(body["price"]["close"]) == DAYS
    assert body["price"]["close"][0] == 100.0
    assert body["provenance"]["artifact_sha256"] == {}


def test_series_refuses_price_when_a_stored_bar_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_store(tmp_path, _bars())
    _run(tmp_path, fingerprint=_fingerprint(tmp_path))
    _write_store(tmp_path, _bars(bump=3.0))
    body = _get(_client(tmp_path, monkeypatch))
    assert body["price"] == {"status": "bars_changed_since_run", "ts": [], "close": []}
    assert len(body["equity"]) == DAYS


def test_series_says_price_was_not_saved_without_a_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_store(tmp_path, _bars())
    _run(tmp_path, fingerprint=None, with_benchmark=False)
    body = _get(_client(tmp_path, monkeypatch))
    assert body["price"]["status"] == "price_not_saved_with_run"
    assert body["benchmark"] is None


def test_series_samples_to_the_limit_and_keeps_both_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_store(tmp_path, _bars())
    _run(tmp_path, fingerprint=_fingerprint(tmp_path))
    body = _get(_client(tmp_path, monkeypatch), "?limit=10")
    assert len(body["ts"]) == 10
    assert body["bounds"]["points"]["truncated"] is True
    assert body["bounds"]["points"]["original"] == DAYS
    assert body["ts"][0] == START.timestamp()
    assert body["ts"][-1] == _days()[-1].timestamp()
    assert len(body["price"]["ts"]) <= 10


def test_series_rejects_a_limit_over_the_cap_and_an_unknown_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get(f"/api/runs/{RUN_ID}/series?limit=5001").status_code == 422
    assert client.get(f"/api/runs/{RUN_ID}/series").status_code == 404
