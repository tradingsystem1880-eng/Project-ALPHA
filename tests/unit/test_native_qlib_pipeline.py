import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_core import DataError


def predictions() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "session_ts": datetime(2024, 4, 1, tzinfo=UTC) + timedelta(days=i),
                "symbol": "SYN00",
                "score": score,
                "synthetic_target": 0.0,
            }
            for i, score in enumerate([0.7, -0.2, 0.4, -0.8])
        ]
    )


def test_native_scores_execute_only_on_next_open_and_reconcile_cash() -> None:
    from alpha_cli.native_qlib_pipeline import replay_predictions

    result, accounts, links = replay_predictions(predictions(), fee_bps=10, slippage_bps=2)
    assert len(result.decision_trace) == 4
    assert len(result.equity_curve) == 5
    assert result.fills == 4
    assert [fill.side for fill in result.fill_trace] == ["BUY", "SELL", "BUY", "SELL"]
    assert all(fill.quantity == 1 for fill in result.fill_trace)
    for fill, link in zip(result.fill_trace, links, strict=True):
        assert fill.ts.isoformat() == link["executable_at"]
        assert fill.ts > datetime.fromisoformat(link["available_at"])
        assert fill.instrument_id == "SYN00.SIM"
    assert sum(row.commission for row in accounts) > 0
    assert accounts[-1].position_units == 0


@pytest.mark.bias_guard
def test_future_score_poison_cannot_change_prior_native_fills() -> None:
    from alpha_cli.native_qlib_pipeline import replay_predictions

    data = predictions()
    poison = data.with_columns(
        pl.when(pl.col("session_ts") >= datetime(2024, 4, 3, tzinfo=UTC))
        .then(-pl.col("score"))
        .otherwise(pl.col("score"))
        .alias("score")
    )
    first, _, _ = replay_predictions(data, fee_bps=0, slippage_bps=0)
    second, _, _ = replay_predictions(poison, fee_bps=0, slippage_bps=0)
    cutoff = datetime(2024, 4, 4, tzinfo=UTC)
    assert [f for f in first.fill_trace if f.ts < cutoff] == [
        f for f in second.fill_trace if f.ts < cutoff
    ]
    assert first.fill_trace != second.fill_trace  # poison actually changes the later decisions


@pytest.mark.bias_guard
def test_future_poison_guard_rejects_deliberately_leaky_twin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_cli.native_qlib_pipeline import replay_predictions
    from alpha_strategies.signal_replay import SignalReplay

    data = predictions()
    poison = data.with_columns(
        pl.when(pl.col("session_ts") >= datetime(2024, 4, 3, tzinfo=UTC))
        .then(-pl.col("score"))
        .otherwise(pl.col("score"))
        .alias("score")
    )
    monkeypatch.setattr(SignalReplay, "_signal", lambda self: int(self._signals[-1]))
    first, _, _ = replay_predictions(data, fee_bps=0, slippage_bps=0)
    second, _, _ = replay_predictions(poison, fee_bps=0, slippage_bps=0)
    cutoff = datetime(2024, 4, 3, tzinfo=UTC)
    with pytest.raises(AssertionError):
        assert [f for f in first.fill_trace if f.ts < cutoff] == [
            f for f in second.fill_trace if f.ts < cutoff
        ]


def test_terminal_open_quote_executes_last_score_without_invented_liquidation() -> None:
    from alpha_cli.native_qlib_pipeline import replay_predictions

    data = predictions().with_columns(pl.lit(0.7).alias("score"))
    result, accounts, links = replay_predictions(data, fee_bps=0, slippage_bps=0)
    assert len(result.decision_trace) == len(links) == 4
    assert len(result.equity_curve) == 5
    assert result.fills == 1 and result.trades == []
    assert accounts[-1].position_units == 1


