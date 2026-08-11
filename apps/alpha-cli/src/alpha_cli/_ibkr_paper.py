"""Fail-closed Interactive Brokers Paper boundary owned by ``alpha_cli``.

This module contains no live-capital mode.  It validates the immutable operator boundary before
Nautilus clients are constructed and defines the content-bound decision artifact used as the
broker idempotency reference.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import signal
import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from types import FrameType
from typing import Any, Literal, cast

from alpha_cli._atomic import write_text
from alpha_core import DataError

IBKR_PAPER_HOST = "127.0.0.1"
IBKR_PAPER_PORT = 4002
IBKR_CLIENT_ID_MIN = 20
IBKR_CLIENT_ID_MAX = 29
_ACCOUNT_RE = re.compile(r"^DU[A-Z0-9]+$")
_DIGEST_IMAGE_RE = re.compile(r"^[A-Za-z0-9._/:+-]+@sha256:[0-9a-f]{64}$")
_MICRO_FUTURE_RE = re.compile(r"^(?:MES|MNQ|M2K|MCL|MGC)[FGHJKMNQUVXZ][0-9]{1,2}\.[A-Z0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

type AssetClass = Literal["stock", "etf", "future"]
type JsonScalar = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class PaperRiskProfile:
    id: str
    allow_short: bool
    max_order_nav: float
    max_position_nav: float
    max_gross_nav: float
    daily_loss_halt: float
    max_open_orders: int
    max_leverage: float

    def to_dict(self) -> dict[str, JsonScalar]:
        return {
            "id": self.id,
            "allow_short": self.allow_short,
            "max_order_nav": self.max_order_nav,
            "max_position_nav": self.max_position_nav,
            "max_gross_nav": self.max_gross_nav,
            "daily_loss_halt": self.daily_loss_halt,
            "max_open_orders": self.max_open_orders,
            "max_leverage": self.max_leverage,
        }


EQUITY_RISK_PROFILE = PaperRiskProfile(
    id="ibkr-equity-paper-v1",
    allow_short=False,
    max_order_nav=0.05,
    max_position_nav=0.10,
    max_gross_nav=0.50,
    daily_loss_halt=0.01,
    max_open_orders=5,
    max_leverage=1.0,
)
FUTURES_PROBE_RISK_PROFILE = PaperRiskProfile(
    id="ibkr-micro-futures-probe-v1",
    allow_short=False,
    max_order_nav=0.0,
    max_position_nav=0.0,
    max_gross_nav=0.0,
    daily_loss_halt=0.01,
    max_open_orders=1,
    max_leverage=1.0,
)


@dataclass(frozen=True, slots=True)
class IBKRPaperBoundary:
    account_id: str
    gateway_image: str
    allowed_instruments: frozenset[str]
    host: str
    port: int
    client_id: int

    @classmethod
    def create(
        cls,
        *,
        account_id: str,
        gateway_image: str,
        allowed_instruments: Sequence[str],
        host: str = IBKR_PAPER_HOST,
        port: int = IBKR_PAPER_PORT,
        client_id: int = IBKR_CLIENT_ID_MIN,
        paper_enabled: bool,
        ibkr_paper_enabled: bool,
        execution_requested: bool,
    ) -> IBKRPaperBoundary:
        account = account_id.strip().upper()
        if _ACCOUNT_RE.fullmatch(account) is None:
            raise DataError("IBKR paper account must be an explicitly allowlisted DU… account")
        if _DIGEST_IMAGE_RE.fullmatch(gateway_image) is None:
            raise DataError("IBKR Gateway image must be pinned by an approved sha256 digest")
        if host != IBKR_PAPER_HOST:
            raise DataError("IBKR Gateway must bind to IPv4 loopback 127.0.0.1")
        if port != IBKR_PAPER_PORT:
            raise DataError(
                "IBKR Paper requires paper port 4002; live and desktop ports are denied"
            )
        if client_id < IBKR_CLIENT_ID_MIN or client_id + 1 >= IBKR_CLIENT_ID_MAX:
            raise DataError(
                f"IBKR data client ID must be in approved range {IBKR_CLIENT_ID_MIN}.."
                f"{IBKR_CLIENT_ID_MAX - 2}; execution uses the next ID"
            )
        if execution_requested and not (paper_enabled and ibkr_paper_enabled):
            raise DataError(
                "IBKR order authority requires two independent enable flags: "
                "ALPHA_PAPER_ENABLED and ALPHA_IBKR_PAPER_ENABLED"
            )
        normalized = frozenset(item.strip().upper() for item in allowed_instruments if item.strip())
        if not normalized:
            raise DataError("IBKR paper requires a non-empty approved-instrument allowlist")
        return cls(
            account_id=account,
            gateway_image=gateway_image,
            allowed_instruments=normalized,
            host=host,
            port=port,
            client_id=client_id,
        )

    def require_instrument(
        self,
        instrument_id: str,
        *,
        asset_class: AssetClass,
        strategy_generated: bool,
    ) -> str:
        instrument = instrument_id.strip().upper()
        if instrument not in self.allowed_instruments:
            raise DataError(f"IBKR instrument {instrument!r} is not in the approved allowlist")
        if asset_class == "future":
            if strategy_generated:
                raise DataError("strategy-generated futures orders are disabled in this milestone")
            if _MICRO_FUTURE_RE.fullmatch(instrument) is None:
                raise DataError("futures probes require an explicit dated micro contract")
        return instrument


def build_ibkr_client_configs(boundary: IBKRPaperBoundary, *, read_only: bool) -> tuple[Any, Any]:
    """Construct pinned native Nautilus IB clients after the boundary has passed."""
    from nautilus_trader.adapters.interactive_brokers.config import (
        DockerizedIBGatewayConfig,
        InteractiveBrokersDataClientConfig,
        InteractiveBrokersExecClientConfig,
        InteractiveBrokersInstrumentProviderConfig,
    )
    from nautilus_trader.model.identifiers import InstrumentId

    instrument_ids = frozenset(
        InstrumentId.from_str(instrument) for instrument in boundary.allowed_instruments
    )
    instrument_provider = InteractiveBrokersInstrumentProviderConfig(load_ids=instrument_ids)
    gateway = DockerizedIBGatewayConfig(
        username=None,
        password=None,
        trading_mode="paper",
        read_only_api=read_only,
        container_image=boundary.gateway_image,
        vnc_port=None,
    )
    data_config = InteractiveBrokersDataClientConfig(
        instrument_provider=instrument_provider,
        ibg_host=boundary.host,
        ibg_port=boundary.port,
        ibg_client_id=boundary.client_id,
        dockerized_gateway=gateway,
        use_regular_trading_hours=True,
    )
    exec_config = InteractiveBrokersExecClientConfig(
        instrument_provider=instrument_provider,
        ibg_host=boundary.host,
        ibg_port=boundary.port,
        ibg_client_id=boundary.client_id + 1,
        account_id=boundary.account_id,
        dockerized_gateway=gateway,
        fetch_all_open_orders=True,
    )
    return data_config, exec_config


def _aware_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"order intent {field} must be timezone-aware")
    return value.astimezone(UTC)


def _parameters(value: Mapping[str, object]) -> dict[str, JsonScalar]:
    clean: dict[str, JsonScalar] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise DataError("order intent parameter names must be non-empty strings")
        if (
            item is None
            or isinstance(item, (str, bool, int))
            or (isinstance(item, float) and math.isfinite(item))
        ):
            clean[key] = item
        else:
            raise DataError("order intent parameters must be finite JSON scalars")
    return clean


@dataclass(frozen=True, slots=True)
class OrderIntent:
    intent_id: str
    strategy: str
    strategy_version: str
    parameters: Mapping[str, JsonScalar]
    snapshot_id: str
    snapshot_sha256: str
    instrument_id: str
    target_quantity: float
    next_session: str
    risk_profile: PaperRiskProfile
    knowledge_cutoff: datetime
    expires_at: datetime

    @classmethod
    def create(
        cls,
        *,
        strategy: str,
        strategy_version: str,
        parameters: Mapping[str, object],
        snapshot_id: str,
        snapshot_sha256: str,
        instrument_id: str,
        target_quantity: float,
        next_session: str,
        risk_profile: PaperRiskProfile,
        knowledge_cutoff: datetime,
        expires_at: datetime,
    ) -> OrderIntent:
        authority_strings = (
            strategy,
            strategy_version,
            snapshot_id,
            snapshot_sha256,
            instrument_id,
            next_session,
        )
        if any(not isinstance(value, str) for value in authority_strings):
            raise DataError("order intent authority identifiers must be strings")
        if isinstance(target_quantity, bool) or not isinstance(target_quantity, (int, float)):
            raise DataError("order intent target_quantity must be numeric")
        try:
            date.fromisoformat(next_session)
        except ValueError as exc:
            raise DataError("order intent next_session must be an ISO date") from exc
        if _SHA256_RE.fullmatch(snapshot_sha256) is None:
            raise DataError("order intent requires a lowercase snapshot SHA-256")
        if not math.isfinite(target_quantity):
            raise DataError("order intent target_quantity must be finite")
        cutoff = _aware_utc(knowledge_cutoff, "knowledge_cutoff")
        expiry = _aware_utc(expires_at, "expires_at")
        if expiry <= cutoff:
            raise DataError("order intent expiry must follow its knowledge cutoff")
        clean_strategy = strategy.strip()
        clean_version = strategy_version.strip()
        clean_parameters = _parameters(parameters)
        clean_snapshot = snapshot_id.strip()
        clean_instrument = instrument_id.strip().upper()
        values = {
            "strategy": clean_strategy,
            "strategy_version": clean_version,
            "parameters": clean_parameters,
            "snapshot_id": clean_snapshot,
            "snapshot_sha256": snapshot_sha256,
            "instrument_id": clean_instrument,
            "target_quantity": target_quantity,
            "next_session": next_session,
            "risk_profile": risk_profile.to_dict(),
            "knowledge_cutoff": cutoff.isoformat(),
            "expires_at": expiry.isoformat(),
        }
        if not all((clean_strategy, clean_version, clean_snapshot, clean_instrument)):
            raise DataError("order intent authority identifiers must be non-empty")
        intent_id = hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        return cls(
            intent_id=intent_id,
            strategy=clean_strategy,
            strategy_version=clean_version,
            parameters=clean_parameters,
            snapshot_id=clean_snapshot,
            snapshot_sha256=snapshot_sha256,
            instrument_id=clean_instrument,
            target_quantity=target_quantity,
            next_session=next_session,
            risk_profile=risk_profile,
            knowledge_cutoff=cutoff,
            expires_at=expiry,
        )

    def authority_payload(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "strategy_version": self.strategy_version,
            "parameters": dict(self.parameters),
            "snapshot_id": self.snapshot_id,
            "snapshot_sha256": self.snapshot_sha256,
            "instrument_id": self.instrument_id,
            "target_quantity": self.target_quantity,
            "next_session": self.next_session,
            "risk_profile": self.risk_profile,
            "knowledge_cutoff": self.knowledge_cutoff,
            "expires_at": self.expires_at,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "intent_id": self.intent_id,
            **{
                **self.authority_payload(),
                "risk_profile": self.risk_profile.to_dict(),
                "knowledge_cutoff": self.knowledge_cutoff.isoformat(),
                "expires_at": self.expires_at.isoformat(),
            },
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> OrderIntent:
        fields = {
            "schema_version",
            "intent_id",
            "strategy",
            "strategy_version",
            "parameters",
            "snapshot_id",
            "snapshot_sha256",
            "instrument_id",
            "target_quantity",
            "next_session",
            "risk_profile",
            "knowledge_cutoff",
            "expires_at",
        }
        if set(raw) != fields:
            raise DataError("invalid order intent schema fields")
        schema_version = raw.get("schema_version")
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version != 1
        ):
            raise DataError("unsupported order intent schema")
        risk = raw.get("risk_profile")
        if not isinstance(risk, Mapping) or dict(risk) != EQUITY_RISK_PROFILE.to_dict():
            raise DataError("unsupported order intent risk profile")
        try:
            parameters = raw["parameters"]
            if not isinstance(parameters, Mapping):
                raise TypeError
            string_fields = (
                "intent_id",
                "strategy",
                "strategy_version",
                "snapshot_id",
                "snapshot_sha256",
                "instrument_id",
                "next_session",
                "knowledge_cutoff",
                "expires_at",
            )
            if any(not isinstance(raw[name], str) for name in string_fields):
                raise TypeError
            target = raw["target_quantity"]
            if isinstance(target, bool) or not isinstance(target, (int, float)):
                raise TypeError
            intent = cls.create(
                strategy=cast(str, raw["strategy"]),
                strategy_version=cast(str, raw["strategy_version"]),
                parameters=parameters,
                snapshot_id=cast(str, raw["snapshot_id"]),
                snapshot_sha256=cast(str, raw["snapshot_sha256"]),
                instrument_id=cast(str, raw["instrument_id"]),
                target_quantity=float(target),
                next_session=cast(str, raw["next_session"]),
                risk_profile=EQUITY_RISK_PROFILE,
                knowledge_cutoff=datetime.fromisoformat(cast(str, raw["knowledge_cutoff"])),
                expires_at=datetime.fromisoformat(cast(str, raw["expires_at"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError("invalid order intent") from exc
        if raw.get("intent_id") != intent.intent_id:
            raise DataError("order intent hash does not match its authority payload")
        return intent

    def require_releasable(self, now: datetime) -> None:
        if _aware_utc(now, "release time") >= self.expires_at:
            raise DataError(f"order intent {self.intent_id} expired before release")


def persist_order_intent(data_dir: Path, intent: OrderIntent) -> Path:
    """Idempotently publish one immutable, content-addressed order intent."""
    root = Path(data_dir) / "paper" / "intents"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{intent.intent_id}.json"
    content = json.dumps(intent.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DataError(f"cannot read immutable order intent at {path}") from exc
        if existing != content:
            raise DataError(f"immutable order intent conflict at {path}")
        return path
    write_text(path, content)
    return path


def load_order_intent(data_dir: Path, intent_id: str) -> OrderIntent:
    """Load and verify one exact immutable intent by its content-derived identifier."""
    if _SHA256_RE.fullmatch(intent_id) is None:
        raise DataError("order intent id must be a lowercase SHA-256")
    path = Path(data_dir) / "paper" / "intents" / f"{intent_id}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DataError(f"no immutable order intent {intent_id}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"cannot read immutable order intent {intent_id}") from exc
    if not isinstance(raw, Mapping):
        raise DataError(f"invalid immutable order intent {intent_id}")
    intent = OrderIntent.from_dict(raw)
    if intent.intent_id != intent_id:
        raise DataError("order intent filename does not match its authority payload")
    return intent


def claim_order_intent_release(data_dir: Path, intent_id: str, session_id: str) -> Path:
    """Atomically consume one intent before broker node construction.

    Claims are deliberately never removed: an ambiguous process death cannot make the same broker
    reference eligible for resubmission. A later decision cycle must create a new content hash.
    """
    if _SHA256_RE.fullmatch(intent_id) is None:
        raise DataError("order intent id must be a lowercase SHA-256")
    try:
        if str(uuid.UUID(session_id)) != session_id:
            raise ValueError
    except ValueError as exc:
        raise DataError("order intent release requires a canonical session UUID") from exc
    root = Path(data_dir) / "paper" / "intent-releases"
    if root.is_symlink():
        raise DataError(f"order intent release root must not be a symlink: {root}")
    root.mkdir(parents=True, exist_ok=True)
    claim_root = root / intent_id
    try:
        claim_root.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise DataError(
            f"order intent {intent_id} is already claimed; reconcile instead of retrying"
        ) from exc
    claim_path = claim_root / "claim.json"
    write_text(
        claim_path,
        json.dumps(
            {
                "schema_version": 1,
                "intent_id": intent_id,
                "session_id": session_id,
                "claimed_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return claim_path


@dataclass(frozen=True, slots=True)
class IBKRWarmup:
    bars: Sequence[Any]
    snapshot_sha256: str
    knowledge_cutoff: datetime
    expected_session: date


def load_ibkr_warmup(
    data_dir: Path,
    snapshot_id: str,
    symbol: str,
    spec: Any,
    *,
    expected_session: date,
) -> IBKRWarmup:
    """Load a verified, versioned Tiingo snapshot ending on the expected session."""
    from alpha_cli import _strategies
    from alpha_cli._runner import load_bars
    from alpha_data.snapshot import snapshot_manifest_hash, verify_snapshot
    from alpha_data.store import ParquetStore

    if (
        not snapshot_id
        or ".." in snapshot_id
        or "/" in snapshot_id
        or "\\" in snapshot_id
        or snapshot_id.startswith(".")
    ):
        raise DataError(f"invalid IBKR warmup snapshot id {snapshot_id!r}")
    canonical = symbol.strip().upper()
    snapshot_dir = Path(data_dir) / "snapshots" / snapshot_id
    verify_snapshot(snapshot_dir)
    try:
        manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("corrupt IBKR warmup snapshot manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("source") != "tiingo":
        raise DataError("IBKR strategy warmup requires authoritative Tiingo provenance")
    symbols = manifest.get("symbols")
    if not isinstance(symbols, dict) or canonical not in symbols:
        raise DataError(f"IBKR warmup snapshot does not contain {canonical!r}")
    provenance = ParquetStore(snapshot_dir).read_provenance(canonical)
    if not isinstance(provenance, dict) or provenance.get("schema_version") != 2:
        raise DataError("IBKR warmup requires versioned dataset identity and fetch receipt")
    dataset = provenance.get("dataset")
    receipt = provenance.get("receipt")
    if (
        not isinstance(dataset, dict)
        or dataset.get("provider") != "tiingo"
        or dataset.get("timeframe") != "1D"
        or dataset.get("price_basis") != "raw"
        or not isinstance(receipt, dict)
    ):
        raise DataError("IBKR warmup provenance is not authoritative raw Tiingo daily data")
    try:
        cutoff = datetime.fromisoformat(str(receipt["fetched_at"])).astimezone(UTC)
    except (KeyError, ValueError) as exc:
        raise DataError("IBKR warmup has an invalid knowledge cutoff") from exc
    bars, _ = load_bars(canonical, data_dir=Path(data_dir), snapshot_id=snapshot_id)
    if not bars or bars[-1].ts.date() != expected_session:
        actual = None if not bars else bars[-1].ts.date().isoformat()
        raise DataError(
            f"IBKR warmup latest completed session is {actual}; expected {expected_session}"
        )
    required = _strategies.warmup_for(spec)
    if len(bars) < required:
        raise DataError(f"IBKR warmup requires {required} bars, got {len(bars)}")
    return IBKRWarmup(
        bars=bars,
        snapshot_sha256=snapshot_manifest_hash(snapshot_dir),
        knowledge_cutoff=cutoff,
        expected_session=expected_session,
    )


def run_ibkr_paper(
    spec: Any,
    *,
    boundary: IBKRPaperBoundary,
    symbol: str,
    instrument_id: str,
    warmup: IBKRWarmup,
    order_intent: OrderIntent,
    order_cutoff: datetime,
    expected_position_units: float,
    event_sink: object,
    trader_id: str,
    heartbeat: Any | None = None,
    stop_requested: Any | None = None,
    heartbeat_interval: float = 10.0,
    node_type: Any | None = None,
    data_factory: Any | None = None,
    exec_factory: Any | None = None,
) -> bool:
    """Run an approved equity strategy through Nautilus's native IB paper clients."""
    from nautilus_trader.live.config import (
        LiveExecEngineConfig,
        LiveRiskEngineConfig,
        TradingNodeConfig,
    )
    from nautilus_trader.model.identifiers import InstrumentId

    from alpha_backtest.feed import daily_bar_type
    from alpha_cli import _strategies
    from alpha_strategies.base import PaperRiskLimits, VolTargetStrategy

    if spec.allow_short or spec.max_leverage > 0.10:
        raise DataError("IBKR equity paper requires long-only strategy leverage at or below 10%")
    if not math.isfinite(heartbeat_interval) or heartbeat_interval <= 0.0:
        raise DataError("paper heartbeat_interval must be finite and positive")
    approved = boundary.require_instrument(
        instrument_id, asset_class="stock", strategy_generated=True
    )
    cutoff = _aware_utc(order_cutoff, "order cutoff")
    warmup_cutoff = _aware_utc(warmup.knowledge_cutoff, "warmup knowledge cutoff")
    if (
        order_intent.instrument_id != approved
        or order_intent.snapshot_sha256 != warmup.snapshot_sha256
        or order_intent.knowledge_cutoff != warmup_cutoff
        or order_intent.expires_at != cutoff
        or order_intent.next_session != cutoff.date().isoformat()
        or order_intent.risk_profile != EQUITY_RISK_PROFILE
    ):
        raise DataError("IBKR paper intent does not match warmup, cutoff, or risk authority")
    iid = InstrumentId.from_str(approved)
    data_config, exec_config = build_ibkr_client_configs(boundary, read_only=False)
    max_order_notional = spec.starting_cash * EQUITY_RISK_PROFILE.max_order_nav
    node_config = TradingNodeConfig(
        trader_id=trader_id,
        data_clients={"IB": data_config},
        exec_clients={"IB": exec_config},
        risk_engine=LiveRiskEngineConfig(max_notional_per_order={"USD": int(max_order_notional)}),
        exec_engine=LiveExecEngineConfig(
            reconciliation=True,
            reconciliation_instrument_ids=[iid],
            generate_missing_orders=True,
            open_check_interval_secs=5.0,
            position_check_interval_secs=5.0,
        ),
    )
    strategy = _strategies.build_strategy(
        spec,
        iid,
        daily_bar_type(str(iid.symbol), venue=str(iid.venue)),
        event_sink=event_sink,
    )
    if not isinstance(strategy, VolTargetStrategy):
        raise DataError(f"strategy {spec.strategy_name!r} cannot execute in IBKR paper")
    strategy.prime_history(warmup.bars)
    strategy.configure_paper_risk(
        PaperRiskLimits(
            max_order_notional=max_order_notional,
            max_position_notional=spec.starting_cash * EQUITY_RISK_PROFILE.max_position_nav,
            max_gross_notional=spec.starting_cash * EQUITY_RISK_PROFILE.max_gross_nav,
            daily_loss_fraction=EQUITY_RISK_PROFILE.daily_loss_halt,
            max_open_orders=EQUITY_RISK_PROFILE.max_open_orders,
            max_quote_age_seconds=5.0,
            intent_id=order_intent.intent_id,
            account_id=boundary.account_id,
            expected_position_units=expected_position_units,
            order_cutoff=order_cutoff,
        )
    )
    strategy.release_paper_intent(
        intent_id=order_intent.intent_id,
        target_quantity=order_intent.target_quantity,
    )
    if node_type is None:
        from nautilus_trader.live.node import TradingNode

        node_type = TradingNode
    if data_factory is None:
        from nautilus_trader.adapters.interactive_brokers.factories import (
            InteractiveBrokersLiveDataClientFactory,
        )

        data_factory = InteractiveBrokersLiveDataClientFactory
    if exec_factory is None:
        from nautilus_trader.adapters.interactive_brokers.factories import (
            InteractiveBrokersLiveExecClientFactory,
        )

        exec_factory = InteractiveBrokersLiveExecClientFactory

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
        nonlocal interrupted
        while not heartbeat_stop.wait(heartbeat_interval):
            try:
                if heartbeat is not None:
                    heartbeat()
                if stop_requested is not None and stop_requested():
                    interrupted = True
                    node.stop()
                    return
            except BaseException as exc:
                heartbeat_errors.append(exc)
                node.stop()
                return

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, _stop)
        node.add_data_client_factory("IB", data_factory)
        node.add_exec_client_factory("IB", exec_factory)
        node.trader.add_strategy(strategy)
        node.build()
        if interrupted:
            return False
        heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            name="alpha-ibkr-paper-heartbeat",
            daemon=True,
        )
        heartbeat_thread.start()
        # TradingNode waits for client connection, execution reconciliation, and portfolio
        # initialization before Strategy.on_start performs ALPHA's exact flat-account check.
        node.run(raise_exception=True)
    finally:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join()
        for restore_signal, handler in previous_handlers.items():
            signal.signal(restore_signal, handler)
        node.dispose()
    if heartbeat_errors:
        raise RuntimeError("IBKR paper heartbeat journal failed") from heartbeat_errors[0]
    return not interrupted


__all__ = [
    "EQUITY_RISK_PROFILE",
    "FUTURES_PROBE_RISK_PROFILE",
    "IBKR_CLIENT_ID_MAX",
    "IBKR_CLIENT_ID_MIN",
    "IBKR_PAPER_HOST",
    "IBKR_PAPER_PORT",
    "IBKRPaperBoundary",
    "IBKRWarmup",
    "OrderIntent",
    "PaperRiskProfile",
    "build_ibkr_client_configs",
    "claim_order_intent_release",
    "load_order_intent",
    "load_ibkr_warmup",
    "persist_order_intent",
    "run_ibkr_paper",
]
