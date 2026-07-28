"""Sharded, resumable detection and event-row construction.

One parquet shard per ``(asset, timeframe, variant)``. Cells already on disk are skipped, so an
interrupted run resumes instead of restarting — at 15-minute resolution a full pass is ~20 minutes
of pure Python swing search, which is long enough that losing it to a timeout would matter.

Each row is a complete description of one detected structure: what it looked like, where in the
market it appeared, and what happened next under every trade convention the literature proposes.
The point of carrying all of them per event is that entry/stop choice can then be compared
*within* the same population rather than across separately-detected ones.

Run: ``python -m research.hs_quasimodo.detect [--tf 4h] [--asset XRP] [--force]``
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import polars as pl

from alpha_patterns import (
    OHLCV,
    HSConfig,
    HSEvent,
    atr,
    detect_head_shoulders,
    distance_from_low,
    find_fair_value_gaps,
    find_order_blocks,
    rolling_max,
    rolling_min,
    trend_state_ma,
    trend_state_vwap,
)
from alpha_validation import barrier_outcome
from research.hs_quasimodo import config as C
from research.hs_quasimodo.data import REPO_ROOT, iso_of, load

EVENTS_DIR = REPO_ROOT / C.OUT_DIR / "events"
PATHS_DIR = REPO_ROOT / C.OUT_DIR / "paths"
PANEL_DIR = REPO_ROOT / C.OUT_DIR / "panel"


def _context_block(bars: OHLCV, timeframe: str) -> dict[str, object]:
    """Per-bar market context, computed once per cell and indexed into per event.

    The 90-day windows are expressed in bars so they mean the same span at every timeframe — a
    90-bar lookback would be three months on daily bars and one day on 15-minute bars.
    """
    bpd = C.BARS_PER_DAY[timeframe]
    w90 = max(20, 90 * bpd)
    a = atr(bars, 14)
    return {
        "atr": a,
        "atr_pct": a / np.maximum(bars.close, 1e-12),
        "trend_vwap": trend_state_vwap(bars, window=w90),
        "trend_ma": trend_state_ma(bars, fast=max(10, 2 * bpd), slow=max(30, 8 * bpd)),
        "dist_low": distance_from_low(bars, window=w90),
        "roll_low": rolling_min(bars.low, w90),
        "roll_high": rolling_max(bars.high, w90),
        "order_blocks": find_order_blocks(bars),
        "fvgs": find_fair_value_gaps(bars),
    }


def _overhead_supply(ctx: dict[str, object], index: int, price: float) -> tuple[int, int]:
    """Unmitigated bearish order blocks and unfilled bearish FVGs above ``price`` at ``index``.

    Only structures formed before the bar and unresolved as of it are counted, so this is a
    point-in-time read of "how much supply is stacked overhead" — the user's actual situation.
    """
    obs = ctx["order_blocks"]
    fvgs = ctx["fvgs"]
    n_ob = sum(
        1
        for ob in obs  # type: ignore[attr-defined]
        if ob.direction == "bearish"
        and ob.index < index
        and (ob.mitigated_index < 0 or ob.mitigated_index > index)
        and price < ob.bottom < price * 1.25
    )
    n_fvg = sum(
        1
        for g in fvgs  # type: ignore[attr-defined]
        if g.direction == "bearish"
        and g.index < index
        and (g.filled_index < 0 or g.filled_index > index)
        and price < g.bottom < price * 1.25
    )
    return n_ob, n_fvg


def _entry_points(ev: HSEvent, bars: OHLCV) -> dict[str, tuple[int, float]]:
    """The four entry conventions, each as (bar index, price). ``-1`` means never triggered."""
    out: dict[str, tuple[int, float]] = {
        "confirm": (ev.confirmed_index, float(bars.close[ev.confirmed_index])),
        "neckline_break": (
            ev.neckline_break_index,
            ev.neckline_break_price if ev.neckline_break_index >= 0 else float("nan"),
        ),
        "neckline_retest": (
            ev.retest_index,
            float(bars.close[ev.retest_index]) if ev.retest_index >= 0 else float("nan"),
        ),
        "qm_line": (ev.qm_entry_index, ev.qm_entry_price),
    }
    return out


def _outcome_columns(
    ev: HSEvent, bars: OHLCV, timeframe: str, entries: dict[str, tuple[int, float]]
) -> dict[str, object]:
    """Forward returns, the barrier grid, and the pattern's own measured-move trade."""
    n = len(bars)
    bpd = C.BARS_PER_DAY[timeframe]
    long = ev.direction == "bullish"
    row: dict[str, object] = {}

    base_idx = ev.confirmed_index
    for days in C.FORWARD_HORIZONS_DAYS:
        h = days * bpd
        nxt = base_idx + h
        raw = float(bars.close[nxt] / bars.close[base_idx] - 1.0) if nxt < n else float("nan")
        # Signed so a "win" is positive for both directions — otherwise pooling flips the sign.
        row[f"fwd_{days}d"] = raw if long else -raw

    for stop_f, tgt_r, days in C.BARRIER_GRID:
        key = f"b_s{int(stop_f * 100)}_r{tgt_r:g}_{days}d"
        idx, px = entries["confirm"]
        row[key] = _barrier(bars, idx, px, stop_f, tgt_r, days * bpd, long)

    # The pattern's own trade: measured-move target against each geometric stop.
    for stop_name, stop_px in (("head", ev.stop_head), ("right_shoulder", ev.stop_rs)):
        for entry_name in C.ENTRIES:
            idx, px = entries[entry_name]
            tag = f"m_{entry_name}_{stop_name}"
            if idx < 0 or not np.isfinite(px) or idx + 1 >= n:
                row[tag] = None
                row[f"{tag}_rr"] = float("nan")
                continue
            risk = abs(px - stop_px)
            reward = abs(ev.target_measured - px)
            valid = risk > 0 and (
                (long and stop_px < px < ev.target_measured)
                or (not long and ev.target_measured < px < stop_px)
            )
            row[f"{tag}_rr"] = reward / risk if (valid and risk > 0) else float("nan")
            row[tag] = (
                _resolve(bars, idx, px, stop_px, ev.target_measured, 90 * bpd) if valid else None
            )
    return row


