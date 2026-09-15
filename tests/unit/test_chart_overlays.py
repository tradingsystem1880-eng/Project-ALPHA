"""``alpha_cli.chart_cmds`` pure helpers: spec parsing, head-only warm-up nulls, fail-loud data."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta

import pytest

from alpha_cli.chart_cmds import (
    _NAN_AFTER_WARMUP,
    PATTERNS,
    PIP_COUNT,
    IndicatorSpec,
    compute_overlays,
    indicator_series,
    parse_indicator,
    parse_pattern,
    to_ohlcv,
)
from alpha_core import Bar, DataError
from alpha_patterns import geometric_brownian_series


def _bars(n: int, *, closes: list[float] | None = None) -> list[Bar]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    out = []
    for i in range(n):
        c = closes[i] if closes else 100.0 + math.sin(i / 3.0) * 5.0 + i * 0.1
        out.append(
            Bar(
                symbol="ZZ",
                ts=start + timedelta(days=i),
                open=c - 0.2,
                high=c + 1.0,
                low=c - 1.0,
                close=c,
                volume=1000.0 + i,
            )
        )
    return out


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("sma:20", IndicatorSpec("sma", (20.0,))),
        ("EMA:50", IndicatorSpec("ema", (50.0,))),
        ("bbands:20:2.5", IndicatorSpec("bbands", (20.0, 2.5))),
        ("rsi:14", IndicatorSpec("rsi", (14.0,))),
        ("atr:14", IndicatorSpec("atr", (14.0,))),
        ("macd:12:26:9", IndicatorSpec("macd", (12.0, 26.0, 9.0))),
        ("hawkes:0.1:168", IndicatorSpec("hawkes", (0.1, 168.0))),
        ("perm_entropy:3:28", IndicatorSpec("perm_entropy", (3.0, 28.0))),
        ("reversibility:10", IndicatorSpec("reversibility", (10.0,))),
    ],
)
def test_parse_indicator_accepts_the_documented_forms(spec: str, expected: IndicatorSpec) -> None:
    assert parse_indicator(spec) == expected


@pytest.mark.parametrize(
    "spec",
    [
        "foo:2",
        "sma",
        "sma:20:3",
        "sma:abc",
        "sma:1",
        "sma:2.5",
        "bbands:20:0",
        "macd:26:12:9",
        "hawkes:0:20",  # decay must be positive
        "hawkes:0.1:1",  # the lookback is still an integer window
        "hawkes:0.1:2.5",
        "reversibility:9",  # d=3 ordinal patterns need >= 10 points
        "vg_path:1",
        "cmma:10",
    ],
)
def test_parse_indicator_rejects_bad_specs_with_a_typed_error(spec: str) -> None:
    with pytest.raises(DataError):
        parse_indicator(spec)


def test_parse_pattern_is_closed() -> None:
    assert parse_pattern("Swings") == "swings"
    with pytest.raises(DataError, match="unknown pattern"):
        parse_pattern("cups")


def test_indicator_spec_id_round_trips_params() -> None:
    assert parse_indicator("bbands:20:2").id == "bbands:20:2"
    assert parse_indicator("bbands:20:2.5").id == "bbands:20:2.5"


@pytest.mark.parametrize(
    ("spec", "warmups"),
    [
        ("sma:20", [19]),
        ("ema:20", [19]),
        ("bbands:20:2", [19, 19, 19]),
        ("rsi:14", [14]),
        ("atr:14", [13]),
        ("macd:12:26:9", [25, 33, 33]),
    ],
)
def test_warmup_is_nulled_at_the_head_only(spec: str, warmups: list[int]) -> None:
    series = to_ohlcv(_bars(80))
    rows = indicator_series(series, parse_indicator(spec))
    assert [row["warmup"] for row in rows] == warmups
    for row in rows:
        values = row["values"]
        assert len(values) == 80
        assert all(v is None for v in values[: row["warmup"]])
        assert all(isinstance(v, float) and math.isfinite(v) for v in values[row["warmup"] :])


@pytest.mark.parametrize(
    ("spec", "warmups"),
    [
        ("hawkes:0.1:20", [20]),
        ("vsa:10", [20]),
        ("runs_z:10", [10]),
        ("perm_entropy:3:4", [26]),
        ("cmma:10:14", [13]),
        ("vg_path:12", [12, 12]),
        ("reversibility:30", [29]),
        ("rsi_pc1:20", [43]),
    ],
)
def test_ported_oscillators_sit_in_their_own_pane_with_head_only_warmup(
    spec: str, warmups: list[int]
) -> None:
    series = to_ohlcv(_gbm_bars(80, seed=3))  # a smooth sine leaves reversibility undefined
    parsed = parse_indicator(spec)
    rows = indicator_series(series, parsed)
    assert [row["warmup"] for row in rows] == warmups
    for row in rows:
        assert row["pane"] == parsed.name and row["style"] == "line"
        values = row["values"]
        assert len(values) == 80
        assert all(v is None for v in values[: row["warmup"]])
        tail = values[row["warmup"] :]
        assert any(isinstance(v, float) and math.isfinite(v) for v in tail)
        if parsed.name in _NAN_AFTER_WARMUP:
            assert all(v is None or (isinstance(v, float) and math.isfinite(v)) for v in tail)
        else:
            assert all(isinstance(v, float) and math.isfinite(v) for v in tail)


def test_vg_path_publishes_the_price_and_inverse_graphs_as_two_series() -> None:
    price, inverse = indicator_series(to_ohlcv(_bars(40)), parse_indicator("vg_path:10"))
    assert (price["id"], inverse["id"]) == ("vg_path:10:price", "vg_path:10:inverse")
    assert price["name"].endswith(" price") and inverse["name"].endswith(" inverse")


def test_sma_matches_a_plain_trailing_mean() -> None:
    bars = _bars(30)
    series = to_ohlcv(bars)
    (row,) = indicator_series(series, parse_indicator("sma:5"))
    closes = [b.close for b in bars]
    assert row["values"][10] == pytest.approx(sum(closes[6:11]) / 5)
    assert row["pane"] == "price" and row["style"] == "line"


def test_bbands_are_symmetric_around_the_middle_band() -> None:
    series = to_ohlcv(_bars(40))
    upper, middle, lower = indicator_series(series, parse_indicator("bbands:10:2"))
    for i in range(9, 40):
        assert upper["values"][i] - middle["values"][i] == pytest.approx(
            middle["values"][i] - lower["values"][i]
        )


def test_short_window_fails_loud() -> None:
    series = to_ohlcv(_bars(30))
    with pytest.raises(DataError, match="needs more than 50 bars"):
        indicator_series(series, parse_indicator("sma:50"))
    with pytest.raises(DataError, match="needs more than"):
        indicator_series(series, parse_indicator("macd:12:26:9"))
    # the guard is the longest window each indicator reads, not its first parameter
    with pytest.raises(DataError, match="needs more than 99 bars"):
        indicator_series(series, parse_indicator("perm_entropy:4:4"))
    with pytest.raises(DataError, match="needs more than 34 bars"):
        indicator_series(series, parse_indicator("rsi_pc1:10"))
    with pytest.raises(DataError, match="needs more than 30 bars"):
        indicator_series(series, parse_indicator("vsa:15"))


def test_to_ohlcv_fails_on_non_finite_or_too_short() -> None:
    with pytest.raises(DataError, match=">= 2 bars"):
        to_ohlcv(_bars(1))
    bars = _bars(5)
    bad = bars[:2] + [bars[2].model_copy(update={"close": float("nan"), "low": float("nan")})]
    with pytest.raises(DataError, match="non-finite"):
        to_ohlcv(bad)


def test_pattern_annotations_are_chart_annotation_shaped_and_knowable() -> None:
    bars = _bars(120)
    body = compute_overlays(bars, [], ["swings", "trendlines", "levels"])
    assert len(body["t"]) == 120
    assert body["indicators"] == []
    rows = body["annotations"]
    assert rows, "a sine-wave series has confirmed swings"
    assert [r["annotation_id"] for r in rows] == list(range(1, len(rows) + 1))
    for row in rows:
        assert set(row) == {
            "annotation_id",
            "decision_sequence_id",
            "kind",
            "label",
            "unit",
            "reason",
            "anchors",
        }
        assert row["decision_sequence_id"] is None and row["unit"] == "price"
        for anchor in row["anchors"]:
            assert 0 <= anchor["anchor_index"] < 120
            assert anchor["ts"] == body["t"][anchor["anchor_index"]]
    swings = [r for r in rows if r["label"].startswith("Swing")]
    # A fractal swing with L=5 is only knowable 5 bars later: none sits in the last 5 bars.
    assert all(r["anchors"][0]["anchor_index"] <= 114 for r in swings)
    fibs = [r for r in rows if r["label"].startswith("Fib")]
    assert fibs and all(r["anchors"][-1]["anchor_index"] == 119 for r in fibs)


def test_no_patterns_means_no_annotations() -> None:
    assert compute_overlays(_bars(10), [], [])["annotations"] == []


def _gbm_bars(n: int, *, seed: int) -> list[Bar]:
    path = geometric_brownian_series(n, vol_per_bar=0.02, seed=seed, start=100.0)
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="ZZ",
            ts=start + timedelta(days=i),
            open=float(path.open[i]),
            high=float(path.high[i]),
            low=float(path.low[i]),
            close=float(path.close[i]),
            volume=float(path.volume[i]),
        )
        for i in range(n)
    ]


def test_ported_patterns_are_knowable_on_the_last_bar_and_name_that_bar() -> None:
    bars = _gbm_bars(400, seed=11)
    last = len(bars) - 1
    ported = [p for p in PATTERNS if p not in {"swings", "trendlines", "levels"}]
    rows = compute_overlays(bars, [], ported)["annotations"]
    kinds = {row["kind"] for row in rows}
    assert kinds <= {"line", "polyline", "marker"}
    by_prefix = {
        prefix: [r for r in rows if r["label"].startswith(prefix)]
        for prefix in ("DC ", "PIPs", "Profile level", "Bull ", "Structure L")
    }
    assert all(by_prefix.values()), {k: len(v) for k, v in by_prefix.items()}
    for row in rows:
        assert row["unit"] == "price"
        if row["kind"] == "marker":
            assert len(row["anchors"]) == 1
        else:
            assert len(row["anchors"]) >= 2
        # every reason names the bar the pattern became drawable, and it is never after --end
        (bar,) = re.findall(r"(?:from|on) bar (\d+)", row["reason"])
        assert int(bar) <= last
        assert all(0 <= a["anchor_index"] <= last for a in row["anchors"])
    (pips,) = by_prefix["PIPs"]
    assert pips["kind"] == "polyline" and len(pips["anchors"]) == PIP_COUNT
    assert pips["anchors"][-1]["anchor_index"] == last
    assert all(r["kind"] == "marker" for r in by_prefix["DC "] + by_prefix["Structure L"])
    assert all(r["kind"] == "line" for r in by_prefix["Profile level"])
    (flag,) = by_prefix["Bull "]
    assert flag["kind"] == "polyline" and len(flag["anchors"]) == 3
    assert flag["reason"].endswith("confirmed on bar 267")


def test_ported_patterns_never_draw_what_the_last_bar_cannot_confirm() -> None:
    bars = _gbm_bars(400, seed=11)
    # Standing on bar 266 the seed-11 bull flag (confirmed on bar 267) does not exist yet.
    early = compute_overlays(bars[:267], [], ["flags", "dc_extremes", "structure_levels"])
    assert not [r for r in early["annotations"] if r["label"].startswith("Bull ")]
    late = compute_overlays(bars[:268], [], ["flags", "dc_extremes", "structure_levels"])
    assert [r["reason"][-3:] for r in late["annotations"] if r["label"].startswith("Bull ")] == [
        "267"
    ]
    # a marker drawn on a shorter window is drawn identically on the longer one
    early_markers = {(r["label"], r["anchors"][0]["anchor_index"]) for r in early["annotations"]}
    late_markers = {(r["label"], r["anchors"][0]["anchor_index"]) for r in late["annotations"]}
    assert early_markers <= late_markers
