"""Coin Metrics Community catalog and reviewed on-chain metric ingestion."""

from __future__ import annotations

import math
from typing import Final, cast
from urllib.parse import urlencode

import polars as pl

from alpha_core import DataError

from ..contracts import parse_iso8601_utc
from ._wire import decode_json_object, fetch_bounded, resolve_endpoint

type QueryScalar = str | int

REVIEWED_COMMUNITY_METRICS: Final[dict[str, str]] = {
    "PriceUSD": "reference_price",
    "SplyCur": "supply",
    "TxCnt": "transactions",
    "AdrActCnt": "addresses",
    "FeeTotNtv": "fees",
    "HashRate": "network_security",
}
_ENDPOINTS: Final = {
    "catalog": (
        "/catalog-all-v2/asset-metrics",
        frozenset({"assets", "metrics", "page_size", "next_page_token"}),
    ),
    "asset_metrics": (
        "/timeseries/asset-metrics",
        frozenset(
            {
                "assets",
                "metrics",
                "frequency",
                "start_time",
                "end_time",
                "status",
                "page_size",
                "next_page_token",
            }
        ),
    ),
}


def coinmetrics_community_url(endpoint: str, params: dict[str, QueryScalar]) -> str:
    path, pairs = resolve_endpoint(
        _ENDPOINTS, endpoint, params, provider="Coin Metrics Community", max_params=8
    )
    query = urlencode(pairs).replace("%2C", ",")
    return f"https://community-api.coinmetrics.io/v4{path}" + (f"?{query}" if query else "")


def fetch_coinmetrics_community(url: str, *, timeout_seconds: int = 30) -> bytes:
    """Fetch one bounded response from the credential-free Community host."""
    if not 1 <= timeout_seconds <= 60:
        raise DataError("Coin Metrics Community timeout must be between 1 and 60 seconds")
    if not url.startswith("https://community-api.coinmetrics.io/v4/"):
        raise DataError("Coin Metrics Community request host is invalid")
    return fetch_bounded(
        url,
        provider="Coin Metrics Community",
        host_prefix="https://community-api.coinmetrics.io/v4/",
        content_types=frozenset({"application/json", "text/json"}),
        max_bytes=16 * 1024 * 1024,
        timeout_seconds=timeout_seconds,
    )


def _decode(payload: bytes) -> dict[str, object]:
    raw = decode_json_object(
        payload, provider="Coin Metrics Community", shape_message="has invalid data"
    )
    if not isinstance(raw.get("data"), list):
        raise DataError("Coin Metrics Community response has invalid data")
    return raw


def parse_asset_metric_catalog(payload: bytes) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for asset_record in cast(list[object], _decode(payload)["data"]):
        if not isinstance(asset_record, dict) or not isinstance(asset_record.get("asset"), str):
            raise DataError("Coin Metrics catalog asset is invalid")
        metrics = asset_record.get("metrics")
        if not isinstance(metrics, list):
            raise DataError("Coin Metrics catalog metrics are invalid")
        for metric_record in metrics:
            if not isinstance(metric_record, dict):
                raise DataError("Coin Metrics catalog metric is invalid")
            metric = metric_record.get("metric")
            if metric not in REVIEWED_COMMUNITY_METRICS:
                continue
            frequencies = metric_record.get("frequencies")
            if not isinstance(frequencies, list):
                raise DataError("Coin Metrics catalog frequencies are invalid")
            for frequency_record in frequencies:
                if not isinstance(frequency_record, dict) or not isinstance(
                    frequency_record.get("frequency"), str
                ):
                    raise DataError("Coin Metrics catalog frequency is invalid")
                rows.append(
                    {
                        "asset": asset_record["asset"],
                        "metric": metric,
                        "family": REVIEWED_COMMUNITY_METRICS[str(metric)],
                        "frequency": frequency_record["frequency"],
                        "min_time": frequency_record.get("min_time"),
                        "max_time": frequency_record.get("max_time"),
                    }
                )
    return pl.DataFrame(rows)


def coinmetrics_next_page_token(payload: bytes) -> str | None:
    """Return one validated Community cursor without exposing provider response text."""
    raw = _decode(payload)
    token = raw.get("next_page_token")
    if token is None:
        return None
    if not isinstance(token, str) or not token or len(token) > 1_024:
        raise DataError("Coin Metrics pagination token is invalid")
    return token


def parse_asset_metrics(
    payload: bytes, *, assets: tuple[str, ...], metrics: tuple[str, ...]
) -> pl.DataFrame:
    if (
        not assets
        or not metrics
        or any(metric not in REVIEWED_COMMUNITY_METRICS for metric in metrics)
    ):
        raise DataError("Coin Metrics requested asset or metric set is invalid")
    allowed_assets = set(assets)
    rows: list[dict[str, object]] = []
    for record in cast(list[object], _decode(payload)["data"]):
        if not isinstance(record, dict) or record.get("asset") not in allowed_assets:
            raise DataError("Coin Metrics timeseries asset is invalid")
        raw_time = record.get("time")
        if not isinstance(raw_time, str):
            raise DataError("Coin Metrics timeseries timestamp is invalid")
        timestamp = parse_iso8601_utc(raw_time, "Coin Metrics timeseries timestamp")
        for metric in metrics:
            raw_value = record.get(metric)
            value: float | None
            if raw_value is None:
                value = None
            elif isinstance(raw_value, str):
                try:
                    value = float(raw_value)
                except ValueError as exc:
                    raise DataError("Coin Metrics timeseries value is invalid") from exc
                if not math.isfinite(value):
                    raise DataError("Coin Metrics timeseries value is not finite")
            else:
                raise DataError("Coin Metrics timeseries value is invalid")
            status = record.get(f"{metric}-status")
            if status is not None and not isinstance(status, str):
                raise DataError("Coin Metrics provider status is invalid")
            rows.append(
                {
                    "asset": record["asset"],
                    "timestamp": timestamp,
                    "metric": metric,
                    "family": REVIEWED_COMMUNITY_METRICS[metric],
                    "value": value,
                    "provider_status": status,
                }
            )
    return pl.DataFrame(rows)


__all__ = [
    "REVIEWED_COMMUNITY_METRICS",
    "coinmetrics_community_url",
    "coinmetrics_next_page_token",
    "fetch_coinmetrics_community",
    "parse_asset_metric_catalog",
    "parse_asset_metrics",
]