def _barrier(
    bars: OHLCV, idx: int, entry: float, stop_f: float, tgt_r: float, horizon: int, long: bool
) -> str | None:
    if idx < 0 or idx + 1 >= len(bars) or not np.isfinite(entry):
        return None
    sign = 1.0 if long else -1.0
    stop = entry * (1.0 - sign * stop_f)
    target = entry * (1.0 + sign * stop_f * tgt_r)
    return _resolve(bars, idx, entry, stop, target, horizon)


def _resolve(
    bars: OHLCV, idx: int, entry: float, stop: float, target: float, horizon: int
) -> str | None:
    end = min(idx + 1 + horizon, len(bars))
    if end <= idx + 1:
        return None
    try:
        return barrier_outcome(
            bars.high[idx + 1 : end],
            bars.low[idx + 1 : end],
            entry=entry,
            stop=stop,
            target=target,
        ).outcome
    except Exception:  # noqa: BLE001 — a degenerate level is a missing outcome, not a crash
        return None


def event_rows(
    bars: OHLCV, events: list[HSEvent], key: str, timeframe: str, variant: str
) -> pl.DataFrame:
    """Turn detected events into the wide event table for one cell."""
    if not events:
        return pl.DataFrame()
    ctx = _context_block(bars, timeframe)
    rows: list[dict[str, object]] = []

    for ev in events:
        i = ev.confirmed_index
        price = float(bars.close[i])
        n_ob, n_fvg = _overhead_supply(ctx, i, price)
        entries = _entry_points(ev, bars)

        row: dict[str, object] = {
            "event_id": f"{key}_{timeframe}_{variant}_{ev.head_index}",
            "asset": key,
            "symbol": ev.symbol,
            "timeframe": timeframe,
            "variant": ev.variant,
            "base_variant": variant,
            "direction": ev.direction,
            "config": ev.config_label,
            "has_bos": ev.has_bos,
            # geometry
            "ls_index": ev.ls_index,
            "ls_price": ev.ls_price,
            "n1_index": ev.n1_index,
            "n1_price": ev.n1_price,
            "head_index": ev.head_index,
            "head_price": ev.head_price,
            "n2_index": ev.n2_index,
            "n2_price": ev.n2_price,
            "rs_index": ev.rs_index,
            "rs_price": ev.rs_price,
            "confirmed_index": i,
            "confirmed_ts": iso_of(bars, i),
            "head_ts": iso_of(bars, ev.head_index),
            "head_depth": ev.head_depth,
            "shoulder_asymmetry": ev.shoulder_asymmetry,
            "time_asymmetry": ev.time_asymmetry,
            "neckline_slope": ev.neckline_slope,
            "span_bars": ev.span_bars,
            "bos_index": ev.bos_index,
            # trade levels
            "neckline_break_index": ev.neckline_break_index,
            "neckline_at_break": ev.neckline_at_break,
            "break_volume_ratio": ev.break_volume_ratio,
            "volume_confirmed": bool(ev.break_volume_ratio >= C.VOLUME_CONFIRM_MULTIPLE)
            if np.isfinite(ev.break_volume_ratio)
            else None,
            "retest_index": ev.retest_index,
            "qm_entry_index": ev.qm_entry_index,
            "target_measured": ev.target_measured,
            "stop_head": ev.stop_head,
            "stop_rs": ev.stop_rs,
            # context
            "close_at_confirm": price,
            "atr_pct": float(ctx["atr_pct"][i]),  # type: ignore[index]
            "trend_vwap": ctx["trend_vwap"][i],  # type: ignore[index]
            "trend_ma": ctx["trend_ma"][i],  # type: ignore[index]
            "dist_from_low": float(ctx["dist_low"][i]),  # type: ignore[index]
            "dist_from_high": float(price / max(float(ctx["roll_high"][i]), 1e-12) - 1.0),  # type: ignore[index]
            "overhead_bear_obs": n_ob,
            "overhead_bear_fvgs": n_fvg,
            "under_supply": n_ob > 0,
        }
        for name, (eidx, epx) in entries.items():
            row[f"entry_{name}_index"] = eidx
            row[f"entry_{name}_price"] = epx
            row[f"entry_{name}_lag"] = eidx - i if eidx >= 0 else -1
        row.update(_outcome_columns(ev, bars, timeframe, entries))
        rows.append(row)

    return pl.DataFrame(rows, strict=False)


