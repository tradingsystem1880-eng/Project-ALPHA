"""Wake-safe daily Tiingo → snapshot → Nautilus decision scheduler.

``launchd`` invokes one short tick every five minutes. Exchange calendars and immutable per-session
outcomes make missed wall-clock invocations harmless across sleep, wake, and daylight-saving
changes. A crash marker fails closed and requires explicit repair before that session can rerun.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from alpha_cli import _ibkr_paper, _runner
from alpha_cli._atomic import write_text
from alpha_core import DataError
from alpha_data.adapters.base import FetchReceipt
from alpha_data.adapters.tiingo_adapter import TiingoAdapter
from alpha_data.pipeline import stage_and_promote
from alpha_data.snapshot import create_snapshot, snapshot_manifest_hash, verify_snapshot
from alpha_data.store import ParquetStore


@dataclass(frozen=True, slots=True)
class DailyInstrument:
    symbol: str
    provider_symbol: str
    instrument_id: str
    asset_class: str
    venue: str
    calendar: str
    currency: str
    history_start: date
    correction_delay_minutes: int
    nav: float
    strategy: str
    strategy_params: tuple[tuple[str, float], ...]
    lookback: int
    skip: int
    vol_window: int
    target_vol: float
    rebalance_every: int
    cutoff_minutes_after_open: int


def _integer(raw: Mapping[str, object], name: str, *, minimum: int) -> int:
    value = raw.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise DataError(f"daily scheduler {name} must be an integer >= {minimum}")
    return value


def _text(raw: Mapping[str, object], name: str) -> str:
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"daily scheduler {name} must be a non-empty string")
    return value.strip()


def _identifier(raw: Mapping[str, object], name: str, *, punctuation: str) -> str:
    value = _text(raw, name)
    if (
        value in {".", ".."}
        or "/" in value
        or "\\" in value
        or any(not (char.isalnum() or char in punctuation) for char in value)
    ):
        raise DataError(f"daily scheduler {name} contains unsafe characters")
    return value


def _parse_instrument(raw: object) -> DailyInstrument:
    if not isinstance(raw, Mapping):
        raise DataError("daily scheduler instruments must be objects")
    try:
        history_start = date.fromisoformat(_text(raw, "history_start"))
    except ValueError as exc:
        raise DataError("daily scheduler history_start must be an ISO date") from exc
    nav = raw.get("nav")
    target_vol = raw.get("target_vol")
    if (
        isinstance(nav, bool)
        or not isinstance(nav, (int, float))
        or not math.isfinite(float(nav))
        or float(nav) <= 0.0
    ):
        raise DataError("daily scheduler nav must be finite and positive")
    if (
        isinstance(target_vol, bool)
        or not isinstance(target_vol, (int, float))
        or not math.isfinite(float(target_vol))
        or float(target_vol) <= 0.0
    ):
        raise DataError("daily scheduler target_vol must be finite and positive")
    raw_params = raw.get("strategy_params", {})
    if not isinstance(raw_params, Mapping):
        raise DataError("daily scheduler strategy_params must be an object")
    params: list[tuple[str, float]] = []
    for name, value in raw_params.items():
        if (
            not isinstance(name, str)
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise DataError("daily scheduler strategy_params must be numeric")
        params.append((name, float(value)))
    asset_class = _text(raw, "asset_class")
    if asset_class not in {"stock", "etf"}:
        raise DataError("daily scheduler supports only stock or ETF Tiingo datasets")
    return DailyInstrument(
        symbol=_identifier(raw, "symbol", punctuation="._-").upper(),
        provider_symbol=_identifier(raw, "provider_symbol", punctuation="._-").upper(),
        instrument_id=_identifier(raw, "instrument_id", punctuation="._:-").upper(),
        asset_class=asset_class,
        venue=_text(raw, "venue"),
        calendar=_text(raw, "calendar"),
        currency=_text(raw, "currency"),
        history_start=history_start,
        correction_delay_minutes=_integer(raw, "correction_delay_minutes", minimum=0),
        nav=float(nav),
        strategy=_text(raw, "strategy"),
        strategy_params=tuple(sorted(params)),
        lookback=_integer(raw, "lookback", minimum=1),
        skip=_integer(raw, "skip", minimum=0),
        vol_window=_integer(raw, "vol_window", minimum=2),
        target_vol=float(target_vol),
        rebalance_every=_integer(raw, "rebalance_every", minimum=1),
        cutoff_minutes_after_open=_integer(raw, "cutoff_minutes_after_open", minimum=0),
    )


def load_schedule(path: Path) -> tuple[DailyInstrument, ...]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"cannot read daily scheduler configuration at {path}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise DataError("daily scheduler configuration requires schema_version 1")
    instruments = raw.get("instruments")
    if not isinstance(instruments, list) or not instruments:
        raise DataError("daily scheduler requires a non-empty instruments list")
    parsed = tuple(_parse_instrument(item) for item in instruments)
    symbols = [item.symbol for item in parsed]
    if len(symbols) != len(set(symbols)):
        raise DataError("daily scheduler contains duplicate symbols")
    return parsed


def due_session(item: DailyInstrument, now: datetime) -> date:
    """Latest session whose close plus correction window is known by ``now``."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise DataError("daily scheduler clock must be timezone-aware")
    import exchange_calendars as xcals  # type: ignore[import-untyped]  # noqa: PLC0415

    calendar = xcals.get_calendar(item.calendar)
    utc_now = now.astimezone(UTC)
    candidate = calendar.date_to_session(utc_now.date(), direction="previous")
    eligible = calendar.session_close(candidate).to_pydatetime() + timedelta(
        minutes=item.correction_delay_minutes
    )
    if utc_now < eligible:
        candidate = calendar.previous_session(candidate)
    candidate_date = candidate.date()
    if not isinstance(candidate_date, date):
        raise DataError("exchange calendar returned an invalid session date")
    return candidate_date


