"""Spot vs perp: is a move real buying, or is it leveraged froth?

Open interest, funding and true CVD all need exchange APIs that are egress-blocked here. What is
available is better than nothing and, for two of those three, is close to the real thing:

**Perp premium (basis) — a genuine funding proxy, not a hand-wave.** A perpetual has no expiry, so
the funding mechanism exists precisely to drag its price back to spot. Funding is therefore a
monotone function of the perp-spot spread by construction. When the perp trades above spot, longs
are paying — the crowd is leveraged long and someone is financing it. Measuring the spread measures
the thing funding is computed from.

**Perp share of volume — the "who is driving this" measure, measured directly.** XRP's Binance perp
turns over roughly 3x its spot book. A move where that ratio spikes further is being pushed by
leverage; one where spot volume carries its weight has real buyers behind it. This is exactly the
distinction between a spot-led advance and a perp-led squeeze, and it needs no proxy at all.

**Bar-level delta — a genuinely crude CVD stand-in, and labelled as such.** True cumulative volume
delta needs trade-level data with an aggressor flag. From OHLCV the best available approximation is
to split each bar's volume by where the close sits within its range. That is a real technique and
it is also demonstrably wrong on any bar that round-trips, so :func:`delta_proxy` reports it under
a name that cannot be mistaken for the real quantity, and nothing in the study rests on it alone.

The point of all this is not description. It is to make the "perp scam pump" claim **falsifiable**:
if leverage-driven advances really do fail more often than spot-led ones, conditioning on perp share
should move the forward-return distribution. :func:`scam_pump_test` runs that comparison through the
same conditional-lift machinery, with the same overlap deflation, as every other claim in this
project.

Run: ``python -m research.xrp_pumps.flow``
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from alpha_core import DataError
from alpha_patterns import percentile_rank
from alpha_validation import conditional_lift
from research.xrp_pumps import config as C

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "data" / "cache" / "raw_github"

#: The two Binance mirrors that make the comparison possible: same asset, same venue, same 5m grid.
PAIRS: dict[str, tuple[str, str]] = {
    "XRP": ("binance_linear_XRPUSDT_5m.parquet", "binance_spot_XRPUSDT_5m.parquet"),
}

#: Trailing window for percentile ranks, in daily bars — one year of the asset's own history.
RANK_WINDOW = 365


@dataclass(frozen=True)
class FlowPanel:
    """Daily spot/perp flow measures, aligned on one timestamp grid."""

    ts: np.ndarray
    close_perp: np.ndarray
    close_spot: np.ndarray
    basis: np.ndarray  # perp/spot - 1: positive means longs are paying
    basis_pct: np.ndarray  # its trailing percentile rank
    perp_share: np.ndarray  # perp notional / (perp + spot) notional
    perp_share_pct: np.ndarray
    total_notional: np.ndarray
    delta_proxy_perp: np.ndarray  # crude CVD stand-in — see module docstring
    delta_proxy_spot: np.ndarray

    def __len__(self) -> int:
        return int(self.ts.size)

    def date(self, i: int) -> str:
        return str(np.datetime64(int(self.ts[i]), "ms"))[:10]


def delta_proxy(
    open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray
) -> np.ndarray:
    """Signed volume approximated from the close's position in the bar range.

    ``2 * (close - low) / (high - low) - 1`` maps a close at the low to -1 and at the high to +1,
    scaled by volume. This is the standard OHLCV stand-in for volume delta and it is **not** CVD:
    a bar that rallies hard then gives it all back closes mid-range and scores ~0, when the true
    aggressor flow may have been enormous in both directions. Zero-range bars score 0.

    It is included because its *direction* over many bars is still informative, and excluded from
    any headline claim because its magnitude is not trustworthy.
    """
    span = high - low
    with np.errstate(divide="ignore", invalid="ignore"):
        position = np.where(
            span > 0, 2.0 * (close - low) / np.where(span > 0, span, 1.0) - 1.0, 0.0
        )
    return np.asarray(position * volume)


def _daily(path: Path) -> pl.DataFrame:
    """Aggregate a 5-minute parquet to daily OHLCV plus notional turnover."""
    if not path.exists():
        raise DataError(f"{path} is absent — this analysis needs the cached 5m mirrors")
    return (
        pl.read_parquet(path)
        .with_columns(pl.from_epoch("timestamp", time_unit="ms").alias("ts"))
        .sort("ts")
        .group_by_dynamic("ts", every="1d", closed="left")
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
            pl.col("volume_usd").sum().alias("notional"),
        )
        .drop_nulls()
    )


def load_flow(symbol: str = "XRP") -> FlowPanel:
    """Align the spot and perp mirrors and derive the flow measures."""
    if symbol not in PAIRS:
        raise DataError(f"no spot/perp pair configured for {symbol!r}; have {sorted(PAIRS)}")
    perp_file, spot_file = PAIRS[symbol]
    perp = _daily(RAW / perp_file)
    spot = _daily(RAW / spot_file)

    # Inner join: a day is only comparable if BOTH books traded it. An outer join would silently
    # compare a perp day against a missing spot day and read as an infinite perp share.
    merged = perp.join(spot, on="ts", how="inner", suffix="_spot").sort("ts")
    if merged.height < 200:
        raise DataError(f"only {merged.height} overlapping days between the spot and perp mirrors")

    cp = merged["close"].to_numpy().astype(np.float64)
    cs = merged["close_spot"].to_numpy().astype(np.float64)
    np_ = merged["notional"].to_numpy().astype(np.float64)
    ns = merged["notional_spot"].to_numpy().astype(np.float64)

    basis = cp / np.maximum(cs, 1e-12) - 1.0
    total = np_ + ns
    share = np.where(total > 0, np_ / np.where(total > 0, total, 1.0), np.nan)

    return FlowPanel(
        ts=merged["ts"].to_numpy().astype("datetime64[ms]").astype(np.float64),
        close_perp=cp,
        close_spot=cs,
        basis=basis,
        basis_pct=percentile_rank(basis, RANK_WINDOW),
        perp_share=share,
        perp_share_pct=percentile_rank(np.nan_to_num(share, nan=0.5), RANK_WINDOW),
        total_notional=total,
        delta_proxy_perp=delta_proxy(
            merged["open"].to_numpy().astype(np.float64),
            merged["high"].to_numpy().astype(np.float64),
            merged["low"].to_numpy().astype(np.float64),
            cp,
            merged["volume"].to_numpy().astype(np.float64),
        ),
        delta_proxy_spot=delta_proxy(
            merged["open_spot"].to_numpy().astype(np.float64),
            merged["high_spot"].to_numpy().astype(np.float64),
            merged["low_spot"].to_numpy().astype(np.float64),
            cs,
            merged["volume_spot"].to_numpy().astype(np.float64),
        ),
    )


def scam_pump_test(
    panel: FlowPanel, *, up_move: float = 0.05, lookback: int = 3, horizon: int = 10
) -> dict[str, object]:
    """Do leverage-driven advances fail more often than spot-led ones?

    The falsifiable form of "perp scam pump". Take every advance of at least ``up_move`` over
    ``lookback`` days, split it by whether the perp share of volume was elevated or not, and compare
    what happened next. If the folklore is right, the perp-led half should give more back.

    Overlap deflation is applied exactly as everywhere else in this project: consecutive days share
    most of their forward window, so the nominal count massively overstates the information.
    """
    n = len(panel)
    close = panel.close_spot  # judge the outcome on SPOT — the perp can print anything
    past = np.full(n, np.nan)
    past[lookback:] = close[lookback:] / close[:-lookback] - 1.0
    fwd = np.full(n, np.nan)
    fwd[: n - horizon] = close[horizon:] / close[: n - horizon] - 1.0

    advanced = np.nan_to_num(past, nan=-1.0) >= up_move
    perp_led = advanced & (panel.perp_share_pct >= 0.70)
    spot_led = advanced & (panel.perp_share_pct <= 0.30)
    valid = np.isfinite(fwd) & (perp_led | spot_led)
    gave_back = np.nan_to_num(fwd, nan=0.0) < 0.0

    out: dict[str, object] = {
        "n_advances": int(np.count_nonzero(advanced & np.isfinite(fwd))),
        "n_perp_led": int(np.count_nonzero(perp_led & np.isfinite(fwd))),
        "n_spot_led": int(np.count_nonzero(spot_led & np.isfinite(fwd))),
    }
    if out["n_perp_led"] < 10 or out["n_spot_led"] < 10:  # type: ignore[operator]
        out["verdict"] = "too few advances in one or both arms to compare"
        return out

    overlap = float(max(1.0, horizon))
    lift = conditional_lift(
        perp_led[valid],
        gave_back[valid],
        label="perp-led advance",
        outcome_label=f"negative {horizon}d return",
        overlap=overlap,
    )
    out.update(
        {
            "rate_perp_led": lift.rate_condition,
            "rate_spot_led": lift.rate_complement,
            "difference": lift.difference,
            "ci": (lift.interval_difference.lower, lift.interval_difference.upper),
            "n_eff_perp": lift.n_condition_eff,
            "pvalue": lift.pvalue,
            "separated": lift.separated,
        }
    )
    return out


def report(symbol: str = "XRP") -> None:
    panel = load_flow(symbol)
    last = len(panel) - 1
    print("=" * 100)
    print(f"SPOT vs PERP FLOW — {symbol} (Binance spot + linear perp, same 5m grid)")
    print("=" * 100)
    print(f"  {len(panel):,} overlapping days, {panel.date(0)} .. {panel.date(last)}")
    print(
        "\n  NOT MEASURED (all exchange endpoints egress-blocked): open interest, true funding\n"
        "  rate, true CVD. Basis is a funding PROXY — sound, because funding exists to close it.\n"
        "  Perp share of volume is measured directly, not a proxy."
    )

    print(f"\n  CURRENT READING ({panel.date(last)}):")
    print(f"    perp close      {panel.close_perp[last]:>10.4f}")
    print(f"    spot close      {panel.close_spot[last]:>10.4f}")
    print(
        f"    basis           {panel.basis[last]:>+10.4%}   "
        f"({panel.basis_pct[last]:.0%}ile of the trailing year)"
    )
    print(
        f"    perp share      {panel.perp_share[last]:>10.1%}   "
        f"({panel.perp_share_pct[last]:.0%}ile)"
    )
    print(f"    total notional  ${panel.total_notional[last] / 1e6:>9,.0f}M")

    print("\n  LAST 14 DAYS — the breakout window:")
    print(
        f"    {'date':<12}{'spot':>9}{'perp':>9}{'basis':>9}{'b%ile':>7}"
        f"{'perp$share':>11}{'s%ile':>7}{'notional$M':>12}"
    )
    for i in range(max(0, last - 13), last + 1):
        print(
            f"    {panel.date(i):<12}{panel.close_spot[i]:>9.4f}{panel.close_perp[i]:>9.4f}"
            f"{panel.basis[i]:>+9.3%}{panel.basis_pct[i]:>7.0%}{panel.perp_share[i]:>11.1%}"
            f"{panel.perp_share_pct[i]:>7.0%}{panel.total_notional[i] / 1e6:>12,.0f}"
        )

    print("\n" + "=" * 100)
    print("IS THE 'PERP SCAM PUMP' REAL? — advances split by who drove them")
    print("=" * 100)
    for up in (0.05, 0.10):
        res = scam_pump_test(panel, up_move=up)
        print(f"\n  advances >= {up:.0%} over 3 days   ({res['n_advances']} of them)")
        if "verdict" in res:
            print(
                f"    {res['verdict']}  (perp-led {res['n_perp_led']}, "
                f"spot-led {res['n_spot_led']})"
            )
            continue
        lo, hi = res["ci"]  # type: ignore[misc]
        print(
            f"    P(gave it back in 10d | PERP-led) = {res['rate_perp_led']:.1%}  "
            f"(n={res['n_perp_led']}, n_eff={res['n_eff_perp']})"
        )
        print(
            f"    P(gave it back in 10d | SPOT-led) = {res['rate_spot_led']:.1%}  "
            f"(n={res['n_spot_led']})"
        )
        print(
            f"    difference {res['difference']:>+.1%}  95% CI [{lo:+.1%}, {hi:+.1%}]  "
            f"p={res['pvalue']:.3g}  ->  "
            f"{'SEPARATES from zero' if res['separated'] else 'contains zero'}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Spot vs perp flow analysis")
    ap.add_argument("--symbol", default=C.SUBJECT_KEY)
    args = ap.parse_args(argv)
    try:
        report(args.symbol)
    except DataError as exc:
        print(f"FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
