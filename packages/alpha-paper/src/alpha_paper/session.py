"""Run a paper-trading session and persist its artifacts.

A session builds the sandbox ``TradingNode`` (4d), replays a recorded execution feed through it via
``ReplayDataClient``, records a per-session mark-to-market equity curve, and writes the session
artifacts (provenance ``session.json`` + ``audit.log.jsonl`` + ``equity_curve.parquet``). It stays
free of the validation/pandas edge — the CLI computes report metrics from the stored equity curve.

The strategy is supplied by the caller (composition stays in the CLI), so the same runner serves any
strategy. Metrics are *not* computed here; ``alpha paper report`` does that.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nautilus_trader.common.actor import Actor
from nautilus_trader.model.data import QuoteTick

from alpha_execution import order_signature
from alpha_paper.artifacts import (
    AuditLog,
    new_session_id,
    session_dir,
    write_equity_curve,
    write_session,
)
from alpha_paper.config import PaperSpec
from alpha_paper.node import build_paper_node, run_node_for
from alpha_paper.replay import (
    ReplayDataClientConfig,
    ReplayDataClientFactory,
    register_replay_events,
)

if TYPE_CHECKING:
    import asyncio

    from nautilus_trader.core.data import Data
    from nautilus_trader.model.identifiers import InstrumentId, Venue
    from nautilus_trader.model.instruments import Instrument
    from nautilus_trader.trading.strategy import Strategy

_NS_PER_SECOND = 1_000_000_000


def _ns_to_dt(ns: int) -> datetime:
    return datetime.fromtimestamp(ns / _NS_PER_SECOND, tz=UTC)


def _sum_pnls(pnls: Any) -> float:
    return float(sum(money.as_double() for money in pnls.values()))


class _EquityRecorder(Actor):  # type: ignore[misc]  # nautilus Actor is untyped (Cython)
    """Snapshots net-liquidation equity once per session (each open quote), as in the backtest."""

    def __init__(self, instrument_id: InstrumentId, venue: Venue, starting_cash: float) -> None:
        super().__init__()
        self._iid = instrument_id
        self._venue = venue
        self._starting_cash = starting_cash
        self.curve: list[tuple[datetime, float]] = []

    def on_start(self) -> None:
        self.subscribe_quote_ticks(self._iid)

    def on_quote_tick(self, quote: QuoteTick) -> None:
        equity = (
            self._starting_cash
            + _sum_pnls(self.portfolio.realized_pnls(self._venue))
            + _sum_pnls(self.portfolio.unrealized_pnls(self._venue))
        )
        self.curve.append((_ns_to_dt(quote.ts_event), equity))


@dataclass(frozen=True)
class PaperSessionResult:
    """What the CLI needs after a session: the id/dir and headline counts."""

    session_id: str
    session_dir: Path
    n_orders: int
    n_fills: int
    order_log: list[tuple[str, float]]
    final_equity: float


def run_paper_session(
    spec: PaperSpec,
    instrument: Instrument,
    events: list[Data],
    strategy: Strategy,
    *,
    data_dir: Path,
    loop: asyncio.AbstractEventLoop,
    feed_interval: float = 0.02,
    now: datetime | None = None,
) -> PaperSessionResult:
    """Run ``strategy`` over ``events`` through the sandbox; write artifacts; return the result."""
    started = now if now is not None else datetime.now(UTC)
    session_id = new_session_id(started)
    register_replay_events(session_id, events)

    node = build_paper_node(
        spec,
        instrument,
        data_client_name="REPLAY",
        data_client_factory=ReplayDataClientFactory,
        data_client_config=ReplayDataClientConfig(
            key=session_id, feed_delay=0.2, feed_interval=feed_interval
        ),
    )
    recorder = _EquityRecorder(instrument.id, instrument.id.venue, spec.starting_cash)
    node.trader.add_actor(recorder)
    node.trader.add_strategy(strategy)
    cache = node.cache

    duration = spec.duration_seconds or (0.2 + len(events) * feed_interval + 1.0)
    loop.run_until_complete(run_node_for(node, duration, dispose=False))

    orders = sorted(cache.orders(), key=lambda o: o.ts_init)
    order_log = [order_signature(o) for o in orders]
    n_fills = sum(1 for o in orders if o.status.name == "FILLED")
    final_equity = recorder.curve[-1][1] if recorder.curve else spec.starting_cash

    sdir = session_dir(data_dir, session_id)
    audit = AuditLog(sdir)
    for order in orders:
        audit.record(
            "order",
            side=order.side.name,
            quantity=float(order.quantity),
            status=order.status.name,
            avg_px=float(order.avg_px) if order.avg_px is not None else None,
        )
    write_equity_curve(sdir, recorder.curve)
    write_session(
        sdir,
        {
            "schema_version": 1,
            "session_id": session_id,
            "started_at": started.isoformat(),
            "symbol": spec.symbol,
            "exchange": spec.exchange,
            "venue": spec.venue,
            "instrument_id": str(instrument.id),
            "params": {
                "lookback": spec.lookback,
                "skip": spec.skip,
                "vol_window": spec.vol_window,
                "target_vol": spec.target_vol,
                "rebalance_every": spec.rebalance_every,
                "max_leverage": spec.max_leverage,
                "allow_short": spec.allow_short,
                "periods_per_year": spec.periods_per_year,
                "fee_bps": spec.fee_bps,
                "slippage_bps": spec.slippage_bps,
                "starting_cash": spec.starting_cash,
                "account_type": spec.account_type,
            },
            "n_events": len(events),
            "n_orders": len(orders),
            "n_fills": n_fills,
            "final_equity": final_equity,
            "nautilus_version": version("nautilus-trader"),
        },
    )
    node.dispose()
    return PaperSessionResult(
        session_id=session_id,
        session_dir=sdir,
        n_orders=len(orders),
        n_fills=n_fills,
        order_log=order_log,
        final_equity=final_equity,
    )
