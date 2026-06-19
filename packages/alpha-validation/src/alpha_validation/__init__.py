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
from alpha_validation.metrics import (
    FloatArray,
    FloatSeq,
    annualized_volatility,
    cagr,
    max_drawdown,
    sharpe_ratio,
    to_returns,
)
from alpha_validation.montecarlo import NullResult, StrategyFn, randomized_price_null
from alpha_validation.tearsheet import (
    CISummary,
    FoldSummary,
    GauntletReport,
    NullSummary,
    RunMetadata,
    build_outcomes,
    render_tearsheet_html,
    report_to_manifest,
)
from alpha_validation.volatility import (
    garch_conditional_volatility,
    garch_volatility_forecast,
)
from alpha_validation.walkforward import Split, walk_forward_splits

__version__ = "0.0.0"

__all__ = [
    "CISummary",
    "ConfidenceInterval",
    "FloatArray",
    "FloatSeq",
    "FoldSummary",
    "GauntletReport",
    "NullResult",
    "NullSummary",
    "RunMetadata",
    "Split",
    "Statistic",
    "StrategyFn",
    "__version__",
    "annualized_volatility",
    "block_bootstrap_ci",
    "build_outcomes",
    "cagr",
    "garch_conditional_volatility",
    "garch_volatility_forecast",
    "max_drawdown",
    "randomized_price_null",
    "render_tearsheet_html",
    "report_to_manifest",
    "sharpe_ratio",
    "stationary_bootstrap_indices",
    "to_returns",
    "walk_forward_splits",
]