def test_existing_signal_replay_defaults_keep_their_volatility_warmup() -> None:
    from alpha_backtest.engine import run_backtest
    from alpha_backtest.feed import daily_bar_type, to_execution_feed
    from alpha_backtest.instruments import equity_instrument
    from alpha_core import Bar
    from alpha_strategies.signal_replay import SignalReplay

    instrument = equity_instrument("SYN00")
    bar_type = daily_bar_type("SYN00")
    strategy = SignalReplay(
        instrument_id=instrument.id,
        bar_type=bar_type,
        signals=[1] * 4,
        min_history=1,
        allow_short=False,
    )
    bars = [
        Bar(
            symbol="SYN00",
            ts=datetime(2024, 4, 1, tzinfo=UTC) + timedelta(days=i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100 + i,
            volume=1000,
        )
        for i in range(4)
    ]
    result = run_backtest(instrument, to_execution_feed(bars, bar_type), strategy)
    assert result.orders == 0 and result.decision_trace == ()


@pytest.mark.parametrize("tamper_input,fee", [(False, 1.0), (True, 1.0), (False, 1e12)])
def test_composer_isolates_qrun_stage_and_exports_real_native_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tamper_input: bool,
    fee: float,
) -> None:
    """Stub only Qlib subprocesses; actual native strategy, fills and cash still execute."""
    from alpha_cli import native_qlib_pipeline as pipeline

    root = Path(pipeline.__file__).resolve().parents[4]
    source = root / "apps/alpha-web/frontend/public/demos/native-qlib"
    output = tmp_path / "run with spaces"
    calls: list[list[str]] = []
    monkeypatch.setenv("ALPHA_BROKER_TOKEN", "test-sentinel-do-not-inherit")

    def qlib_stage(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert "ALPHA_BROKER_TOKEN" not in kwargs["env"]
        assert kwargs["env"]["HOME"] == str(output)
        if command[1:3] == ["-m", "qlib.cli.run"]:
            assert json.loads((output / "workflow.yaml").read_text())["qlib_init"][
                "provider_uri"
            ] == str(output / "empty_provider")
        elif command[1].endswith("export.py"):
            for name in ["native_predictions.csv", "daily_signal_diagnostics.csv"]:
                shutil.copyfile(source / name, output / name)
            artifacts = output / "mlruns/run/artifacts"
            artifacts.mkdir(parents=True)
            (output / "qrun-result.json").write_text(
                json.dumps(
                    {
                        "synthetic": True,
                        "qlib_version": "0.9.7",
                        "recorder": {
                            "status": "FINISHED",
                            "run_uuid": "f" * 32,
                            "artifact_uri": str(artifacts),
                        },
                    }
                )
            )
            if tamper_input:
                (output / "synthetic_input.parquet").write_bytes(b"changed while running")
        else:
            assert command[1] == "-c"  # runtime pin preflight, no fit in this unit test
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(pipeline.subprocess, "run", qlib_stage)
    if fee > 1e9:
        with pytest.raises(DataError, match="did not fully execute"):
            pipeline.build_pipeline(output, Path(sys.executable), fee_bps=fee, slippage_bps=2)
        assert not (output / "result.json").exists()
        return
    if tamper_input:
        with pytest.raises(DataError, match="changed during native execution"):
            pipeline.build_pipeline(output, Path(sys.executable), fee_bps=1, slippage_bps=2)
        assert not (output / "result.json").exists()
        return
    pipeline.build_pipeline(output, Path(sys.executable), fee_bps=1, slippage_bps=2)
    data = json.loads((output / "result.json").read_text())
    assert len(calls) == 3 and len(data["fills"]) == 10
    assert data["pipeline"]["predictions_consumed"] == 16
    assert "--fee-bps 1" in data["reproduction_template"]
    assert "--slippage-bps 2" in data["reproduction_template"]
    assert data["admission"] == "not_admitted"
    provenance = json.loads((output / "provenance.json").read_text())
    for name in [
        "workers/qlib/examples/native-synthetic/export.py",
        "packages/alpha-strategies/src/alpha_strategies/base.py",
        "packages/alpha-backtest/src/alpha_backtest/instruments.py",
        "packages/alpha-backtest/src/alpha_backtest/frictions.py",
    ]:
        assert (
            provenance["source_sha256"][name]
            == hashlib.sha256((root / name).read_bytes()).hexdigest()
        )
    assert (
        hashlib.sha256(data["account_events_csv"].encode()).hexdigest()
        == data["artifact_sha256"]["account-events.csv"]
    )
    assert json.loads(capsys.readouterr().out)["fills"] == 10
    with pytest.raises(FileExistsError):
        pipeline.build_pipeline(output, Path(sys.executable), fee_bps=1, slippage_bps=2)
    assert len(calls) == 3  # existing output never triggers another fit


@pytest.mark.parametrize("fee,slip", [(-1, 0), (float("nan"), 0), (0, 10_000)])
def test_invalid_costs_fail_before_creating_output_or_fitting(
    tmp_path: Path,
    fee: float,
    slip: float,
) -> None:
    from alpha_cli.native_qlib_pipeline import build_pipeline

    output = tmp_path / "not-created"
    with pytest.raises(DataError):
        build_pipeline(output, Path(sys.executable), fee_bps=fee, slippage_bps=slip)
    assert not output.exists()


@pytest.mark.parametrize("kind", ["nan", "duplicate", "disordered", "intraday", "foreign"])
def test_invalid_prediction_identity_or_clock_fails(kind: str) -> None:
    from alpha_cli.native_qlib_pipeline import replay_predictions

    data = predictions()
    if kind == "nan":
        data = data.with_columns(pl.lit(float("nan")).alias("score"))
    elif kind == "duplicate":
        data = pl.concat([data, data.tail(1)])
    elif kind == "disordered":
        data = data.reverse()
    elif kind == "intraday":
        data = data.with_columns(pl.col("session_ts") + pl.duration(hours=1))
    else:
        data = data.with_columns(pl.lit("BTCUSD").alias("symbol"))
    with pytest.raises(DataError):
        replay_predictions(data, fee_bps=0, slippage_bps=0)
