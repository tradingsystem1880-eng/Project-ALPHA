"""Offline W05 cross-seam evidence; no research admission or provider availability claim."""

from __future__ import annotations

import hashlib
import http.client
import io
import json
import socket
from datetime import UTC, date, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_core import DataError
from alpha_data import snapshot
from alpha_data.crypto.providers._wire import RequestBudget
from alpha_data.crypto.storage import CryptoBulkStore
from alpha_data.pipeline import stage_and_promote
from alpha_data.source import PointInTimeSource
from alpha_data.store import ParquetStore
from tests.unit.test_crypto_request_budget import (
    HOST,
    SyntheticResponse,
    klines,
    response,
    transport,
)
from tests.unit.test_crypto_storage import _store
from tests.unit.test_ingest_pipeline import _bars, _result

START = datetime(2024, 3, 8, tzinfo=UTC)
START_MS = int(START.timestamp() * 1000)
DAY_MS = 86_400_000
runner = CliRunner()


@pytest.fixture(autouse=True)
def forbid_external_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("integration fixture attempted network or control-store access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(crypto_data_cmds, "_control_store", forbidden)


@pytest.fixture
def bulk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CryptoBulkStore:
    store = _store(tmp_path)
    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: store)
    monkeypatch.setattr(crypto_data_cmds, "_snapshot_root", lambda: tmp_path / "snapshots")
    monkeypatch.setattr(crypto_data_cmds, "_now", lambda: START + timedelta(days=4))
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "control"))
    return store


def acquire_args(*, start: str = "2024-03-08", end: str = "2024-03-12") -> list[str]:
    return [
        "crypto-data",
        "acquire",
        "binance",
        "market_bars",
        "BTCUSDT",
        "--base",
        "BTC",
        "--quote",
        "USDT",
        "--category",
        "spot",
        "--frequency",
        "1d",
        "--start",
        start + "T00:00:00Z",
        "--end",
        end + "T00:00:00Z",
        "--max-requests",
        "2",
        "--max-total-bytes",
        "1000000",
        "--json",
    ]


def success(args: list[str]) -> dict[str, Any]:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    value = json.loads(result.stdout)
    assert isinstance(value, dict)
    return value


def candles(manifest_id: str) -> list[str]:
    return [
        "data",
        "candles",
        "BTCUSDT",
        "--manifest-id",
        manifest_id,
        "--end",
        "2024-03-10",
        "--json",
    ]


