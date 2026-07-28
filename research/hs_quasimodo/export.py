"""Dataset export: consolidated event table, bar-level panel, per-instance paths, data dictionary.

Three artefacts, each answering a different question:

* ``events.parquet`` — one row per detected structure. The analysis table.
* ``panel.parquet`` — one row per *bar*, labelled with whether a pattern was active and with the
  same context features. This is the shape a model wants: a feature matrix with labels, rather than
  a list of hand-picked episodes.
* ``paths/<asset>_<tf>.parquet`` — the forward OHLCV window after every event. This is what makes
  the dataset durable: a new exit rule, a trailing stop, a partial take-profit can all be tested
  later without re-running detection, which is the expensive part.

Everything derives from the event shards, so this is cheap to re-run.

Run: ``python -m research.hs_quasimodo.export [--paths] [--panel]``
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import polars as pl

from alpha_patterns import atr, distance_from_low, rolling_max, rolling_min, trend_state_vwap
from research.hs_quasimodo import config as C
from research.hs_quasimodo.data import REPO_ROOT, load
from research.hs_quasimodo.detect import PANEL_DIR, PATHS_DIR
from research.hs_quasimodo.study import load_events

OUT = REPO_ROOT / C.OUT_DIR
FORWARD_BARS = 240  # forward window retained per instance


def write_events() -> pl.DataFrame:
    """Consolidate every shard into one table, with a dataset-level lookahead assertion."""
    df = load_events()
    if df.height == 0:
        print("no shards found")
        return df

    violations = 0
    for entry in C.ENTRIES:
        col = f"entry_{entry}_index"
        if col in df.columns:
            violations += df.filter(
                (pl.col(col) >= 0) & (pl.col(col) < pl.col("confirmed_index"))
            ).height
    if violations:
        raise AssertionError(
            f"{violations} events have an entry index before confirmation — lookahead leak"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    df.write_parquet(OUT / "events.parquet")
    print(f"events.parquet: {df.height:,} rows x {df.width} cols  (0 lookahead violations)")
    return df


def write_panel(df: pl.DataFrame) -> None:
    """Bar-level feature/label panel: every bar, with pattern state attached.

    ``pattern_active`` marks bars between a structure's confirmation and the end of its validity
    window — the span during which a trader watching that pattern would still be waiting for it to
    resolve. ``bars_since_confirm`` lets a model condition on how stale the signal is.
    """
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for src, tf in C.cells():
        sub = df.filter((pl.col("asset") == src.key) & (pl.col("timeframe") == tf))
        try:
            bars, prov = load(src, tf)
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP panel {src.key} {tf}: {exc}")
            continue

        n = len(bars)
        bpd = C.BARS_PER_DAY[tf]
        w90 = max(20, 90 * bpd)
        a = atr(bars, 14)

        active = np.zeros(n, dtype=bool)
        since = np.full(n, -1, dtype=np.int64)
        variant = np.array([""] * n, dtype=object)
        for row in sub.iter_rows(named=True):
            i = int(row["confirmed_index"])
            j = min(i + 250, n)
            active[i:j] = True
            since[i:j] = np.arange(0, j - i)
            variant[i:j] = row["variant"]

        panel = pl.DataFrame(
            {
                "asset": [src.key] * n,
                "timeframe": [tf] * n,
                "bar_index": np.arange(n),
                "ts": bars.ts.astype("datetime64[ms]"),
                "open": bars.open,
                "high": bars.high,
                "low": bars.low,
                "close": bars.close,
                "volume": bars.volume,
                "atr_pct": a / np.maximum(bars.close, 1e-12),
                "ret_1": np.concatenate(([np.nan], bars.close[1:] / bars.close[:-1] - 1.0)),
                "dist_from_low": distance_from_low(bars, window=w90),
                "dist_from_high": bars.close / np.maximum(rolling_max(bars.high, w90), 1e-12) - 1.0,
                "roll_low_90d": rolling_min(bars.low, w90),
                "roll_high_90d": rolling_max(bars.high, w90),
                "trend_vwap": trend_state_vwap(bars, window=w90),
                "pattern_active": active,
                "bars_since_confirm": since,
                "active_variant": [str(v) for v in variant],
            }
        )
        panel.write_parquet(PANEL_DIR / f"{src.key}_{tf}.parquet")
        written += n
    print(f"panel: {written:,} bar rows across {len(C.cells())} cells")


def write_paths(df: pl.DataFrame) -> None:
    """Forward OHLCV window per event, so any future exit rule is testable without re-detection."""
    PATHS_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for src, tf in C.cells():
        sub = df.filter((pl.col("asset") == src.key) & (pl.col("timeframe") == tf))
        if sub.height == 0:
            continue
        try:
            bars, _ = load(src, tf)
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP paths {src.key} {tf}: {exc}")
            continue

        n = len(bars)
        ids: list[str] = []
        offs: list[int] = []
        o: list[float] = []
        h: list[float] = []
        low: list[float] = []
        c: list[float] = []
        v: list[float] = []
        for row in sub.iter_rows(named=True):
            i = int(row["confirmed_index"])
            end = min(i + 1 + FORWARD_BARS, n)
            k = end - (i + 1)
            if k <= 0:
                continue
            ids.extend([row["event_id"]] * k)
            offs.extend(range(1, k + 1))
            o.extend(bars.open[i + 1 : end].tolist())
            h.extend(bars.high[i + 1 : end].tolist())
            low.extend(bars.low[i + 1 : end].tolist())
            c.extend(bars.close[i + 1 : end].tolist())
            v.extend(bars.volume[i + 1 : end].tolist())

        if ids:
            pl.DataFrame(
                {
                    "event_id": ids,
                    "bar_offset": offs,
                    "open": o,
                    "high": h,
                    "low": low,
                    "close": c,
                    "volume": v,
                }
            ).write_parquet(PATHS_DIR / f"{src.key}_{tf}.parquet")
            total += len(ids)
    print(f"paths: {total:,} forward bars ({FORWARD_BARS} per event)")


_DICT = """# Data dictionary — head & shoulders / Quasimodo dataset

