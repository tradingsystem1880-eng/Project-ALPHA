"""Safe Binance-public-data + local-sandbox paper assembly, all exercised offline with fakes."""

from __future__ import annotations

import hashlib
import json
import os
import signal
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import _ibkr_paper, _paper, daily_scheduler, paper_store
from alpha_cli._runner import RunSpec
from alpha_cli.main import app
from alpha_core import Bar, DataError
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore

runner = CliRunner()


def _spec(account_type: str = "CASH") -> RunSpec:
    return RunSpec(
        lookback=252,
        skip=21,
        vol_window=63,
        target_vol=0.15,
        rebalance_every=21,
        max_leverage=1.0,
        allow_short=account_type == "MARGIN",
        periods_per_year=252,
        fee_bps=1.0,
        slippage_bps=2.0,
        starting_cash=100_000.0,
        account_type=account_type,
        train_size=504,
        test_size=63,
        embargo=5,
        anchored=False,
    )


def test_sandbox_exec_config_constructs() -> None:
    cfg = _paper.build_sandbox_exec_config(
        venue="SANDBOX", account_type="CASH", starting_cash=100_000.0, currency="USD"
    )
    assert str(cfg.venue) == "SANDBOX"
    assert cfg.bar_execution is False  # backtest parity: quotes fill, bars decide


def test_node_config_carries_the_sandbox_exec_client() -> None:
    cfg = _paper.build_sandbox_exec_config(
        venue="SANDBOX", account_type="MARGIN", starting_cash=50_000.0, currency="USD"
    )
    node = _paper.build_paper_node_config(trader_id="PAPER-001", exec_config=cfg)
    assert "SANDBOX" in node.exec_clients


def test_binance_data_config_is_public_live_and_instrument_scoped() -> None:
    config = _paper.build_binance_data_config("BTC/USDT")

    assert config.api_key is None and config.api_secret is None
    assert config.environment.value == "LIVE"
    assert {str(i) for i in config.instrument_provider.load_ids or ()} == {"BTCUSDT.BINANCE"}


def test_symbol_mapping_is_strict() -> None:
    assert str(_paper.binance_instrument_id("BTC/USDT")) == "BTCUSDT.BINANCE"
    with pytest.raises(DataError, match="BASE/USDT"):
        _paper.binance_instrument_id("BTC/USD")


class _FakeTrader:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.strategy: object | None = None

    def add_strategy(self, strategy: object) -> None:
        self.strategy = strategy
        self.calls.append("strategy")


class _FakeNode:
    calls: list[str] = []
    last: _FakeNode | None = None

    def __init__(self, *, config: object) -> None:
        del config
        type(self).last = self
        self.trader = _FakeTrader(self.calls)
        self.calls.append("init")

    def add_data_client_factory(self, name: str, factory: type[object]) -> None:
        assert name == "BINANCE" and factory is _FakeDataFactory
        self.calls.append("data_factory")

    def add_exec_client_factory(self, name: str, factory: type[object]) -> None:
        assert name == "BINANCE" and factory is _FakeExecFactory
        self.calls.append("exec_factory")

    def build(self) -> None:
        assert self.trader.strategy is not None
        self.calls.append("build")

    def run(self, raise_exception: bool = False) -> None:
        assert raise_exception is True
        self.calls.append("run")

    def stop(self) -> None:
        self.calls.append("stop")

    def dispose(self) -> None:
        self.calls.append("dispose")


class _FakeDataFactory:
    pass


class _FakeExecFactory:
    pass


def _warmup_bars(n: int = 300) -> list[Bar]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol="BTC/USDT",
            ts=start + timedelta(days=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1_000.0,
        )
        for i in range(n)
    ]


def test_run_paper_registers_factories_and_strategy_before_build_and_disposes() -> None:
    _FakeNode.calls = []
    completed = _paper.run_paper(
        _spec("MARGIN"),
        symbol="BTC/USDT",
        warmup_bars=_warmup_bars(),
        node_type=_FakeNode,
        data_factory=_FakeDataFactory,
        exec_factory=_FakeExecFactory,
    )

    assert completed is True
    assert _FakeNode.calls == [
        "init",
        "data_factory",
        "exec_factory",
        "strategy",
        "build",
        "run",
        "dispose",
    ]


