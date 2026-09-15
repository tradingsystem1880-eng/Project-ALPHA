"""``alpha chart`` — indicator and pattern overlays computed in Python over point-in-time bars.

The terminal's price chart never computes analytics in the browser (CLAUDE.md "Never draw in the
SPA"). This module reads the same ``load_bars(as_of=--end)`` window ``alpha data candles`` serves
and hands ``alpha_patterns`` the whole window, then removes everything a trader standing on the
last bar could not have known: warm-up values are nulled at the head only, swings are filtered
through ``swings_known_by``, trendlines must be confirmed (``active_from``) by the last bar, and
the Fibonacci grid is the one ``fib_levels_at`` says was drawable there. The neurotrader888 port
adds oscillators (each in its own sub-pane named after the indicator) and patterns that every
pass through their ``*_known_by(last)`` filter. Read-only; no authority.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING, Any, Literal

import typer

from alpha_core import Bar, DataError
from alpha_core.config import AlphaSettings

if TYPE_CHECKING:
    from alpha_patterns import OHLCV, Swing

chart_app = typer.Typer(help="Chart overlays (indicators, swings, trendlines, Fibonacci levels).")

PatternName = Literal[
    "swings",
    "trendlines",
    "levels",
    "dc_extremes",
    "pips",
    "market_profile",
    "harmonics",
    "flags",
    "structure_levels",
]
PATTERNS: tuple[PatternName, ...] = (
    "swings",
    "trendlines",
    "levels",
    "dc_extremes",
    "pips",
    "market_profile",
    "harmonics",
    "flags",
    "structure_levels",
)
SWING_LOOKBACK = 5
# fixed pattern parameters (documented in the reason strings; never caller-selected)
DC_SIGMA = 0.02
PIP_LOOKBACK, PIP_COUNT = 48, 5
PROFILE_LOOKBACK = 120
STRUCTURE_LEVELS, STRUCTURE_ATR = 3, 14
RSI_PC1_PERIODS = tuple(range(2, 25))
# indicators whose finite output legitimately gaps after warm-up (zero-range windows,
# all-one-sign windows, absent ordinal patterns, non-finite regression windows): NaN there
# becomes null, never an error
_NAN_AFTER_WARMUP = frozenset({"hawkes", "vsa", "runs_z", "reversibility", "rsi_pc1"})
# indicators taking a float first parameter (a decay rate), not an integer window
_FLOAT_FIRST = frozenset({"hawkes"})

# name -> (parameter count, human label)
INDICATORS: dict[str, tuple[int, str]] = {
    "sma": (1, "SMA"),
    "ema": (1, "EMA"),
    "bbands": (2, "Bollinger"),
    "rsi": (1, "RSI"),
    "atr": (1, "ATR"),
    "macd": (3, "MACD"),
    "hawkes": (2, "Hawkes vol"),
    "vsa": (1, "VSA"),
    "runs_z": (1, "Runs z"),
    "perm_entropy": (2, "Perm. entropy"),
    "cmma": (2, "CMMA"),
    "vg_path": (1, "VG path"),
    "reversibility": (1, "Reversibility"),
    "rsi_pc1": (1, "RSI PC1"),
}


@dataclass(frozen=True)
class IndicatorSpec:
    """One ``name:p1[:p2[:p3]]`` request, e.g. ``sma:20`` or ``macd:12:26:9``."""

    name: str
    params: tuple[float, ...]

    @property
    def id(self) -> str:
        return ":".join([self.name, *(_fmt(p) for p in self.params)])


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def parse_indicator(spec: str) -> IndicatorSpec:
    """Parse ``name:params``; every failure is a typed ``DataError`` naming the spec."""
    head, *rest = spec.strip().lower().split(":")
    if head not in INDICATORS:
        raise DataError(f"unknown indicator {head!r}; choose from {sorted(INDICATORS)}")
    arity, _label = INDICATORS[head]
    if len(rest) != arity:
        raise DataError(f"{head} takes {arity} parameter(s), got {len(rest)} in {spec!r}")
    try:
        params = tuple(float(p) for p in rest)
    except ValueError as exc:
        raise DataError(f"indicator parameters must be numeric: {spec!r}") from exc
    if head == "bbands":
        windows = params[:1]
    elif head in _FLOAT_FIRST:
        windows = params[1:]
    else:
        windows = params
    if any(not w.is_integer() or w < 2 for w in windows):
        raise DataError(f"indicator windows must be integers >= 2: {spec!r}")
    if head == "bbands" and params[1] <= 0:
        raise DataError(f"bbands width must be > 0: {spec!r}")
    if head in _FLOAT_FIRST and params[0] <= 0:
        raise DataError(f"{head} decay must be > 0: {spec!r}")
    if head == "reversibility" and params[0] < 10:
        raise DataError(f"reversibility window must be >= 10: {spec!r}")
    if head == "macd" and not params[0] < params[1]:
        raise DataError(f"macd fast window must be shorter than slow: {spec!r}")
    return IndicatorSpec(head, params)


def parse_pattern(spec: str) -> PatternName:
    name = spec.strip().lower()
    for known in PATTERNS:
        if name == known:
            return known
    raise DataError(f"unknown pattern {name!r}; choose from {list(PATTERNS)}")


def to_ohlcv(bars: list[Bar]) -> OHLCV:
    """The alpha_patterns series for ``bars`` (epoch-ms timestamps, fail-loud validation)."""
    import numpy as np

    from alpha_patterns import OHLCV

    if len(bars) < 2:
        raise DataError(f"overlays need >= 2 bars, got {len(bars)}")
    return OHLCV(
        ts=np.asarray([b.ts.timestamp() * 1000.0 for b in bars], dtype=np.float64),
        open=np.asarray([b.open for b in bars], dtype=np.float64),
        high=np.asarray([b.high for b in bars], dtype=np.float64),
        low=np.asarray([b.low for b in bars], dtype=np.float64),
        close=np.asarray([b.close for b in bars], dtype=np.float64),
        volume=np.asarray([b.volume for b in bars], dtype=np.float64),
        symbol=bars[0].symbol,
    )


def _series(
    id_: str,
    name: str,
    pane: str,
    values: Any,
    warmup: int,
    style: str = "line",
    *,
    nan_ok: bool = False,
) -> dict[str, Any]:
    """Null the head ``warmup`` values (partial averages, seeded recursions); fail on NaN/inf.

    ``nan_ok`` names the indicators whose statistic is legitimately undefined on some later
    windows (documented per indicator); their NaN becomes null instead of an error.
    """
    out: list[float | None] = []
    for i, raw in enumerate(values.tolist()):
        if i < warmup:
            out.append(None)
            continue
        if not math.isfinite(raw):
            if nan_ok and math.isnan(raw):
                out.append(None)
                continue
            raise DataError(f"{id_} produced a non-finite value at bar {i}")
        out.append(float(raw))
    return {"id": id_, "name": name, "pane": pane, "style": style, "values": out, "warmup": warmup}


def indicator_series(series: OHLCV, spec: IndicatorSpec) -> list[dict[str, Any]]:
    """The output series for one spec. Warm-up is nulled at the head only, never elsewhere."""
    from alpha_patterns import atr, ema, macd, rolling_mean, rolling_std, rsi

    n = len(series)
    label = INDICATORS[spec.name][1]
    p = [int(v) if float(v).is_integer() else v for v in spec.params]
    longest = _bars_needed(spec)
    if longest >= n:
        raise DataError(f"{spec.id} needs more than {longest} bars, the window has {n}")
    if spec.name in _PORTED:
        return _ported_series(series, spec, label)
    if spec.name == "sma":
        w = int(p[0])
        return [_series(spec.id, f"{label} {w}", "price", rolling_mean(series.close, w), w - 1)]
    if spec.name == "ema":
        w = int(p[0])
        return [_series(spec.id, f"{label} {w}", "price", ema(series.close, w), w - 1)]
    if spec.name == "bbands":
        w, k = int(p[0]), float(p[1])
        mid = rolling_mean(series.close, w)
        sd = rolling_std(series.close, w)
        return [
            _series(f"{spec.id}:upper", f"{label} {w} +{_fmt(k)}σ", "price", mid + k * sd, w - 1),
            _series(f"{spec.id}:middle", f"{label} {w} mid", "price", mid, w - 1),
            _series(f"{spec.id}:lower", f"{label} {w} -{_fmt(k)}σ", "price", mid - k * sd, w - 1),
        ]
    if spec.name == "rsi":
        w = int(p[0])
        return [_series(spec.id, f"{label} {w}", "rsi", rsi(series.close, w), w)]
    if spec.name == "atr":
        w = int(p[0])
        return [_series(spec.id, f"{label} {w}", "atr", atr(series, w), w - 1)]
    fast, slow, signal = (int(v) for v in p)
    out = macd(series.close, fast=fast, slow=slow, signal=signal)
    tag = f"{label} {fast}/{slow}/{signal}"
    return [
        _series(f"{spec.id}:line", f"{tag} line", "macd", out.line, slow - 1),
        _series(f"{spec.id}:signal", f"{tag} signal", "macd", out.signal, slow + signal - 2),
        _series(
            f"{spec.id}:hist",
            f"{tag} histogram",
            "macd",
            out.histogram,
            slow + signal - 2,
            "histogram",
        ),
    ]


_PORTED = frozenset(
    {"hawkes", "vsa", "runs_z", "perm_entropy", "cmma", "vg_path", "reversibility", "rsi_pc1"}
)


def _bars_needed(spec: IndicatorSpec) -> int:
    """The longest trailing window an indicator reads (the bar-count guard, per indicator)."""
    p = [int(v) if float(v).is_integer() else float(v) for v in spec.params]
    if spec.name == "macd":
        return int(p[1]) + int(p[2])
    if spec.name == "hawkes":
        return int(p[1])
    if spec.name == "vsa":
        return 2 * int(p[0])
    if spec.name == "perm_entropy":
        return math.factorial(int(p[0])) * int(p[1]) + int(p[0]) - 1
    if spec.name == "cmma":
        return max(int(p[0]), int(p[1]))
    if spec.name == "rsi_pc1":
        return int(p[0]) + max(RSI_PC1_PERIODS)
    return int(p[0])


def _ported_series(series: OHLCV, spec: IndicatorSpec, label: str) -> list[dict[str, Any]]:
    """The neurotrader888 oscillators; every one sits in a sub-pane named after the indicator."""
    import numpy as np

    from alpha_patterns import (
        cmma,
        hawkes_process,
        log_atr,
        permutation_entropy,
        rolling_perm_reversibility,
        rolling_runs_z,
        rolling_vg_shortest_path,
        rsi_matrix,
        vsa_indicator,
    )

    name, pane = spec.name, spec.name
    nan_ok = name in _NAN_AFTER_WARMUP
    p = [int(v) if float(v).is_integer() else float(v) for v in spec.params]
    tag = f"{label} {'/'.join(_fmt(v) for v in spec.params)}"
    if name == "hawkes":
        kappa, lookback = float(p[0]), int(p[1])
        with np.errstate(divide="ignore", invalid="ignore"):  # a zero-range window is NaN
            norm_range = np.log(series.high / series.low) / log_atr(series, lookback)
        values = hawkes_process(norm_range, kappa=kappa)
        return [_series(spec.id, tag, pane, values, lookback, nan_ok=nan_ok)]
    if name == "vsa":
        w = int(p[0])
        return [
            _series(
                spec.id, tag, pane, vsa_indicator(series, norm_lookback=w), 2 * w, nan_ok=nan_ok
            )
        ]
    if name == "runs_z":
        w = int(p[0])
        return [
            _series(spec.id, tag, pane, rolling_runs_z(series.close, lookback=w), w, nan_ok=nan_ok)
        ]
    if name == "perm_entropy":
        d, mult = int(p[0]), int(p[1])
        values = permutation_entropy(series.close, d=d, mult=mult)
        return [_series(spec.id, tag, pane, values, math.factorial(d) * mult + d - 1)]
    if name == "cmma":
        lookback, atr_lookback = int(p[0]), int(p[1])
        values = cmma(series, lookback=lookback, atr_lookback=atr_lookback)
        return [_series(spec.id, tag, pane, values, max(lookback, atr_lookback) - 1)]
    if name == "vg_path":
        w = int(p[0])
        pos, neg = rolling_vg_shortest_path(series.close, lookback=w)
        return [
            _series(f"{spec.id}:price", f"{tag} price", pane, pos, w),
            _series(f"{spec.id}:inverse", f"{tag} inverse", pane, neg, w),
        ]
    if name == "reversibility":
        w = int(p[0])
        values = rolling_perm_reversibility(series.close, window=w)
        return [_series(spec.id, tag, pane, values, w - 1, nan_ok=nan_ok)]
    from alpha_research import rolling_pca_scores

    w = int(p[0])
    scores = rolling_pca_scores(rsi_matrix(series.close, RSI_PC1_PERIODS), window=w, n_components=1)
    return [_series(spec.id, tag, pane, scores[:, 0], w + max(RSI_PC1_PERIODS) - 1, nan_ok=nan_ok)]


def _anchor(series: OHLCV, index: int, value: float) -> dict[str, float | int]:
    ts = float(series.ts[index] / 1000.0)
    return {"anchor_index": int(index), "ts": ts, "value": float(value)}


def _known_swings(series: OHLCV) -> list[Swing]:
    from alpha_patterns import find_swings, swings_known_by

    last = len(series) - 1
    both = find_swings(series, lookback=SWING_LOOKBACK, kind="high") + find_swings(
        series, lookback=SWING_LOOKBACK, kind="low"
    )
    return sorted(swings_known_by(both, last), key=lambda s: (s.index, s.kind))


def pattern_annotations(series: OHLCV, patterns: list[PatternName]) -> list[dict[str, Any]]:
    """``ChartAnnotation``-shaped rows for the requested patterns, all knowable on the last bar."""
    import numpy as np

    from alpha_patterns import (
        TrendlineConfig,
        build_trendlines,
        dc_known_by,
        detect_flags_pips,
        detect_harmonics,
        directional_change,
        extremes_known_by,
        fib_levels_at,
        find_pips,
        flags_known_by,
        harmonics_known_by,
        hierarchical_extremes,
        support_resistance_levels,
    )

    last = len(series) - 1
    when = datetime.fromtimestamp(series.ts[last] / 1000.0, tz=UTC).date().isoformat()
    rows: list[dict[str, Any]] = []

    def add(kind: str, label: str, reason: str, anchors: list[dict[str, float | int]]) -> None:
        rows.append(
            {
                "annotation_id": len(rows) + 1,
                "decision_sequence_id": None,
                "kind": kind,
                "label": label,
                "unit": "price",
                "reason": reason,
                "anchors": anchors,
            }
        )

    swings = _known_swings(series) if {"swings", "levels"} & set(patterns) else []
    if "swings" in patterns:
        for s in swings:
            add(
                "marker",
                f"Swing {s.kind}",
                f"fractal L={s.lookback}; knowable from bar {s.confirmed_index}",
                [_anchor(series, s.index, s.price)],
            )
    if "trendlines" in patterns:
        for line in build_trendlines(series, TrendlineConfig(lookback=SWING_LOOKBACK)):
            if line.active_from > last:
                continue  # its second anchor is not confirmed yet — a trader could not draw it
            end = min(line.retire_at, last)
            i1, i2 = line.anchor_indices
            p1, p2 = line.anchor_prices
            state = "retired" if line.retire_at <= last else "active"
            add(
                "line",
                f"Descending trendline ({line.touches} touches, {state})",
                f"{line.scale} scale; confirmed at bar {line.active_from}, "
                f"retires at {line.retire_at}",
                [
                    _anchor(series, i1, p1),
                    _anchor(series, i2, p2),
                    _anchor(series, end, line.value_at(end)),
                ],
            )
    if "dc_extremes" in patterns:
        for e in dc_known_by(directional_change(series, sigma=DC_SIGMA), last):
            add(
                "marker",
                f"DC {e.kind}",
                f"directional change sigma={DC_SIGMA}; knowable from bar {e.confirmed_index}",
                [_anchor(series, e.index, e.price)],
            )
    if "pips" in patterns:
        start = max(0, last - PIP_LOOKBACK + 1)
        idx, prices = find_pips(series.close[start : last + 1], PIP_COUNT)
        add(
            "polyline",
            f"PIPs {PIP_COUNT}",
            f"perceptually important points of the last {last + 1 - start} closes; the window "
            f"ends on bar {last} so every point is knowable there",
            [_anchor(series, start + int(i), float(v)) for i, v in zip(idx, prices, strict=True)],
        )
    if "market_profile" in patterns:
        lookback = min(PROFILE_LOOKBACK, last)
        levels = support_resistance_levels(series, lookback=lookback)[last]
        for price in [] if levels is None else levels.tolist():
            add(
                "line",
                f"Profile level {price:g}",
                f"market-profile density peak over bars {last - lookback + 1}..{last} "
                f"(drawable from bar {last})",
                [_anchor(series, last - lookback + 1, price), _anchor(series, last, price)],
            )
    if "harmonics" in patterns:
        extremes = directional_change(series, sigma=DC_SIGMA)
        scan = detect_harmonics(series, extremes)
        for h in harmonics_known_by(scan.patterns, last):
            points = [h.x, h.a, h.b, h.c, h.d]
            add(
                "polyline",
                f"{h.name} ({'bullish' if h.bullish else 'bearish'})",
                f"XABCD ratio error {h.error:.3f}; completes on bar {h.confirmed_index}",
                [_anchor(series, i, float(series.close[i])) for i in points],
            )
    if "flags" in patterns:
        for f in flags_known_by(
            detect_flags_pips(np.log(series.close), order=SWING_LOOKBACK), last
        ):
            kind = "pennant" if f.pennant else "flag"
            add(
                "polyline",
                f"{'Bull' if f.bullish else 'Bear'} {kind}",
                f"PIP flag on log closes, order={SWING_LOOKBACK}; confirmed on bar "
                f"{f.confirmed_index}",
                [
                    _anchor(series, f.base_index, math.exp(f.base_price)),
                    _anchor(series, f.tip_index, math.exp(f.tip_price)),
                    _anchor(series, f.confirmed_index, math.exp(f.confirmed_price)),
                ],
            )
    if "structure_levels" in patterns:
        tiers = hierarchical_extremes(series, levels=STRUCTURE_LEVELS, atr_lookback=STRUCTURE_ATR)
        for level, tier in enumerate(tiers):
            for x in extremes_known_by(tier, last):
                add(
                    "marker",
                    f"Structure L{level} {x.kind}",
                    f"hierarchical extreme, ATR({STRUCTURE_ATR}) reversal; knowable from bar "
                    f"{x.confirmed_index}",
                    [_anchor(series, x.index, x.price)],
                )
    if "levels" in patterns:
        grid = fib_levels_at(swings, last)
        if grid is not None:
            leg = "up" if grid.upward else "down"
            for ratio, price in sorted(grid.levels.items()):
                add(
                    "line",
                    f"Fib {_fmt(ratio)}",
                    f"retracement of the {leg} leg {grid.swing_low:g}→{grid.swing_high:g}, "
                    f"drawable from bar {grid.known_at} (as of {when})",
                    [_anchor(series, grid.known_at, price), _anchor(series, last, price)],
                )
    return rows


def compute_overlays(
    bars: list[Bar], indicators: list[IndicatorSpec], patterns: list[PatternName]
) -> dict[str, Any]:
    series = to_ohlcv(bars)
    return {
        "t": [float(v) / 1000.0 for v in series.ts.tolist()],
        "indicators": [row for spec in indicators for row in indicator_series(series, spec)],
        "annotations": pattern_annotations(series, patterns),
    }


@chart_app.command("overlays")
def overlays(
    symbol: str,
    indicator: list[str] = typer.Option(  # noqa: B008
        [],
        "--indicator",
        "-i",
        help="sma:20 | ema:50 | bbands:20:2 | rsi:14 | atr:14 | macd:12:26:9 | hawkes:0.1:168 | "
        "vsa:168 | runs_z:24 | perm_entropy:3:28 | cmma:24:168 | vg_path:12 | reversibility:30 | "
        "rsi_pc1:60",
    ),
    pattern: list[str] = typer.Option(  # noqa: B008
        [],
        "--pattern",
        "-p",
        help="swings | trendlines | levels | dc_extremes | pips | market_profile | harmonics | "
        "flags | structure_levels",
    ),
    end: str = typer.Option(None, help="as-of cutoff YYYY-MM-DD (inclusive)"),
    snapshot: str = typer.Option(None, help="snapshot id for provenance"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Indicator series and pattern annotations over the PIT candle window of SYMBOL.

    Every value is computed in Python from the same look-ahead-safe window ``alpha data candles``
    returns; nothing is knowable here that was not knowable on the last bar. Read-only.
    """
    from alpha_cli._runner import load_bars
    from alpha_cli.data_cmds import _candle_provenance

    try:
        when = datetime.combine(date.fromisoformat(end), time.max, tzinfo=UTC) if end else None
    except ValueError as exc:
        raise typer.BadParameter(f"--end must be YYYY-MM-DD: {exc}") from exc
    try:
        specs = [parse_indicator(s) for s in indicator]
        names = [parse_pattern(s) for s in pattern]
        bars, snap = load_bars(
            symbol, data_dir=AlphaSettings().data_dir, snapshot_id=snapshot, as_of=when
        )
        body = compute_overlays(bars, specs, names)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    payload = {
        "symbol": symbol,
        "snapshot_id": snap,
        "provenance": _candle_provenance(
            symbol, snapshot_id=snap, knowledge_cutoff=when or bars[-1].ts
        ),
        "authority": "none",
        **body,
    }
    if json_out:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(
            f"{symbol}: {len(body['t'])} bars, {len(body['indicators'])} series, "
            f"{len(body['annotations'])} annotations"
        )
