"""The distinct pump episodes themselves — the descriptive answer to "when does XRP pump?".

The lift tables answer an inferential question and answer it badly, because the record contains far
fewer independent forward windows than it contains rows. This module answers the descriptive
question instead, and answers it well: it identifies each **separate** episode in which XRP rose by
a large amount, and prints the market state on the day the move began.

That is a more honest presentation of a small sample than any p-value. With roughly a dozen distinct
episodes in nine years, a reader can see the whole population at once and judge for themselves
whether the conditions that preceded them look like a pattern or like a dozen unrelated stories.
The statistics section then says, correctly, that a dozen observations cannot establish much — but
the reader has already seen the dozen.

Episodes are de-duplicated by requiring one horizon's separation between onsets, so a single
three-month rally is one episode rather than ninety overlapping ones. That collapse is the same
information the effective-sample-size calculation reports as a number.

Run: ``python -m research.xrp_pumps.episodes [--asset XRP] [--timeframe 1d]``
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import numpy as np
import polars as pl

from alpha_core import DataError
from alpha_validation import (
    ProportionInterval,
    autocorrelation_effective_size,
    newcombe_diff_interval,
)
from research.xrp_pumps import config as C
from research.xrp_pumps import labels

#: Feature columns printed for each episode onset, with the width to print them at.
#: ``ret_momentum`` leads deliberately: it is what tells a reader whether a given episode started
#: from a standing base or is a continuation printed 30 bars into a rally that was already running.
#: Without it the table invites exactly the wrong reading.
STATE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("ret_momentum", "prior30", "{:+.0%}"),
    ("bandwidth_pct", "bw%ile", "{:.0%}"),
    ("realvol_pct", "vol%ile", "{:.0%}"),
    ("consolidation_bars", "consol", "{:.0f}"),
    ("wedge_near_apex", "wedge", "{:.0f}"),
    ("breadth_compressed", "breadth", "{:.0%}"),
    ("btc_corr_60", "btcCorr", "{:+.2f}"),
    ("btc_ret_30", "btc30d", "{:+.0%}"),
    ("mvrv_pct", "mvrv%", "{:.0%}"),
    ("dominance_pct", "dom%", "{:.0%}"),
)


@dataclass(frozen=True)
class Episode:
    """One distinct pump: where it started, how far it went, and the state on the onset bar."""

    index: int
    date: str
    close: float
    peak_return: float
    peak_date: str
    bars_to_peak: int
    state: dict[str, float]

    def line(self) -> str:
        cells = []
        for col, _, fmt in STATE_COLUMNS:
            v = self.state.get(col, float("nan"))
            cells.append("     --" if not np.isfinite(v) else f"{fmt.format(v):>7}")
        return (
            f"  {self.date}  {self.close:>9.4f} {self.peak_return:>+8.0%} "
            f"{self.peak_date} {self.bars_to_peak:>4}d  " + " ".join(cells)
        )


def find_episodes(
    panel: pl.DataFrame, label: labels.Label, *, separation: int | None = None
) -> list[Episode]:
    """Distinct onsets of a labelled move, one per episode rather than one per qualifying bar.

    ``separation`` defaults to the label's own horizon: two onsets closer than that are looking at
    overlapping windows and are, for any practical purpose, the same event. Taking the *first*
    qualifying bar of each cluster is deliberate — it is the moment the setup existed, which is the
    moment whose preconditions are worth reading.
    """
    sep = label.horizon_bars if separation is None else separation
    if sep < 1:
        raise DataError(f"separation must be >= 1, got {sep}")

    closes = panel["close"].to_numpy().astype(np.float64)
    ts = panel["ts"].to_numpy().astype(np.float64)
    hits = np.flatnonzero(label.hit & label.valid)

    episodes: list[Episode] = []
    last = -(10**9)
    for i in hits:
        if i - last < sep:
            continue
        last = int(i)
        end = min(int(i) + label.horizon_bars + 1, closes.size)
        window = closes[i + 1 : end]
        if window.size == 0:
            continue
        peak = int(np.argmax(window)) + int(i) + 1
        episodes.append(
            Episode(
                index=int(i),
                date=_iso(ts[i]),
                close=float(closes[i]),
                peak_return=float(closes[peak] / closes[i] - 1.0),
                peak_date=_iso(ts[peak]),
                bars_to_peak=peak - int(i),
                state={col: _value(panel, col, int(i)) for col, _, _ in STATE_COLUMNS},
            )
        )
    return episodes


def _iso(ts_millis: float) -> str:
    return str(np.datetime64(int(ts_millis), "ms"))[:10]


def _value(panel: pl.DataFrame, column: str, index: int) -> float:
    if column not in panel.columns:
        return float("nan")
    v = panel[column][index]
    return float("nan") if v is None else float(v)


@dataclass(frozen=True)
class Precondition:
    """How often a condition held at an episode's first bar, against its background frequency."""

    name: str
    hits: int
    n_episodes: int
    share: float  # P(condition | episode)
    base: float  # P(condition) over all bars
    base_n_eff: float  # background bars, deflated for the condition's own autocorrelation
    interval: ProportionInterval  # on the difference

    @property
    def gap(self) -> float:
        return self.share - self.base

    @property
    def separated(self) -> bool:
        return not self.interval.contains(0.0)

    def line(self) -> str:
        mark = "*" if self.separated else " "
        return (
            f"    {self.name:<34} {self.hits:>3}/{self.n_episodes:<3} {self.share:>6.0%} "
            f"{self.base:>8.0%} {self.gap:>+7.0%} "
            f"[{self.interval.lower:>+5.0%},{self.interval.upper:>+5.0%}] {mark}"
        )