class _FailingNode(_FakeNode):
    def run(self, raise_exception: bool = False) -> None:
        del raise_exception
        self.calls.append("run")
        raise RuntimeError("feed failed")


def test_run_paper_always_disposes_on_runtime_failure() -> None:
    _FailingNode.calls = []
    with pytest.raises(RuntimeError, match="feed failed"):
        _paper.run_paper(
            _spec("MARGIN"),
            symbol="BTC/USDT",
            warmup_bars=_warmup_bars(),
            node_type=_FailingNode,
            data_factory=_FakeDataFactory,
            exec_factory=_FakeExecFactory,
        )
    assert _FailingNode.calls[-1] == "dispose"


class _FailingBuildNode(_FakeNode):
    def build(self) -> None:
        self.calls.append("build")
        raise RuntimeError("build failed")


def test_run_paper_disposes_when_node_build_fails() -> None:
    _FailingBuildNode.calls = []
    with pytest.raises(RuntimeError, match="build failed"):
        _paper.run_paper(
            _spec("MARGIN"),
            symbol="BTC/USDT",
            warmup_bars=_warmup_bars(),
            node_type=_FailingBuildNode,
            data_factory=_FakeDataFactory,
            exec_factory=_FakeExecFactory,
        )
    assert _FailingBuildNode.calls[-2:] == ["build", "dispose"]


class _SignalNode(_FakeNode):
    def run(self, raise_exception: bool = False) -> None:
        assert raise_exception is True
        self.calls.append("run")
        os.kill(os.getpid(), signal.SIGTERM)


def test_run_paper_handles_sigterm_and_restores_handler() -> None:
    _SignalNode.calls = []
    previous = signal.getsignal(signal.SIGTERM)

    completed = _paper.run_paper(
        _spec("MARGIN"),
        symbol="BTC/USDT",
        warmup_bars=_warmup_bars(),
        node_type=_SignalNode,
        data_factory=_FakeDataFactory,
        exec_factory=_FakeExecFactory,
    )

    assert completed is False
    assert _SignalNode.calls[-3:] == ["run", "stop", "dispose"]
    assert signal.getsignal(signal.SIGTERM) is previous


class _SignalDuringBuildNode(_FakeNode):
    def build(self) -> None:
        super().build()
        os.kill(os.getpid(), signal.SIGTERM)


def test_run_paper_honors_sigterm_during_build_without_starting_node() -> None:
    _SignalDuringBuildNode.calls = []
    previous = signal.getsignal(signal.SIGTERM)

    completed = _paper.run_paper(
        _spec("MARGIN"),
        symbol="BTC/USDT",
        warmup_bars=_warmup_bars(),
        node_type=_SignalDuringBuildNode,
        data_factory=_FakeDataFactory,
        exec_factory=_FakeExecFactory,
    )

    assert completed is False
    assert "run" not in _SignalDuringBuildNode.calls
    assert _SignalDuringBuildNode.calls[-3:] == ["build", "stop", "dispose"]
    assert signal.getsignal(signal.SIGTERM) is previous


def _snapshot(
    root: Path,
    *,
    source: str = "ccxt:binance",
    symbol: str = "BTC/USDT",
    start: datetime,
    n: int,
) -> None:
    rows: list[dict[str, Any]] = []
    for i in range(n):
        ts = start + timedelta(days=i)
        rows.append(
            {"ts": ts, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}
        )
    store = ParquetStore(root / "store")
    store.write_bars(symbol, pl.DataFrame(rows))
    store.write_provenance(
        symbol,
        source=source,
        adapter_version="test",
        parser_version="test",
    )
    create_snapshot(
        store,
        root / "snapshots",
        "warmup",
        [symbol],
        source=source,
        adapter_version="test",
        parser_version="test",
        created_at=start,
    )


