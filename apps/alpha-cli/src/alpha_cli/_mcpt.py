"""In-sample Monte Carlo permutation test of a parameter sweep (``alpha optim mcpt``).

Masters, *Testing and Tuning Market Trading Systems* (Apress 2018) ch. 7, MCPT_TRN: optimise the
strategy on the observed series, then on each bar permutation re-run the SAME optimisation and
rank the observed best against the permuted bests. A high p-value means the optimiser finds an
equally good parameter set on price paths that carry no exploitable order — the observed edge is
selection, not signal. Provenance: github.com/neurotrader888/mcpt/insample_donchian_mcpt.py
@ 2c0d70c (MIT); adapted: the statistic is the best IN-SAMPLE full-series Sharpe over the grid
(upstream picks the best in-sample profit factor; Masters' program the best total return), every
bar after the first is permuted by ``alpha_validation.bar_permutation`` through
``alpha_validation.mcpt.permutation_test`` (one semantic seed, Davison & Hinkley ranking), and
the real engine scores each configuration via ``_runner.run_full_backtest``.

This is an optimisation-overfit test only. It never produces out-of-sample evidence: the
walk-forward ``randomized_price_null`` tiers of ``alpha validate`` remain the gates.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

from alpha_cli._artifacts import publish_artifact
from alpha_cli._optim import Config, _spec_for, expand_grid
from alpha_cli._runner import RunSpec, run_full_backtest
from alpha_core import Bar, CorporateAction
from alpha_validation import NullResult, permutation_test, sharpe_ratio, to_returns
from alpha_validation.bar_permutation import OHLC

STATISTIC = "in_sample_sharpe"
CAVEAT = (
    "In-sample optimisation-overfit test: the observed best configuration is ranked against the "
    "best configurations found on bar permutations of the same series. It is never "
    "out-of-sample evidence; the walk-forward null tiers of `alpha validate` remain the gates."
)


@dataclass(frozen=True)
class McptResult:
    configs: tuple[Config, ...]
    observed_config: Config
    null: NullResult
    permuted_configs: tuple[Config, ...]  # the best configuration on each permutation, in order


def in_sample_sharpe(
    bars: Sequence[Bar], spec: RunSpec, *, dividends: Sequence[CorporateAction] = ()
) -> float:
    """Annualized Sharpe of the full-series engine equity curve; 0.0 when it is flat."""
    result = run_full_backtest(bars, spec, dividends=dividends)
    equity = np.asarray([value for _, value in result.equity_curve], dtype=np.float64)
    if equity.size < 2:
        return 0.0
    returns = to_returns(equity)
    if float(np.std(returns, ddof=1)) > 0.0:
        return sharpe_ratio(returns, periods_per_year=spec.periods_per_year)
    return 0.0


def best_in_sample(
    bars: Sequence[Bar],
    base: RunSpec,
    configs: Sequence[Config],
    *,
    dividends: Sequence[CorporateAction] = (),
) -> tuple[Config, float]:
    """The configuration with the highest in-sample Sharpe (first wins a tie) and its score."""
    scores = [in_sample_sharpe(bars, _spec_for(base, c), dividends=dividends) for c in configs]
    best = int(np.argmax(scores))
    return configs[best], float(scores[best])


def run_mcpt(
    bars: Sequence[Bar],
    base: RunSpec,
    grid: Mapping[str, Sequence[float]],
    *,
    n_perms: int,
    seed: int,
    threshold: float = 0.95,
    dividends: Sequence[CorporateAction] = (),
) -> McptResult:
    """Rank the observed best in-sample score against ``n_perms`` re-optimised permutations."""
    configs = tuple(expand_grid(grid))
    template = list(bars)
    selections: list[Config] = []

    def score(ohlc: OHLC) -> float:
        path = [
            Bar(
                symbol=b.symbol,
                ts=b.ts,
                open=float(ohlc.open[i]),
                high=float(ohlc.high[i]),
                low=float(ohlc.low[i]),
                close=float(ohlc.close[i]),
                volume=b.volume,
            )
            for i, b in enumerate(template)
        ]
        config, statistic = best_in_sample(path, base, configs, dividends=dividends)
        selections.append(config)
        return statistic

    ohlc = OHLC(
        open=np.array([b.open for b in bars], dtype=np.float64),
        high=np.array([b.high for b in bars], dtype=np.float64),
        low=np.array([b.low for b in bars], dtype=np.float64),
        close=np.array([b.close for b in bars], dtype=np.float64),
    )
    # permutation_test scores the observed series first, then every permutation
    null = permutation_test(
        ohlc, score, n_perms=n_perms, start_index=0, seed=seed, threshold=threshold
    )
    return McptResult(
        configs=configs,
        observed_config=selections[0],
        null=null,
        permuted_configs=tuple(selections[1:]),
    )


def write_mcpt_null(rdir: Path, result: McptResult) -> None:
    """Write ``mcpt_null.parquet``: one row per permutation with its best score and config."""
    frame = pl.DataFrame(
        {
            "path_index": np.arange(result.null.n_paths, dtype=np.int64),
            "statistic": np.asarray(result.null.null, dtype=np.float64),
            "best_config": [json.dumps(dict(c)) for c in result.permuted_configs],
        },
        schema={"path_index": pl.Int64(), "statistic": pl.Float64(), "best_config": pl.String()},
    )
    publish_artifact(rdir / "mcpt_null.parquet", frame.write_parquet)


__all__ = [
    "CAVEAT",
    "STATISTIC",
    "McptResult",
    "best_in_sample",
    "in_sample_sharpe",
    "run_mcpt",
    "write_mcpt_null",
]