Generated by `python -m research.hs_quasimodo.export`. Three artefacts under `data/hs/`.

**Provenance.** All market data comes from third-party GitHub mirrors of exchange data, because
every market-data API is egress-blocked in the environment that produced this. Each source file is
SHA-256 pinned in `research/hs_quasimodo/config.py`. Series end 2026-07-25.

**Point-in-time guarantee.** Every column is computed from bars at or before the bar it is attached
to. `confirmed_index` is the latest of the five pivot confirmation lags — the earliest bar at which
a live trader could have known the structure existed. Every `entry_*_index` is greater than
`confirmed_index`; `export.py` asserts this across the whole table and refuses to write otherwise.

## events.parquet — one row per detected structure

### Identity
| column | meaning |
|---|---|
| `event_id` | `{asset}_{timeframe}_{variant}_{head_index}` — unique, joins to `paths/` |
| `asset` / `symbol` | source key (e.g. `XRP_BITSTAMP`) and the underlying (`XRP`) |
| `timeframe` | 15m / 1h / 4h / 1d |
| `variant` | `inverse_head_shoulders`, `head_shoulders`, `bullish_quasimodo`, `bearish_quasimodo` |
| `base_variant` | the population before the Quasimodo flag was applied |
| `direction` | `bullish` (bottoming) or `bearish` (topping) |
| `config` | detector configuration label |
| `has_bos` | a break of structure occurred — this is what makes it a Quasimodo |

### Geometry
`ls_*`, `n1_*`, `head_*`, `n2_*`, `rs_*` give the bar index and price of the five anchors: left
shoulder, first neckline pivot, head, second neckline pivot, right shoulder.

