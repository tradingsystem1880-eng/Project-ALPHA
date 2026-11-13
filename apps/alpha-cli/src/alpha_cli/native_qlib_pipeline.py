"""Bounded synthetic qrun -> native Nautilus -> inert Results artifacts; no admission.

Shelved (2026-11-14, triage card F): not wired in, kept as a reproducible made-up-data
demonstration that real Qlib and NautilusTrader connect to ALPHA.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import BaseModel

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.frictions import BpsFeeModel
from alpha_backtest.instruments import equity_instrument
from alpha_backtest.results import AccountingTrace, BacktestResult
from alpha_core import Bar, DataError
from alpha_strategies.signal_replay import SignalReplay

INPUT_SHA256 = "b418e27d4cd4b78abbe2f0fa5ca1bebcad82900a094dd570c395b3defd5e4690"
SYMBOL = "SYN00"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: Any) -> None:
    def encode(item: Any) -> Any:
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        raise TypeError(f"unsupported artifact value: {type(item).__name__}")

    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=encode) + "\n")


def _costs(fee_bps: float, slippage_bps: float) -> None:
    if any(not math.isfinite(x) or x < 0 for x in (fee_bps, slippage_bps)):
        raise DataError("demo fees/slippage must be finite and nonnegative")
    if slippage_bps >= 10_000:
        raise DataError("demo slippage cannot make the bid nonpositive")


def replay_predictions(
    frame: pl.DataFrame,
    *,
    fee_bps: float,
    slippage_bps: float,
) -> tuple[BacktestResult, list[AccountingTrace], list[dict[str, Any]]]:
    """Bind modeled close availability to existing fixed-unit native next-open execution."""
    _costs(fee_bps, slippage_bps)
    if set(frame.columns) != {"session_ts", "symbol", "score", "synthetic_target"}:
        raise DataError("unexpected native prediction columns")
    rows = frame.to_dicts()
    keys: set[tuple[datetime, str]] = set()
    prior: tuple[datetime, str] | None = None
    for row in rows:
        ts, symbol = row["session_ts"], row["symbol"]
        if not isinstance(ts, datetime) or ts.tzinfo is None or ts.utcoffset() != timedelta(0):
            raise DataError("native synthetic sessions require aware UTC")
        if (ts.hour, ts.minute, ts.second, ts.microsecond) != (0, 0, 0, 0):
            raise DataError("session identity must be midnight; availability is separate")
        if (
            not isinstance(symbol, str)
            or len(symbol) != 5
            or not symbol.startswith("SYN")
            or not symbol[3:].isdigit()
        ):
            raise DataError("only explicitly synthetic instruments are accepted")
        if not all(
            isinstance(row[k], (int, float)) and math.isfinite(row[k])
            for k in ("score", "synthetic_target")
        ):
            raise DataError("native scores and constructed targets must be finite")
        key = (ts, symbol)
        if key in keys or (prior is not None and key <= prior):
            raise DataError("native prediction identities must be unique and ordered")
        keys.add(key)
        prior = key
    selected = [row for row in rows if row["symbol"] == SYMBOL]
    if not selected:
        raise DataError("the fixed SYN00 demo instrument is missing")
    dates = [row["session_ts"] for row in selected]
    terminal = dates[-1] + timedelta(days=1)
    while terminal.weekday() >= 5:
        terminal += timedelta(days=1)
    dates.append(terminal)
    bars = [
        Bar(
            symbol=SYMBOL,
            ts=ts,
            open=100 + i,
            high=100.25 + i,
            low=99.75 + i,
            close=100.1 + i,
            volume=1_000_000,
        )
        for i, ts in enumerate(dates)
    ]
    links = [
        {
            "session_ts": row["session_ts"].isoformat(),
            "symbol": SYMBOL,
            "instrument_id": f"{SYMBOL}.SIM",
            "score": row["score"],
            "signal": int(row["score"] > 0),
            "available_at": (row["session_ts"] + timedelta(hours=23)).isoformat(),
            "executable_at": dates[i + 1].isoformat(),
        }
        for i, row in enumerate(selected)
    ]
    instrument = equity_instrument(SYMBOL)
    bar_type = daily_bar_type(SYMBOL)
    strategy = SignalReplay(
        instrument_id=instrument.id,
        bar_type=bar_type,
        signals=[row["signal"] for row in links],
        min_history=1,
        rebalance_every=1,
        allow_short=False,
        fixed_quantity=1,
    )
    # Keep the extra opening quote, never a phantom extra decision bar.
    feed = to_execution_feed(bars, bar_type, slippage_bps=slippage_bps)[:-1]
    accounts: list[AccountingTrace] = []
    result = run_backtest(
        instrument,
        feed,
        strategy,
        starting_cash=1_000_000,
        fee_bps=fee_bps,
        accounting_trace=accounts,
    )
    expected = {datetime.fromisoformat(row["executable_at"]) for row in links}
    if any(
        fill.ts not in expected or fill.instrument_id != f"{SYMBOL}.SIM"
        for fill in result.fill_trace
    ):
        raise DataError("native fills do not reconcile to declared next opening events")
    return result, accounts, links


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_pipeline(output: Path, qlib_python: Path, *, fee_bps: float, slippage_bps: float) -> None:
    """Run only the bundled fabricated fixture; never load owner data or publish a run."""
    _costs(fee_bps, slippage_bps)
    if importlib.metadata.version("nautilus-trader") != "1.228.0":
        raise DataError("the pinned native demo requires NautilusTrader 1.228.0")
    root = Path(__file__).resolve().parents[4]
    fixture = root / "workers/qlib/examples/native-synthetic"
    qlib_python = qlib_python.absolute()
    if not qlib_python.is_file():
        raise DataError("an existing isolated Qlib Python/qrun environment is required")
    input_bytes = (fixture / "input.parquet").read_bytes()
    if hashlib.sha256(input_bytes).hexdigest() != INPUT_SHA256:
        raise DataError("frozen synthetic input changed")
    output = output.absolute()
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    (output / "empty_provider").mkdir()
    (output / "synthetic_input.parquet").write_bytes(input_bytes)
    config = json.loads((fixture / "workflow.yaml.template").read_text())
    config["qlib_init"]["provider_uri"] = str(output / "empty_provider")
    config["qlib_init"]["exp_manager"]["kwargs"]["uri"] = "sqlite:///" + str(output / "mlflow.db")
    loader = config["task"]["dataset"]["kwargs"]["handler"]["kwargs"]["data_loader"]
    loader["kwargs"]["config"] = str(output / "synthetic_input.parquet")
    _json(output / "workflow.yaml", config)  # JSON is also valid native YAML; paths stay escaped.
    # No inherited provider/model/broker credentials or user tracking configuration.
    worker_env = {
        "PATH": os.defpath,
        "HOME": str(output),
        "LANG": "C.UTF-8",
        "TMPDIR": str(output),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "PYTHONNOUSERSITE": "1",
        "MLFLOW_ENABLE_TELEMETRY": "false",
    }
    subprocess.run(
        [
            str(qlib_python),
            "-c",
            "import importlib.metadata as m; "
            "assert m.version('pyqlib')=='0.9.7'; "
            "assert m.version('lightgbm')=='4.6.0'",
        ],
        env=worker_env,
        timeout=15,
        check=True,
    )
    qrun_command = [str(qlib_python), "-m", "qlib.cli.run", str(output / "workflow.yaml")]
    start = time.monotonic()
    with (output / "qrun.log").open("wb") as stream:
        subprocess.run(
            qrun_command,
            cwd=output,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=True,
            env=worker_env,
        )
    subprocess.run(
        [str(qlib_python), str(fixture / "export.py"), str(output)],
        cwd=output,
        timeout=60,
        check=True,
        env=worker_env,
    )
    native = json.loads((output / "qrun-result.json").read_text())
    if _sha(output / "synthetic_input.parquet") != INPUT_SHA256:
        raise DataError("synthetic input changed during native execution")
    if (
        native["qlib_version"] != "0.9.7"
        or native["synthetic"] is not True
        or native["recorder"]["status"] != "FINISHED"
        or not Path(native["recorder"]["artifact_uri"]).resolve().is_relative_to(output)
    ):
        raise DataError("unexpected native Qlib source")
    frame = pl.read_csv(output / "native_predictions.csv", try_parse_dates=True)
    result, accounts, links = replay_predictions(frame, fee_bps=fee_bps, slippage_bps=slippage_bps)
    if result.rejected or result.orders != result.fills:
        raise DataError("bounded native demo did not fully execute its market orders")
    decisions = [dataclasses.asdict(row) for row in result.order_trace]
    fills = [dataclasses.asdict(row) for row in result.fill_trace]
    trades = [dataclasses.asdict(row) for row in result.trades]
    _csv(output / "orders.csv", decisions)
    _csv(output / "fills.csv", fills)
    _csv(output / "positions.csv", trades)
    _csv(output / "signals.csv", links)
    balances = [
        {
            "sequence": i,
            "timestamp": row.ts.isoformat(),
            "account_balance": row.cash,
            "locked_balance": row.cash - row.cash_free,
            "free_balance": row.cash_free,
            "currency": row.currency,
        }
        for i, row in enumerate(accounts)
    ]
    _csv(output / "account-events.csv", balances)
    _csv(output / "account-observations.csv", [dataclasses.asdict(row) for row in accounts])
    _csv(
        output / "equity.csv",
        [{"timestamp": ts.isoformat(), "equity": value} for ts, value in result.equity_curve],
    )
    assumptions = {
        "instrument_id": "SYN00.SIM",
        "strategy": "SignalReplay",
        "signal": "1 if native score >0 else0",
        "fixed_quantity": 1,
        "account_type": "CASH",
        "starting_cash_usd": 1_000_000,
        "fee_bps": fee_bps,
        "slippage_bps": slippage_bps,
        "funding": "none; synthetic cash equity",
        "borrow": "none; long/flat",
        "availability": "modeled session+23h, not measured upstream publication",
        "execution": "next synthetic weekday opening quote; bar_execution=False",
        "price_path": "fabricated 100+i open; independent of constructed regression target",
        "risk": "one share maximum, one instrument, no shorting or leverage",
        "terminal_position_units": accounts[-1].position_units,
        "fit_trials_this_invocation": 1,
        "global_trial_history": "not audited",
        "cash_observations": (
            "native account cache after opening quotes/fills; locked=cash-cash_free"
        ),
        "result_contract": "ALPHA BacktestResult observed from native Nautilus execution",
    }
    _json(output / "native-config.json", assumptions)
    _json(output / "native-result.json", dataclasses.asdict(result))
    hashes = {
        name: _sha(output / name)
        for name in [
            "synthetic_input.parquet",
            "workflow.yaml",
            "native_predictions.csv",
            "daily_signal_diagnostics.csv",
            "qrun-result.json",
            "signals.csv",
            "orders.csv",
            "fills.csv",
            "positions.csv",
            "account-events.csv",
            "account-observations.csv",
            "equity.csv",
            "native-config.json",
            "native-result.json",
        ]
    }
    provenance = {
        "source_sha256": {
            str(path.relative_to(root)): _sha(path)
            for path in (
                Path(__file__).resolve(),
                Path(inspect.getfile(SignalReplay)),
                Path(inspect.getfile(SignalReplay.__bases__[0])),
                Path(inspect.getfile(run_backtest)),
                Path(inspect.getfile(to_execution_feed)),
                Path(inspect.getfile(equity_instrument)),
                Path(inspect.getfile(BpsFeeModel)),
                fixture / "export.py",
                fixture / "workflow.yaml.template",
            )
        },
        "binding_limit": (
            "Selected source hashes and package versions; not whole binary qualification"
        ),
        "root_runtime": {
            "python": sys.version,
            "architecture": platform.machine(),
            "packages": {
                n: importlib.metadata.version(n) for n in ("nautilus-trader", "numpy", "polars")
            },
        },
        "harness_sha256": _sha(Path(inspect.getfile(run_backtest))),
        "feed_sha256": _sha(Path(inspect.getfile(to_execution_feed))),
        "qrun_command": qrun_command,
        "synthetic": True,
        "admission": "not_admitted",
        "qrun": native,
        "input_sha256": INPUT_SHA256,
        "artifacts_sha256": hashes,
        "strategy_sha256": _sha(Path(inspect.getfile(SignalReplay))),
        "composer_sha256": _sha(Path(__file__)),
        "wall_seconds": time.monotonic() - start,
        "not_established": [
            "real-data/scientific acceptance",
            "research admission",
            "FitPlan/resource policy",
            "live or paper trading",
        ],
    }
    _json(output / "provenance.json", provenance)
    payload = {
        "schema_version": 1,
        "synthetic": True,
        "admission": "not_admitted",
        "source": "upstream_qrun_to_nautilus",
        "balance_kind": "account_balance_events_not_equity",
        "version": importlib.metadata.version("nautilus-trader"),
        "upstream_commit": "3aa1ddffdc4947d05f3cf1c011290e44fc99b9a5",
        "strategy": "alpha_strategies.signal_replay:SignalReplay (fixed one share)",
        "strategy_sha256": provenance["strategy_sha256"],
        "run_id": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "config_id": hashes["native-config.json"],
        "selected_run": "one joined synthetic run",
        "instrument": "SYN00.SIM",
        "currency": "USD",
        "input_ticks": len(result.equity_curve),
        "simulation_seconds": (
            result.equity_curve[-1][0] - result.equity_curve[0][0]
        ).total_seconds(),
        "producer_runs": 1,
        "producer_processes": None,
        "normalized_reports_agree": False,
        "normalized_reports_sha256": hashes["native-result.json"],
        "reproduction_template": (
            "uv run python -m alpha_cli.native_qlib_pipeline "
            "--qlib-python workers/qlib/.venv/bin/python --output NEW_DIRECTORY "
            f"--fee-bps {fee_bps} --slippage-bps {slippage_bps}"
        ),
        "native_config": assumptions,
        "balances": balances,
        "orders": [
            {
                "id": str(x.sequence_id),
                "timestamp": x.ts.isoformat(),
                "instrument": x.instrument_id,
                "side": x.side,
                "quantity": str(x.quantity),
                "status": x.status,
                "price": next(
                    f.price for f in result.fill_trace if f.order_sequence_id == x.sequence_id
                ),
            }
            for x in result.order_trace
        ],
        "fills": [
            {
                "id": str(x.sequence_id),
                "order_id": str(x.order_sequence_id),
                "timestamp": x.ts.isoformat(),
                "side": x.side,
                "quantity": str(x.quantity),
                "price": str(x.price),
                "commission": str(
                    next(a.commission for a in accounts if a.fill_sequence_id == x.sequence_id)
                ),
                "currency": "USD",
            }
            for x in result.fill_trace
        ],
        "positions": [
            {
                "id": str(i),
                "opened_at": t.entry_ts.isoformat(),
                "closed_at": t.exit_ts.isoformat(),
                "entry": t.side,
                "peak_quantity": str(t.quantity),
                "open_price": t.entry_price,
                "close_price": t.exit_price,
                "realized_pnl": str(t.realized_pnl),
            }
            for i, t in enumerate(result.trades)
        ],
        "artifact_sha256": hashes,
        "account_events_csv": (output / "account-events.csv").read_text(),
        "pipeline": {
            "qlib_run_id": native["recorder"]["run_uuid"],
            "predictions_total": frame.height,
            "predictions_consumed": len(links),
            "instrument": "SYN00.SIM",
            "availability_is_modeled": True,
            "links": links,
            "unconsumed": "Other synthetic symbols are retained in CSV but not traded.",
        },
    }
    _json(output / "result.json", payload)
    print(
        json.dumps(
            {
                "output": str(output),
                "orders": result.orders,
                "fills": result.fills,
                "qlib_recorder": native["recorder"]["run_uuid"],
                "admission": "not_admitted",
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qlib-python", type=Path, required=True)
    parser.add_argument("--fee-bps", type=float, required=True)
    parser.add_argument("--slippage-bps", type=float, required=True)
    args = parser.parse_args()
    build_pipeline(
        args.output, args.qlib_python, fee_bps=args.fee_bps, slippage_bps=args.slippage_bps
    )


if __name__ == "__main__":
    main()
