"""Synthetic Alpaca responses: no provider data or network."""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import urllib.error
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

from alpha_core import ActionType, DataError
from alpha_data.adapters.alpaca_adapter import AlpacaAdapter, parse_alpaca_daily

START = date(2024, 1, 2)
END = date(2024, 1, 3)
NOW = datetime(2024, 5, 1, 12, tzinfo=UTC)
KEY = "sentinel-private-key"
SECRET = "sentinel-private-secret"


def bar(day: int, price: float) -> dict[str, Any]:
    return dict(t=f"2024-01-{day:02d}T05:00:00Z", o=price, h=price, l=price, c=price, v=100)


def bodies() -> list[dict[str, Any]]:
    return [
        {"bars": {"SPY": [bar(2, 100)]}, "next_page_token": "raw-next", "currency": "USD"},
        {"bars": {"SPY": [bar(3, 51)]}, "next_page_token": None},
        {"bars": {"SPY": [bar(2, 50), bar(3, 51)]}, "next_page_token": None},
        {
            "corporate_actions": {
                "forward_splits": [
                    dict(symbol="SPY", ex_date="2024-01-03", old_rate=1, new_rate=2)
                ],
                "cash_dividends": [
                    dict(
                        symbol="SPY",
                        ex_date="2024-01-02",
                        rate=0.5,
                        record_date="2024-01-03",
                        payable_date="2024-01-08",
                    )
                ],
            },
            "next_page_token": None,
        },
    ]


class FakeTransport:
    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses = list(bodies() if responses is None else responses)
        self.calls: list[tuple[str, Mapping[str, str], float]] = []

    def __call__(
        self, url: str, headers: Mapping[str, str], timeout: float
    ) -> tuple[int, Mapping[str, str], bytes]:
        self.calls.append((url, headers, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            return response
        return 200, {}, json.dumps(response).encode()


def adapter(
    transport: FakeTransport, waits: list[float] | None = None, **kwargs: Any
) -> AlpacaAdapter:
    return AlpacaAdapter(
        api_key_id=KEY,
        api_secret_key=SECRET,
        transport=transport,
        sleep=(waits if waits is not None else []).append,
        clock=lambda: NOW,
        **kwargs,
    )


def envelope() -> dict[str, Any]:
    raw = adapter(FakeTransport()).fetch("SPY", START, END).raw_response
    assert raw is not None
    value: dict[str, Any] = json.loads(raw)
    return value


def replace_body(page: dict[str, Any], body: Any) -> None:
    raw = json.dumps(body).encode()
    page["body_b64"] = base64.b64encode(raw).decode()
    page["body_sha256"] = hashlib.sha256(raw).hexdigest()


def parse(value: Any) -> Any:
    return parse_alpaca_daily(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(),
        symbol="SPY",
        provider_symbol="SPY",
        asset_class="etf",
        venue="US",
        calendar="XNYS",
        currency="USD",
        start=START,
        end=END,
        fetched_at=NOW,
    )


def test_happy_path_raw_actions_receipt_replay_and_requests() -> None:
    transport = FakeTransport()
    waits: list[float] = []
    result = adapter(transport, waits, asset_class="etf").fetch("spy", START, END)
    assert result.bars["close"].to_list() == [100.0, 51.0]
    assert result.bars["ts"].to_list() == [datetime(2024, 1, d, tzinfo=UTC) for d in (2, 3)]
    dividend, split = result.actions
    assert dividend.action_type == ActionType.DIVIDEND and dividend.amount == 0.5
    assert dividend.record_date == END and dividend.pay_date == date(2024, 1, 8)
    assert split.ratio == 2 and split.action_type == ActionType.SPLIT
    assert all(a.announce_date is None and a.knowledge_is_estimated for a in result.actions)
    assert result.identity is not None and result.receipt is not None
    assert result.raw_response is not None
    assert result.identity.provider == "alpaca" and result.identity.price_basis == "raw"
    assert result.identity.asset_class == "etf"
    assert result.receipt.row_count == 2 and result.receipt.action_count == 2
    assert dict(result.receipt.request_metadata) == {
        "endpoint_bars": "/v2/stocks/bars",
        "endpoint_actions": "/v1/corporate-actions",
        "feed": "sip",
        "adjustment": "raw; split used as cross-check",
        "asof": str(END),
        "pages": "4",
    }
    assert waits == [0.35] * 3
    replay = parse(json.loads(result.raw_response))
    assert replay.bars.equals(result.bars) and replay.actions == result.actions
    assert replay.receipt == result.receipt
    assert (
        result.raw_response
        == adapter(FakeTransport(), asset_class="etf").fetch("SPY", START, END).raw_response
    )
    pages = json.loads(result.raw_response)["pages"]
    for (url, headers, timeout), page in zip(transport.calls, pages, strict=True):
        assert headers == {
            "APCA-API-KEY-ID": KEY,
            "APCA-API-SECRET-KEY": SECRET,
            "Accept": "application/json",
            "User-Agent": "Project-ALPHA/1.0",
        }
        assert timeout == 30
        assert urlsplit(url).netloc == "data.alpaca.markets"
        assert page["query"] == [list(pair) for pair in parse_qsl(urlsplit(url).query)]
    assert dict(pages[0]["query"]) == {
        "symbols": "SPY",
        "timeframe": "1Day",
        "start": str(START),
        "end": str(END),
        "adjustment": "raw",
        "feed": "sip",
        "asof": str(END),
        "currency": "USD",
        "limit": "10000",
        "sort": "asc",
    }
    assert dict(pages[-1]["query"]) == {
        "symbols": "SPY",
        "types": "forward_split,reverse_split,cash_dividend,stock_dividend,spin_off,unit_split",
        "start": str(START),
        "end": "2024-04-02",
        "limit": "1000",
        "sort": "asc",
    }
    for key in (KEY, SECRET):
        assert key not in result.raw_response.decode()
        assert key not in str(result.receipt.to_dict())


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda p: p[1]["query"].append(["page_token", "wrong"]), "continuation"),
        (lambda p: replace_body(p[1], {"bars": {}, "next_page_token": "raw-next"}), "token"),
        (lambda p: p.pop(), "missing series"),
        (lambda p: p[0].update(body_sha256="0" * 64), "hash"),
        (lambda p: replace_body(p[0], []), "object"),
        (lambda p: replace_body(p[0], {"bars": [], "next_page_token": "raw-next"}), "bars"),
        (
            lambda p: replace_body(p[0], {"bars": {"OTHER": []}, "next_page_token": "raw-next"}),
            "symbol",
        ),
        (
            lambda p: replace_body(
                p[0], {"bars": {}, "currency": "EUR", "next_page_token": "raw-next"}
            ),
            "currency",
        ),
        (lambda p: replace_body(p[0], {"bars": {}}), "next_page_token"),
        (lambda p: replace_body(p[0], {"bars": {}, "next_page_token": 123}), "next_page_token"),
    ],
)
def test_envelope_failures(change: Any, match: str) -> None:
    value = envelope()
    change(value["pages"])
    with pytest.raises(DataError, match=match):
        parse(value)


