from __future__ import annotations

import json
import urllib.error
from datetime import UTC, date, datetime
from email.message import Message

import pytest

from alpha_core import ActionType, DataError
from alpha_data.adapters.tiingo_adapter import TiingoAdapter, parse_tiingo_eod


def _payload() -> bytes:
    return json.dumps(
        [
            {
                "date": "2020-08-28T00:00:00.000Z",
                "open": 500.0,
                "high": 505.0,
                "low": 498.0,
                "close": 500.0,
                "volume": 1_000_000,
                "adjOpen": 125.0,
                "adjHigh": 126.25,
                "adjLow": 124.5,
                "adjClose": 125.0,
                "adjVolume": 4_000_000,
                "divCash": 0.0,
                "splitFactor": 1.0,
            },
            {
                "date": "2020-08-31T00:00:00.000Z",
                "open": 127.0,
                "high": 131.0,
                "low": 126.0,
                "close": 129.0,
                "volume": 2_000_000,
                "adjOpen": 127.0,
                "adjHigh": 131.0,
                "adjLow": 126.0,
                "adjClose": 129.0,
                "adjVolume": 2_000_000,
                "divCash": 0.82,
                "splitFactor": 4.0,
            },
        ]
    ).encode()


def test_parse_tiingo_eod_preserves_raw_bars_actions_and_receipt() -> None:
    fetched_at = datetime(2026, 8, 3, 10, 15, tzinfo=UTC)
    result = parse_tiingo_eod(
        _payload(),
        symbol="AAPL",
        provider_symbol="AAPL",
        asset_class="stock",
        venue="XNAS",
        calendar="XNAS",
        currency="USD",
        start=date(2020, 8, 28),
        end=date(2020, 9, 1),
        fetched_at=fetched_at,
    )

    assert result.bars["close"].to_list() == [500.0, 129.0]
    assert [(action.action_type, action.ex_date) for action in result.actions] == [
        (ActionType.DIVIDEND, date(2020, 8, 31)),
        (ActionType.SPLIT, date(2020, 8, 31)),
    ]
    assert result.identity is not None
    assert result.identity.to_dict() == {
        "asset_class": "stock",
        "calendar": "XNAS",
        "currency": "USD",
        "price_basis": "raw",
        "provider": "tiingo",
        "provider_symbol": "AAPL",
        "symbol": "AAPL",
        "timeframe": "1D",
        "venue": "XNAS",
    }
    assert result.receipt is not None
    assert result.receipt.fetched_at == fetched_at
    assert result.receipt.row_count == 2
    assert result.receipt.action_count == 2
    assert result.raw_response == _payload()


def test_parse_tiingo_eod_rejects_inconsistent_adjustment_ratios() -> None:
    payload = json.loads(_payload())
    payload[0]["adjHigh"] = 200.0
    with pytest.raises(DataError, match="adjustment ratios"):
        parse_tiingo_eod(
            json.dumps(payload).encode(),
            symbol="AAPL",
            provider_symbol="AAPL",
            asset_class="stock",
            venue="XNAS",
            calendar="XNAS",
            currency="USD",
            start=date(2020, 8, 28),
            end=date(2020, 9, 1),
            fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
        )


def test_parse_tiingo_eod_rejects_nonpositive_adjusted_prices() -> None:
    payload = json.loads(_payload())
    for field in ("adjOpen", "adjHigh", "adjLow", "adjClose"):
        payload[0][field] = 0.0
    with pytest.raises(DataError, match="adjusted prices must be positive"):
        parse_tiingo_eod(
            json.dumps(payload).encode(),
            symbol="AAPL",
            provider_symbol="AAPL",
            asset_class="stock",
            venue="XNAS",
            calendar="XNAS",
            currency="USD",
            start=date(2020, 8, 28),
            end=date(2020, 9, 1),
            fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
        )


@pytest.mark.bias_guard
def test_parse_tiingo_eod_rejects_rows_outside_requested_knowledge_window() -> None:
    payload = json.loads(_payload())
    payload.append({**payload[-1], "date": "2020-09-02T00:00:00.000Z"})
    with pytest.raises(DataError, match="outside requested range"):
        parse_tiingo_eod(
            json.dumps(payload).encode(),
            symbol="AAPL",
            provider_symbol="AAPL",
            asset_class="stock",
            venue="XNAS",
            calendar="XNAS",
            currency="USD",
            start=date(2020, 8, 28),
            end=date(2020, 9, 1),
            fetched_at=datetime(2026, 8, 3, tzinfo=UTC),
        )


