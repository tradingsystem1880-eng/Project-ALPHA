"""Project ALPHA validation gauntlet (spec §8): walk-forward, randomized-price null, bootstrap CIs.

Engine-agnostic statistical primitives consumed by the ``alpha validate`` CLI. They operate on
return/equity arrays and an injected strategy callable, so this package depends only on
``alpha_core`` (the architecture DAG).
"""

from __future__ import annotations

from importlib.metadata import version

from alpha_validation.barrier import (
    BarrierCounts,
    BarrierResult,
    Outcome,
    aggregate_outcomes,
    barrier_outcome,
    excursion_quantiles,
)
from alpha_validation.bootstrap import (
    ConfidenceInterval,
    Statistic,
    block_bootstrap_ci,
    risk_of_ruin,
    stationary_bootstrap_indices,
)
from alpha_validation.conditional import (
    LiftResult,
    apply_fdr,
    conditional_lift,
    lift_table,
    monotonic_trend,
    two_proportion_pvalue,
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
from alpha_validation.proportion import (
    MultipleTestResult,
    ProportionInterval,
    autocorrelation_effective_size,
    benjamini_hochberg,
    effective_sample_size,
    newcombe_diff_interval,
    overlap_factor,
    wilson_interval,
)
from alpha_validation.reality_check import DataSnoopingResult, reality_check, spa_test
from alpha_validation.scenario import ScenarioSummary, scenario_metrics
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

__version__ = version("alpha-validation")

__all__ = [
    "BarrierCounts",
    "BarrierResult",
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
    "LiftResult",
    "MultipleTestResult",
    "NullResult",
    "NullSummary",
    "OriginScore",
    "Outcome",
    "PBOResult",
    "PropFirmResult",
    "PropFirmRules",
    "ProportionInterval",
    "RunMetadata",
    "ScenarioSummary",
    "Split",
    "Statistic",
    "StrategyFn",
    "VerdictSummary",
    "__version__",
    "aggregate_outcomes",
    "annualized_volatility",
    "apply_fdr",
    "autocorrelation_effective_size",
    "barrier_outcome",
    "benjamini_hochberg",
    "block_bootstrap_ci",
    "bootstrap_end_returns",
    "build_outcomes",
    "cagr",
    "central_coverage",
    "combinatorial_purged_splits",
    "conditional_lift",
    "crps_sample",
    "deflated_sharpe",
    "effective_sample_size",
    "excursion_quantiles",
    "expected_max_sharpe",
    "expected_shortfall",
    "garch_paths",
    "grade_verdict",
    "lift_table",
    "max_drawdown",
    "monotonic_trend",
    "n_cpcv_splits",
    "newcombe_diff_interval",
    "overlap_factor",
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
    "scenario_metrics",
    "score_origin",
    "sharpe_ratio",
    "simulate_propfirm",
    "spa_test",
    "stationary_bootstrap_indices",
    "student_t_paths",
    "summarize_scores",
    "to_returns",
    "two_proportion_pvalue",
    "value_at_risk",
    "walk_forward_splits",
    "wilson_interval",
]
