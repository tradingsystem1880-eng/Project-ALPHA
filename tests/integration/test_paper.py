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

from alpha_cli import _paper, paper_store
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