def run_cell(src: C.Source, timeframe: str, variant: str, *, force: bool) -> int:
    """Detect one (asset, timeframe, variant) cell and write its shard. Returns the row count."""
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    out = EVENTS_DIR / f"{src.key}_{timeframe}_{variant}.parquet"
    if out.exists() and not force:
        return -1  # already done

    bars, _prov = load(src, timeframe)
    cfg = HSConfig(**C.PRIMARY[variant])  # type: ignore[arg-type]
    events = detect_head_shoulders(bars, cfg)
    df = event_rows(bars, events, src.key, timeframe, variant)
    if df.height:
        df.write_parquet(out)
    else:
        pl.DataFrame({"event_id": []}).write_parquet(out)
    return df.height


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Detect H&S / Quasimodo structures across all cells")
    ap.add_argument("--tf", nargs="*", default=None, help="restrict to these timeframes")
    ap.add_argument("--asset", nargs="*", default=None, help="restrict to these asset keys")
    ap.add_argument("--force", action="store_true", help="re-run cells already on disk")
    args = ap.parse_args(argv)

    cells = [
        (s, tf)
        for s, tf in C.cells()
        if (args.tf is None or tf in args.tf) and (args.asset is None or s.key in args.asset)
    ]
    total, done, skipped = 0, 0, 0
    t_start = time.time()

    for src, tf in cells:
        for variant in C.BASE_VARIANTS:
            t0 = time.time()
            try:
                n = run_cell(src, tf, variant, force=args.force)
            except Exception as exc:  # noqa: BLE001 — one bad cell must not kill the sweep
                print(f"  FAIL {src.key} {tf} {variant}: {type(exc).__name__}: {exc}", flush=True)
                continue
            if n < 0:
                skipped += 1
                continue
            total += n
            done += 1
            print(
                f"  {src.key:<14} {tf:<4} {variant:<24} {n:>6,} events  {time.time() - t0:>6.1f}s",
                flush=True,
            )

    print(
        f"\n{done} cells written, {skipped} skipped, {total:,} events total "
        f"in {time.time() - t_start:.0f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
