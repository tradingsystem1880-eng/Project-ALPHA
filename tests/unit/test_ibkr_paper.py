"""Fail-closed IBKR Paper boundary and content-bound intent contracts."""

from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest

from alpha_cli._ibkr_paper import (
    EQUITY_RISK_PROFILE,
    IBKRPaperBoundary,
    OrderIntent,
    build_ibkr_client_configs,
    claim_order_intent_release,
    load_ibkr_warmup,
    load_order_intent,
    persist_order_intent,
    run_ibkr_paper,
)
from alpha_cli._runner import RunSpec
from alpha_core import Bar, DataError
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore

DIGEST_IMAGE = "ghcr.io/gnzsnz/ib-gateway@sha256:" + "a" * 64


def _spec() -> RunSpec:
    return RunSpec(
        lookback=20,
        skip=1,
        vol_window=10,
        target_vol=0.15,
        rebalance_every=1,
        max_leverage=0.10,
        allow_short=False,
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=504,
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name="ts_momentum",
    )


def _future_intent() -> OrderIntent:
    return OrderIntent.create(
        strategy="ts_momentum",
        strategy_version="approved-v1",
        parameters={},
        snapshot_id="spy",
        snapshot_sha256="c" * 64,
        instrument_id="SPY.ARCA",
        target_quantity=10.0,
        next_session="2099-01-03",
        risk_profile=EQUITY_RISK_PROFILE,
        knowledge_cutoff=datetime(2099, 1, 2, tzinfo=UTC),
        expires_at=datetime(2099, 1, 3, 14, 25, tzinfo=UTC),
    )


def _boundary(**overrides: object) -> IBKRPaperBoundary:
    kwargs: dict[str, object] = {
        "account_id": "DU1234567",
        "gateway_image": DIGEST_IMAGE,
        "allowed_instruments": ("SPY.ARCA",),
        "host": "127.0.0.1",
        "port": 4002,
        "client_id": 20,
        "paper_enabled": True,
        "ibkr_paper_enabled": True,
        "execution_requested": True,
    }
    kwargs.update(overrides)
    return IBKRPaperBoundary.create(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("account_id", "U123", "DU"),
        ("gateway_image", "ghcr.io/gnzsnz/ib-gateway:stable", "digest"),
        ("host", "0.0.0.0", "loopback"),
        ("port", 7497, "4002"),
        ("port", 4001, "4002"),
        ("client_id", 4, "client ID"),
        ("client_id", 28, "client ID"),
        ("paper_enabled", False, "two independent"),
        ("ibkr_paper_enabled", False, "two independent"),
    ],
)
def test_boundary_rejects_live_or_ambiguous_configuration(
    field: str, value: object, match: str
) -> None:
    with pytest.raises(DataError, match=match):
        _boundary(**{field: value})


def test_read_only_preflight_does_not_require_execution_flags() -> None:
    boundary = _boundary(
        paper_enabled=False,
        ibkr_paper_enabled=False,
        execution_requested=False,
    )
    assert boundary.account_id == "DU1234567"


def test_boundary_enforces_instrument_allowlist_and_explicit_micro_futures() -> None:
    boundary = _boundary(allowed_instruments=("SPY.ARCA", "MESZ26.CME", "ES.CME"))
    boundary.require_instrument("SPY.ARCA", asset_class="stock", strategy_generated=True)
    boundary.require_instrument("MESZ26.CME", asset_class="future", strategy_generated=False)
    with pytest.raises(DataError, match="allowlist"):
        boundary.require_instrument("QQQ.NASDAQ", asset_class="etf", strategy_generated=True)
    with pytest.raises(DataError, match="strategy-generated"):
        boundary.require_instrument("MESZ26.CME", asset_class="future", strategy_generated=True)
    with pytest.raises(DataError, match="explicit dated micro"):
        boundary.require_instrument("ES.CME", asset_class="future", strategy_generated=False)
    with pytest.raises(DataError, match="non-empty"):
        _boundary(allowed_instruments=())