def _run_spec(item: DailyInstrument) -> _runner.RunSpec:
    return _runner.RunSpec(
        lookback=item.lookback,
        skip=item.skip,
        vol_window=item.vol_window,
        target_vol=item.target_vol,
        rebalance_every=item.rebalance_every,
        max_leverage=0.10,
        allow_short=False,
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=item.nav,
        account_type="CASH",
        train_size=max(504, item.lookback + item.skip + 1, item.vol_window + 1),
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name=item.strategy,
        strategy_params=item.strategy_params,
    )


def _next_session_times(item: DailyInstrument, session: date) -> tuple[date, datetime]:
    import exchange_calendars as xcals  # noqa: PLC0415

    calendar = xcals.get_calendar(item.calendar)
    next_session = calendar.next_session(session.isoformat())
    cutoff = calendar.session_open(next_session).to_pydatetime() + timedelta(
        minutes=item.cutoff_minutes_after_open
    )
    return next_session.date(), cutoff.astimezone(UTC)


def _state_paths(data_dir: Path, item: DailyInstrument, session: date) -> tuple[Path, Path]:
    root = data_dir / "operations" / "daily-cycles" / item.symbol
    return root / f"{session.isoformat()}.json", root / f"{session.isoformat()}.running"


def _snapshot_receipt(snapshot_dir: Path, item: DailyInstrument, session: date) -> FetchReceipt:
    verify_snapshot(snapshot_dir)
    provenance = ParquetStore(snapshot_dir).read_provenance(item.symbol)
    if not isinstance(provenance, dict) or provenance.get("schema_version") != 2:
        raise DataError("daily snapshot requires versioned provenance")
    receipt = FetchReceipt.from_dict(provenance.get("receipt"))
    dataset = provenance.get("dataset")
    if (
        not isinstance(dataset, dict)
        or dataset.get("provider") != "tiingo"
        or dataset.get("symbol") != item.symbol
        or receipt.requested_end != session
    ):
        raise DataError("daily snapshot does not match the scheduled Tiingo session")
    return receipt


