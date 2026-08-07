"""Synthetic v3 run directories, complete enough to build every figure.

The figure tests were originally written against the run corpus in ``data/``, which is
gitignored -- so on CI they skipped in silence, took the renderer's coverage down with
them, and reported green locally while proving nothing anywhere else. A test that only
runs on the machine that wrote it is not a test.

These builders write the same artifacts a real run publishes, with the same schemas, into
a tmp directory. They are deliberately small (a year of sessions, a handful of trades) and
fully deterministic: no clock, no randomness, no reliance on anything outside the repo.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

#: Fixed identity so a caller can address the run without inspecting the directory.
BACKTEST_RUN = "1111111111111111"
VALIDATE_RUN = "2222222222222222"
PORTFOLIO_RUN = "3333333333333333"

_START = datetime(2023, 1, 2, tzinfo=UTC)
_SESSIONS = 260


def _stamps(count: int = _SESSIONS, *, step_days: int = 1) -> list[datetime]:
    return [_START + timedelta(days=index * step_days) for index in range(count)]


def _equity(count: int = _SESSIONS) -> list[float]:
    """A curve that rises, gives some back, and recovers -- so drawdown figures have work."""
    values = [1.0]
    for index in range(1, count):
        drift = 0.0006
        wobble = 0.012 * ((index * 7919 % 23) / 11.0 - 1.0)
        values.append(values[-1] * (1.0 + drift + wobble))
    return values


def _returns(equity: list[float]) -> list[float]:
    return [0.0] + [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]


def _write(directory: Path, name: str, frame: pl.DataFrame) -> None:
    frame.write_parquet(directory / name)


def _manifest(directory: Path, payload: dict[str, Any]) -> None:
    """Write a manifest whose declared artifact digests match the bytes on disk.

    The figure cache keys on those digests, so a fixture with fabricated hashes would
    exercise the mtime-fallback path instead of the one real runs use.
    """
    # Built by the production contract helper rather than hand-rolled, so the fixture
    # cannot drift out of step with what `verify_manifest_artifacts` demands.
    from alpha_cli.artifact_contract import artifact_contract

    artifacts = artifact_contract(directory)
    # The identity fields `verify_manifest_artifacts` insists on. They are fixed strings
    # rather than computed ones: this fixture stands in for a run, it does not re-derive
    # run identity, and a deterministic value keeps the figure cache key stable.
    document = {
        "artifact_contract_version": 3,
        "schema_version": 3,
        "run_identity_version": 3,
        "execution_fingerprint": "1" * 64,
        "strategy_fingerprint": "2" * 64,
        "source_fingerprint": "3" * 64,
        "snapshot_hash": None,
        **payload,
    }
    document["artifacts"] = artifacts
    (directory / "manifest.json").write_text(json.dumps(document, indent=2, sort_keys=True))


def _performance_artifacts(directory: Path) -> tuple[list[datetime], list[float]]:
    stamps = _stamps()
    equity = _equity()
    returns = _returns(equity)

    _write(directory, "equity_curve.parquet", pl.DataFrame({"ts": stamps, "equity": equity}))

    passive = [1.0]
    for index in range(1, len(stamps)):
        passive.append(passive[-1] * (1.0 + 0.0004 + 0.009 * ((index * 104729 % 17) / 8.0 - 1.0)))
    _write(
        directory,
        "benchmark_comparison.parquet",
        pl.DataFrame(
            {
                "ts": stamps,
                "strategy_equity": equity,
                "benchmark_equity": passive,
                "strategy_return": returns,
                "benchmark_return": _returns(passive),
                "excess_return": [s - b for s, b in zip(returns, _returns(passive), strict=True)],
                "available": [True] * len(stamps),
                "benchmark_kind": ["passive_open_to_open_price_only"] * len(stamps),
                "unavailable_reason": [None] * len(stamps),
            }
        ),
    )

    window = 126
    rolling_ts = stamps[window:]
    _write(
        directory,
        "rolling_metrics.parquet",
        pl.DataFrame(
            {
                "ts": rolling_ts,
                "window": [window] * len(rolling_ts),
                "return_value": [
                    0.04 + 0.01 * ((i % 9) / 4.0 - 1.0) for i in range(len(rolling_ts))
                ],
                "volatility": [0.14 + 0.02 * ((i % 7) / 3.0 - 1.0) for i in range(len(rolling_ts))],
                "sharpe": [0.8 + 0.4 * ((i % 11) / 5.0 - 1.0) for i in range(len(rolling_ts))],
                "gross_exposure": [1.0] * len(rolling_ts),
                "net_exposure": [0.8] * len(rolling_ts),
                "turnover": [0.05] * len(rolling_ts),
                "exposure_available": [True] * len(rolling_ts),
                "turnover_available": [True] * len(rolling_ts),
            }
        ),
    )

    months = [(2023, month) for month in range(1, 13)]
    _write(
        directory,
        "calendar_returns.parquet",
        pl.DataFrame(
            {
                "period_type": ["month"] * len(months) + ["year"],
                "year": [year for year, _ in months] + [2023],
                "month": [month for _, month in months] + [None],
                "return_value": [0.01 * ((index % 5) - 2) for index in range(len(months))] + [0.08],
            }
        ),
    )

    bins = 24
    _write(
        directory,
        "return_distribution.parquet",
        pl.DataFrame(
            {
                "kind": ["histogram"] * bins + ["qq"] * bins,
                "index": list(range(bins)) * 2,
                "left": [-0.03 + 0.0025 * i for i in range(bins)] + [None] * bins,
                "right": [-0.03 + 0.0025 * (i + 1) for i in range(bins)] + [None] * bins,
                "count": [max(1, 12 - abs(i - bins // 2)) for i in range(bins)] + [None] * bins,
                "probability": [1.0 / bins] * bins + [None] * bins,
                "theoretical": [None] * bins + [-2.0 + 4.0 * i / (bins - 1) for i in range(bins)],
                "sample": [None] * bins + [-1.9 + 3.9 * i / (bins - 1) for i in range(bins)],
            }
        ),
    )

    _write(
        directory,
        "exposure_turnover.parquet",
        pl.DataFrame(
            {
                "start_ts": stamps[:-1],
                "end_ts": stamps[1:],
                "gross_exposure": [1.0] * (len(stamps) - 1),
                "net_exposure": [0.6 + 0.3 * ((i % 5) / 2.0 - 1.0) for i in range(len(stamps) - 1)],
                "turnover": [0.02 * (i % 4) for i in range(len(stamps) - 1)],
                "exposure_available": [True] * (len(stamps) - 1),
                "turnover_available": [True] * (len(stamps) - 1),
                "exposure_unavailable_reason": [None] * (len(stamps) - 1),
                "turnover_unavailable_reason": [None] * (len(stamps) - 1),
            }
        ),
    )
    return stamps, equity


def _trace_artifacts(directory: Path, stamps: list[datetime]) -> None:
    """Trades, orders and fills, plus the annotations and indicators price_signal draws."""
    entries = list(range(20, 220, 40))
    exits = [index + 15 for index in entries]
    _write(
        directory,
        "trades.parquet",
        pl.DataFrame(
            {
                "instrument_id": ["TEST.SIM"] * len(entries),
                "side": ["BUY" if index % 2 == 0 else "SELL" for index in range(len(entries))],
                "quantity": [10.0] * len(entries),
                "entry_price": [100.0 + index for index in entries],
                "exit_price": [100.0 + index + (3 if index % 3 else -2) for index in entries],
                "entry_ts": [stamps[index] for index in entries],
                "exit_ts": [stamps[index] for index in exits],
                "realized_pnl": [30.0 if index % 3 else -20.0 for index in entries],
                "realized_return": [0.03 if index % 3 else -0.02 for index in entries],
            }
        ),
    )

    sequences = list(range(1, len(entries) * 2 + 1))
    event_ts = [stamps[index] for index in entries] + [stamps[index] for index in exits]
    _write(
        directory,
        "execution_trace.parquet",
        pl.DataFrame(
            {
                "sequence_id": sequences,
                "event_type": ["fill"] * len(sequences),
                "ts": event_ts,
                "parent_sequence_id": [None] * len(sequences),
                "instrument_id": ["TEST.SIM"] * len(sequences),
                "side": ["BUY"] * len(entries) + ["SELL"] * len(exits),
                "quantity": [10.0] * len(sequences),
                "filled_quantity": [10.0] * len(sequences),
                "price": [100.0 + index for index in entries + exits],
                "status": ["FILLED"] * len(sequences),
                "signal": [1] * len(entries) + [-1] * len(exits),
                "decision_reason": ["synthetic"] * len(sequences),
                "entry_ts": [None] * len(sequences),
                "exit_ts": [None] * len(sequences),
                "entry_price": [None] * len(sequences),
                "exit_price": [None] * len(sequences),
                "realized_pnl": [None] * len(sequences),
                "realized_return": [None] * len(sequences),
            }
        ),
    )

    # Two annotations: a swing polyline and a zone, so both branches of the drawing code run.
    anchor = [40, 60, 80]
    _write(
        directory,
        "chart_annotations.parquet",
        pl.DataFrame(
            {
                "annotation_id": [1, 1, 1, 2, 2],
                "decision_sequence_id": [1, 1, 1, 2, 2],
                "kind": ["polyline"] * 3 + ["zone"] * 2,
                "label": ["double bottom"] * 3 + ["neckline"] * 2,
                "unit": ["price"] * 5,
                "reason": ["pattern"] * 5,
                "anchor_index": anchor + [100, 130],
                "ts": [stamps[i] for i in anchor] + [stamps[100], stamps[130]],
                "value": [118.0, 112.0, 119.0, 125.0, 125.0],
            }
        ),
    )

    names = ("close", "momentum_fast", "momentum_slow", "momentum_return")
    units = ("price", "price", "price", "ratio")
    indices = list(range(0, len(stamps), 5))
    _write(
        directory,
        "indicator_series.parquet",
        pl.DataFrame(
            {
                "sequence_id": list(range(len(indices) * len(names))),
                "decision_sequence_id": [1] * (len(indices) * len(names)),
                "ts": [stamps[i] for _ in names for i in indices],
                "instrument_id": ["TEST.SIM"] * (len(indices) * len(names)),
                "name": [name for name in names for _ in indices],
                "value": [
                    (100.0 + i * 0.4 if unit == "price" else 0.02 * ((i % 9) - 4))
                    for _, unit in zip(names, units, strict=True)
                    for i in indices
                ],
                "unit": [unit for unit in units for _ in indices],
            }
        ),
    )


def backtest_run(root: Path) -> Path:
    """A complete v3 ``backtest run`` directory."""
    directory = root / "runs" / BACKTEST_RUN
    directory.mkdir(parents=True, exist_ok=True)
    stamps, _ = _performance_artifacts(directory)
    _trace_artifacts(directory, stamps)
    _manifest(
        directory,
        {
            "run_id": BACKTEST_RUN,
            "command": "backtest_run",
            "metadata": {
                "symbol": "TEST",
                "strategy_name": "ts_momentum",
                "snapshot_hash": "a" * 64,
                "start": "2023-01-02",
                "end": "2023-12-31",
            },
        },
    )
    return directory


def validate_run(root: Path) -> Path:
    """A ``validate`` run: everything a backtest has, plus nulls, folds and intervals."""
    directory = root / "runs" / VALIDATE_RUN
    directory.mkdir(parents=True, exist_ok=True)
    stamps, _ = _performance_artifacts(directory)
    _trace_artifacts(directory, stamps)

    tiers = ("returns_level", "full_engine")
    counts = (400, 64)
    _write(
        directory,
        "nulls.parquet",
        pl.DataFrame(
            {
                "tier": [
                    tier for tier, count in zip(tiers, counts, strict=True) for _ in range(count)
                ],
                "path_index": [i for count in counts for i in range(count)],
                "statistic": [
                    ((i * 37 % 101) / 50.0 - 1.0) for count in counts for i in range(count)
                ],
            }
        ),
    )

    _manifest(
        directory,
        {
            "run_id": VALIDATE_RUN,
            "command": "validate",
            "metadata": {
                "symbol": "TEST",
                "strategy_name": "ts_momentum",
                "snapshot_hash": "b" * 64,
                "start": "2023-01-02",
                "end": "2023-12-31",
            },
            # One flat fold, so the degenerate branch is drawn rather than dropped.
            "folds": [
                {"oos_sharpe": 0.9, "oos_return": 0.05},
                {"oos_sharpe": -0.3, "oos_return": -0.02},
                {"oos_sharpe": None, "oos_return": 0.0},
                {"oos_sharpe": 1.4, "oos_return": 0.09},
            ],
            "cis": [
                {"metric": "sharpe", "point": 0.8, "lower": 0.1, "upper": 1.5},
                {"metric": "cagr", "point": 0.06, "lower": -0.01, "upper": 0.13},
            ],
            "nulls": [
                {"tier": "returns_level", "observed": 1.02, "percentile": 0.97, "threshold": 0.95},
                {"tier": "full_engine", "observed": 1.01, "percentile": 0.96, "threshold": 0.95},
            ],
        },
    )
    return directory


def portfolio_run(root: Path) -> Path:
    """A basket run, for the allocation and correlation figures."""
    directory = root / "portfolio" / PORTFOLIO_RUN
    directory.mkdir(parents=True, exist_ok=True)
    stamps, _ = _performance_artifacts(directory)

    # Six sleeves against a four-slot palette, so the "other" bucket is exercised.
    symbols = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")
    picked = stamps[::5]
    _write(
        directory,
        "portfolio_allocations.parquet",
        pl.DataFrame(
            {
                "ts": [stamp for _ in symbols for stamp in picked],
                "symbol": [symbol for symbol in symbols for _ in picked],
                "weight": [
                    (position + 1) / 21.0 for position, _ in enumerate(symbols) for _ in picked
                ],
            }
        ),
    )

    pairs = [(a, b) for a in symbols for b in symbols if a < b]
    _write(
        directory,
        "correlations.parquet",
        pl.DataFrame(
            {
                "asset_a": [a for a, _ in pairs],
                "asset_b": [b for _, b in pairs],
                "correlation": [((index * 13 % 17) / 8.0 - 1.0) for index in range(len(pairs))],
                "sample_count": [250] * len(pairs),
            }
        ),
    )

    _manifest(
        directory,
        {
            "run_id": PORTFOLIO_RUN,
            "command": "backtest_portfolio",
            "metadata": {
                "symbols": list(symbols),
                "strategy_name": "ts_momentum",
                "snapshot_hash": "c" * 64,
                "start": "2023-01-02",
                "end": "2023-12-31",
            },
        },
    )
    return directory


def all_runs(root: Path) -> dict[str, Path]:
    """Every synthetic run, keyed by run id."""
    return {
        BACKTEST_RUN: backtest_run(root),
        VALIDATE_RUN: validate_run(root),
        PORTFOLIO_RUN: portfolio_run(root),
    }