def test_native_nautilus_configs_are_paper_loopback_and_read_only() -> None:
    data_config, exec_config = build_ibkr_client_configs(_boundary(), read_only=True)
    assert data_config.ibg_host == "127.0.0.1"
    assert data_config.ibg_port == 4002
    assert exec_config.account_id == "DU1234567"
    assert exec_config.ibg_client_id == 21
    assert exec_config.dockerized_gateway.trading_mode == "paper"
    assert exec_config.dockerized_gateway.read_only_api is True
    assert exec_config.dockerized_gateway.container_image == DIGEST_IMAGE


def test_order_intent_hash_binds_all_authority_inputs() -> None:
    intent = OrderIntent.create(
        strategy="ts_momentum",
        strategy_version="approved-v1",
        parameters={"lookback": 252, "allow_short": False},
        snapshot_id="spy-2026-08-03",
        snapshot_sha256="b" * 64,
        instrument_id="SPY.ARCA",
        target_quantity=12.0,
        next_session="2026-08-04",
        risk_profile=EQUITY_RISK_PROFILE,
        knowledge_cutoff=datetime(2026, 8, 3, 21, tzinfo=UTC),
        expires_at=datetime(2026, 8, 4, 13, 25, tzinfo=UTC),
    )
    assert len(intent.intent_id) == 64
    assert intent == OrderIntent.from_dict(intent.to_dict())
    changed = OrderIntent.create(
        **{**intent.authority_payload(), "target_quantity": 13.0}  # type: ignore[arg-type]
    )
    assert changed.intent_id != intent.intent_id


def test_expired_intent_is_never_releasable() -> None:
    intent = OrderIntent.create(
        strategy="ts_momentum",
        strategy_version="approved-v1",
        parameters={},
        snapshot_id="spy",
        snapshot_sha256="c" * 64,
        instrument_id="SPY.ARCA",
        target_quantity=1.0,
        next_session="2026-08-04",
        risk_profile=EQUITY_RISK_PROFILE,
        knowledge_cutoff=datetime(2026, 8, 3, tzinfo=UTC),
        expires_at=datetime(2026, 8, 4, 13, 25, tzinfo=UTC),
    )
    with pytest.raises(DataError, match="expired"):
        intent.require_releasable(intent.expires_at)


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"next_session": "bad"}, "ISO date"),
        ({"snapshot_sha256": "BAD"}, "snapshot SHA"),
        ({"target_quantity": float("nan")}, "target_quantity"),
        ({"strategy": ""}, "identifiers"),
        ({"knowledge_cutoff": datetime(2099, 1, 2)}, "timezone-aware"),
        (
            {
                "knowledge_cutoff": datetime(2099, 1, 3, tzinfo=UTC),
                "expires_at": datetime(2099, 1, 2, tzinfo=UTC),
            },
            "expiry",
        ),
        ({"parameters": {"bad": float("inf")}}, "finite JSON"),
    ],
)
def test_order_intent_rejects_invalid_authority_fields(
    override: dict[str, object], match: str
) -> None:
    values: dict[str, object] = {
        "strategy": "ts_momentum",
        "strategy_version": "approved-v1",
        "parameters": {},
        "snapshot_id": "spy",
        "snapshot_sha256": "c" * 64,
        "instrument_id": "SPY.ARCA",
        "target_quantity": 1.0,
        "next_session": "2099-01-03",
        "risk_profile": EQUITY_RISK_PROFILE,
        "knowledge_cutoff": datetime(2099, 1, 2, tzinfo=UTC),
        "expires_at": datetime(2099, 1, 3, tzinfo=UTC),
    }
    values.update(override)
    with pytest.raises(DataError, match=match):
        OrderIntent.create(**values)  # type: ignore[arg-type]


