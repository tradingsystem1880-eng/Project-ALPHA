"""Provider-family capability projection derived from contracts and verified artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from alpha_core import DataError

from .contracts import (
    FAMILY_AUTHORITIES,
    CryptoDatasetIdentityV1,
    CryptoFamily,
    CryptoQualityReportV1,
    ProviderDatasetCapabilityV1,
    QualificationState,
)

_FREQUENCIES: Final[dict[CryptoFamily, tuple[str, ...]]] = {
    "market_bars": ("1d", "1h", "5m", "1m"),
    "trades": ("trade_events",),
    "aggregate_trades": ("aggregate_trade_events",),
    "book_snapshots": ("point_in_time_book",),
    "funding": ("funding_interval",),
    "open_interest": ("5m", "15m", "30m", "1h", "4h", "1d"),
    "long_short_ratio": ("5m", "15m", "30m", "1h", "4h", "1d"),
    "mark_bars": ("1m", "5m", "1h", "1d"),
    "index_bars": ("1m", "5m", "1h", "1d"),
    "premium_bars": ("1m", "5m", "1h", "1d"),
    "option_instruments": ("catalog_snapshot",),
    "option_quotes": ("point_in_time_chain",),
    "historical_volatility": ("1h",),
    "asset_metadata": ("catalog_snapshot",),
    "market_reference": ("point_in_time_reference",),
    "onchain_metrics": ("1d",),
    "dex_pools": ("catalog_snapshot",),
    "dex_ohlcv": ("1d", "1h", "5m", "1m"),
    "dex_transactions": ("transaction_events",),
    "comparison_bars": ("1d", "1h", "5m", "1m"),
}

_LIMITS: Final[dict[CryptoFamily, tuple[str, ...]]] = {
    "market_bars": (
        "daily_all_available",
        "hourly_prior_day_top_250",
        "one_minute_research_selected_max_50",
    ),
    "trades": ("research_window_max_50_instruments_31_days",),
    "aggregate_trades": ("research_window_max_50_instruments_31_days",),
    "book_snapshots": ("explicit_snapshot_max_1000_levels_per_side",),
    "funding": ("bybit_page_200",),
    "open_interest": ("bybit_page_200_cursor_max_100_pages",),
    "long_short_ratio": ("bybit_page_200_cursor_max_100_pages",),
    "mark_bars": ("bybit_page_1000",),
    "index_bars": ("bybit_page_1000",),
    "premium_bars": ("bybit_page_1000",),
    "option_instruments": ("bybit_page_1000_cursor_max_100_pages",),
    "option_quotes": ("hourly_all_supported_underlyings", "five_minute_top_3_by_open_interest"),
    "historical_volatility": ("window_max_30_days",),
    "asset_metadata": ("tracked_or_research_requested_details",),
    "market_reference": ("daily_paginated_market_universe",),
    "onchain_metrics": ("reviewed_community_catalog_only", "page_max_10000"),
    "dex_pools": ("daily_top_100_on_5_reviewed_networks",),
    "dex_ohlcv": ("tracked_or_case_bound_pools",),
    "dex_transactions": ("tracked_or_case_bound_pools",),
    "comparison_bars": ("diagnostic_only_no_automatic_substitution",),
}


def _state(reports: list[CryptoQualityReportV1]) -> QualificationState:
    states = {report.state for report in reports}
    for state in ("qualified", "warning", "quarantined", "unavailable"):
        if state in states:
            return state
    return "unverified"


def _bounds(
    reports: list[CryptoQualityReportV1],
) -> tuple[datetime | None, datetime | None]:
    starts = [report.observed_start for report in reports if report.observed_start is not None]
    ends = [report.observed_end for report in reports if report.observed_end is not None]
    return (min(starts) if starts else None, max(ends) if ends else None)


def project_provider_capabilities(
    manifests: tuple[dict[str, object], ...],
) -> tuple[ProviderDatasetCapabilityV1, ...]:
    """Project supported, receipt-verified, and qualified states without probing providers."""
    reports: dict[CryptoFamily, list[CryptoQualityReportV1]] = {
        family: [] for family in FAMILY_AUTHORITIES
    }
    observed_frequencies: dict[CryptoFamily, set[str]] = {
        family: set() for family in FAMILY_AUTHORITIES
    }
    for manifest in manifests:
        if manifest.get("artifact_kind") != "normalized":
            continue
        try:
            dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
            quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
        except DataError as exc:
            raise DataError("crypto capability input manifest is invalid") from exc
        if dataset.provider != FAMILY_AUTHORITIES[dataset.family]:
            continue
        reports[dataset.family].append(quality)
        observed_frequencies[dataset.family].add(dataset.frequency)

    result: list[ProviderDatasetCapabilityV1] = []
    for family, provider in FAMILY_AUTHORITIES.items():
        family_reports = reports[family]
        earliest, latest = _bounds(family_reports)
        frequencies = tuple(sorted(set(_FREQUENCIES[family]) | observed_frequencies[family]))
        result.append(
            ProviderDatasetCapabilityV1(
                provider=provider,
                family=family,
                authentication="demo_key" if provider == "coingecko" else "none",
                earliest=earliest,
                latest=latest,
                frequencies=frequencies,
                limits=_LIMITS[family],
                verification_state="receipt_verified" if family_reports else "not_verified",
                qualification_state=_state(family_reports),
            )
        )
    return tuple(result)


__all__ = ["project_provider_capabilities"]