@pytest.mark.bias_guard
def test_snapshot_warmup_enforces_provider_future_and_freshness(tmp_path: Path) -> None:
    now = datetime(2026, 7, 19, 12, tzinfo=UTC)
    today = now.replace(hour=0)
    _snapshot(tmp_path, start=today - timedelta(days=300), n=300)
    bars = _paper.load_paper_warmup(tmp_path, "warmup", "BTC/USDT", _spec("MARGIN"), now=now)
    assert len(bars) == 300

    wrong = tmp_path / "wrong"
    _snapshot(wrong, source="ccxt:coinbase", start=today - timedelta(days=300), n=300)
    # Relabelling only the mutable top-level manifest cannot change the hashed pull sidecar.
    wrong_manifest_path = wrong / "snapshots" / "warmup" / "manifest.json"
    wrong_manifest = json.loads(wrong_manifest_path.read_text(encoding="utf-8"))
    wrong_manifest["source"] = "ccxt:binance"
    wrong_manifest_path.write_text(json.dumps(wrong_manifest), encoding="utf-8")
    with pytest.raises(DataError, match="matching hashed ccxt:binance"):
        _paper.load_paper_warmup(wrong, "warmup", "BTC/USDT", _spec("MARGIN"), now=now)

    future = tmp_path / "future"
    _snapshot(future, start=today - timedelta(days=299), n=300)
    with pytest.raises(DataError, match="future bar"):
        _paper.load_paper_warmup(future, "warmup", "BTC/USDT", _spec("MARGIN"), now=now)

    stale = tmp_path / "stale"
    _snapshot(stale, start=now - timedelta(days=400), n=300)
    with pytest.raises(DataError, match="stale"):
        _paper.load_paper_warmup(stale, "warmup", "BTC/USDT", _spec("MARGIN"), now=now)


def test_snapshot_warmup_rejects_insufficient_strategy_history(tmp_path: Path) -> None:
    now = datetime(2026, 7, 19, 12, tzinfo=UTC)
    _snapshot(tmp_path, start=now.replace(hour=0) - timedelta(days=100), n=100)
    with pytest.raises(DataError, match="warmup requires"):
        _paper.load_paper_warmup(tmp_path, "warmup", "BTC/USDT", _spec("MARGIN"), now=now)


@pytest.mark.parametrize("mutation", ["missing", "noncanonical"])
def test_snapshot_warmup_requires_canonical_hashed_pull_provenance(
    tmp_path: Path, mutation: str
) -> None:
    now = datetime(2026, 7, 19, 12, tzinfo=UTC)
    _snapshot(tmp_path, start=now.replace(hour=0) - timedelta(days=300), n=300)
    snapshot_dir = tmp_path / "snapshots" / "warmup"
    manifest_path = snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    symbol_entry = manifest["symbols"]["BTC/USDT"]
    if mutation == "missing":
        symbol_entry.pop("provenance_file")
        symbol_entry.pop("provenance_sha256")
    else:
        canonical = snapshot_dir / symbol_entry["provenance_file"]
        alternate = snapshot_dir / "provenance" / "alternate.json"
        alternate.write_bytes(canonical.read_bytes())
        symbol_entry["provenance_file"] = "provenance/alternate.json"
        symbol_entry["provenance_sha256"] = hashlib.sha256(alternate.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DataError, match="canonical hashed pull provenance"):
        _paper.load_paper_warmup(tmp_path, "warmup", "BTC/USDT", _spec("MARGIN"), now=now)


def test_snapshot_warmup_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="invalid paper warmup snapshot id"):
        _paper.load_paper_warmup(
            tmp_path,
            "../outside",
            "BTC/USDT",
            _spec("MARGIN"),
            now=datetime(2026, 7, 19, tzinfo=UTC),
        )


def test_cli_preflight_reports_readiness_and_parity() -> None:
    result = runner.invoke(app, ["paper", "preflight", "BTC/USDT", "--strategy", "ma_crossover"])
    assert result.exit_code == 0, result.output
    assert "paper preflight OK" in result.output
    assert "MovingAverageCrossover constructed" in result.output  # same class as the backtest
    assert "bar_execution=False" in result.output
    assert "public Binance LIVE data" in result.output
    assert "local SANDBOX execution" in result.output


def test_cli_preflight_rejects_unknown_strategy() -> None:
    result = runner.invoke(app, ["paper", "preflight", "BTC/USDT", "--strategy", "nope"])
    assert result.exit_code != 0


@pytest.mark.parametrize("value", ["-1", "nan", "inf"])
def test_cli_preflight_rejects_invalid_starting_cash(value: str) -> None:
    result = runner.invoke(
        app,
        ["paper", "preflight", "BTC/USDT", f"--starting-cash={value}"],
    )
    assert result.exit_code != 0
    assert "starting_cash must be finite and > 0" in result.output


