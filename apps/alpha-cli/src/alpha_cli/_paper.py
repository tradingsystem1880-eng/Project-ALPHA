"""Crypto paper composition: public Binance data with local Nautilus sandbox execution only.

This module lives in ``alpha_cli`` because it is the sole layer allowed to compose data, strategy,
and engine packages.  Historical CCXT/Binance bars prime strategy state; the network session then
subscribes to Binance ``LIVE`` public data while every order is routed to Nautilus's local
``SandboxExecutionClient``.  A Binance execution client is never imported or constructed.
"""

from __future__ import annotations

import json
import math
import re
import signal
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, Any

from alpha_core import Bar, DataError

if TYPE_CHECKING:
    from alpha_cli._runner import RunSpec

_BINANCE_PAIR = re.compile(r"^[A-Z0-9]+/USDT$")
_BINANCE_VENUE = "BINANCE"
_MAX_WARMUP_AGE = timedelta(days=2)


def binance_instrument_id(symbol: str) -> Any:
    """Map canonical ``BASE/USDT`` to Nautilus's ``BASEUSDT.BINANCE`` identifier."""
    from nautilus_trader.model.identifiers import InstrumentId

    canonical = symbol.strip().upper()
    if not _BINANCE_PAIR.fullmatch(canonical):
        raise DataError(f"Binance paper symbol must be BASE/USDT, got {symbol!r}")
    base, quote = canonical.split("/", maxsplit=1)
    if base == quote:
        raise DataError(
            f"Binance paper symbol must be BASE/USDT with a distinct base, got {symbol!r}"
        )
    return InstrumentId.from_str(f"{base}{quote}.{_BINANCE_VENUE}")


def build_binance_data_config(symbol: str) -> Any:
    """Public, credential-free Binance LIVE data config scoped to one instrument."""
    from nautilus_trader.adapters.binance.common.enums import (
        BinanceAccountType,
        BinanceEnvironment,
    )
    from nautilus_trader.adapters.binance.config import BinanceDataClientConfig
    from nautilus_trader.config import InstrumentProviderConfig

    instrument_id = binance_instrument_id(symbol)
    return BinanceDataClientConfig(
        api_key=None,
        api_secret=None,
        account_type=BinanceAccountType.SPOT,
        environment=BinanceEnvironment.LIVE,
        instrument_provider=InstrumentProviderConfig(load_ids=frozenset({instrument_id})),
    )


def build_sandbox_exec_config(
    *, venue: str, account_type: str, starting_cash: float, currency: str
) -> Any:
    """A local ``SandboxExecutionClientConfig`` with quote-driven, next-open fills."""
    from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig

    return SandboxExecutionClientConfig(
        venue=venue,
        starting_balances=[f"{starting_cash:.2f} {currency}"],
        base_currency=currency,
        account_type=account_type,
        oms_type="NETTING",
        bar_execution=False,
    )


def build_paper_node_config(
    *, trader_id: str, exec_config: Any, data_clients: dict[str, Any] | None = None
) -> Any:
    """Assemble a trading node whose only execution client is the local sandbox."""
    from nautilus_trader.live.config import TradingNodeConfig

    return TradingNodeConfig(
        trader_id=trader_id,
        exec_clients={str(exec_config.venue): exec_config},
        data_clients=data_clients or {},
    )