def test_budgeted_acquisition_snapshot_member_query_preserves_revisions_and_lineage(
    bulk: CryptoBulkStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = klines(START_MS, 3)
    revised = json.loads(original)
    revised[0][4] = "102"
    calls = transport(monkeypatch, [response(original), response(json.dumps(revised).encode())])
    first = success(acquire_args())
    assert first["state"] == "qualified" and first["execution_authority"] is False
    manifest_id = first["normalized_manifest_id"]
    normalized = bulk.verify_manifest(manifest_id)
    assert normalized["input_manifest_ids"] == first["raw_manifest_ids"]
    raw = bulk.verify_manifest(first["raw_manifest_id"])
    assert raw["artifact_sha256"] == hashlib.sha256(original).hexdigest()
    frozen = success(["crypto-data", "snapshot-create", "--manifest-id", manifest_id, "--json"])
    verify = ["crypto-data", "snapshot-verify", frozen["snapshot_id"], "--json"]
    assert success(verify)["eligible"] is True
    (member,) = crypto_data_cmds._read_snapshot(frozen["snapshot_id"]).members
    assert member.artifact_key == normalized["artifact_key"]
    assert member.artifact_sha256 == normalized["artifact_sha256"]
    assert member.dataset.to_dict() == normalized["dataset"]
    saved = {p: p.read_bytes() for p in (tmp_path / "snapshots").rglob("*.json")}
    before = success(candles(manifest_id))
    assert [bar["c"] for bar in before["bars"]] == pytest.approx([101.0, 101.0])
    assert before["provenance"]["manifest_id"] == manifest_id
    assert before["provenance"]["history_kind"] == "reconstructed_from_verified_archive"

    changed = success(acquire_args())
    assert len(calls) == 2 and changed["normalized_manifest_id"] != manifest_id
    assert success(candles(changed["normalized_manifest_id"]))["bars"][0]["c"] == pytest.approx(102)
    assert success(candles(manifest_id)) == before
    assert success(verify)["eligible"] is True
    assert all(p.read_bytes() == content for p, content in saved.items())
    # REST revisions are versioned; archive-only automatic correction policy is not inferred.
    (bulk.bulk_root / str(raw["artifact_key"])).write_bytes(b"tampered synthetic raw page")
    assert runner.invoke(app, candles(manifest_id)).exit_code != 0
    assert runner.invoke(app, verify).exit_code != 0


@pytest.mark.parametrize("kind", ["missing_day", "partial_period", "future_row"])
def test_budgeted_bad_bars_cannot_cross_snapshot_or_query_boundary(
    bulk: CryptoBulkStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    rows = json.loads(klines(START_MS, 4))
    if kind == "missing_day":
        rows = [rows[0], rows[2]]
    else:
        monkeypatch.setattr(crypto_data_cmds, "_now", lambda: START + timedelta(days=2, hours=12))
    if kind == "partial_period":
        rows = rows[:3]
    calls = transport(monkeypatch, [response(json.dumps(rows).encode())])
    args = acquire_args(end="2024-03-12" if kind == "missing_day" else "2024-03-10")
    if kind == "future_row":
        rejected = runner.invoke(app, args)
        assert rejected.exit_code != 0 and "outside" in rejected.output
        assert len(calls) == 1 and bulk.inventory() == ()
        assert not list((tmp_path / "snapshots").rglob("*.json"))
        return
    acquired = success(args)
    expected = "warning" if kind == "missing_day" else "quarantined"
    assert acquired["state"] == expected
    if kind == "missing_day":
        assert "cadence_gap" in acquired["warnings"]
    else:
        assert "partial_period" in acquired["failures"]
    manifest_id = acquired["normalized_manifest_id"]
    quality = bulk.verify_manifest(manifest_id)["quality"]
    assert isinstance(quality, dict)
    assert quality["row_count"] == len(rows)
    assert (
        runner.invoke(
            app, ["crypto-data", "snapshot-create", "--manifest-id", manifest_id, "--json"]
        ).exit_code
        != 0
    )
    assert runner.invoke(app, candles(manifest_id)).exit_code != 0
    assert not list((tmp_path / "snapshots").rglob("*.json"))


@pytest.mark.parametrize("failure", ["redirect", "interrupted_body"])
def test_second_page_transport_failure_publishes_no_partial_dataset(
    bulk: CryptoBulkStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    class Interrupted(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            if self.tell() == 0:
                return super().read(2)
            raise http.client.IncompleteRead(b"xy", 4)

    first = response(klines(1577836800000, 1000))
    headers = Message()
    headers["Content-Type"] = "application/json"
    second = (
        response(code=302)
        if failure == "redirect"
        else SyntheticResponse(Interrupted(b"abcd"), headers, HOST + "klines", 200)
    )
    calls = transport(monkeypatch, [first, second])
    result = runner.invoke(app, acquire_args(start="2020-01-01", end="2022-12-31"))
    assert result.exit_code != 0 and len(calls) == 2
    assert first.closed and second.closed
    if failure == "interrupted_body":
        assert isinstance(result.exception, http.client.IncompleteRead)
    assert bulk.inventory() == ()
    assert not list((tmp_path / "snapshots").rglob("*.json"))


@pytest.mark.bias_guard
def test_legacy_snapshot_then_promoted_snapshot_preserve_dst_pit_cutoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    store = ParquetStore(tmp_path / "store")
    store.write_bars("AAPL", _bars([("2024-03-08", 100.0), ("2024-03-11", 101.0)]))
    store.write_actions("AAPL", [])
    store.write_provenance("AAPL", source="yfinance", adapter_version="1", parser_version="2")
    cutoff = datetime(2024, 3, 11, tzinfo=UTC)
    snapshots = tmp_path / "snapshots"
    snapshot.create_snapshot(
        store,
        snapshots,
        "legacy",
        ["AAPL"],
        source="yfinance",
        adapter_version="1",
        parser_version="2",
        created_at=cutoff,
    )
    legacy = {p: p.read_bytes() for p in (snapshots / "legacy").rglob("*") if p.is_file()}
    result = _result(
        [("2024-03-12", 9.9e9)], start=date(2024, 3, 12), end=date(2024, 3, 12), raw=b"future"
    )
    assert stage_and_promote(store, result, authoritative_source="tiingo").status == "promoted"
    snapshot.create_snapshot(
        store,
        snapshots,
        "promoted",
        ["AAPL"],
        source="tiingo",
        adapter_version="1",
        parser_version="1",
        created_at=cutoff,
    )
    for name in ("legacy", "promoted"):
        snapshot.verify_snapshot(snapshots / name)
        reader = PointInTimeSource(ParquetStore(snapshots / name), actions={})
        utc = reader.as_of("AAPL", cutoff)
        assert utc == reader.as_of("AAPL", cutoff.astimezone(ZoneInfo("America/New_York")))
        assert [bar.close for bar in utc] == pytest.approx([100.0, 101.0])
        queried = success(
            ["data", "candles", "AAPL", "--snapshot", name, "--end", "2024-03-11", "--json"]
        )
        assert [bar["c"] for bar in queried["bars"]] == pytest.approx([100.0, 101.0])
    assert all(p.read_bytes() == content for p, content in legacy.items())
    leaky = PointInTimeSource(ParquetStore(snapshots / "promoted"), actions={})
    assert leaky.as_of("AAPL", cutoff + timedelta(days=1))[-1].close == pytest.approx(9.9e9)


def test_binance_page_ceiling_stops_at_100_without_a_101st_http_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = transport(monkeypatch, [response(b"[]") for _ in range(101)])

    def cursor_frame(_payload: bytes, *, source: str) -> pl.DataFrame:
        assert source == "rest_json"
        start = int(parse_qs(urlsplit(calls[-1]).query)["startTime"][0])
        return pl.DataFrame(
            {
                "open_time": [
                    datetime.fromtimestamp((start + index * DAY_MS) / 1000, tz=UTC)
                    for index in range(1000)
                ]
            }
        )

    monkeypatch.setattr(crypto_data_cmds, "parse_binance_klines", cursor_frame)
    budget = RequestBudget(101, 1000)
    with pytest.raises(DataError, match="100-page safety limit"):
        crypto_data_cmds._fetch_binance_tail_pages(
            category="spot",
            symbol="BTCUSDT",
            frequency="1d",
            start_ms=START_MS,
            end_ms=START_MS + 100001 * DAY_MS,
            budget=budget,
        )
    assert len(calls) == budget.requests_used == 100
    assert budget.bytes_read == 200