@pytest.mark.parametrize(
    "bad,match",
    [
        (bar(4, 100), "outside"),
        ({**bar(2, 100), "t": "2024-01-02T00:00:00Z"}, "midnight"),
        ({**bar(2, 100), "t": "2024-01-02T05:00:00"}, "RFC 3339"),
        ({k: v for k, v in bar(2, 100).items() if k != "v"}, "numeric"),
        ({**bar(2, 100), "c": True}, "numeric"),
        ({**bar(2, 100), "c": float("nan")}, "finite"),
        ({**bar(2, 100), "c": 0}, "positive"),
        ({**bar(2, 100), "v": -1}, "volume"),
        ({**bar(2, 100), "h": 99}, "bar"),
        (None, "object"),
    ],
)
def test_bad_bar(bad: Any, match: str) -> None:
    responses = bodies()
    responses[0]["bars"]["SPY"] = [bad]
    with pytest.raises(DataError, match=match):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)


def test_duplicate_and_descending_dates() -> None:
    for days in ((2, 2), (3, 2)):
        responses = bodies()
        responses[0]["bars"]["SPY"] = [bar(days[0], 100)]
        responses[1]["bars"]["SPY"] = [bar(days[1], 51)]
        with pytest.raises(DataError, match="duplicate|descending"):
            adapter(FakeTransport(responses)).fetch("SPY", START, END)