def precondition_frequency(
    panel: pl.DataFrame, episodes: list[Episode], conditions: dict[str, np.ndarray]
) -> list[Precondition]:
    """``P(condition | episode)`` against ``P(condition)``, with an interval on the difference.

    This is the reverse of the lift tables' ``P(pump | condition)``, and it is the quantity a
    chartist is implicitly quoting when they say "every big move started from a squeeze". Stating
    it next to the condition's *background* frequency is what turns that into a claim with content:
    a condition present at 80% of episodes but also on 80% of all bars has said nothing.

    **Two sample sizes, deflated differently.** Episode bars are separated by at least one horizon
    by construction, so they are treated as independent. Background bars are not — a compression
    reading persists for weeks — so the background arm is deflated by
    :func:`~alpha_validation.autocorrelation_effective_size` computed on the condition series
    itself. The two arms overlap by the episode count, ~1% of the background, which is small enough
    to treat as disjoint for the Newcombe interval; the report states the approximation.
    """
    if not episodes:
        raise DataError("no episodes to summarise")
    idx = np.array([e.index for e in episodes], dtype=np.intp)
    n_ep = int(idx.size)

    rows: list[Precondition] = []
    for name, mask in conditions.items():
        hits = int(np.count_nonzero(mask[idx]))
        base_hits = int(np.count_nonzero(mask))
        base = base_hits / mask.size
        try:
            n_eff = autocorrelation_effective_size(mask.astype(np.float64))
        except DataError:
            n_eff = float(mask.size)  # a constant condition has no autocorrelation to correct for
        n_eff_int = max(2, int(round(n_eff)))
        base_hits_eff = min(n_eff_int, int(round(base * n_eff_int)))
        rows.append(
            Precondition(
                name=name,
                hits=hits,
                n_episodes=n_ep,
                share=hits / n_ep,
                base=base,
                base_n_eff=n_eff,
                interval=newcombe_diff_interval(hits, n_ep, base_hits_eff, n_eff_int),
            )
        )
    return sorted(rows, key=lambda r: -r.gap)


#: A "cold start" is an episode whose trailing 30-bar return was below this — a move that began from
#: something like a standing base rather than 30 bars into a rally already under way. This is the
#: population the compression folklore is actually about.
COLD_START_MAX = 0.10


def cold_starts(episodes: list[Episode]) -> list[Episode]:
    """Episodes that began from a quiet base rather than mid-trend.

    The unfiltered episode list mixes two different things: genuine starts, and continuations that
    qualify again 30 bars into a rally that was already running. Any question of the form "what
    conditions precede a move" is really about the first kind, and separating them costs one column.
    """
    return [
        e
        for e in episodes
        if np.isfinite(e.state.get("ret_momentum", float("nan")))
        and e.state["ret_momentum"] < COLD_START_MAX
    ]


def _frequency_table(
    label: str, panel: pl.DataFrame, eps: list[Episode], conditions: dict[str, np.ndarray]
) -> None:
    if not eps:
        print(f"\n  {label}: no episodes")
        return
    print(
        f"\n  {label} (n={len(eps)}) — condition present at the episode's first bar vs on any bar:"
    )
    print(
        f"    {'condition':<34} {'at ep':>7} {'share':>6} {'base':>8} {'gap':>7} "
        f"{'95% CI on gap':>15}"
    )
    for row in precondition_frequency(panel, eps, conditions):
        if abs(row.gap) < 0.05:
            continue
        print(row.line())


def report(asset_key: str, timeframe: str, label_name: str) -> list[Episode]:
    """Print the episode table and the precondition-frequency tables for one asset."""
    # Local import: study imports episodes for its descriptive section, so a module-level import
    # here would close the cycle.
    from research.xrp_pumps.study import build_asset

    asset = build_asset(asset_key, timeframe)
    if label_name not in asset.labels:
        raise DataError(f"unknown label {label_name!r}; have {sorted(asset.labels)}")
    lab = asset.labels[label_name]
    eps = find_episodes(asset.panel, lab)

    header = " ".join(f"{h:>7}" for _, h, _ in STATE_COLUMNS)
    print(f"\n{'=' * 126}")
    print(f"DISTINCT {label_name.upper()} EPISODES — {asset_key} {timeframe}")
    print("=" * 126)
    print(
        f"  {int(np.count_nonzero(lab.hit & lab.valid)):,} qualifying bars collapse to "
        f"{len(eps)} distinct episodes at {lab.horizon_bars}-bar separation.\n"
        f"  That collapse IS the effective sample size — {labels.effective_n(lab):.0f} by the "
        "formula, and here it is as a list you can read.\n"
        "  'prior30' is the trailing 30-bar return: a large positive value means this episode\n"
        "  is a continuation of a rally already running, not a move starting from a base.\n"
    )
    print(f"  {'starts':<10} {'close':>9} {'peak':>8} {'peak on':<10} {'took':>5}  {header}")
    for e in eps:
        print(e.line())

    cold = cold_starts(eps)
    _frequency_table("ALL EPISODES", asset.panel, eps, asset.conditions)
    _frequency_table(
        f"COLD STARTS ONLY (prior 30-bar return < {COLD_START_MAX:.0%})",
        asset.panel,
        cold,
        asset.conditions,
    )
    return eps


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Distinct XRP pump episodes and their preconditions")
    ap.add_argument("--asset", default=C.SUBJECT_KEY)
    ap.add_argument("--timeframe", default=C.PRIMARY_TIMEFRAME, choices=list(C.BARS_PER_DAY))
    ap.add_argument("--label", default=C.PUMPS[0].label)
    args = ap.parse_args(argv)
    report(args.asset, args.timeframe, args.label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