def test_order_intent_readers_reject_tamper_and_missing_files(tmp_path: Path) -> None:
    intent = _future_intent()
    tampered = intent.to_dict()
    tampered["intent_id"] = "f" * 64
    with pytest.raises(DataError, match="hash"):
        OrderIntent.from_dict(tampered)
    with pytest.raises(DataError, match="lowercase SHA"):
        load_order_intent(tmp_path, "bad")
    with pytest.raises(DataError, match="no immutable"):
        load_order_intent(tmp_path, "e" * 64)
    path = tmp_path / "paper" / "intents" / f"{intent.intent_id}.json"
    path.parent.mkdir(parents=True)
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(DataError, match="cannot read"):
        load_order_intent(tmp_path, intent.intent_id)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"schema_version": 2}, "unsupported order intent schema"),
        ({"risk_profile": {}}, "unsupported order intent risk profile"),
        (
            {"risk_profile": EQUITY_RISK_PROFILE.to_dict() | {"max_order_nav": 1.0}},
            "unsupported order intent risk profile",
        ),
        ({"parameters": []}, "invalid order intent"),
        ({"target_quantity": True}, "invalid order intent"),
        ({"strategy": 1}, "invalid order intent"),
        ({"expires_at": "bad"}, "invalid order intent"),
        ({"unexpected": "field"}, "invalid order intent"),
    ],
)
def test_order_intent_reader_rejects_invalid_documents(
    mutation: dict[str, object], match: str
) -> None:
    raw = _future_intent().to_dict() | mutation
    with pytest.raises(DataError, match=match):
        OrderIntent.from_dict(raw)


def test_intent_storage_rejects_content_and_filename_conflicts(tmp_path: Path) -> None:
    intent = _future_intent()
    path = persist_order_intent(tmp_path, intent)
    path.write_text("different", encoding="utf-8")
    with pytest.raises(DataError, match="immutable order intent conflict"):
        persist_order_intent(tmp_path, intent)

    other = OrderIntent.create(
        **{**intent.authority_payload(), "target_quantity": 11.0}  # type: ignore[arg-type]
    )
    wrong_path = tmp_path / "paper" / "intents" / f"{other.intent_id}.json"
    wrong_path.write_text(json.dumps(intent.to_dict()), encoding="utf-8")
    with pytest.raises(DataError, match="filename does not match"):
        load_order_intent(tmp_path, other.intent_id)


def test_order_intent_is_published_immutably_and_idempotently(tmp_path: Path) -> None:
    intent = OrderIntent.create(
        strategy="ts_momentum",
        strategy_version="approved-v1",
        parameters={},
        snapshot_id="spy",
        snapshot_sha256="c" * 64,
        instrument_id="SPY.ARCA",
        target_quantity=1.0,
        next_session="2026-08-04",
        risk_profile=EQUITY_RISK_PROFILE,
        knowledge_cutoff=datetime(2026, 8, 3, tzinfo=UTC),
        expires_at=datetime(2026, 8, 4, 13, 25, tzinfo=UTC),
    )
    path = persist_order_intent(tmp_path, intent)
    assert persist_order_intent(tmp_path, intent) == path
    assert OrderIntent.from_dict(json.loads(path.read_text())) == intent
    assert load_order_intent(tmp_path, intent.intent_id) == intent


def test_order_intent_release_claim_is_one_shot_across_processes(tmp_path: Path) -> None:
    intent = _future_intent()
    session_id = "20d917a3-05f1-4c41-9b88-ce0b0917c143"
    claim = claim_order_intent_release(tmp_path, intent.intent_id, session_id)
    assert claim.is_file()
    with pytest.raises(DataError, match="already claimed"):
        claim_order_intent_release(
            tmp_path,
            intent.intent_id,
            "54496726-73b1-4ec9-b341-bcf91c3d5cc6",
        )