def test_empty_intermediate_page_is_allowed_but_empty_result_fails() -> None:
    responses = bodies()
    responses[0]["bars"] = {}
    responses[1]["bars"]["SPY"] = [bar(2, 100), bar(3, 51)]
    assert adapter(FakeTransport(responses)).fetch("SPY", START, END).bars.height == 2
    for response in responses[:3]:
        response["bars"] = {}
    with pytest.raises(DataError, match="Alpaca returned no bars for SPY 2024-01-02..2024-01-03"):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda b: b[2]["bars"]["SPY"].pop(), "session dates"),
        (lambda b: b[3]["corporate_actions"].pop("forward_splits"), "split cross-check failed"),
        (lambda b: b[0]["bars"]["SPY"].__setitem__(0, bar(2, 50)), "split cross-check failed"),
    ],
)
def test_split_cross_check(change: Any, match: str) -> None:
    responses = bodies()
    change(responses)
    with pytest.raises(DataError, match=match):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)


# Field names follow Alpaca's corporate-action schemas: spin-offs name source_symbol and
# new_symbol; unit splits name old/new/alternate symbols and carry an effective_date.
UNSUPPORTED = {
    "stock_dividends": dict(symbol="SPY", ex_date="2024-01-02", rate=0.1),
    "spin_offs": dict(source_symbol="SPY", new_symbol="NEWCO", ex_date="2024-01-02"),
    "unit_splits": dict(
        old_symbol="SPY", new_symbol="SPYU", alternate_symbol="SPYW", effective_date="2024-01-02"
    ),
}


@pytest.mark.parametrize("kind", sorted(UNSUPPORTED))
def test_unsupported_actions_refuse_symbol(kind: str) -> None:
    responses = bodies()
    responses[3]["corporate_actions"][kind] = [UNSUPPORTED[kind]]
    with pytest.raises(DataError, match=rf"{kind}.*2024-01-02.*cannot adjust"):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)


def test_spin_off_into_the_queried_symbol_does_not_refuse_it() -> None:
    responses = bodies()
    responses[3]["corporate_actions"]["spin_offs"] = [
        dict(source_symbol="PARENT", new_symbol="SPY", ex_date="2024-01-02")
    ]
    assert adapter(FakeTransport(responses)).fetch("SPY", START, END).bars.height == 2


def test_reverse_split_listed_under_its_new_symbol_is_applied() -> None:
    responses = bodies()
    actions = responses[3]["corporate_actions"]
    del actions["forward_splits"]
    actions["reverse_splits"] = [
        dict(symbol="OLD", new_symbol="SPY", ex_date="2024-01-03", old_rate=1, new_rate=2)
    ]
    (split,) = [
        a
        for a in adapter(FakeTransport(responses)).fetch("SPY", START, END).actions
        if a.action_type == ActionType.SPLIT
    ]
    assert split.ratio == 2


@pytest.mark.parametrize(
    "series,name,value",
    [
        ("bars_raw", "adjustment", "split"),
        ("bars_raw", "feed", "iex"),
        ("bars_split", "adjustment", "all"),
        ("bars_raw", "symbols", "QQQ"),
        ("bars_raw", "asof", "2024-01-02"),
        ("actions", "types", "cash_dividend"),
    ],
)
def test_envelope_query_must_match_the_adapter_request(series: str, name: str, value: str) -> None:
    value_envelope = envelope()
    page = next(p for p in value_envelope["pages"] if p["series"] == series)
    page["query"] = [[k, value if k == name else v] for k, v in page["query"]]
    with pytest.raises(DataError, match="not the adapter's request"):
        parse(value_envelope)


def test_actions_sum_dividends_and_reject_wrong_symbol_or_duplicate_split() -> None:
    responses = bodies()
    actions = responses[3]["corporate_actions"]
    actions["cash_dividends"].append(dict(actions["cash_dividends"][0]))
    result = adapter(FakeTransport(responses)).fetch("SPY", START, END)
    assert result.actions[0].amount == 0.5  # an identical repeated record counts once
    actions["cash_dividends"][1] = dict(actions["cash_dividends"][0], rate=0.25, special=True)
    result = adapter(FakeTransport(responses)).fetch("SPY", START, END)
    assert result.actions[0].amount == 0.75  # a distinct special dividend adds to the regular one
    actions["cash_dividends"][1]["payable_date"] = "2024-02-01"
    with pytest.raises(DataError, match="record or pay date"):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)
    del actions["cash_dividends"][1]
    with_id = dict(actions["cash_dividends"][0], id="ca-1")
    actions["cash_dividends"][:] = [with_id, dict(with_id, rate=0.6)]
    with pytest.raises(DataError, match="listed twice, differently"):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)
    actions["cash_dividends"][:] = [dict(with_id, id="ca-1", rate=0.5)]
    actions["forward_splits"].append(dict(actions["forward_splits"][0], new_rate=3))
    with pytest.raises(DataError, match="two splits"):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)
    actions["forward_splits"].pop()
    actions["cash_dividends"][0]["symbol"] = "OTHER"
    with pytest.raises(DataError, match="symbol"):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)


