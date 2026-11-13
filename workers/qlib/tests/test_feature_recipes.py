"""Provider-free feature version regressions on original fabricated OHLCV panels."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import polars as pl
import pytest

from alpha_qlib_worker.feature_recipes import build_features, feature_recipe_diagnostics
from alpha_qlib_worker.features import alpha158_features
from alpha_qlib_worker.real import _normalize_features, _normalize_label

FAMILIES = ("MA", "STD", "VSTD", "RANK", "IMAX", "IMIN", "IMXD", "WVMA")
WINDOWS = (5, 10, 20, 30, 60)


def panel(kind: str = "monotonic", count: int = 65) -> pl.DataFrame:
    cycle = [10, 10, 10, 10, 10, 12, 9, 18, 6, 24, 12, 30, 15]
    volumes = [10, 10, 10, 10, 10, 20, 8, 30, 12, 40, 15, 50, 18]
    rows = []
    for i in range(count):
        close = float(10 + i if kind == "monotonic" else cycle[i % len(cycle)])
        volume = float(1000 if kind == "monotonic" else volumes[i % len(volumes)])
        if kind == "zero_volume":
            volume = 0.0
        rows.append(
            {
                "symbol": "SYNTH",
                "session_ts": datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i),
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": volume,
            }
        )
    return pl.DataFrame(rows)


def reference(raw: pl.DataFrame, window: int) -> dict[str, pd.Series]:
    """Independent pandas references, pinned to inspected Qlib 0.9.7 conventions."""
    close, high, low, volume = (raw[x].to_pandas() for x in ("close", "high", "low", "volume"))
    rolling = close.rolling(window, min_periods=1)
    imax = high.rolling(window, min_periods=1).apply(lambda x: np.argmax(x) + 1, raw=True)
    imin = low.rolling(window, min_periods=1).apply(lambda x: np.argmin(x) + 1, raw=True)
    weighted = (close / close.shift(1) - 1).abs() * volume
    return {
        "MA": rolling.mean() / close,
        "STD": rolling.std(ddof=1) / close,
        "VSTD": volume.rolling(window, min_periods=1).std(ddof=1) / (volume + 1e-12),
        "RANK": rolling.rank(method="average", pct=True),
        "IMAX": imax / window,
        "IMIN": imin / window,
        "IMXD": (imax - imin) / window,
        "WVMA": weighted.rolling(window, min_periods=1).std(ddof=1)
        / (weighted.rolling(window, min_periods=1).mean() + 1e-12),
    }


@pytest.mark.parametrize("kind", ["monotonic", "ties_irregular", "zero_volume"])
@pytest.mark.parametrize("count", [3, 65])
def test_v2_matches_pinned_conventions_and_preserves_other_columns(kind: str, count: int) -> None:
    raw = panel(kind, count)
    observed = build_features(raw, version=2)
    legacy = alpha158_features(raw)
    corrected = {f"{family}{window}" for family in FAMILIES for window in WINDOWS}
    pd.testing.assert_frame_equal(
        observed.drop(columns=sorted(corrected)),
        legacy.drop(columns=sorted(corrected)),
        check_exact=True,
    )
    for window in WINDOWS:
        for family, values in reference(raw, window).items():
            actual = observed[f"{family}{window}"].to_numpy()
            expected = values.to_numpy()
            np.testing.assert_array_equal(np.isnan(actual), np.isnan(expected))
            np.testing.assert_array_equal(np.isfinite(actual), np.isfinite(expected))
            finite = np.isfinite(expected)
            np.testing.assert_allclose(actual[finite], expected[finite], atol=1e-12, rtol=1e-12)


def test_v1_is_the_unchanged_default_and_unknown_versions_fail() -> None:
    raw = panel("ties_irregular")
    expected = alpha158_features(raw)
    pd.testing.assert_frame_equal(build_features(raw), expected, check_exact=True)
    pd.testing.assert_frame_equal(build_features(raw, version=1), expected, check_exact=True)
    for version in (0, 4, True, 1.0, "2"):
        with pytest.raises(ValueError, match="feature recipe version"):
            build_features(raw, version=version)


def test_independent_hand_computable_anchors() -> None:
    trend = build_features(panel(), version=2)
    tied = build_features(panel("ties_irregular"), version=2)
    assert trend["IMAX5"].iloc[4] == pytest.approx(1.0)
    assert trend["IMIN5"].iloc[4] == pytest.approx(0.2)
    assert trend["IMXD5"].iloc[4] == pytest.approx(0.8)
    assert trend["STD5"].iloc[4] == pytest.approx((10 / 4) ** 0.5 / 14, abs=1e-12)
    assert tied["RANK5"].iloc[4] == pytest.approx(0.6)
    assert tied["IMAX5"].iloc[4] == pytest.approx(0.2)
    assert tied["VSTD5"].iloc[5] == pytest.approx(20**0.5 / (20 + 1e-12), abs=1e-12)
    assert trend["WVMA5"].iloc[5] == pytest.approx(0.13372392712545345, abs=1e-12)
    assert trend["MA5"].iloc[0] == pytest.approx(1.0)
    assert np.isnan(trend["STD5"].iloc[0]) and not np.isnan(trend["STD5"].iloc[1])
    assert np.isnan(trend["WVMA5"].iloc[1]) and not np.isnan(trend["WVMA5"].iloc[2])


def test_v2_is_causal_and_cache_isolated_between_panels_and_symbols() -> None:
    raw = panel("ties_irregular")
    cutoff = raw["session_ts"][30]
    base = build_features(raw, version=2)
    future = raw.with_columns(
        [
            pl.when(pl.col("session_ts") > cutoff).then(pl.col(c) * 3).otherwise(pl.col(c)).alias(c)
            for c in ("open", "high", "low", "close", "volume")
        ]
    )
    altered = build_features(future, version=2)
    prefix = build_features(raw.head(31), version=2)
    pd.testing.assert_frame_equal(base.iloc[:31], altered.iloc[:31], check_exact=True)
    pd.testing.assert_frame_equal(base.iloc[:31], prefix, check_exact=True)
    changed = panel()
    assert not np.allclose(base["IMXD5"], build_features(changed, version=2)["IMXD5"])
    other = changed.with_columns(pl.lit("OTHER").alias("symbol"))
    joined = build_features(pl.concat([raw, other]), version=2)
    pd.testing.assert_frame_equal(
        joined.xs("SYNTH", level="instrument"),
        base.xs("SYNTH", level="instrument"),
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        joined.xs("OTHER", level="instrument"),
        build_features(other, version=2).xs("OTHER", level="instrument"),
        check_exact=True,
    )


def test_v2_provenance_is_explicit_and_v1_diagnostics_remain_legacy() -> None:
    original = feature_recipe_diagnostics(1)
    assert set(original) == {"name", "feature_count", "names", "vwap_source"}
    native = feature_recipe_diagnostics(2)
    detail = native["versioned_correction"]
    assert detail["version"] == 2 and detail["full_alpha158_parity"] is False
    assert len(detail["corrected_columns"]) == 40
    assert len(detail["inherited_v1_columns"]) == 118
    assert detail["upstream"]["versions"]["pyqlib"] == "0.9.7"
    assert "proxy" in native["vwap_source"]


def test_native_correction_does_not_register_providers_or_change_numpy_error_mode() -> None:
    import qlib
    from qlib.config import C
    from qlib.data import data

    assert qlib.__version__ == "0.9.7"
    assert C.registered is False
    before = np.geterr()
    build_features(panel(), version=2)
    assert np.geterr() == before
    assert C.registered is False
    assert all(
        vars(getattr(data, key)).get("_provider") is None
        for key in ("Cal", "Inst", "FeatureD", "PITD", "ExpressionD", "DatasetD", "D")
    )


def golden_panel() -> pl.DataFrame:
    """Fixed multi-symbol fabricated panel for the legacy v1/v2 golden digests."""
    rng = np.random.default_rng(20261114)
    rows = []
    start = datetime(2021, 1, 4, tzinfo=UTC)
    sessions = [start + timedelta(days=i + (i // 5) * 2) for i in range(90)]
    for k, symbol in enumerate(("AAA", "BBB", "CCC")):
        close = 40.0 + 10 * k
        for i, ts in enumerate(sessions):
            close *= float(np.exp(rng.normal(0, 0.02)))
            open_ = close * float(np.exp(rng.normal(0, 0.01)))
            high = max(open_, close) * (1 + float(rng.uniform(0, 0.02)))
            low = min(open_, close) * (1 - float(rng.uniform(0, 0.02)))
            volume = 0.0 if (k == 2 and i == 17) else float(rng.integers(1_000, 90_000))
            rows.append(
                {
                    "symbol": symbol,
                    "session_ts": ts,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
    return pl.DataFrame(rows).sort(["session_ts", "symbol"])


def frame_digest(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    digest.update(",".join(frame.columns).encode())
    digest.update(frame.index.get_level_values(0).astype("int64").to_numpy().tobytes())
    digest.update("|".join(frame.index.get_level_values(1)).encode())
    digest.update(np.ascontiguousarray(frame.to_numpy(dtype="<f8")).tobytes())
    return digest.hexdigest()


# Recorded from the pre-v3 worker (branch point 598fd98b) on golden_panel(). Stored v1/v2
# exchanges stay reproducible only while these bytes are unchanged.
GOLDEN_FEATURES = {
    1: "39af83e5a389907fcd257da3476798b28a43dfb73cb12b69f0c8500f3adcce8e",
    2: "cfcaa0bd09a2d2e00dc0ab9d5b86cc0653e30eeda773d2e82d7362ea11e1a23e",
}


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_feature_matrices_are_byte_for_byte_unchanged(version: int) -> None:
    assert frame_digest(build_features(golden_panel(), version=version)) == GOLDEN_FEATURES[version]


def test_legacy_normalisation_is_byte_for_byte_unchanged() -> None:
    features = build_features(golden_panel(), version=1)
    dates = features.index.get_level_values("datetime")
    cut = sorted(dates.unique())[60]
    train, other = features.loc[dates < cut], features.loc[dates >= cut]
    normalized_train, (normalized_other,), statistics, missing = _normalize_features(train, [other])
    assert frame_digest(normalized_train) == (
        "6e69bdeaec0f8a6a74b59510cd63d40d5cf85e2a8a869ff9a5cf82a3bc3fd46e"
    )
    assert frame_digest(normalized_other) == (
        "d27289c6630b046dec349e03b2d92b0db8df335bb922040a1413b47c81cb2de0"
    )
    assert statistics == "0c52adc34f94083f5804fb7be20bc97275b2742c655edbad7acd6ba1da0fb72d"
    assert missing == 12
    labels = pd.Series(np.sin(np.arange(len(train))), index=train.index)
    normalized = _normalize_label(
        labels, pd.Series(train.index.get_level_values("datetime"), index=train.index)
    )
    assert hashlib.sha256(normalized.to_numpy(dtype="<f8").tobytes()).hexdigest() == (
        "402ce48f5d4ce0b474a828565f910e6a565bedc3a71e5acd460b9ef93512f16b"
    )
