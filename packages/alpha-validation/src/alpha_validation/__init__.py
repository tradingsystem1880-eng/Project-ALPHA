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
    risk_of_ruin,
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
    expected_shortfall,
    max_drawdown,
    sharpe_ratio,
    to_returns,
    value_at_risk,
)
from alpha_validation.forecast_eval import (
    ForecastEvalSummary,
    OriginScore,
    bootstrap_end_returns,
    central_coverage,
    crps_sample,
    pinball_loss,
    rw_drift_end_returns,
    score_origin,
    summarize_scores,
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
from alpha_validation.propfirm import (
    FIRM_PRESETS,
    PropFirmResult,
    PropFirmRules,
    simulate_propfirm,
)
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
    render_returns_tearsheet,
    render_tearsheet_html,
    report_to_manifest,
)
from alpha_validation.verdict import VerdictSummary, grade_verdict
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
    "FIRM_PRESETS",
    "FloatArray",
    "FloatSeq",
    "FoldSummary",
    "ForecastEvalSummary",
    "GauntletReport",
    "NullResult",
    "NullSummary",
    "OriginScore",
    "PBOResult",
    "PropFirmResult",
    "PropFirmRules",
    "RunMetadata",
    "Split",
    "Statistic",
    "StrategyFn",
    "VerdictSummary",
    "__version__",
    "annualized_volatility",
    "block_bootstrap_ci",
    "bootstrap_end_returns",
    "build_outcomes",
    "cagr",
    "central_coverage",
    "combinatorial_purged_splits",
    "crps_sample",
    "deflated_sharpe",
    "expected_max_sharpe",
    "expected_shortfall",
    "garch_paths",
    "grade_verdict",
    "max_drawdown",
    "n_cpcv_splits",
    "parametric_price_null",
    "pinball_loss",
    "probabilistic_sharpe_ratio",
    "probability_of_backtest_overfitting",
    "randomized_price_null",
    "reality_check",
    "render_returns_tearsheet",
    "render_tearsheet_html",
    "report_to_manifest",
    "risk_of_ruin",
    "rw_drift_end_returns",
    "score_origin",
    "sharpe_ratio",
    "simulate_propfirm",
    "spa_test",
    "stationary_bootstrap_indices",
    "student_t_paths",
    "summarize_scores",
    "to_returns",
    "value_at_risk",
    "walk_forward_splits",
]
