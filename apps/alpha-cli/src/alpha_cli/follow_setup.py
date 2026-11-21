"""Replay a followed setup trade over stored bars, one session at a time. Paper only.

The same code path as the study: `find_candidates` and `cluster_candidates` find the occurrences,
`prepare_exits` and `simulate` (`spine/setup_exits.py`) apply the exits, and the same one position
per asset rule blocks an overlapping entry. The study sees all bars at once. This replay hands
each session only the bars up to its close, so no decision changes when later bars arrive. A
trigger that closes on the last known bar is an order for the next open (the study calls that row
`no-next-bar`; here it is the signal). Nothing here reads a clock, a store or the `forward/` folder.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli.spine import setup_exits
from alpha_cli.spine import setup_find as study_find
from alpha_cli.spine.setup_costs import round_trip
from alpha_core import Bar, DataError
from alpha_study.setup.evaluate import find_candidates

NO_NEXT_BAR = "no-next-bar"
INVALID_LEVELS = "the exit levels were not valid at the open (the study skips such a trade too)"
IN_TRADE = "a setup closed while a paper position was open (the study skips such a trade too)"


@dataclass
class Day:
    """What the replay did on one session."""

    signal: bool = False
    skipped: str = ""
    fills: list[dict[str, Any]] = field(default_factory=list)
    held: bool = False
    exit_pending: bool = False
    stop: float | None = None
    target: float | None = None
    trade: dict[str, Any] | None = None


def setup_code_sha256() -> str:
    """One hash of the source of the setup replay and the study code it shares. A change to any
    of them shows later as a replay that disagrees, not as a silent new number."""
    import alpha_study.setup as setup_package

    here = Path(__file__).parent
    files = [here / "follow_setup.py", here / "spine" / "setup_exits.py"]
    files += [
        here / "spine" / "setup_find.py",
        *Path(setup_package.__file__ or "").parent.glob("*.py"),
    ]
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda p: (p.parent.name, p.name)):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def frame_of(bars: Sequence[Bar]) -> pl.DataFrame:
    schema: dict[str, Any] = {
        "ts": pl.Datetime("us", "UTC"),
        **dict.fromkeys(("open", "high", "low", "close", "volume"), pl.Float64),
    }
    return pl.DataFrame({k: [getattr(b, k) for b in bars] for k in schema}, schema=schema)


def _signal(spec: Any, frame: pl.DataFrame, asset: str) -> bool:
    """True when a first-in-its-cluster setup trigger closes on the last bar of `frame`."""
    found = find_candidates(spec, frame, symbol=asset)
    if not found.height:
        return False
    as_orders = found.with_columns(
        pl.when(pl.col("reason") == NO_NEXT_BAR)
        .then(pl.lit("accepted"))
        .otherwise(pl.col("status"))
        .alias("status")
    )
    clustered = study_find.cluster_candidates(frame, as_orders)
    mine = clustered.filter((pl.col("reason") == NO_NEXT_BAR) & pl.col("cluster_first"))
    return bool(mine.height)


def _cut(prepared: setup_exits.PreparedExits, upto: int) -> setup_exits.PreparedExits:
    """The same compiled exits, seen up to bar `upto` only."""
    levels = {
        k: (kind, mult, vals[: upto + 1]) for k, (kind, mult, vals) in prepared.levels.items()
    }
    return replace(
        prepared,
        bars=prepared.bars[: upto + 1],
        levels=levels,
        opposite=prepared.opposite[: upto + 1],
    )


def replay(
    bars: Sequence[Bar], spec: Any, asset: str, costs: dict[str, Any], first: int
) -> dict[date, Day]:
    """One `Day` for each session from bar index `first` on. The follow starts flat."""
    if not 2 <= first < len(bars):
        raise DataError("the replay needs bars before the first forward bar and the bar itself")
    cost = round_trip(costs)
    full = setup_exits.prepare_exits(spec, list(bars), carry_per_day=0.0)
    frame = frame_of(bars)
    days: dict[date, Day] = {}
    entry: int | None = None
    pending_buy = False
    for i in range(first, len(bars)):
        day = Day()
        view = _cut(full, i)
        if pending_buy:
            pending_buy = False
            row = setup_exits.simulate(view, i, cost)
            if row["reason"] == "invalid-levels":
                day.skipped = INVALID_LEVELS
            else:
                entry = i
                day.fills.append(_fill("buy", bars[i].open, bars[i].ts, "entry"))
        if entry is not None:
            row = setup_exits.simulate(view, entry, cost)
            if row["complete"] and row["exit_index"] == i:
                day.fills.append(_fill("sell", row["exit_price"], bars[i].ts, row["reason"]))
                day.trade = _trade(row)
                entry = None
            else:
                day.stop, day.target = row["stop"], row["target"]
                day.exit_pending = view.opposite[i] is True
        day.held = entry is not None
        if _signal(spec, frame.head(i + 1), asset):
            if entry is None:
                day.signal, pending_buy = True, True
            else:
                day.skipped = IN_TRADE
        days[bars[i].ts.date()] = day
    return days


def _fill(side: str, price: float, ts: Any, reason: str) -> dict[str, Any]:
    return {"side": side, "raw_price": price, "bar_ts": ts.isoformat(), "reason": reason}


def _trade(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_ts": row["entry_ts"].isoformat(),
        "entry_price": row["entry_price"],
        "exit_ts": row["exit_ts"].isoformat(),
        "exit_price": row["exit_price"],
        "reason": row["reason"],
        "bars_held": row["bars_held"],
        "net_return": row["net_return"],
    }
