from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.features import (
    FEATURE_METHOD_VERSION,
    CryptoFeatureArtifactV1,
    QualifiedCryptoFrame,
    basis_features,
    funding_features,
    liquidity_features,
    onchain_features,
    open_interest_features,
    volatility_surface_features,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _dataset(family: str, market_type: str = "linear") -> CryptoDatasetIdentityV1:
    provider = {
        "dex_pools": "geckoterminal",
        "onchain_metrics": "coinmetrics",
    }.get(family, "bybit")
    return CryptoDatasetIdentityV1(
        provider=provider,
        venue=provider,
        market_type=market_type,  # type: ignore[arg-type]
        family=family,  # type: ignore[arg-type]
        instrument="BTC",
        base_asset="BTC",
        quote_asset="USDT" if market_type == "linear" else None,
        frequency="1h",
        units="native",
        timestamp_convention="interval_end_utc",
    )


def _source(
    name: str,
    family: str,
    frame: pl.DataFrame,
    marker: str,
    *,
    market_type: str = "linear",
    state: str = "qualified",
) -> QualifiedCryptoFrame:
    digest = marker * 64
    report = CryptoQualityReportV1(
        dataset_sha256=digest,
        method_version="crypto-quality-v1",
        state=state,  # type: ignore[arg-type]
        failures=(),
        warnings=() if state == "qualified" else ("review",),
        observed_start=NOW - timedelta(hours=2),
        observed_end=NOW - timedelta(hours=1),
        row_count=frame.height,
        correction_lineage=(),
    )
    return QualifiedCryptoFrame(
        name=name,
        dataset=_dataset(family, market_type),
        artifact_sha256=digest,
        quality=report,
        frame=frame,
    )


def test_funding_and_open_interest_features_bind_exact_qualified_inputs() -> None:
    timestamps = [NOW - timedelta(hours=2), NOW - timedelta(hours=1)]
    funding = _source(
        "funding",
        "funding",
        pl.DataFrame({"timestamp": timestamps, "funding_rate": [0.001, -0.0005]}),
        "a",
    )
    oi = _source(
        "open_interest",
        "open_interest",
        pl.DataFrame({"timestamp": timestamps, "open_interest": [100.0, 110.0]}),
        "b",
    )

    funding_frame, funding_artifact = funding_features(funding, available_at=NOW)
    oi_frame, oi_artifact = open_interest_features(oi, available_at=NOW)

    assert funding_frame["cumulative_funding"].to_list() == [0.001, 0.0005]
    assert funding_frame["funding_rate_change"].to_list() == [None, -0.0015]
    assert oi_frame["open_interest_change"].to_list() == [None, 10.0]
    assert oi_frame["open_interest_pct_change"].to_list() == [None, 0.1]
    assert funding_artifact.input_sha256 == (("funding", "a" * 64),)
    assert oi_artifact.available_at == NOW
    assert funding_artifact.feature_id != oi_artifact.feature_id

    changed = _source("funding", "funding", funding.frame, "c")
    _, changed_artifact = funding_features(changed, available_at=NOW)
    assert changed_artifact.feature_id != funding_artifact.feature_id


def test_basis_features_preserve_mark_index_and_reported_premium() -> None:
    timestamps = [NOW - timedelta(hours=2), NOW - timedelta(hours=1)]
    common = {"timestamp": timestamps, "category": ["linear", "linear"], "symbol": ["BTCUSDT"] * 2}
    mark = _source("mark", "mark_bars", pl.DataFrame(common | {"close": [101.0, 102.0]}), "a")
    index = _source("index", "index_bars", pl.DataFrame(common | {"close": [100.0, 100.0]}), "b")
    premium = _source(
        "premium", "premium_bars", pl.DataFrame(common | {"close": [0.009, 0.019]}), "c"
    )

    frame, artifact = basis_features(mark, index, premium, available_at=NOW)

    assert frame["mark_close"].to_list() == [101.0, 102.0]
    assert frame["index_close"].to_list() == [100.0, 100.0]
    assert frame["observed_basis"].to_list() == pytest.approx([0.01, 0.02])
    assert frame["basis_premium_difference"].to_list() == pytest.approx([0.001, 0.001])
    assert artifact.input_sha256 == (("mark", "a" * 64), ("index", "b" * 64), ("premium", "c" * 64))


def test_volatility_surface_joins_exact_option_identity_without_rewriting_greeks() -> None:
    quotes = _source(
        "quotes",
        "option_quotes",
        pl.DataFrame(
            {
                "available_at": [NOW - timedelta(minutes=5)],
                "symbol": ["BTC-30AUG26-100000-C"],
                "underlying_price": [95_000.0],
                "mark_iv": [0.55],
                "delta": [0.4],
                "gamma": [0.0001],
                "vega": [15.0],
                "theta": [-20.0],
                "open_interest": [25.0],
            }
        ),
        "d",
        market_type="option",
    )
    instruments = _source(
        "instruments",
        "option_instruments",
        pl.DataFrame(
            {
                "symbol": ["BTC-30AUG26-100000-C"],
                "delivery_time": [NOW + timedelta(days=15)],
                "strike_price": [100_000.0],
                "option_kind": ["call"],
            }
        ),
        "e",
        market_type="option",
    )

    frame, artifact = volatility_surface_features(quotes, instruments, available_at=NOW)

    assert frame.row(0, named=True)["moneyness"] == pytest.approx(100_000 / 95_000)
    assert frame.row(0, named=True)["mark_iv"] == 0.55
    assert frame.row(0, named=True)["delta"] == 0.4
    assert frame.row(0, named=True)["time_to_expiry_years"] == pytest.approx(
        (15 + 5 / (24 * 60)) / 365.25
    )
    assert artifact.input_sha256 == (("quotes", "d" * 64), ("instruments", "e" * 64))


def test_liquidity_and_onchain_features_retain_native_observations() -> None:
    pools = _source(
        "pools",
        "dex_pools",
        pl.DataFrame(
            {
                "network": ["eth"],
                "pool_address": ["0xpool"],
                "reserve_usd": [1_000_000.0],
                "h24_volume_usd": [250_000.0],
                "h24_buys": [100],
                "h24_sells": [80],
            }
        ),
        "f",
        market_type="dex",
    )
    onchain = _source(
        "onchain",
        "onchain_metrics",
        pl.DataFrame(
            {
                "asset": ["btc", "btc"],
                "timestamp": [NOW - timedelta(days=2), NOW - timedelta(days=1)],
                "metric": ["AdrActCnt", "AdrActCnt"],
                "family": ["addresses", "addresses"],
                "value": [1_000.0, 1_100.0],
            }
        ),
        "1",
        market_type="network",
    )

    liquidity, liquidity_artifact = liquidity_features(pools, available_at=NOW)
    network, network_artifact = onchain_features(onchain, available_at=NOW)

    assert liquidity.row(0, named=True)["turnover_to_reserve"] == 0.25
    assert liquidity.row(0, named=True)["buy_sell_imbalance"] == pytest.approx(20 / 180)
    assert network["value_change"].to_list() == [None, 100.0]
    assert network["value_pct_change"].to_list() == [None, 0.1]
    assert liquidity_artifact.feature_name == "liquidity"
    assert network_artifact.feature_name == "onchain_change"


def test_features_fail_closed_for_warning_hash_mismatch_and_early_availability() -> None:
    frame = pl.DataFrame({"timestamp": [NOW - timedelta(hours=1)], "funding_rate": [0.001]})
    with pytest.raises(DataError, match="exact qualified input"):
        _source("funding", "funding", frame, "a", state="warning")

    qualified = _source("funding", "funding", frame, "b")
    object.__setattr__(qualified, "artifact_sha256", "c" * 64)
    with pytest.raises(DataError, match="hash does not match"):
        funding_features(qualified, available_at=NOW)

    qualified = _source("funding", "funding", frame, "d")
    with pytest.raises(DataError, match="availability precedes"):
        funding_features(qualified, available_at=NOW - timedelta(hours=2))


def test_feature_contracts_and_input_boundary_reject_malformed_state() -> None:
    frame = pl.DataFrame({"timestamp": [NOW - timedelta(hours=1)], "funding_rate": [0.001]})
    source = _source("funding", "funding", frame, "a")
    for attribute, value, message in (
        ("name", "", "name"),
        ("artifact_sha256", "bad", "hash"),
        ("frame", pl.DataFrame(), "row count"),
    ):
        changed = _source("funding", "funding", frame, "a")
        object.__setattr__(changed, attribute, value)
        with pytest.raises(DataError, match=message):
            changed.validate()

    _, artifact = funding_features(source, available_at=NOW)
    base = {
        "feature_id": artifact.feature_id,
        "feature_name": artifact.feature_name,
        "method_version": FEATURE_METHOD_VERSION,
        "input_sha256": artifact.input_sha256,
        "available_at": NOW,
        "row_count": 1,
        "artifact_sha256": artifact.artifact_sha256,
    }
    for overrides, message in (
        ({"feature_id": "bad"}, "artifact hash"),
        ({"method_version": "future"}, "provenance"),
        ({"input_sha256": (("", "a" * 64),)}, "inputs"),
        ({"available_at": NOW.replace(tzinfo=None)}, "timezone-aware"),
        ({"row_count": 0}, "row count"),
    ):
        with pytest.raises(DataError, match=message):
            CryptoFeatureArtifactV1(**(base | overrides))  # type: ignore[arg-type]


def test_feature_derivations_reject_wrong_shape_alignment_and_numeric_boundaries() -> None:
    timestamp = NOW - timedelta(hours=1)
    missing = _source("funding", "funding", pl.DataFrame({"timestamp": [timestamp]}), "a")
    with pytest.raises(DataError, match="missing columns"):
        funding_features(missing, available_at=NOW)

    wrong_family = _source(
        "funding",
        "open_interest",
        pl.DataFrame({"timestamp": [timestamp], "funding_rate": [0.1]}),
        "b",
    )
    with pytest.raises(DataError, match="requires funding"):
        funding_features(wrong_family, available_at=NOW)

    common = {"timestamp": [timestamp], "category": ["linear"], "symbol": ["BTCUSDT"]}
    mark = _source("mark", "mark_bars", pl.DataFrame(common | {"close": [101.0]}), "c")
    index = _source("index", "index_bars", pl.DataFrame(common | {"close": [0.0]}), "d")
    premium = _source("premium", "premium_bars", pl.DataFrame(common | {"close": [0.01]}), "e")
    with pytest.raises(DataError, match="index values"):
        basis_features(mark, index, premium, available_at=NOW)

    unmatched_index = _source(
        "index",
        "index_bars",
        pl.DataFrame(common | {"symbol": ["ETHUSDT"], "close": [100.0]}),
        "f",
    )
    with pytest.raises(DataError, match="not exactly aligned"):
        basis_features(mark, unmatched_index, premium, available_at=NOW)

    zero_reserve = _source(
        "pools",
        "dex_pools",
        pl.DataFrame(
            {
                "network": ["eth"],
                "pool_address": ["0xpool"],
                "reserve_usd": [0.0],
                "h24_volume_usd": [0.0],
                "h24_buys": [0],
                "h24_sells": [0],
            }
        ),
        "1",
        market_type="dex",
    )
    with pytest.raises(DataError, match="reserve"):
        liquidity_features(zero_reserve, available_at=NOW)