def load_paper_warmup(
    data_dir: Path,
    snapshot_id: str,
    symbol: str,
    spec: RunSpec,
    *,
    now: datetime | None = None,
    max_age: timedelta = _MAX_WARMUP_AGE,
) -> list[Bar]:
    """Verify and load a same-symbol ``ccxt:binance`` snapshot for paper priming.

    Unlike a normal PIT query, this first reads the complete verified snapshot so future-dated
    rows are rejected rather than silently filtered.  Crypto history must also reach the strategy's
    warmup floor and remain recent enough to hand cadence over to the live daily stream.
    """
    from alpha_cli import _strategies
    from alpha_cli._runner import load_bars
    from alpha_data.snapshot import verify_snapshot

    canonical = symbol.strip().upper()
    binance_instrument_id(canonical)
    if (
        not snapshot_id
        or ".." in snapshot_id
        or "/" in snapshot_id
        or "\\" in snapshot_id
        or snapshot_id.startswith(".")
    ):
        raise DataError(f"invalid paper warmup snapshot id {snapshot_id!r}")
    snapshot_dir = Path(data_dir) / "snapshots" / snapshot_id
    verify_snapshot(snapshot_dir)
    try:
        manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"corrupt snapshot manifest at {snapshot_dir / 'manifest.json'}") from exc
    if manifest.get("source") != "ccxt:binance":
        raise DataError(
            f"paper warmup requires source 'ccxt:binance', got {manifest.get('source')!r}"
        )
    symbols = manifest.get("symbols")
    if not isinstance(symbols, dict) or canonical not in symbols:
        raise DataError(
            f"paper warmup snapshot {snapshot_id!r} does not contain symbol {canonical!r}"
        )
    from alpha_data.store import ParquetStore

    snapshot_store = ParquetStore(snapshot_dir)
    symbol_entry = symbols[canonical]
    canonical_provenance_file = (
        snapshot_store._provenance_path(canonical)
        .relative_to(  # noqa: SLF001 -- paper binds the snapshot/store peer contract
            snapshot_dir
        )
        .as_posix()
    )
    if (
        not isinstance(symbol_entry, dict)
        or not isinstance(symbol_entry.get("provenance_sha256"), str)
        or not symbol_entry["provenance_sha256"]
        or symbol_entry.get("provenance_file") != canonical_provenance_file
    ):
        raise DataError(
            f"paper warmup snapshot {snapshot_id!r} lacks canonical hashed pull provenance "
            f"for {canonical!r}"
        )
    pull_provenance = snapshot_store.read_provenance(canonical)
    expected_provenance = {
        "source": "ccxt:binance",
        "adapter_version": manifest.get("adapter_version"),
        "parser_version": manifest.get("parser_version"),
    }
    if pull_provenance != expected_provenance:
        raise DataError(
            f"paper warmup snapshot {snapshot_id!r} lacks matching hashed ccxt:binance "
            "pull provenance"
        )

    bars, _ = load_bars(canonical, data_dir=Path(data_dir), snapshot_id=snapshot_id)
    cutoff = now or datetime.now(UTC)
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise DataError("paper warmup cutoff must be timezone-aware")
    # Daily crypto bars are keyed at the UTC session *open*.  Their OHLC is not knowable until
    # the next UTC boundary, so today's 00:00 row is incomplete even though ``bar.ts <= now``.
    future = next((bar for bar in bars if bar.ts + timedelta(days=1) > cutoff), None)
    if future is not None:
        raise DataError(
            f"paper warmup snapshot contains future bar or incomplete daily bar "
            f"{future.ts.isoformat()} beyond knowledge cutoff {cutoff.isoformat()}"
        )
    required = _strategies.warmup_for(spec)
    if len(bars) < required:
        raise DataError(
            f"strategy {spec.strategy_name!r} warmup requires {required} bars, got {len(bars)}"
        )
    age = cutoff - bars[-1].ts
    if age > max_age:
        raise DataError(
            f"paper warmup snapshot is stale: latest {bars[-1].ts.isoformat()} is "
            f"{age.total_seconds() / 3600:.1f}h old (limit {max_age.total_seconds() / 3600:.0f}h)"
        )
    return bars