@pytest.mark.parametrize("raw", [b"{", b"null", b'{"schema":"wrong","pages":[]}'])
def test_bad_envelope(raw: bytes) -> None:
    with pytest.raises(DataError):
        parse_alpaca_daily(
            raw,
            symbol="SPY",
            provider_symbol="SPY",
            asset_class="stock",
            venue="US",
            calendar="XNYS",
            currency="USD",
            start=START,
            end=END,
            fetched_at=NOW,
        )


def test_malformed_page_json() -> None:
    value = envelope()
    page = value["pages"][0]
    page["body_b64"] = base64.b64encode(b"{").decode()
    page["body_sha256"] = hashlib.sha256(b"{").hexdigest()
    with pytest.raises(DataError, match="JSON"):
        parse(value)


@pytest.mark.parametrize(
    "status,headers,wait",
    [
        (429, {"Retry-After": "7"}, 7),
        (500, {}, 1),
        (429, {"Retry-After": "999"}, 60),
        (429, {"Retry-After": "bad", "X-RateLimit-Reset": str(int(NOW.timestamp()) + 9)}, 9),
    ],
)
def test_retries_then_success(status: int, headers: dict[str, str], wait: Any) -> None:
    transport = FakeTransport([(status, headers, b"{}"), *bodies()])
    waits: list[float] = []
    result = adapter(transport, waits).fetch("SPY", START, END)
    assert wait in waits and len(transport.calls) == 5
    assert result.receipt is not None and result.raw_response is not None
    assert result.receipt.row_count == 2
    assert len(json.loads(result.raw_response)["pages"]) == 4


@pytest.mark.parametrize("status", [401, 403, 301, 404, 429, 503])
def test_http_failures_are_redacted(status: int) -> None:
    transport = FakeTransport([(status, {}, json.dumps({"message": KEY + SECRET}).encode())] * 3)
    with pytest.raises(DataError, match=f"HTTP {status}") as caught:
        adapter(transport).fetch("SPY", START, END)
    assert KEY not in str(caught.value) and SECRET not in str(caught.value)
    assert len(transport.calls) == (3 if status in (429, 503) else 1)
    if status == 429:
        assert str(caught.value) == "Alpaca rate limit (HTTP 429) persisted after 3 attempts"
    if status == 403:
        assert "free plan" in str(caught.value)


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.URLError(KEY),
        TimeoutError(KEY),
        OSError(KEY),
        http.client.IncompleteRead(KEY.encode(), 99),
    ],
)
def test_transport_failure_redacted(failure: Exception) -> None:
    transport = FakeTransport([failure] * 3)
    with pytest.raises(DataError) as caught:
        adapter(transport).fetch("SPY", START, END)
    assert str(caught.value) == f"Alpaca transport failed: {type(failure).__name__}"
    assert caught.value.__suppress_context__
    assert len(transport.calls) == 3


@pytest.mark.parametrize("key,secret", [(None, None), ("", SECRET), (KEY, " ")])
def test_missing_credentials_before_request(
    monkeypatch: pytest.MonkeyPatch, key: str | None, secret: str | None
) -> None:
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    transport = FakeTransport()
    instance = AlpacaAdapter(api_key_id=key, api_secret_key=secret, transport=transport)
    with pytest.raises(DataError) as caught:
        instance.fetch("SPY", START, END)
    assert "APCA_API_KEY_ID" in str(caught.value) and "APCA_API_SECRET_KEY" in str(caught.value)
    assert "create a free Alpaca account" in str(caught.value)
    assert "docs/operations/alpaca-stock-data.md" in str(caught.value)
    assert not transport.calls


def test_keys_are_read_at_fetch_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    instance = AlpacaAdapter(transport=FakeTransport(), sleep=lambda _: None, clock=lambda: NOW)
    monkeypatch.setenv("APCA_API_KEY_ID", KEY)
    monkeypatch.setenv("APCA_API_SECRET_KEY", SECRET)
    assert instance.fetch("SPY", START, END).bars.height == 2