| column | meaning |
|---|---|
| `head_depth` | how far the head extends beyond the shoulder mean, as a fraction |
| `shoulder_asymmetry` | \\|LS − RS\\| relative to head depth. 0 = perfectly level shoulders |
| `time_asymmetry` | shorter leg / longer leg in bars. 1 = perfectly timed |
| `neckline_slope` | N2/N1 − 1. Positive = rising neckline |
| `span_bars` | left shoulder to right shoulder |
| `confirmed_index` / `confirmed_ts` | the earliest honest decision bar |
| `bos_index` | bar of the break of structure (−1 if none) |

### Trade levels
| column | meaning |
|---|---|
| `neckline_break_index` | first close beyond the neckline |
| `neckline_at_break` | the neckline's value at that bar |
| `break_volume_ratio` | break-bar volume / trailing 20-bar mean |
| `volume_confirmed` | ratio >= 1.5 — the quoted confirmation rule, carried so it can be tested |
| `retest_index` | first return to the neckline after the break |
| `qm_entry_index` | first touch of the left-shoulder level (the Quasimodo entry) |
| `target_measured` | neckline ± (neckline − head): the measured move |
| `stop_head` / `stop_rs` | the two stop conventions: beyond the head (QM) or the right shoulder |

### Context (all point-in-time as of `confirmed_index`)
`close_at_confirm`, `atr_pct`, `trend_vwap`, `trend_ma`, `dist_from_low`, `dist_from_high`,
`overhead_bear_obs` (unmitigated bearish order blocks within 25% above), `overhead_bear_fvgs`
(unfilled bearish fair-value gaps above), `under_supply` (any overhead order block).

### Outcomes
| pattern | meaning |
|---|---|
| `fwd_{5,10,20,30,60}d` | forward return, **signed**: positive always means the pattern worked |
| `b_s{stop%}_r{R}_{days}d` | barrier outcome from confirmation: target / stop / unresolved |
| `m_{entry}_{stop}` | the measured-move trade under one entry × stop convention |
| `m_{entry}_{stop}_rr` | that convention's reward:risk — **varies per event**, so pool with care |

Entries: `confirm`, `neckline_break`, `neckline_retest`, `qm_line`. Stops: `head`, `right_shoulder`.

## panel.parquet — one row per bar
OHLCV plus `atr_pct`, `ret_1`, `dist_from_low`, `dist_from_high`, `roll_low_90d`, `roll_high_90d`,
`trend_vwap`, and the labels `pattern_active`, `bars_since_confirm`, `active_variant`. This is the
feature-matrix form: every bar, labelled, with no survivorship selection.

## paths/*.parquet — forward window per event
`event_id`, `bar_offset` (1 = the bar after confirmation), and OHLCV. 240 bars per event. Join to
`events.parquet` on `event_id` to re-test any exit rule without re-running detection.

## Reading the numbers honestly
- Compare a target-first rate against **breakeven** = 1/(1+R), never against 50%.
- Nominal `n` overstates information whenever the forward horizon exceeds the spacing between
  events. Use the effective sample size reported by `study.py`.
- `m_*_rr` differs per event, so a pooled win rate has no single breakeven — the distribution of
  R:R must be reported with it.
"""


def write_dictionary() -> None:
    (OUT / "DATA_DICTIONARY.md").write_text(_DICT)
    print(f"DATA_DICTIONARY.md: {len(_DICT.splitlines())} lines")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export the H&S/Quasimodo datasets")
    ap.add_argument("--panel", action="store_true", help="also build the bar-level panel")
    ap.add_argument("--paths", action="store_true", help="also build per-instance forward paths")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    df = write_events()
    if df.height and (args.panel or args.all):
        write_panel(df)
    if df.height and (args.paths or args.all):
        write_paths(df)
    write_dictionary()
    print(f"done in {time.time() - t0:.0f}s -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