def test_cli_run_requires_explicit_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ALPHA_PAPER_ENABLED", raising=False)

    result = runner.invoke(
        app,
        ["paper", "run", "BTC/USDT", "--provider", "binance", "--snapshot", "warmup"],
    )

    assert result.exit_code != 0
    assert "ALPHA_PAPER_ENABLED=true" in result.output
    assert paper_store.list_sessions(tmp_path) == []


def test_cli_run_journals_a_completed_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    monkeypatch.setattr(_paper, "load_paper_warmup", lambda *args, **kwargs: _warmup_bars())
    seen: dict[str, object] = {}

    def fake_run(spec: RunSpec, **kwargs: object) -> bool:
        seen.update(kwargs)
        return True

    monkeypatch.setattr(_paper, "run_paper", fake_run)

    result = runner.invoke(
        app,
        [
            "paper",
            "run",
            "BTC/USDT",
            "--provider",
            "binance",
            "--snapshot",
            "warmup",
            "--strategy",
            "ma_crossover",
            "--param",
            "fast=5",
            "--param",
            "slow=20",
        ],
    )

    assert result.exit_code == 0, result.output
    sessions = paper_store.list_sessions(tmp_path)
    assert len(sessions) == 1
    session = sessions[0]
    assert f"-> session {session['session_id']}" in result.output
    assert session["status"] == "completed" and session["sandbox"] is True
    assert session["provider"] == "binance"
    assert session["instrument_id"] == "BTCUSDT.BINANCE"
    event_sink = seen["event_sink"]
    assert isinstance(event_sink, paper_store.PaperEventSink)
    assert event_sink.session_id == session["session_id"]
    events = paper_store.read_events(tmp_path, str(session["session_id"]))
    assert [event["event_type"] for event in events] == ["lifecycle", "lifecycle"]

    listed = runner.invoke(app, ["paper", "sessions", "--json"])
    shown = runner.invoke(app, ["paper", "show", str(session["session_id"]), "--json"])
    assert listed.exit_code == 0 and json.loads(listed.stdout)[0]["status"] == "completed"
    assert shown.exit_code == 0 and json.loads(shown.stdout)["symbol"] == "BTC/USDT"
    plain_list = runner.invoke(app, ["paper", "sessions"])
    plain_show = runner.invoke(app, ["paper", "show", str(session["session_id"])])
    assert (
        plain_list.exit_code == 0 and "completed BTC/USDT ma_crossover SANDBOX" in plain_list.stdout
    )
    assert plain_show.exit_code == 0 and '"sandbox": true' in plain_show.stdout


def test_cli_run_journals_runtime_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    monkeypatch.setattr(_paper, "load_paper_warmup", lambda *args, **kwargs: _warmup_bars())

    def fail_run(spec: RunSpec, **kwargs: object) -> bool:
        del spec, kwargs
        raise RuntimeError("public feed failed")

    monkeypatch.setattr(_paper, "run_paper", fail_run)

    result = runner.invoke(
        app,
        ["paper", "run", "BTC/USDT", "--snapshot", "warmup", "--strategy", "breakout"],
    )

    assert result.exit_code == 1
    assert "paper session failed: RuntimeError: public feed failed" in result.output
    session = paper_store.list_sessions(tmp_path)[0]
    assert session["status"] == "failed"
    assert session["terminal_error"] == "RuntimeError: public feed failed"
    events = paper_store.read_events(tmp_path, str(session["session_id"]))
    assert [cast(dict[str, object], event["payload"])["status"] for event in events] == [
        "starting",
        "failed",
    ]


def test_cli_run_rejects_kronos_before_creating_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    result = runner.invoke(
        app,
        [
            "paper",
            "run",
            "BTC/USDT",
            "--snapshot",
            "warmup",
            "--strategy",
            "kronos",
        ],
    )
    assert result.exit_code != 0
    assert "does not support live paper" in result.output
    assert paper_store.list_sessions(tmp_path) == []


def test_ibkr_preflight_is_read_only_redacted_and_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = "DU1234567"
    image = "ghcr.io/gnzsnz/ib-gateway@sha256:" + "a" * 64
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ACCOUNT", account)
    monkeypatch.setenv("ALPHA_IBKR_GATEWAY_IMAGE", image)

    result = runner.invoke(app, ["paper", "ibkr-preflight", "SPY.ARCA"])

    assert result.exit_code == 0, result.output
    assert "paper, read-only, digest pinned" in result.output
    assert "DU…4567" in result.output
    assert account not in result.output and image not in result.output