@pytest.mark.parametrize(
    "symbol,start,end,match",
    [
        ("SPY", date(2015, 12, 31), END, "2016"),
        ("SPY", START, NOW.date(), "2024-04-30"),
        ("SPY", END, START, "precedes"),
        ("", START, END, "symbol"),
        ("A/B", START, END, "symbol"),
    ],
)
def test_invalid_requests_before_transport(symbol: Any, start: Any, end: Any, match: str) -> None:
    transport = FakeTransport()
    with pytest.raises(DataError, match=match):
        adapter(transport).fetch(symbol, start, end)
    assert not transport.calls


@pytest.mark.parametrize("series", [[], {}, None, 1])
def test_malformed_series_is_a_data_error(series: Any) -> None:
    value = envelope()
    value["pages"][0]["series"] = series
    with pytest.raises(DataError, match="series"):
        parse(value)


def test_action_pagination_filters_ex_dates_and_looks_90_days_past_the_end() -> None:
    responses = bodies()
    responses[3]["next_page_token"] = "actions-next"
    responses.append(
        {
            "corporate_actions": {"stock_dividends": [{"symbol": "SPY", "ex_date": "2024-01-04"}]},
            "next_page_token": None,
        }
    )
    transport = FakeTransport(responses)
    instance = AlpacaAdapter(
        api_key_id=KEY,
        api_secret_key=SECRET,
        transport=transport,
        sleep=lambda _: None,
        clock=lambda: datetime(2024, 1, 5, 2, tzinfo=UTC),
    )
    result = instance.fetch("SPY", START, END)
    assert len(result.actions) == 2
    # Not capped at the latest session: a dividend's process (pay) date can be weeks after its
    # ex-date, and ex-dates after the requested end are dropped by the parser.
    assert dict(parse_qsl(urlsplit(transport.calls[-1][0]).query))["end"] == "2024-04-02"
    assert dict(parse_qsl(urlsplit(transport.calls[-1][0]).query))["page_token"] == "actions-next"
    assert result.raw_response is not None
    assert parse(json.loads(result.raw_response)).actions == result.actions


@pytest.mark.parametrize(
    "field,value",
    [
        ("old_rate", 0),
        ("new_rate", -1),
        ("new_rate", 1),
        ("new_rate", float("inf")),
        ("old_rate", True),
    ],
)
def test_invalid_split_rates(field: str, value: Any) -> None:
    responses = bodies()
    responses[-1]["corporate_actions"]["forward_splits"][0][field] = value
    with pytest.raises(DataError):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rate", 0),
        ("rate", -1),
        ("rate", True),
        ("rate", float("nan")),
        ("currency", "EUR"),
        ("ex_date", "bad"),
        ("record_date", "bad"),
        ("payable_date", "bad"),
    ],
)
def test_invalid_dividends(field: str, value: Any) -> None:
    responses = bodies()
    responses[-1]["corporate_actions"]["cash_dividends"][0][field] = value
    with pytest.raises(DataError):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)


def test_reverse_split() -> None:
    responses = bodies()
    responses[0]["bars"]["SPY"] = [bar(2, 25)]
    actions = responses[-1]["corporate_actions"]
    actions.pop("forward_splits")
    actions["reverse_splits"] = [dict(symbol="SPY", ex_date="2024-01-03", old_rate=2, new_rate=1)]
    result = adapter(FakeTransport(responses)).fetch("SPY", START, END)
    assert result.actions[-1].ratio == 0.5


def test_page_cap_stops_even_empty_continuing_pages() -> None:
    transport = FakeTransport([{"bars": {}, "next_page_token": f"page-{n}"} for n in range(201)])
    with pytest.raises(DataError, match="200 pages"):
        adapter(transport).fetch("SPY", START, END)
    assert len(transport.calls) == 200


def test_page_size_cap() -> None:
    transport = FakeTransport([(200, {}, b" " * (32 * 1024 * 1024 + 1))])
    with pytest.raises(DataError, match="32 MiB"):
        adapter(transport).fetch("SPY", START, END)
    assert len(transport.calls) == 1


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_default_transport_refuses_redirect_and_closes_response(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    import io
    import urllib.request
    import urllib.response
    from email.message import Message

    requests: list[Any] = []
    streams: list[Any] = []

    class FakeHTTPS(urllib.request.HTTPSHandler):
        def https_open(self, request: Any) -> Any:
            requests.append(request)
            headers = Message()
            headers["Location"] = "https://elsewhere.invalid/steal"
            stream = io.BytesIO(b"{}")
            streams.append(stream)
            response = urllib.response.addinfourl(stream, headers, request.full_url, code)
            response.msg = "Redirect"  # type: ignore[attr-defined]
            return response

    build = urllib.request.build_opener
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: build(urllib.request.ProxyHandler({}), FakeHTTPS(), *handlers),
    )
    instance = AlpacaAdapter(api_key_id=KEY, api_secret_key=SECRET, clock=lambda: NOW)
    with pytest.raises(DataError, match=f"HTTP {code}"):
        instance.fetch("SPY", START, END)
    assert len(requests) == 1 and requests[0].host == "data.alpaca.markets"
    assert all(stream.closed for stream in streams)