def run_paper(
    spec: RunSpec,
    *,
    symbol: str,
    warmup_bars: Sequence[Bar],
    event_sink: object | None = None,
    trader_id: str = "PAPER-001",
    heartbeat: Callable[[], object] | None = None,
    heartbeat_interval: float = 10.0,
    node_type: Any | None = None,
    data_factory: Any | None = None,
    exec_factory: Any | None = None,
) -> bool:
    """Run one strategy on public Binance data and local sandbox execution.

    Returns ``False`` when SIGINT/SIGTERM requested a clean stop, otherwise ``True``.  Factory and
    node injection exists solely for deterministic offline tests; production defaults are the
    official Binance live-data and Sandbox execution factories pinned to Nautilus 1.228.0.
    """
    from alpha_backtest.feed import daily_bar_type
    from alpha_cli import _strategies
    from alpha_strategies.base import VolTargetStrategy

    if spec.account_type.upper() != "MARGIN":
        raise DataError("crypto paper execution requires account_type='MARGIN'")
    if not math.isfinite(heartbeat_interval) or heartbeat_interval <= 0.0:
        raise DataError("paper heartbeat_interval must be finite and > 0")
    definition = _strategies.STRATEGIES.get(spec.strategy_name)
    if definition is None:
        raise DataError(
            f"unknown strategy {spec.strategy_name!r}; known: {_strategies.known_strategies()}"
        )
    if not definition.supports_live_paper:
        raise DataError(f"strategy {spec.strategy_name!r} does not support live paper execution")

    instrument_id = binance_instrument_id(symbol)
    raw_symbol = str(instrument_id.symbol)
    data_config = build_binance_data_config(symbol)
    exec_config = build_sandbox_exec_config(
        venue=_BINANCE_VENUE,
        account_type="MARGIN",
        starting_cash=spec.starting_cash,
        currency="USDT",
    )
    node_config = build_paper_node_config(
        trader_id=trader_id,
        exec_config=exec_config,
        data_clients={_BINANCE_VENUE: data_config},
    )

    if node_type is None:
        from nautilus_trader.live.node import TradingNode

        node_type = TradingNode
    if data_factory is None:
        from nautilus_trader.adapters.binance.factories import BinanceLiveDataClientFactory

        data_factory = BinanceLiveDataClientFactory
    if exec_factory is None:
        from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory

        exec_factory = SandboxLiveExecClientFactory

    strategy = _strategies.build_strategy(
        spec,
        instrument_id,
        daily_bar_type(raw_symbol, venue=_BINANCE_VENUE),
        event_sink=event_sink,
    )
    if not isinstance(strategy, VolTargetStrategy):
        raise DataError(f"strategy {spec.strategy_name!r} cannot be primed for paper execution")
    strategy.prime_history(warmup_bars)
    if strategy.pending_target is not None:
        raise DataError("paper warmup created a pending order target")

    node = node_type(config=node_config)
    interrupted = False
    previous_handlers: dict[signal.Signals, Any] = {}
    heartbeat_stop = threading.Event()
    heartbeat_errors: list[BaseException] = []
    heartbeat_thread: threading.Thread | None = None

    def _stop(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        nonlocal interrupted
        interrupted = True
        node.stop()

    def _heartbeat_loop() -> None:
        while not heartbeat_stop.wait(heartbeat_interval):
            try:
                if heartbeat is not None:
                    heartbeat()
            except BaseException as exc:  # fail closed: stop the node if journaling dies
                heartbeat_errors.append(exc)
                node.stop()
                return

    try:
        # Install process-stop handlers as soon as the node exists, before factory registration or
        # build, so cancellation cannot bypass disposal during startup.
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, _stop)
        node.add_data_client_factory(_BINANCE_VENUE, data_factory)
        node.add_exec_client_factory(_BINANCE_VENUE, exec_factory)
        node.trader.add_strategy(strategy)
        node.build()
        if interrupted:
            return False
        if heartbeat is not None:
            heartbeat_thread = threading.Thread(
                target=_heartbeat_loop,
                name="alpha-paper-heartbeat",
                daemon=True,
            )
            heartbeat_thread.start()
        node.run(raise_exception=True)
    finally:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join()
        for restore_signal, handler in previous_handlers.items():
            signal.signal(restore_signal, handler)
        node.dispose()
    if heartbeat_errors:
        raise RuntimeError("paper heartbeat journal failed") from heartbeat_errors[0]
    return not interrupted