def test_ibkr_run_requires_both_independent_enable_flags_before_creating_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    monkeypatch.delenv("ALPHA_IBKR_PAPER_ENABLED", raising=False)
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ACCOUNT", "DU1234567")
    monkeypatch.setenv("ALPHA_IBKR_GATEWAY_IMAGE", "ghcr.io/gnzsnz/ib-gateway@sha256:" + "a" * 64)

    result = runner.invoke(
        app,
        [
            "paper",
            "ibkr-run",
            "SPY",
            "--instrument-id",
            "SPY.ARCA",
            "--snapshot",
            "spy",
            "--expected-session",
            "2099-01-02",
            "--next-session",
            "2099-01-03",
            "--order-cutoff",
            "2099-01-03T14:25:00+00:00",
            "--nav",
            "100000",
        ],
    )

    assert result.exit_code != 0
    assert "two independent enable flags" in result.output
    assert paper_store.list_sessions(tmp_path) == []


def test_ibkr_run_journals_native_paper_mode_with_offline_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ACCOUNT", "DU1234567")
    monkeypatch.setenv("ALPHA_IBKR_GATEWAY_IMAGE", "ghcr.io/gnzsnz/ib-gateway@sha256:" + "a" * 64)
    warmup = _ibkr_paper.IBKRWarmup(
        bars=_warmup_bars(),
        snapshot_sha256="b" * 64,
        knowledge_cutoff=datetime(2099, 1, 2, tzinfo=UTC),
        expected_session=datetime(2099, 1, 2, tzinfo=UTC).date(),
    )
    from alpha_cli._identity import strategy_fingerprint

    version = strategy_fingerprint("ts_momentum")
    assert version is not None
    approved = _ibkr_paper.OrderIntent.create(
        strategy="ts_momentum",
        strategy_version=version,
        parameters={
            "paper_nav": 100000.0,
            "lookback": 252,
            "skip": 21,
            "vol_window": 63,
            "target_vol": 0.15,
            "rebalance_every": 21,
        },
        snapshot_id="spy",
        snapshot_sha256="b" * 64,
        instrument_id="SPY.ARCA",
        target_quantity=10.0,
        next_session="2099-01-03",
        risk_profile=_ibkr_paper.EQUITY_RISK_PROFILE,
        knowledge_cutoff=datetime(2099, 1, 2, tzinfo=UTC),
        expires_at=datetime(2099, 1, 3, 14, 25, tzinfo=UTC),
    )
    _ibkr_paper.persist_order_intent(tmp_path, approved)
    monkeypatch.setattr(_ibkr_paper, "load_ibkr_warmup", lambda *args, **kwargs: warmup)
    seen: dict[str, object] = {}

    def fake_run(spec: RunSpec, **kwargs: object) -> bool:
        seen.update(kwargs)
        return True

    monkeypatch.setattr(_ibkr_paper, "run_ibkr_paper", fake_run)
    result = runner.invoke(
        app,
        [
            "paper",
            "ibkr-run",
            "SPY",
            "--instrument-id",
            "SPY.ARCA",
            "--snapshot",
            "spy",
            "--expected-session",
            "2099-01-02",
            "--next-session",
            "2099-01-03",
            "--order-cutoff",
            "2099-01-03T14:25:00+00:00",
            "--intent",
            approved.intent_id,
            "--nav",
            "100000",
        ],
    )

    assert result.exit_code == 0, result.output
    session = paper_store.list_sessions(tmp_path)[0]
    assert session["execution_mode"] == "ibkr_paper"
    assert session["sandbox"] is False
    assert session["risk_profile_id"] == "ibkr-equity-paper-v1"
    assert len(str(session["decision_artifact_id"])) == 64
    assert seen["instrument_id"] == "SPY.ARCA"


