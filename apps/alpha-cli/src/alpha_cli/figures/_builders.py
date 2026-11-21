"""The builder registry: one builder per catalogue figure, grouped by family module.

Each ``builders_*`` module holds one family. This module only names them, so a reader
finds a figure by its family and the registry stays one table.
"""

from __future__ import annotations

from collections.abc import Callable

from alpha_cli.figures._common import BuildContext, money, mult, pct
from alpha_cli.figures.builders_curves import (
    equity_underwater,
    equity_vs_passive,
    monthly_heatmap,
    rolling_risk,
)
from alpha_cli.figures.builders_exposure import drawdown_episodes, exposure_turnover
from alpha_cli.figures.builders_forecast import forecast_calibration, forecast_fan, forecast_skill
from alpha_cli.figures.builders_mcpaths import (
    monte_carlo_drawdown_ruin,
    monte_carlo_equity_fans,
    monte_carlo_terminal_returns,
)
from alpha_cli.figures.builders_mcregimes import kronos_monte_carlo_calibration, monte_carlo_regimes
from alpha_cli.figures.builders_mlskill import (
    calibrated_reliability,
    forecast_abstention,
    state_conditioned_performance,
)
from alpha_cli.figures.builders_mlstability import (
    ensemble_disagreement,
    feature_stability,
    ml_cost_sensitivity,
)
from alpha_cli.figures.builders_nulls import (
    confidence_intervals,
    fold_sharpe,
    mcpt_null_histogram,
    null_distribution,
)
from alpha_cli.figures.builders_portfolio import (
    portfolio_correlations,
    portfolio_weights,
    propfirm_outcomes,
)
from alpha_cli.figures.builders_returns import qq_normal, return_distribution
from alpha_cli.figures.builders_search import optim_surface, optim_trials, research_discovery_trace
from alpha_cli.figures.builders_signal import price_signal
from alpha_cli.figures.builders_tradestats import holding_period, trade_pnl, trade_runs_test
from alpha_research.figures import FigureSpec

__all__ = ["BUILDERS", "BuildContext", "money", "mult", "pct"]

BUILDERS: dict[str, Callable[[BuildContext], FigureSpec]] = {
    "calibrated_reliability": calibrated_reliability,
    "confidence_intervals": confidence_intervals,
    "drawdown_episodes": drawdown_episodes,
    "ensemble_disagreement": ensemble_disagreement,
    "equity_underwater": equity_underwater,
    "equity_vs_passive": equity_vs_passive,
    "exposure_turnover": exposure_turnover,
    "feature_stability": feature_stability,
    "fold_sharpe": fold_sharpe,
    "forecast_abstention": forecast_abstention,
    "forecast_calibration": forecast_calibration,
    "forecast_fan": forecast_fan,
    "forecast_skill": forecast_skill,
    "holding_period": holding_period,
    "kronos_monte_carlo_calibration": kronos_monte_carlo_calibration,
    "mcpt_null_histogram": mcpt_null_histogram,
    "ml_cost_sensitivity": ml_cost_sensitivity,
    "monte_carlo_drawdown_ruin": monte_carlo_drawdown_ruin,
    "monte_carlo_equity_fans": monte_carlo_equity_fans,
    "monte_carlo_regimes": monte_carlo_regimes,
    "monte_carlo_terminal_returns": monte_carlo_terminal_returns,
    "monthly_heatmap": monthly_heatmap,
    "null_distribution": null_distribution,
    "optim_surface": optim_surface,
    "optim_trials": optim_trials,
    "portfolio_correlations": portfolio_correlations,
    "portfolio_weights": portfolio_weights,
    "price_signal": price_signal,
    "propfirm_outcomes": propfirm_outcomes,
    "qq_normal": qq_normal,
    "research_discovery_trace": research_discovery_trace,
    "return_distribution": return_distribution,
    "rolling_risk": rolling_risk,
    "state_conditioned_performance": state_conditioned_performance,
    "trade_pnl": trade_pnl,
    "trade_runs_test": trade_runs_test,
}
