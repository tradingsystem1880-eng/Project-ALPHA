from __future__ import annotations

import json

import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.coinmetrics import (
    REVIEWED_COMMUNITY_METRICS,
    coinmetrics_community_url,
    coinmetrics_next_page_token,
    fetch_coinmetrics_community,
    parse_asset_metric_catalog,
    parse_asset_metrics,
)


def test_community_url_is_closed_and_never_accepts_api_keys() -> None:
    url = coinmetrics_community_url(
        "asset_metrics", {"assets": "btc", "metrics": "AdrActCnt", "frequency": "1d"}
    )
    assert url.startswith("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?")
    with pytest.raises(DataError, match="unsupported Coin Metrics"):
        coinmetrics_community_url("asset_metrics", {"api_key": "leak"})


def test_catalog_selects_only_reviewed_community_metric_families() -> None:
    payload = json.dumps(
        {
            "data": [
                {
                    "asset": "btc",
                    "metrics": [
                        {"metric": "AdrActCnt", "frequencies": [{"frequency": "1d"}]},
                        {"metric": "UnknownFutureMetric", "frequencies": [{"frequency": "1d"}]},
                    ],
                }
            ]
        }
    ).encode()
    frame = parse_asset_metric_catalog(payload)
    assert frame["metric"].to_list() == ["AdrActCnt"]
    assert "AdrActCnt" in REVIEWED_COMMUNITY_METRICS
    assert "DiffMean" not in REVIEWED_COMMUNITY_METRICS
    assert "FeeTotUSD" not in REVIEWED_COMMUNITY_METRICS
    assert coinmetrics_next_page_token(payload) is None
    assert (
        coinmetrics_next_page_token(json.dumps({"data": [], "next_page_token": "next-1"}).encode())
        == "next-1"
    )
    with pytest.raises(DataError, match="pagination token"):
        coinmetrics_next_page_token(json.dumps({"data": [], "next_page_token": ""}).encode())


def test_metric_parser_preserves_provider_status_and_null_semantics() -> None:
    payload = json.dumps(
        {
            "data": [
                {
                    "asset": "btc",
                    "time": "2026-08-14T00:00:00.000000000Z",
                    "AdrActCnt": "123",
                    "AdrActCnt-status": "reviewed",
                    "FeeTotNtv": None,
                }
            ]
        }
    ).encode()
    frame = parse_asset_metrics(payload, assets=("btc",), metrics=("AdrActCnt", "FeeTotNtv"))
    rows = {row["metric"]: row for row in frame.iter_rows(named=True)}
    assert rows["AdrActCnt"]["value"] == 123.0
    assert rows["AdrActCnt"]["provider_status"] == "reviewed"
    assert rows["FeeTotNtv"]["value"] is None


class _Response:
    def __init__(
        self,
        payload: bytes,
        mime: str = "application/json",
        url: str = "https://community-api.coinmetrics.io/v4/catalog/assets",
    ) -> None:
        self.payload = payload
        self.headers = {"Content-Type": mime}
        self.url = url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return self.payload

    def geturl(self) -> str:
        return self.url


def test_community_fetch_is_bounded_and_host_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    url = coinmetrics_community_url("catalog", {})
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: _Response(b'{"data":[]}')
    )
    assert fetch_coinmetrics_community(url) == b'{"data":[]}'
    with pytest.raises(DataError, match="timeout"):
        fetch_coinmetrics_community(url, timeout_seconds=0)
    with pytest.raises(DataError, match="host"):
        fetch_coinmetrics_community("https://example.com/v4/catalog")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(
            b'{"data":[]}', url="https://attacker.invalid/provider-data"
        ),
    )
    with pytest.raises(DataError, match="redirect host"):
        fetch_coinmetrics_community(url)
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: _Response(b"x", "text/html")
    )
    with pytest.raises(DataError, match="MIME"):
        fetch_coinmetrics_community(url)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(b"x" * (16 * 1024 * 1024 + 1)),
    )
    with pytest.raises(DataError, match="byte limit"):
        fetch_coinmetrics_community(url)
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError())
    )
    with pytest.raises(DataError, match="request failed"):
        fetch_coinmetrics_community(url)


def test_community_envelope_and_catalog_validation_fail_loud() -> None:
    with pytest.raises(DataError, match="endpoint"):
        coinmetrics_community_url("orders", {})
    with pytest.raises(DataError, match="unsupported value"):
        coinmetrics_community_url("catalog", {"page_size": True})
    for payload in (b"bad", b"[]", b"{}"):
        with pytest.raises(DataError, match="response"):
            parse_asset_metric_catalog(payload)
    invalid_records = (
        {"data": [1]},
        {"data": [{"asset": "btc", "metrics": {}}]},
        {"data": [{"asset": "btc", "metrics": [1]}]},
        {"data": [{"asset": "btc", "metrics": [{"metric": "AdrActCnt", "frequencies": {}}]}]},
        {"data": [{"asset": "btc", "metrics": [{"metric": "AdrActCnt", "frequencies": [1]}]}]},
    )
    for raw in invalid_records:
        with pytest.raises(DataError, match="catalog"):
            parse_asset_metric_catalog(json.dumps(raw).encode())


def test_community_timeseries_validation_fail_loud() -> None:
    with pytest.raises(DataError, match="requested"):
        parse_asset_metrics(b'{"data":[]}', assets=(), metrics=("AdrActCnt",))
    cases = (
        ({"data": [{"asset": "eth", "time": "2026-01-01"}]}, "asset"),
        ({"data": [{"asset": "btc", "time": 1}]}, "timestamp"),
        ({"data": [{"asset": "btc", "time": "bad"}]}, "timestamp"),
        ({"data": [{"asset": "btc", "time": "2026-01-01", "AdrActCnt": 1}]}, "value"),
        ({"data": [{"asset": "btc", "time": "2026-01-01", "AdrActCnt": "nan"}]}, "finite"),
        (
            {
                "data": [
                    {"asset": "btc", "time": "2026-01-01", "AdrActCnt": "1", "AdrActCnt-status": 1}
                ]
            },
            "status",
        ),
    )
    for raw, message in cases:
        with pytest.raises(DataError, match=message):
            parse_asset_metrics(json.dumps(raw).encode(), assets=("btc",), metrics=("AdrActCnt",))