def test_ibkr_run_requires_scheduler_intent_after_all_other_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ACCOUNT", "DU1234567")
    monkeypatch.setenv("ALPHA_IBKR_GATEWAY_IMAGE", "ghcr.io/gnzsnz/ib-gateway@sha256:" + "a" * 64)
    monkeypatch.setattr(
        _ibkr_paper,
        "load_ibkr_warmup",
        lambda *args, **kwargs: _ibkr_paper.IBKRWarmup(
            bars=_warmup_bars(),
            snapshot_sha256="b" * 64,
            knowledge_cutoff=datetime(2099, 1, 2, tzinfo=UTC),
            expected_session=datetime(2099, 1, 2, tzinfo=UTC).date(),
        ),
    )
    result = runner.invoke(
        app,
        [
            "paper",
            "ibkr-run",
            "SPY",
            "--instrument-id",
            "SPY.ARCA",
            "--snapshot",
            "spy",
            "--expected-session",
            "2099-01-02",
            "--next-session",
            "2099-01-03",
            "--order-cutoff",
            "2099-01-03T14:25:00+00:00",
            "--nav",
            "100000",
        ],
    )
    assert result.exit_code != 0 and "requires --intent" in result.output
    assert paper_store.list_sessions(tmp_path) == []


def test_ibkr_run_journals_native_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ENABLED", "true")
    monkeypatch.setenv("ALPHA_IBKR_PAPER_ACCOUNT", "DU1234567")
    monkeypatch.setenv("ALPHA_IBKR_GATEWAY_IMAGE", "ghcr.io/gnzsnz/ib-gateway@sha256:" + "a" * 64)
    warmup = _ibkr_paper.IBKRWarmup(
        bars=_warmup_bars(),
        snapshot_sha256="b" * 64,
        knowledge_cutoff=datetime(2099, 1, 2, tzinfo=UTC),
        expected_session=datetime(2099, 1, 2, tzinfo=UTC).date(),
    )
    from alpha_cli._identity import strategy_fingerprint

    approved = _ibkr_paper.OrderIntent.create(
        strategy="ts_momentum",
        strategy_version=cast(str, strategy_fingerprint("ts_momentum")),
        parameters={
            "paper_nav": 100000.0,
            "lookback": 252,
            "skip": 21,
            "vol_window": 63,
            "target_vol": 0.15,
            "rebalance_every": 21,
        },
        snapshot_id="spy",
        snapshot_sha256="b" * 64,
        instrument_id="SPY.ARCA",
        target_quantity=10.0,
        next_session="2099-01-03",
        risk_profile=_ibkr_paper.EQUITY_RISK_PROFILE,
        knowledge_cutoff=datetime(2099, 1, 2, tzinfo=UTC),
        expires_at=datetime(2099, 1, 3, 14, 25, tzinfo=UTC),
    )
    _ibkr_paper.persist_order_intent(tmp_path, approved)
    monkeypatch.setattr(_ibkr_paper, "load_ibkr_warmup", lambda *args, **kwargs: warmup)
    monkeypatch.setattr(
        _ibkr_paper,
        "run_ibkr_paper",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("gateway disconnected")),
    )
    result = runner.invoke(
        app,
        [
            "paper",
            "ibkr-run",
            "SPY",
            "--instrument-id",
            "SPY.ARCA",
            "--snapshot",
            "spy",
            "--expected-session",
            "2099-01-02",
            "--next-session",
            "2099-01-03",
            "--order-cutoff",
            "2099-01-03T14:25:00+00:00",
            "--intent",
            approved.intent_id,
            "--nav",
            "100000",
        ],
    )
    assert result.exit_code == 1 and "gateway disconnected" in result.output
    assert paper_store.list_sessions(tmp_path)[0]["status"] == "failed"


def test_paper_operator_read_commands_and_safe_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    created = paper_store.create_session(
        tmp_path,
        provider="binance",
        symbol="BTC/USDT",
        instrument_id="BTCUSDT.BINANCE",
        strategy="ts_momentum",
        strategy_params={},
        snapshot_id="warmup",
        pid=os.getpid(),
    )
    session_id = str(created["session_id"])
    paper_store.append_event(tmp_path, session_id, "reconciliation_warning", {"detail": "test"})

    listed = runner.invoke(app, ["paper", "sessions"])
    assert listed.exit_code == 0 and session_id in listed.output and "SANDBOX" in listed.output
    shown = runner.invoke(app, ["paper", "show", session_id, "--json"])
    assert shown.exit_code == 0 and json.loads(shown.stdout)["session_id"] == session_id
    reconciled = runner.invoke(app, ["paper", "reconcile", session_id, "--json"])
    assert reconciled.exit_code == 0
    assert json.loads(reconciled.stdout)["operator_approval_supported"] is False
    stopped = runner.invoke(app, ["paper", "stop", session_id])
    assert stopped.exit_code == 0 and "will not be flattened" in stopped.output
    readiness = runner.invoke(app, ["paper", "readiness", "--json"])
    assert readiness.exit_code == 0 and json.loads(readiness.stdout)["paper_passed"] is False
    plain_reconcile = runner.invoke(app, ["paper", "reconcile", session_id])
    plain_readiness = runner.invoke(app, ["paper", "readiness"])
    assert plain_reconcile.exit_code == 0 and '"session_id"' in plain_reconcile.stdout
    assert plain_readiness.exit_code == 0 and '"paper_passed"' in plain_readiness.stdout