def test_load_ibkr_warmup_requires_verified_raw_tiingo_snapshot(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path / "store")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=29)
    bars = pl.DataFrame(
        [
            {
                "ts": start + timedelta(days=index),
                "open": 100.0 + index,
                "high": 101.0 + index,
                "low": 99.0 + index,
                "close": 100.5 + index,
                "volume": 1_000.0,
            }
            for index in range(30)
        ],
        schema={
            "ts": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        },
    )
    identity = DatasetIdentity(
        symbol="SPY",
        provider="tiingo",
        provider_symbol="SPY",
        venue="ARCX",
        asset_class="etf",
        timeframe="1D",
        calendar="XNYS",
        currency="USD",
        price_basis="raw",
    )
    receipt = FetchReceipt.create(
        identity=identity,
        requested_start=start.date(),
        requested_end=end.date(),
        fetched_at=datetime(2026, 2, 1, tzinfo=UTC),
        adapter_version="1",
        parser_version="1",
        response_sha256="d" * 64,
        response_bytes=1,
        row_count=30,
        action_count=0,
        request_metadata={},
    )
    store.write_bars("SPY", bars)
    store.write_actions("SPY", [])
    store.write_provenance(
        "SPY",
        source="tiingo",
        adapter_version="1",
        parser_version="1",
        identity=identity,
        receipt=receipt,
    )
    create_snapshot(
        store,
        tmp_path / "snapshots",
        "spy",
        ["SPY"],
        source="tiingo",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )

    warmup = load_ibkr_warmup(
        tmp_path,
        "spy",
        "SPY",
        _spec(),
        expected_session=end.date(),
    )
    assert len(warmup.bars) == 30
    assert warmup.knowledge_cutoff == datetime(2026, 2, 1, tzinfo=UTC)


class _Trader:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.strategy: object | None = None

    def add_strategy(self, strategy: object) -> None:
        self.strategy = strategy
        self.calls.append("strategy")


class _Node:
    last: _Node | None = None

    def __init__(self, *, config: object) -> None:
        self.config = config
        self.calls: list[str] = ["init"]
        self.trader = _Trader(self.calls)
        type(self).last = self

    def add_data_client_factory(self, name: str, factory: object) -> None:
        assert name == "IB" and factory is _DataFactory
        self.calls.append("data")

    def add_exec_client_factory(self, name: str, factory: object) -> None:
        assert name == "IB" and factory is _ExecFactory
        self.calls.append("exec")

    def build(self) -> None:
        self.calls.append("build")

    def run(self, *, raise_exception: bool) -> None:
        assert raise_exception
        self.calls.append("run")

    def stop(self) -> None:
        self.calls.append("stop")

    def dispose(self) -> None:
        self.calls.append("dispose")


class _DataFactory:
    pass


class _ExecFactory:
    pass


class _Sink:
    def emit(self, event_type: str, payload: object, *, ts_event_ns: int | None = None) -> None:
        del event_type, payload, ts_event_ns


def test_native_ibkr_runner_assembles_reconciled_node_and_exact_intent() -> None:
    bars = [
        Bar(
            symbol="SPY",
            ts=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1_000.0,
        )
        for index in range(30)
    ]
    from alpha_cli._ibkr_paper import IBKRWarmup

    completed = run_ibkr_paper(
        _spec(),
        boundary=_boundary(),
        symbol="SPY",
        instrument_id="SPY.ARCA",
        warmup=IBKRWarmup(
            bars=bars,
            snapshot_sha256="c" * 64,
            knowledge_cutoff=datetime(2099, 1, 2, tzinfo=UTC),
            expected_session=date(2099, 1, 2),
        ),
        order_intent=_future_intent(),
        order_cutoff=datetime(2099, 1, 3, 14, 25, tzinfo=UTC),
        expected_position_units=0.0,
        event_sink=_Sink(),
        trader_id="IBP-TEST",
        node_type=_Node,
        data_factory=_DataFactory,
        exec_factory=_ExecFactory,
    )
    assert completed is True
    assert _Node.last is not None
    assert _Node.last.calls == ["init", "data", "exec", "strategy", "build", "run", "dispose"]
    strategy = cast(Any, _Node.last.trader.strategy)
    assert strategy is not None and strategy.pending_target == 10.0