def test_default_transport_limits_reads_and_closes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib.request
    from unittest.mock import Mock

    class Response:
        status = 200
        headers: dict[str, str] = {}

        def __init__(self) -> None:
            self.closed = False
            self.read_sizes: list[int] = []

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *args: Any) -> None:
            self.closed = True

        def read(self, size: int) -> bytes:
            self.read_sizes.append(size)
            return b" " * size

    response = Response()
    monkeypatch.setattr(
        urllib.request, "build_opener", lambda *args: Mock(open=lambda *a, **kw: response)
    )
    instance = AlpacaAdapter(api_key_id=KEY, api_secret_key=SECRET, clock=lambda: NOW)
    with pytest.raises(DataError, match="32 MiB"):
        instance.fetch("SPY", START, END)
    assert response.read_sizes == [32 * 1024 * 1024 + 1] and response.closed


def test_summer_midnight_uses_new_york_dst() -> None:
    responses = bodies()
    for response in responses[:3]:
        for item in response["bars"]["SPY"]:
            item["t"] = item["t"].replace("01-", "07-").replace("T05", "T04")
    for entries in responses[-1]["corporate_actions"].values():
        for item in entries:
            item["ex_date"] = item["ex_date"].replace("01-", "07-")
    instance = AlpacaAdapter(
        api_key_id=KEY,
        api_secret_key=SECRET,
        transport=FakeTransport(responses),
        sleep=lambda _: None,
        clock=lambda: datetime(2024, 11, 1, tzinfo=UTC),
    )
    result = instance.fetch("SPY", date(2024, 7, 2), date(2024, 7, 3))
    assert result.bars["ts"].to_list() == [datetime(2024, 7, day, tzinfo=UTC) for day in (2, 3)]


def test_submicrosecond_timestamp_is_not_exact_midnight() -> None:
    responses = bodies()
    responses[0]["bars"]["SPY"][0]["t"] = "2024-01-02T05:00:00.0000001Z"
    with pytest.raises(DataError, match="midnight"):
        adapter(FakeTransport(responses)).fetch("SPY", START, END)


@pytest.mark.parametrize(
    "secret", ["sentinel private", "sentinel\rprivate", "sentinel\nx", "séntinel"]
)
def test_credentials_with_inner_breaks_spaces_or_non_ascii_fail_without_echoing(
    secret: str,
) -> None:
    transport = FakeTransport()
    with pytest.raises(DataError, match="APCA_API_SECRET_KEY holds characters") as caught:
        AlpacaAdapter(
            api_key_id=KEY, api_secret_key=secret, transport=transport, clock=lambda: NOW
        ).fetch("SPY", START, END)
    assert "sentinel" not in str(caught.value).replace("Alpaca", "")
    assert transport.calls == []


def test_credentials_are_stripped_before_use() -> None:
    transport = FakeTransport()
    AlpacaAdapter(
        api_key_id=KEY + "\n",
        api_secret_key=SECRET + "\r\n",
        transport=transport,
        sleep=lambda _: None,
        clock=lambda: NOW,
    ).fetch("SPY", START, END)
    assert transport.calls[0][1]["APCA-API-SECRET-KEY"] == SECRET
    assert transport.calls[0][1]["APCA-API-KEY-ID"] == KEY


def test_header_value_errors_become_redacted_data_errors() -> None:
    def refusing(
        url: str, headers: Mapping[str, str], timeout: float
    ) -> tuple[int, dict[str, str], bytes]:
        raise ValueError(f"Invalid header value {headers['APCA-API-SECRET-KEY']!r}")

    with pytest.raises(DataError, match="transport failed: ValueError") as caught:
        AlpacaAdapter(
            api_key_id=KEY,
            api_secret_key=SECRET,
            transport=refusing,
            sleep=lambda _: None,
            clock=lambda: NOW,
        ).fetch("SPY", START, END)
    assert SECRET not in str(caught.value) and caught.value.__cause__ is None