def _read_cycle_outcome(
    data_dir: Path,
    path: Path,
    item: DailyInstrument,
    session: date,
) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"invalid daily cycle outcome at {path}") from exc
    fields = {
        "schema_version",
        "status",
        "symbol",
        "session",
        "receipt_id",
        "snapshot_id",
        "snapshot_sha256",
        "intent_id",
        "simulation_engine",
    }
    expected_snapshot = f"daily-{item.symbol}-{session.isoformat()}"
    if (
        not isinstance(raw, dict)
        or set(raw) != fields
        or raw.get("schema_version") != 1
        or raw.get("status") not in {"no_action", "intent_ready"}
        or raw.get("symbol") != item.symbol
        or raw.get("session") != session.isoformat()
        or raw.get("snapshot_id") != expected_snapshot
        or raw.get("simulation_engine") != "nautilus_trader"
    ):
        raise DataError(f"invalid daily cycle outcome at {path}")
    receipt_id = raw.get("receipt_id")
    snapshot_sha256 = raw.get("snapshot_sha256")
    intent_id = raw.get("intent_id")
    if (
        not isinstance(receipt_id, str)
        or len(receipt_id) != 32
        or not isinstance(snapshot_sha256, str)
        or len(snapshot_sha256) != 64
        or (raw["status"] == "intent_ready" and not isinstance(intent_id, str))
        or (raw["status"] == "no_action" and intent_id is not None)
    ):
        raise DataError(f"invalid daily cycle outcome at {path}")
    snapshot_dir = data_dir / "snapshots" / expected_snapshot
    receipt = _snapshot_receipt(snapshot_dir, item, session)
    if receipt.receipt_id != receipt_id or snapshot_manifest_hash(snapshot_dir) != snapshot_sha256:
        raise DataError(f"daily cycle outcome evidence does not match {path}")
    if isinstance(intent_id, str):
        intent = _ibkr_paper.load_order_intent(data_dir, intent_id)
        if intent.snapshot_id != expected_snapshot or intent.snapshot_sha256 != snapshot_sha256:
            raise DataError(f"daily cycle intent does not match {path}")
    return raw