def test_tiingo_adapter_requires_key_without_leaking_it() -> None:
    adapter = TiingoAdapter(api_key="")
    with pytest.raises(DataError, match="ALPHA_TIINGO_API_KEY") as exc:
        adapter.fetch("AAPL", date(2020, 1, 1), date(2020, 1, 2))
    assert "secret-value" not in str(exc.value)


def test_tiingo_adapter_preserves_canonical_and_provider_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def read(self) -> bytes:
            return _payload()

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: Response())
    result = TiingoAdapter(api_key="secret-value", canonical_symbol="AAPL.XNAS").fetch(
        "AAPL", date(2020, 8, 28), date(2020, 9, 1)
    )
    assert result.symbol == "AAPL.XNAS"
    assert result.identity is not None
    assert result.identity.symbol == "AAPL.XNAS"
    assert result.identity.provider_symbol == "AAPL"


def test_tiingo_http_errors_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(request: object, timeout: int) -> None:
        del request, timeout
        raise urllib.error.HTTPError(
            "https://api.tiingo.com/tiingo/daily/AAPL/prices",
            429,
            "rate limited secret-value",
            Message(),
            None,
        )

    monkeypatch.setattr("urllib.request.urlopen", reject)
    with pytest.raises(DataError, match="HTTP 429") as exc:
        TiingoAdapter(api_key="secret-value").fetch("AAPL", date(2020, 8, 28), date(2020, 9, 1))
    assert "secret-value" not in str(exc.value)


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (b"not-json", "invalid JSON"),
        (b"[]", "no data"),
        (b"{}", "no data"),
        (b"[1]", "expected an object"),
        (json.dumps([{"date": "bad"}]).encode(), "invalid date"),
        (json.dumps([{"date": "2026-08-03"}]).encode(), "timezone-naive"),
    ],
)
def test_tiingo_parser_rejects_malformed_payloads(payload: bytes, match: str) -> None:
    with pytest.raises(DataError, match=match):
        parse_tiingo_eod(
            payload,
            symbol="AAPL",
            provider_symbol="AAPL",
            asset_class="stock",
            venue="XNAS",
            calendar="XNAS",
            currency="USD",
            start=date(2026, 8, 3),
            end=date(2026, 8, 3),
            fetched_at=datetime(2026, 8, 4, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("open", "bad", "not numeric"),
        ("open", float("nan"), "not finite"),
        ("open", 0.0, "prices must be positive"),
        ("splitFactor", 0.0, "invalid Tiingo actions"),
        ("low", 900.0, "invalid Tiingo bar"),
    ],
)
def test_tiingo_parser_rejects_invalid_numeric_rows(field: str, value: object, match: str) -> None:
    payload = json.loads(_payload())[:1]
    payload[0][field] = value
    if field == "low":
        payload[0]["adjLow"] = 225.0
    with pytest.raises(DataError, match=match):
        parse_tiingo_eod(
            json.dumps(payload).encode(),
            symbol="AAPL",
            provider_symbol="AAPL",
            asset_class="stock",
            venue="XNAS",
            calendar="XNAS",
            currency="USD",
            start=date(2020, 8, 28),
            end=date(2020, 8, 28),
            fetched_at=datetime(2026, 8, 4, tzinfo=UTC),
        )


@pytest.mark.parametrize("symbol", ["", "BAD/SYMBOL", ".."])
def test_tiingo_adapter_rejects_invalid_provider_symbols(symbol: str) -> None:
    with pytest.raises(DataError, match="invalid Tiingo symbol"):
        TiingoAdapter(api_key="secret-value").fetch(symbol, date(2026, 8, 3), date(2026, 8, 3))


def test_tiingo_adapter_rejects_range_and_canonical_symbol() -> None:
    with pytest.raises(DataError, match="precedes"):
        TiingoAdapter(api_key="secret-value").fetch("AAPL", date(2026, 8, 4), date(2026, 8, 3))
    with pytest.raises(DataError, match="invalid canonical"):
        TiingoAdapter(api_key="secret-value", canonical_symbol="../AAPL").fetch(
            "AAPL", date(2026, 8, 3), date(2026, 8, 3)
        )


@pytest.mark.parametrize(
    "error",
    [urllib.error.URLError("offline"), TimeoutError("timeout")],
)
def test_tiingo_transport_errors_are_normalized_and_redacted(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def reject(request: object, timeout: int) -> None:
        del request, timeout
        raise error

    monkeypatch.setattr("urllib.request.urlopen", reject)
    with pytest.raises(DataError, match="Tiingo transport failed") as exc:
        TiingoAdapter(api_key="secret-value").fetch("AAPL", date(2026, 8, 3), date(2026, 8, 3))
    assert "secret-value" not in str(exc.value)
