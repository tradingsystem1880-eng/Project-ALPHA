"""A synthetic setup study and a store of daily bars (NYSE sessions) for the setup-follow tests.

Flat prices at 100. A volume of 1 marks an event day; the entry is the next open. After the events
at bars 60 and 120 the high reaches the 10 % target two bars later; after the event at 150 the low
breaks the 5 % stop two bars later; the other events leave through the 3-bar time limit.
Every date is before the held-back boundary, so the study may read all of it.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli import setup_cmds
from alpha_cli.spine import setup_trade
from alpha_data.sessions import session_bounds, sessions_between
from alpha_data.store import ParquetStore

SESSIONS = sessions_between("XNYS", date(2020, 1, 2), date(2020, 12, 31))
N = 200
EVENTS = (30, 60, 90, 120, 150)
START_BAR = 105
SPEC = (
    '[setup]\nname="Synthetic spike"\nidea="Volume spike"\ntimeframe="1D"\nassets=["SPY"]\n'
    'event="volume == 1"\n[reference]\nbase="low"\n'
    '[exit]\ntime_bars=3\nstop="5 %"\ntarget="10 %"\n'
)


def day_of(i: int) -> date:
    return SESSIONS[i]


def bar_rows(n: int = N) -> list[dict[str, Any]]:
    rows = []
    for i in range(n):
        high, low = 101.0, 99.0
        if i - 2 in (60, 120):
            high = 111.0
        if i - 2 == 150:
            low = 90.0
        rows.append(
            {
                "ts": datetime.combine(day_of(i), datetime.min.time(), tzinfo=UTC),
                "open": 100.0,
                "high": high,
                "low": low,
                "close": 100.0,
                "volume": 1.0 if i in EVENTS else 0.0,
            }
        )
    return rows


def make_study(home: Path, *, direction: str = "long") -> dict[str, Any]:
    store = ParquetStore(home / "store")
    store.write_bars("SPY", pl.DataFrame(bar_rows()))
    store.write_provenance("SPY", source="alpaca", adapter_version="1", parser_version="1")
    path = home / "spec.toml"
    path.write_text(SPEC + ('direction="short"\n' if direction == "short" else ""))
    found = setup_cmds.run_find(path, home=home)
    trade = setup_trade.run_trade(found["find_id"], home=home)
    return {"find": found, "trade": trade, "trade_id": trade["trade_id"]}


def clock_after(i: int) -> datetime:
    """Half an hour after the close of session `i`."""
    return session_bounds("XNYS", day_of(i))[1] + timedelta(minutes=30)


START = session_bounds("XNYS", day_of(START_BAR))[0] - timedelta(hours=1)


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value))
