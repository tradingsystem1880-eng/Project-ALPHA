"""Project ALPHA validation gauntlet (spec §8): walk-forward, randomized-price null, bootstrap CIs.

Engine-agnostic statistical primitives consumed by the ``alpha validate`` CLI. They operate on
return/equity arrays and an injected strategy callable, so this package depends only on
``alpha_core`` (the architecture DAG).
"""

from __future__ import annotations

from alpha_validation.bootstrap import (
    ConfidenceInterval,
    Statistic,
    block_bootstrap_ci,
    stationary_bootstrap_indices,
)
from alpha_validation.cpcv import (
    CPCVSplit,
    combinatorial_purged_splits,
    n_cpcv_splits,
)
from alpha_validation.dsr import (
    DeflatedSharpeResult,
    deflated_sharpe,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from alpha_validation.metrics import (
    FloatArray,
    FloatSeq,
    annualized_volatility,
    cagr,
    max_drawdown,
    sharpe_ratio,
    to_returns,
)
from alpha_validation.montecarlo import (
    NullResult,
    StrategyFn,
    garch_paths,
    parametric_price_null,
    randomized_price_null,
    student_t_paths,
)
from alpha_validation.overfitting import PBOResult, probability_of_backtest_overfitting
from alpha_validation.reality_check import DataSnoopingResult, reality_check, spa_test
from alpha_validation.tearsheet import (
    CISummary,
    CPCVSummary,
    DSRSummary,
    FoldSummary,
    GauntletReport,
    NullSummary,
    RunMetadata,
    build_outcomes,
    render_tearsheet_html,
    report_to_manifest,
)
from alpha_validation.walkforward import Split, walk_forward_splits

__version__ = "0.0.0"

__all__ = [
    "CISummary",
    "CPCVSplit",
    "CPCVSummary",
    "ConfidenceInterval",
    "DSRSummary",
    "DataSnoopingResult",
    "DeflatedSharpeResult",
    "FloatArray",
    "FloatSeq",
    "FoldSummary",
    "GauntletReport",
    "NullResult",
    "NullSummary",
    "PBOResult",
    "RunMetadata",
    "Split",
    "Statistic",
    "StrategyFn",
    "__version__",
    "annualized_volatility",
    "block_bootstrap_ci",
    "build_outcomes",
    "cagr",
    "combinatorial_purged_splits",
    "deflated_sharpe",
    "expected_max_sharpe",
    "garch_paths",
    "max_drawdown",
    "n_cpcv_splits",
    "parametric_price_null",
    "probabilistic_sharpe_ratio",
    "probability_of_backtest_overfitting",
    "randomized_price_null",
    "reality_check",
    "render_tearsheet_html",
    "report_to_manifest",
    "sharpe_ratio",
    "spa_test",
    "stationary_bootstrap_indices",
    "student_t_paths",
    "to_returns",
    "walk_forward_splits",
]