def execute_cycle(
    data_dir: Path,
    item: DailyInstrument,
    session: date,
    *,
    adapter_type: Any = TiingoAdapter,
    fetched_at: datetime | None = None,
) -> dict[str, object]:
    """Execute one content-bound daily cycle. Network access occurs only in the adapter."""
    outcome_path, marker_path = _state_paths(data_dir, item, session)
    if outcome_path.is_file():
        return _read_cycle_outcome(data_dir, outcome_path, item, session)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(marker_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise DataError(
            f"daily cycle {item.symbol} {session} has an interrupted run; explicit repair required"
        ) from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as marker:
        marker.write(datetime.now(UTC).isoformat())

    store = ParquetStore(data_dir / "store")
    snapshot_id = f"daily-{item.symbol}-{session.isoformat()}"
    snapshot_dir = data_dir / "snapshots" / snapshot_id
    if snapshot_dir.exists():
        snapshot_receipt = _snapshot_receipt(snapshot_dir, item, session)
    else:
        adapter = adapter_type(
            canonical_symbol=item.symbol,
            asset_class=item.asset_class,
            venue=item.venue,
            calendar=item.calendar,
            currency=item.currency,
        )
        result = adapter.fetch(item.provider_symbol, item.history_start, session)
        promoted = stage_and_promote(store, result, authoritative_source="tiingo")
        if result.receipt is None:
            raise DataError("daily Tiingo cycle lacks a fetch receipt")
        create_snapshot(
            store,
            data_dir / "snapshots",
            snapshot_id,
            [item.symbol],
            source="tiingo",
            adapter_version=result.receipt.adapter_version,
            parser_version=result.receipt.parser_version,
            created_at=fetched_at or result.receipt.fetched_at,
        )
        snapshot_receipt = _snapshot_receipt(snapshot_dir, item, session)
        if snapshot_receipt.receipt_id != promoted.receipt_id:
            raise DataError("daily snapshot receipt does not match the promoted candidate")
    bars, _ = _runner.load_bars(item.symbol, data_dir=data_dir, snapshot_id=snapshot_id)
    spec = _run_spec(item)
    simulation = _runner.run_full_backtest(bars, spec)
    decision = simulation.decision_trace[-1] if simulation.decision_trace else None
    intent_id: str | None = None
    status = "no_action"
    if decision is not None and decision.ts.date() == session:
        from alpha_cli._identity import strategy_fingerprint

        next_session, cutoff = _next_session_times(item, session)
        strategy_version = strategy_fingerprint(item.strategy)
        if strategy_version is None:
            raise DataError(f"registered strategy {item.strategy!r} has no version fingerprint")
        intent = _ibkr_paper.OrderIntent.create(
            strategy=item.strategy,
            strategy_version=strategy_version,
            parameters={
                "paper_nav": item.nav,
                "lookback": item.lookback,
                "skip": item.skip,
                "vol_window": item.vol_window,
                "target_vol": item.target_vol,
                "rebalance_every": item.rebalance_every,
                **dict(item.strategy_params),
            },
            snapshot_id=snapshot_id,
            snapshot_sha256=snapshot_manifest_hash(snapshot_dir),
            instrument_id=item.instrument_id,
            target_quantity=decision.target_quantity,
            next_session=next_session.isoformat(),
            risk_profile=_ibkr_paper.EQUITY_RISK_PROFILE,
            knowledge_cutoff=snapshot_receipt.fetched_at,
            expires_at=cutoff,
        )
        _ibkr_paper.persist_order_intent(data_dir, intent)
        intent_id = intent.intent_id
        status = "intent_ready"
    outcome: dict[str, object] = {
        "schema_version": 1,
        "status": status,
        "symbol": item.symbol,
        "session": session.isoformat(),
        "receipt_id": snapshot_receipt.receipt_id,
        "snapshot_id": snapshot_id,
        "snapshot_sha256": snapshot_manifest_hash(snapshot_dir),
        "intent_id": intent_id,
        "simulation_engine": "nautilus_trader",
    }
    write_text(outcome_path, json.dumps(outcome, indent=2, sort_keys=True) + "\n")
    marker_path.unlink()
    return outcome


def scheduler_tick(
    config_path: Path,
    data_dir: Path,
    *,
    now: datetime | None = None,
    execute: Any = execute_cycle,
) -> list[dict[str, object]]:
    """Catch up every configured instrument exactly once for its latest eligible session."""
    current = datetime.now(UTC) if now is None else now
    outcomes: list[dict[str, object]] = []
    for item in load_schedule(config_path):
        session = due_session(item, current)
        outcome_path, _ = _state_paths(data_dir, item, session)
        if outcome_path.is_file():
            continue
        outcomes.append(execute(data_dir, item, session))
    return outcomes


def scheduler_status(
    config_path: Path, data_dir: Path, *, now: datetime | None = None
) -> list[dict[str, object]]:
    """Return due/completed/interrupted state without contacting any provider."""
    current = datetime.now(UTC) if now is None else now
    rows: list[dict[str, object]] = []
    for item in load_schedule(config_path):
        session = due_session(item, current)
        outcome_path, marker_path = _state_paths(data_dir, item, session)
        rows.append(
            {
                "symbol": item.symbol,
                "due_session": session.isoformat(),
                "completed": outcome_path.is_file(),
                "interrupted": marker_path.is_file(),
                "outcome_path": str(outcome_path),
            }
        )
    return rows


def repair_interrupted_cycle(
    data_dir: Path, item: DailyInstrument, session: date, *, acknowledge: bool
) -> None:
    """Clear only a known crash marker; canonical promotion markers remain separate and blocking."""
    if not acknowledge:
        raise DataError("daily cycle repair requires explicit acknowledgement")
    outcome_path, marker_path = _state_paths(data_dir, item, session)
    if outcome_path.exists():
        raise DataError("completed daily cycle outcomes are immutable")
    if not marker_path.exists():
        raise DataError("no interrupted daily cycle marker exists")
    marker_path.unlink()


__all__ = [
    "DailyInstrument",
    "due_session",
    "execute_cycle",
    "load_schedule",
    "repair_interrupted_cycle",
    "scheduler_tick",
    "scheduler_status",
]