class _SignalBuildNode(_Node):
    def build(self) -> None:
        super().build()
        os.kill(os.getpid(), signal.SIGTERM)


class _HeartbeatNode(_Node):
    def run(self, *, raise_exception: bool) -> None:
        assert raise_exception
        self.calls.append("run")
        deadline = time.monotonic() + 1.0
        while "stop" not in self.calls and time.monotonic() < deadline:
            time.sleep(0.001)


def _run_with_node(node_type: type[_Node], **overrides: object) -> bool:
    bars = [
        Bar(
            symbol="SPY",
            ts=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1_000.0,
        )
        for index in range(30)
    ]
    from alpha_cli._ibkr_paper import IBKRWarmup

    kwargs: dict[str, object] = {
        "boundary": _boundary(),
        "symbol": "SPY",
        "instrument_id": "SPY.ARCA",
        "warmup": IBKRWarmup(
            bars=bars,
            snapshot_sha256="c" * 64,
            knowledge_cutoff=datetime(2099, 1, 2, tzinfo=UTC),
            expected_session=date(2099, 1, 2),
        ),
        "order_intent": _future_intent(),
        "order_cutoff": datetime(2099, 1, 3, 14, 25, tzinfo=UTC),
        "expected_position_units": 0.0,
        "event_sink": _Sink(),
        "trader_id": "IBP-TEST",
        "heartbeat_interval": 0.001,
        "node_type": node_type,
        "data_factory": _DataFactory,
        "exec_factory": _ExecFactory,
    }
    kwargs.update(overrides)
    return run_ibkr_paper(_spec(), **kwargs)  # type: ignore[arg-type]


def test_native_runner_handles_signal_during_build_without_running() -> None:
    assert _run_with_node(_SignalBuildNode) is False
    assert _SignalBuildNode.last is not None
    assert _SignalBuildNode.last.calls[-2:] == ["stop", "dispose"]


def test_native_runner_halts_on_stop_request_and_heartbeat_failure() -> None:
    assert _run_with_node(_HeartbeatNode, stop_requested=lambda: True) is False
    with pytest.raises(RuntimeError, match="heartbeat journal failed"):
        _run_with_node(
            _HeartbeatNode,
            heartbeat=lambda: (_ for _ in ()).throw(OSError("journal unavailable")),
        )


def test_native_runner_rejects_risk_or_heartbeat_before_node_construction() -> None:
    warmup = type(
        "Warmup",
        (),
        {
            "bars": [],
            "snapshot_sha256": "c" * 64,
            "knowledge_cutoff": datetime(2099, 1, 2, tzinfo=UTC),
            "expected_session": date(2099, 1, 2),
        },
    )()
    kwargs = {
        "boundary": _boundary(),
        "symbol": "SPY",
        "instrument_id": "SPY.ARCA",
        "warmup": warmup,
        "order_intent": _future_intent(),
        "order_cutoff": datetime(2099, 1, 3, tzinfo=UTC),
        "expected_position_units": 0.0,
        "event_sink": _Sink(),
        "trader_id": "IBP-TEST",
        "node_type": _Node,
        "data_factory": _DataFactory,
        "exec_factory": _ExecFactory,
    }
    with pytest.raises(DataError, match="long-only"):
        run_ibkr_paper(replace(_spec(), allow_short=True), **kwargs)
    with pytest.raises(DataError, match="heartbeat_interval"):
        run_ibkr_paper(_spec(), heartbeat_interval=0.0, **kwargs)
    with pytest.raises(DataError, match="intent does not match warmup"):
        run_ibkr_paper(
            _spec(),
            order_intent=replace(_future_intent(), snapshot_sha256="d" * 64),
            **{key: value for key, value in kwargs.items() if key != "order_intent"},
        )


def test_load_warmup_rejects_unsafe_snapshot_id(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="invalid IBKR warmup snapshot"):
        load_ibkr_warmup(
            tmp_path,
            "../spy",
            "SPY",
            _spec(),
            expected_session=date(2026, 1, 1),
        )