def test_paper_operator_commands_fail_closed_for_empty_or_unknown_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    empty = runner.invoke(app, ["paper", "sessions"])
    assert empty.exit_code == 0 and "no paper sessions" in empty.output
    for command in (["show", "missing"], ["reconcile", "missing"], ["stop", "missing"]):
        result = runner.invoke(app, ["paper", *command])
        assert result.exit_code != 0


def test_paper_run_rejects_any_non_binance_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_PAPER_ENABLED", "true")
    result = runner.invoke(
        app, ["paper", "run", "BTC/USDT", "--provider", "kraken", "--snapshot", "warmup"]
    )
    assert result.exit_code != 0 and "--provider must be 'binance'" in result.output


def test_ibkr_preflight_requires_secret_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHA_IBKR_PAPER_ACCOUNT", raising=False)
    monkeypatch.delenv("ALPHA_IBKR_GATEWAY_IMAGE", raising=False)
    result = runner.invoke(app, ["paper", "ibkr-preflight", "SPY.ARCA"])
    assert result.exit_code != 0 and "ALPHA_IBKR_PAPER_ACCOUNT" in result.output


def test_scheduler_operator_commands_are_thin_cli_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    config = tmp_path / "daily.json"
    config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        daily_scheduler,
        "scheduler_tick",
        lambda config_path, data_dir: [{"status": "intent_ready"}],
    )
    monkeypatch.setattr(
        daily_scheduler,
        "scheduler_status",
        lambda config_path, data_dir: [{"symbol": "SPY", "completed": False}],
    )
    tick = runner.invoke(app, ["paper", "scheduler-tick", "--config", str(config)])
    assert (
        tick.exit_code == 0 and json.loads(tick.stdout)["executed"][0]["status"] == "intent_ready"
    )
    status = runner.invoke(app, ["paper", "scheduler-status", "--config", str(config)])
    assert status.exit_code == 0 and json.loads(status.stdout)[0]["symbol"] == "SPY"


def test_scheduler_commands_normalize_errors_and_require_explicit_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    config = tmp_path / "daily.json"
    config.write_text("{}", encoding="utf-8")

    def fail(*args: object, **kwargs: object) -> list[object]:
        del args, kwargs
        raise DataError("scheduler unavailable")

    monkeypatch.setattr(daily_scheduler, "scheduler_tick", fail)
    monkeypatch.setattr(daily_scheduler, "scheduler_status", fail)
    assert runner.invoke(app, ["paper", "scheduler-tick", "--config", str(config)]).exit_code != 0
    assert runner.invoke(app, ["paper", "scheduler-status", "--config", str(config)]).exit_code != 0

    class Item:
        symbol = "SPY"

    monkeypatch.setattr(daily_scheduler, "load_schedule", lambda path: [Item()])
    monkeypatch.setattr(daily_scheduler, "repair_interrupted_cycle", lambda *args, **kwargs: None)
    repaired = runner.invoke(
        app,
        [
            "paper",
            "scheduler-repair",
            "SPY",
            "2026-08-03",
            "--config",
            str(config),
            "--acknowledge",
        ],
    )
    assert repaired.exit_code == 0 and "cleared interrupted" in repaired.output
    unknown = runner.invoke(
        app,
        ["paper", "scheduler-repair", "QQQ", "2026-08-03", "--config", str(config)],
    )
    invalid_date = runner.invoke(
        app,
        ["paper", "scheduler-repair", "SPY", "bad", "--config", str(config)],
    )
    assert unknown.exit_code != 0 and "not configured" in unknown.output
    assert invalid_date.exit_code != 0
