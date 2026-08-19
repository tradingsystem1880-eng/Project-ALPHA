"""QuantPad research-only adapter: receipts, wire-schema guards, no canonical authority."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.adapters.quantpad_adapter import (
    QuantPadAdapter,
    parse_quantpad_bars,
    parse_quantpad_csv_bars,
    persist_research_fetch,
)


def _payload(rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    bars = (
        rows
        if rows is not None
        else [
            {"t": "2026-01-05T00:00:00Z", "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5, "v": 1000},
            {
                "t": "2026-01-06T00:00:00Z",
                "o": 100.5,
                "h": 102.0,
                "l": 100.0,
                "c": 101.5,
                "v": 1100,
            },
        ]
    )
    return {"schema_version": 1, "symbol": "AAPL", "interval": "1d", "bars": bars}


def _csv_payload() -> bytes:
    return (
        b'"t","o","h","l","c","v","instrument_id"\n'
        b"1767571200000,100,101,99,100.5,1000,38\n"
        b"1767657600000,100.5,102,100,101.5,1100,38\n"
    )


def test_parser_returns_utc_sorted_daily_bars_with_receipt_inputs() -> None:
    result = parse_quantpad_bars(json.dumps(_payload()).encode("utf-8"), "AAPL")
    assert result.symbol == "AAPL"
    assert result.bars.height == 2
    assert list(result.bars.columns) == ["ts", "open", "high", "low", "close", "volume"]
    assert result.identity is not None
    assert result.identity.provider == "quantpad"
    assert result.actions == []


def test_current_csv_parser_returns_the_same_stable_daily_seam() -> None:
    result = parse_quantpad_csv_bars(_csv_payload(), "AAPL")
    assert result.symbol == "AAPL"
    assert result.bars.height == 2
    ts_dtype = result.bars["ts"].dtype
    assert isinstance(ts_dtype, pl.Datetime)
    assert ts_dtype.time_zone == "UTC"
    assert list(result.bars.columns) == ["ts", "open", "high", "low", "close", "volume"]
    assert result.identity is not None
    assert result.identity.provider_symbol == "AAPL"


def test_parser_fails_loud_on_wire_schema_drift() -> None:
    with pytest.raises(DataError, match="wire schema"):
        parse_quantpad_bars(b'{"schema_version": 2, "bars": []}', "AAPL")
    with pytest.raises(DataError, match="wire schema"):
        parse_quantpad_bars(b'{"rows": []}', "AAPL")
    with pytest.raises(DataError, match="no bars"):
        parse_quantpad_bars(json.dumps(_payload(rows=[])).encode("utf-8"), "AAPL")
    disordered = _payload()
    bars = disordered["bars"]
    assert isinstance(bars, list)
    disordered["bars"] = list(reversed(bars))
    with pytest.raises(DataError, match="ordered"):
        parse_quantpad_bars(json.dumps(disordered).encode("utf-8"), "AAPL")


def test_fetch_requires_the_keychain_backed_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUANTPAD_API_KEY", raising=False)
    adapter = QuantPadAdapter()
    with pytest.raises(DataError, match="QUANTPAD_API_KEY"):
        adapter.fetch("AAPL", date(2026, 1, 1), date(2026, 1, 31))


def test_persist_research_fetch_writes_receipted_scratch_output(tmp_path: Path) -> None:
    raw = json.dumps(_payload()).encode("utf-8")
    result = parse_quantpad_bars(raw, "AAPL")
    assert result.identity is not None
    from alpha_data.adapters.base import FetchReceipt, FetchResult

    receipt = FetchReceipt.create(
        identity=result.identity,
        requested_start=date(2026, 1, 5),
        requested_end=date(2026, 1, 6),
        fetched_at=datetime(2026, 8, 9, tzinfo=UTC),
        adapter_version=QuantPadAdapter.version,
        parser_version=QuantPadAdapter.parser_version,
        response_sha256="a" * 64,
        response_bytes=len(raw),
        row_count=result.bars.height,
        action_count=0,
        request_metadata={"endpoint": "/v1/bars", "interval": "1d"},
    )
    receipted = FetchResult(
        symbol=result.symbol,
        bars=result.bars,
        actions=[],
        identity=result.identity,
        receipt=receipt,
        raw_response=raw,
    )
    written = persist_research_fetch(receipted, tmp_path / "quantpad")
    receipt_path = written["receipt_path"]
    assert isinstance(receipt_path, Path) and receipt_path.is_file()
    saved = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert saved["research_only"] is True
    assert saved["receipt_id"] == receipt.receipt_id
    assert saved["response_sha256"] == "a" * 64
    bars_path = written["bars_path"]
    assert isinstance(bars_path, Path) and bars_path.is_file()

    unreceipted = FetchResult(symbol="AAPL", bars=result.bars, actions=[])
    with pytest.raises(DataError, match="receipt"):
        persist_research_fetch(unreceipted, tmp_path / "quantpad")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"\xff\xfe", "UTF-8 JSON"),
        (b"[]", "not a JSON object"),
        (b'{"schema_version": 1, "interval": "1m", "bars": []}', "daily-only"),
        (b'{"schema_version": 1, "interval": "1d", "bars": 3}', "not a list"),
        (
            b'{"schema_version": 1, "interval": "1d", "bars": [{"t": "x"}]}',
            "fields",
        ),
        (
            b'{"schema_version": 1, "interval": "1d", "bars": '
            b'[{"t": "not-a-date", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]}',
            "ISO-8601",
        ),
        (
            b'{"schema_version": 1, "interval": "1d", "bars": '
            b'[{"t": "2026-01-05T00:00:00+05:00", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]}',
            "not UTC",
        ),
        (
            b'{"schema_version": 1, "interval": "1d", "bars": '
            b'[{"t": "2026-01-05T00:00:00Z", "o": -1, "h": 1, "l": 1, "c": 1, "v": 1}]}',
            "positive number",
        ),
        (
            b'{"schema_version": 1, "interval": "1d", "bars": '
            b'[{"t": "2026-01-05T00:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": -1}]}',
            "non-negative",
        ),
    ],
)
def test_parser_drift_matrix_fails_loud(payload: bytes, message: str) -> None:
    with pytest.raises(DataError, match=message):
        parse_quantpad_bars(payload, "AAPL")


def test_fetch_builds_a_receipted_result_from_a_pinned_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offline transport double: the adapter hashes the exact response bytes it read."""
    import io
    import urllib.request

    raw = _csv_payload()

    class _Response(io.BytesIO):
        headers = {"X-RateLimit-Remaining": "99"}

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

    captured: dict[str, object] = {}

    def _fake_urlopen(request: urllib.request.Request, timeout: float) -> _Response:
        captured["url"] = request.full_url
        captured["api_key"] = request.get_header("X-api-key")
        captured["legacy_auth"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return _Response(raw)

    monkeypatch.setenv("QUANTPAD_API_KEY", "secret-key")
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    result = QuantPadAdapter().fetch("AAPL", date(2026, 1, 5), date(2026, 1, 6))
    assert str(captured["url"]).startswith("https://api.quantpad.ai/v1/bars?symbol=AAPL")
    assert "timeframe=1d" in str(captured["url"])
    assert "format=csv" in str(captured["url"])
    assert "start=" in str(captured["url"]) and "end=" in str(captured["url"])
    assert captured["api_key"] == "secret-key"
    assert captured["legacy_auth"] is None
    receipt = result.receipt
    assert receipt is not None
    import hashlib as _hashlib

    assert receipt.response_sha256 == _hashlib.sha256(raw).hexdigest()
    assert receipt.row_count == 2
    assert dict(receipt.request_metadata)["x-ratelimit-remaining"] == "99"
    # The secret never appears in the receipt.
    assert "secret-key" not in json.dumps(receipt.to_dict())
