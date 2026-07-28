"""Classify the live XRP structure and price the trade its own geometry implies.

The general study says whether the pattern family carries information. This says what the trader is
actually looking at right now: is the June–July 2026 base a valid inverse head and shoulders, a
bullish Quasimodo, or neither — and if it qualifies, what stop and target the pattern's own rules
give, versus the hand-set 0.9990 / 1.3000.

That comparison is the point. The current stop sits 0.33% above the liquidation price, which makes
it barely a stop at all. A geometry-derived stop is either meaningfully lower — in which case it
implies a different position size — or the structure does not qualify and there is no pattern-based
case for the trade.

Run: ``python -m research.hs_quasimodo.current``
"""

from __future__ import annotations

import sys

import numpy as np

from alpha_patterns import HSConfig, detect_head_shoulders
from research.hs_quasimodo import config as C
from research.hs_quasimodo.data import iso_of, load

LOOKBACK_DAYS = 150  # window in which "the current structure" must sit


def main(argv: list[str] | None = None) -> int:
    src = next(s for s in C.SOURCES if s.key == C.PRIMARY_KEY)
    print("=" * 96)
    print("LIVE XRP STRUCTURE — classification under the H&S / Quasimodo detectors")
    print("=" * 96)
    print(
        f"position: {C.QUANTITY:,.0f} XRP @ {C.ENTRY} · {C.LEVERAGE}x isolated · "
        f"stop {C.STOP} · liq {C.LIQUIDATION} · target {C.TARGET}"
    )
    print(
        f"          R:R {C.REWARD_RISK:.2f}:1 · breakeven {C.BREAKEVEN * 100:.2f}% · "
        f"stop-to-liq buffer {C.STOP_TO_LIQ_BUFFER * 100:.2f}%"
    )

    for tf in ("4h", "1d"):
        bars, prov = load(src, tf)
        n = len(bars)
        window = LOOKBACK_DAYS * C.BARS_PER_DAY[tf]
        cutoff = max(0, n - window)
        print(
            f"\n{'-' * 96}\n{tf} — last {LOOKBACK_DAYS} days ({prov.last_ts[:10]} is the final bar)"
        )
        print("-" * 96)

        found = False
        for variant in C.BASE_VARIANTS:
            cfg = HSConfig(**C.PRIMARY[variant])  # type: ignore[arg-type]
            recent = [e for e in detect_head_shoulders(bars, cfg) if e.rs_index >= cutoff]
            for e in recent:
                found = True
                _describe(e, bars, tf)

        if not found:
            print("  No head-and-shoulders-family structure detected in this window under the")
            print("  pre-registered specification. The marked base does not qualify as an inverse")
            print("  head and shoulders at these parameters.")
            _why_not(bars, cutoff, tf)
    return 0


def _describe(e: object, bars: object, tf: str) -> None:
    ev = e  # typed loosely so this stays a reporting helper
    print(f"\n  {ev.variant.upper()}  ({'Quasimodo — BOS present' if ev.has_bos else 'no BOS'})")
    print(
        f"    left shoulder {ev.ls_price:.4f} @ {iso_of(bars, ev.ls_index)[:10]}   "
        f"head {ev.head_price:.4f} @ {iso_of(bars, ev.head_index)[:10]}   "
        f"right shoulder {ev.rs_price:.4f} @ {iso_of(bars, ev.rs_index)[:10]}"
    )
    print(
        f"    neckline {ev.n1_price:.4f} -> {ev.n2_price:.4f} (slope {ev.neckline_slope:+.2%})   "
        f"head depth {ev.head_depth:.2%}   shoulder asym {ev.shoulder_asymmetry:.2f}"
    )
    print(f"    confirmed {iso_of(bars, ev.confirmed_index)[:16]}  (bar {ev.confirmed_index})")

    entry = float(bars.close[ev.confirmed_index])
    print(f"\n    {'convention':<26} {'entry':>9} {'stop':>9} {'target':>9} {'R:R':>7} {'be%':>7}")
    for stop_name, stop_px in (("stop below head", ev.stop_head), ("stop below RS", ev.stop_rs)):
        for ename, epx in (
            ("at confirmation", entry),
            ("neckline break", ev.neckline_break_price),
            ("QM line (LS level)", ev.qm_entry_price),
        ):
            if not np.isfinite(epx) or epx <= stop_px:
                continue
            rr = (ev.target_measured - epx) / (epx - stop_px)
            # A steeply falling neckline can project a measured move BELOW the entry. That is a
            # real property of the geometry, not an error — but it is not a tradeable convention.
            if rr <= 0:
                continue
            print(
                f"    {ename + ' / ' + stop_name:<26} {epx:>9.4f} {stop_px:>9.4f} "
                f"{ev.target_measured:>9.4f} {rr:>7.2f} {100 / (1 + rr):>6.2f}%"
            )

    # Sizing only means something for the long side — the live position is a long.
    if ev.direction == "bullish" and entry > ev.stop_head:
        size = C.RISK_CAP_USDT / (entry - ev.stop_head)
        print(
            f"\n    at the 44 USDT cap with the pattern's own stop ({ev.stop_head:.4f}): "
            f"{size:,.0f} XRP (~${size * entry:,.0f}); the held position is "
            f"{C.QUANTITY / size:,.0f}x that"
        )
        # What the trader's actual entry implies once the pattern supplies the target.
        rr_live = (ev.target_measured - C.ENTRY) / (C.ENTRY - C.STOP)
        print(
            f"    their entry {C.ENTRY} with their stop {C.STOP} and the PATTERN's target "
            f"{ev.target_measured:.4f}: R:R {rr_live:.2f} (breakeven {100 / (1 + rr_live):.2f}%) "
            f"vs the {C.REWARD_RISK:.2f} they assumed"
        )


def _why_not(bars: object, cutoff: int, tf: str) -> None:
    """Show the recent swing lows so the rejection is auditable rather than a bare 'no'."""
    from alpha_patterns import find_swings

    lows = [s for s in find_swings(bars, lookback=5, kind="low") if s.index >= cutoff]
    if not lows:
        return
    print("\n    Recent confirmed swing lows in the window:")
    for s in lows[-8:]:
        print(f"      {iso_of(bars, s.index)[:10]}  {s.price:.4f}")
    if len(lows) >= 3:
        a, b, c = lows[-3], lows[-2], lows[-1]
        shape = (
            "middle LOWER than both — inverse H&S shape"
            if b.price < a.price and b.price < c.price
            else "middle NOT the lowest — not an H&S shape"
        )
        print(f"\n    Last three lows: {a.price:.4f} / {b.price:.4f} / {c.price:.4f}  -> {shape}")


if __name__ == "__main__":
    sys.exit(main())
