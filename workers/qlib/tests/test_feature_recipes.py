"""Provider-free feature version regressions on original fabricated OHLCV panels."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import polars as pl
import pytest

from alpha_qlib_worker.feature_recipes import build_features, feature_recipe_diagnostics
from alpha_qlib_worker.features import alpha158_features

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
    for version in (0, 3, True, 1.0, "2"):
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
