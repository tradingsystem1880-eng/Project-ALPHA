"""What figures exist, what each one answers, and what it needs to be drawable.

The teaching text lives here rather than in a builder because it is a property of the
*figure*, not of any one run: the question a monthly-returns heatmap answers is the same
question whatever the returns were. Only ``plain_language_answer`` is run-specific, and
the builders supply it.

This registry is also the contract the Workstation reads. ``alpha figures list --json``
projects it, the SPA renders the strings beside each image, and a drift-guard fixture in
the frontend asserts every id resolves -- the same mirror discipline the verdict bands use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from alpha_core import DataError
from alpha_research.figures.render import FigureSize

_ID = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")

#: Commands whose runs carry an equity curve and the native tear-sheet sidecars.
_EQUITY_COMMANDS: Final = (
    "backtest_run",
    "backtest_oos",
    "backtest_holdout",
    "validate",
    "ml_replay",
)
_PORTFOLIO_COMMANDS: Final = ("backtest_portfolio", "cross_sectional", "backtest_cross_sectional")


@dataclass(frozen=True, slots=True, kw_only=True)
class FigureDefinition:
    """Static metadata for one figure, independent of any particular run."""

    figure_id: str
    title: str
    #: One line. Doubles as the ``<img alt>`` text, so it must describe the *content*,
    #: not merely name the chart.
    summary: str
    question: str
    uncertainty: str
    caveat: str
    section: str
    run_commands: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    optional_artifacts: tuple[str, ...] = ()
    panel_count: int = 1
    requires_snapshot: bool = False
    order: int = 0

    def __post_init__(self) -> None:
        if _ID.fullmatch(self.figure_id) is None:
            raise DataError(f"figure id {self.figure_id!r} must be lower_snake_case")
        for name in ("title", "summary", "question", "uncertainty", "caveat", "section"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise DataError(f"FigureDefinition.{name} must be a non-empty string")
        if not self.run_commands:
            raise DataError(f"{self.figure_id} must apply to at least one command")
        if not self.required_artifacts:
            raise DataError(f"{self.figure_id} must declare what it reads")
        if self.panel_count < 1:
            raise DataError(f"{self.figure_id} must declare at least one panel")

    @property
    def default_size(self) -> FigureSize:
        from alpha_research.figures.render import default_size

        return default_size(self.panel_count)


def _equity(**kwargs: object) -> FigureDefinition:
    return FigureDefinition(run_commands=_EQUITY_COMMANDS, **kwargs)  # type: ignore[arg-type]


FIGURES: Final[tuple[FigureDefinition, ...]] = (
    # ---------------------------------------------------------------- performance
    _equity(
        figure_id="equity_underwater",
        title="Equity and drawdown",
        summary="Growth of one unit of capital, with every drawdown shown beneath it.",
        question="How did capital grow, and how deep and how long were the holes?",
        uncertainty=(
            "This is one realised path. It shows what did happen, not the range of what "
            "could have happened -- that lives in the robustness figures."
        ),
        caveat=(
            "Equity is marked at the session open before same-open fills settle, net of "
            "modelled fees and slippage only."
        ),
        section="performance",
        required_artifacts=("equity_curve.parquet",),
        panel_count=2,
        order=10,
    ),
    _equity(
        figure_id="equity_vs_passive",
        title="Strategy versus passive",
        summary="Strategy growth against simply holding the asset, plus cumulative excess.",
        question="Did the strategy actually beat holding the asset, and when did it earn that?",
        uncertainty=(
            "A single path against a single benchmark path. A lead that comes from one "
            "short window is not the same as a lead earned steadily."
        ),
        caveat=(
            "The passive leg is an open-to-open price index and EXCLUDES dividends, so it "
            "understates the real return of a dividend-paying asset. It is not a total-return "
            "buy-and-hold benchmark."
        ),
        section="performance",
        required_artifacts=("benchmark_comparison.parquet",),
        panel_count=2,
        order=20,
    ),
    _equity(
        figure_id="rolling_risk",
        title="Rolling risk",
        summary="Rolling Sharpe, volatility and return on a shared time axis.",
        question="Was the edge stable through time, or carried by one regime?",
        uncertainty=(
            "Rolling windows overlap heavily, so neighbouring points are not independent "
            "and the series looks smoother than the evidence warrants."
        ),
        caveat=(
            "A 126-session window cannot see anything shorter than itself, and the first "
            "window's worth of sessions has no value at all."
        ),
        section="performance",
        required_artifacts=("rolling_metrics.parquet",),
        panel_count=3,
        order=30,
    ),
    _equity(
        figure_id="monthly_heatmap",
        title="Monthly returns",
        summary="Every month's return as a diverging heat grid, with annual totals.",
        question="Which months and which years actually produced the result?",
        uncertainty=(
            "Monthly buckets are a calendar convention, not a statistical one; a single "
            "strong month can dominate a year without meaning anything repeatable."
        ),
        caveat="Partial first and last months are shown as-is and are not annualised.",
        section="performance",
        required_artifacts=("calendar_returns.parquet",),
        panel_count=1,
        order=40,
    ),
    # ---------------------------------------------------------------- signals
    _equity(
        figure_id="price_signal",
        title="Price, signals and indicators",
        summary=(
            "Price with the strategy's own annotations, decisions and fills drawn on it, "
            "over its indicator series."
        ),
        question="Did the strategy fire where I think it should have?",
        uncertainty=(
            "Markers show what the engine did, not whether the reasoning was sound. A "
            "correctly-placed marker on a bad rule is still a bad rule."
        ),
        caveat=(
            "Bars come from the run's frozen snapshot. Annotations are authored by the "
            "strategy itself, so an empty chart means the strategy emitted none."
        ),
        section="signals",
        required_artifacts=("execution_trace.parquet",),
        optional_artifacts=(
            "chart_annotations.parquet",
            "indicator_series.parquet",
            "trades.parquet",
        ),
        panel_count=2,
        requires_snapshot=True,
        order=50,
    ),
    # ---------------------------------------------------------------- trades
    _equity(
        figure_id="trade_pnl",
        title="Per-trade profit and loss",
        summary="Each closed trade's realised P&L, and the cumulative total beneath it.",
        question="Did the result come from many small wins or a couple of lucky trades?",
        uncertainty=(
            "Trade count is usually small enough that the ordering is close to noise; "
            "re-running on a shifted window would reshuffle it."
        ),
        caveat="Only closed round trips appear. An open position at the end contributes nothing.",
        section="trades",
        required_artifacts=("trades.parquet",),
        panel_count=2,
        order=60,
    ),
    _equity(
        figure_id="holding_period",
        title="Holding periods",
        summary="How long trades were held, split by whether they made money.",
        question="Is this the holding horizon the strategy was designed for?",
        uncertainty="With few trades the shape of this distribution is not meaningful.",
        caveat=(
            "Measured in calendar days between entry and exit, so weekends and holidays "
            "inflate it relative to sessions held."
        ),
        section="trades",
        required_artifacts=("trades.parquet",),
        panel_count=1,
        order=70,
    ),
    # ---------------------------------------------------------------- risk
    _equity(
        figure_id="return_distribution",
        title="Daily return distribution",
        summary="The histogram of daily returns against a fitted normal, with tail markers.",
        question="How fat are the tails, and how normal is this return stream really?",
        uncertainty=(
            "The normal overlay is a reference shape, not a fitted claim; financial returns "
            "are reliably not normal."
        ),
        caveat="Bins are fixed by the stored artifact, so the shape does not depend on this view.",
        section="risk",
        required_artifacts=("return_distribution.parquet",),
        panel_count=1,
        order=80,
    ),
    _equity(
        figure_id="qq_normal",
        title="Normal Q-Q",
        summary="Sample quantiles against normal quantiles, with the 45-degree reference.",
        question="Where exactly does this return stream depart from normal?",
        uncertainty="The extreme points are each a single observation and move easily.",
        caveat="Departure from the line in the tails is expected and is not itself a defect.",
        section="risk",
        required_artifacts=("return_distribution.parquet",),
        panel_count=1,
        order=90,
    ),
    _equity(
        figure_id="drawdown_episodes",
        title="Worst drawdowns",
        summary="The deepest drawdown windows shaded on equity, with their dates and durations.",
        question="What were the worst stretches, and how long did recovery take?",
        uncertainty=(
            "Depth and recovery are properties of this one path; a different start date "
            "produces different episodes."
        ),
        caveat="An episode still under water at the end has no recovery date and is marked open.",
        section="risk",
        required_artifacts=("equity_curve.parquet",),
        panel_count=2,
        order=100,
    ),
    _equity(
        figure_id="exposure_turnover",
        title="Exposure and turnover",
        summary="Gross and net exposure through time, over per-session turnover.",
        question="How much capital was actually at risk, and how hard did it trade?",
        uncertainty="Exposure is marked at the un-skewed opening midpoint, not at fill prices.",
        caveat=(
            "Turnover is unavailable for some run types; the panel says so rather than "
            "drawing zeros."
        ),
        section="risk",
        required_artifacts=("exposure_turnover.parquet",),
        panel_count=2,
        order=110,
    ),
    # ---------------------------------------------------------------- robustness
    FigureDefinition(
        figure_id="null_distribution",
        title="Randomised-price null",
        summary=(
            "Where the observed statistic falls inside distributions built from paths with "
            "no edge, one panel per tier."
        ),
        question="Could a strategy with no edge at all have produced this result by luck?",
        uncertainty=(
            "The null is a finite sample of synthetic paths, so the percentile carries its "
            "own sampling error; a result near the threshold is not a clean pass."
        ),
        caveat=(
            "Tier 1 scores a surrogate on resampled returns and can credit high-turnover "
            "strategies; Tier 2 runs the real engine and is the one that cannot be rescued."
        ),
        section="robustness",
        run_commands=("validate",),
        required_artifacts=("nulls.parquet",),
        panel_count=2,
        order=120,
    ),
    FigureDefinition(
        figure_id="fold_sharpe",
        title="Per-fold out-of-sample Sharpe",
        summary="Each walk-forward fold's out-of-sample Sharpe on a real numeric axis.",
        question="Did the edge show up in most folds, or in one?",
        uncertainty="Individual folds are short, so each Sharpe is estimated very imprecisely.",
        caveat=(
            "A flat fold has undefined Sharpe. It is drawn hollow at zero and labelled "
            "degenerate rather than dropped, because dropping it would flatter the picture."
        ),
        section="robustness",
        run_commands=("validate", "backtest_oos", "ml_replay"),
        required_artifacts=("manifest.json",),
        panel_count=2,
        order=130,
    ),
    FigureDefinition(
        figure_id="confidence_intervals",
        title="Bootstrap confidence intervals",
        summary="Point estimates and bootstrap intervals for each headline metric.",
        question="How much of this result survives once sampling error is admitted?",
        uncertainty="The interval is itself estimated, and block bootstrap assumes stationarity.",
        caveat="An interval straddling zero means the data cannot rule out no edge at all.",
        section="robustness",
        run_commands=("validate",),
        required_artifacts=("manifest.json",),
        panel_count=1,
        order=140,
    ),
    # ---------------------------------------------------------------- optimisation
    FigureDefinition(
        figure_id="optim_surface",
        title="Parameter surface",
        summary="Out-of-sample Sharpe across the swept parameter grid, failures marked.",
        question="Is the chosen configuration on a plateau, or balanced on a spike?",
        uncertainty=(
            "Every cell is one noisy estimate. Neighbouring cells differing wildly is "
            "evidence of noise, not of a real boundary."
        ),
        caveat=(
            "Failed and pruned trials are drawn as hatched cells, never as blanks: a blank "
            "would read as a bad result rather than a missing one."
        ),
        section="optimisation",
        run_commands=("optim_grid",),
        required_artifacts=("trial_ledger.parquet",),
        panel_count=1,
        order=150,
    ),
    FigureDefinition(
        figure_id="optim_trials",
        title="Per-trial equity",
        summary="Every swept configuration's out-of-sample equity, with the selected one lit.",
        question="How unusual is the selected configuration among everything that was tried?",
        uncertainty="The best curve of many is biased upward by selection, always.",
        caveat="Curves are compounded from stored out-of-sample returns, not re-executed.",
        section="optimisation",
        run_commands=("optim_grid",),
        required_artifacts=("trials.parquet",),
        panel_count=1,
        order=160,
    ),
    # ---------------------------------------------------------------- portfolio
    FigureDefinition(
        figure_id="portfolio_weights",
        title="Sleeve weights through time",
        summary="How capital was allocated across sleeves, and the resulting exposure.",
        question="What was actually held, and how concentrated did it get?",
        uncertainty="Weights are causal at each date but say nothing about future allocation.",
        caveat=(
            "Beyond the verified colour palette the smallest sleeves are aggregated into "
            "'other' rather than given recycled colours."
        ),
        section="portfolio",
        run_commands=_PORTFOLIO_COMMANDS,
        required_artifacts=("portfolio_allocations.parquet",),
        panel_count=2,
        order=170,
    ),
    FigureDefinition(
        figure_id="portfolio_correlations",
        title="Aligned out-of-sample correlations",
        summary="Pairwise sleeve correlation over the aligned out-of-sample window.",
        question="Were these sleeves actually diversifying, or the same bet twice?",
        uncertainty="Correlation is unstable, and rises exactly when diversification is needed.",
        caveat="Association, not causation. Sample counts are annotated in each cell.",
        section="portfolio",
        run_commands=_PORTFOLIO_COMMANDS,
        required_artifacts=("correlations.parquet",),
        panel_count=1,
        order=180,
    ),
    # ---------------------------------------------------------------- prop firm
    FigureDefinition(
        figure_id="propfirm_outcomes",
        title="Evaluation outcomes",
        summary="Simulated days-to-pass and payout distributions across resampled paths.",
        question="Across many resampled futures, how often does this clear the evaluation?",
        uncertainty=(
            "Paths are block-resampled from one realised return stream, so they inherit its "
            "regime and understate genuinely novel conditions."
        ),
        caveat="Firm presets are illustrative and are not authoritative contract terms.",
        section="propfirm",
        run_commands=("propfirm", "propfirm_run"),
        required_artifacts=("propfirm_paths.parquet",),
        panel_count=2,
        order=190,
    ),
    # ---------------------------------------------------------------- Monte Carlo path risk
    FigureDefinition(
        figure_id="monte_carlo_equity_fans",
        title="Monte Carlo equity fans",
        summary="Simulated equity quantile fans with the observed OOS account equity overlaid.",
        question="How wide is the range of account outcomes under each path-generation family?",
        uncertainty=(
            "Bands are finite-simulation quantiles and inherit each generator's assumptions; "
            "they are not confidence intervals for future wealth."
        ),
        caveat=(
            "Classical and Kronos runs are standalone immutable contracts; together their "
            "panels form the required four-family evidence set."
        ),
        section="monte_carlo",
        run_commands=("monte_carlo_classical", "monte_carlo_kronos"),
        required_artifacts=("paths.parquet", "observed_oos.parquet"),
        panel_count=4,
        order=191,
    ),
    FigureDefinition(
        figure_id="monte_carlo_terminal_returns",
        title="Monte Carlo terminal returns",
        summary="Terminal account-return distributions, one panel for each available family.",
        question="How often does each simulated account path finish with a gain or a loss?",
        uncertainty="Histogram shape and tail counts vary with finite path count and binning.",
        caveat="A positive terminal median does not establish that the strategy has edge.",
        section="monte_carlo",
        run_commands=("monte_carlo_classical", "monte_carlo_kronos"),
        required_artifacts=("path_metrics.parquet",),
        panel_count=4,
        order=192,
    ),
    FigureDefinition(
        figure_id="monte_carlo_drawdown_ruin",
        title="Monte Carlo drawdown and ruin",
        summary="Maximum-drawdown distributions with the declared 50% ruin boundary.",
        question="How severe are simulated drawdowns, and how often do they cross ruin?",
        uncertainty="Ruin probabilities carry finite-path sampling uncertainty in the manifest.",
        caveat="Ruin means a 50% peak-to-trough account drawdown, not legal insolvency.",
        section="monte_carlo",
        run_commands=("monte_carlo_classical", "monte_carlo_kronos"),
        required_artifacts=("path_metrics.parquet",),
        panel_count=4,
        order=193,
    ),
    FigureDefinition(
        figure_id="monte_carlo_regimes",
        title="Causal regime diagnostics",
        summary="Calm/volatile return emissions beside the fitted transition matrix.",
        question="Are both causal volatility states supported, and how persistent are they?",
        uncertainty="Two states compress a continuous and evolving volatility process.",
        caveat="The state boundary is frozen from the training prefix and never sees OOS outcomes.",
        section="monte_carlo",
        run_commands=("monte_carlo_classical",),
        required_artifacts=("regime_emissions.parquet", "regime_diagnostics.parquet"),
        panel_count=2,
        order=194,
    ),
    FigureDefinition(
        figure_id="kronos_monte_carlo_calibration",
        title="Kronos calibration and skill",
        summary="Rolling-origin CRPS versus both baselines and empirical interval coverage.",
        question="Was the generator calibrated and more skillful than simple baselines?",
        uncertainty="Rolling origins overlap and post-cutoff samples may remain small.",
        caveat="Weak skill pauses progression for review; it does not turn Kronos into an oracle.",
        section="monte_carlo",
        run_commands=("monte_carlo_kronos",),
        required_artifacts=("calibration_origins.parquet",),
        panel_count=2,
        order=195,
    ),
    # ---------------------------------------------------------------- forecast
    FigureDefinition(
        figure_id="forecast_fan",
        title="Outcome cone",
        summary="Sampled forecast paths as central intervals around the median.",
        question="What range of outcomes does the model consider plausible from here?",
        uncertainty=(
            "The cone is the model's own opinion of uncertainty. It is only as trustworthy "
            "as the model's calibration, which the skill figures measure separately."
        ),
        caveat="Bands are sample quantiles, not analytic confidence intervals.",
        section="forecast",
        run_commands=("forecast_run",),
        required_artifacts=("quantiles.parquet", "history.parquet"),
        optional_artifacts=("paths.parquet",),
        panel_count=1,
        order=200,
    ),
    FigureDefinition(
        figure_id="forecast_skill",
        title="Forecast skill",
        summary="CRPS per origin against baselines, with the skill score beneath.",
        question="Does this model beat a random walk, honestly, out of sample?",
        uncertainty="Origins overlap, so consecutive scores are correlated.",
        caveat=(
            "Origins before the model's pretraining cutoff are shaded: the model may have "
            "seen that period in training, so scores there are not out-of-sample."
        ),
        section="forecast",
        run_commands=("forecast_eval",),
        required_artifacts=("origins.parquet",),
        panel_count=2,
        order=210,
    ),
    FigureDefinition(
        figure_id="forecast_calibration",
        title="Coverage calibration",
        summary="Nominal versus realised interval coverage against the ideal diagonal.",
        question="When the model says 80% confident, is it right 80% of the time?",
        uncertainty=(
            "Only three nominal levels are stored, so this is three points rather than a "
            "curve, and each carries wide binomial error at typical origin counts."
        ),
        caveat="A richer calibration curve needs additional stored coverage levels.",
        section="forecast",
        run_commands=("forecast_eval",),
        required_artifacts=("origins.parquet",),
        panel_count=1,
        order=220,
    ),
    FigureDefinition(
        figure_id="state_conditioned_performance",
        title="State-conditioned forecast performance",
        summary="Raw and calibrated OOS forecast loss by frozen market state.",
        question="Does calibration help across states, or only in one regime?",
        uncertainty="Sparse states use the preregistered pooled fallback and are marked as such.",
        caveat="Market state is descriptive conditioning, not proof that the state caused skill.",
        section="forecast",
        run_commands=("forecast_eval",),
        required_artifacts=("state_performance.parquet",),
        panel_count=2,
        order=221,
    ),
    FigureDefinition(
        figure_id="calibrated_reliability",
        title="Frozen calibration reliability",
        summary="Raw versus calibrated CRPS and interval coverage on validation and OOS origins.",
        question="Did the validation-frozen calibration remain reliable out of sample?",
        uncertainty="Coverage is estimated from a finite and serially dependent origin sample.",
        caveat="A delivered calibration capability is not evidence of profitable forecast skill.",
        section="forecast",
        run_commands=("forecast_eval",),
        required_artifacts=("calibration_reliability.parquet",),
        panel_count=2,
        order=222,
    ),
    FigureDefinition(
        figure_id="forecast_abstention",
        title="Calibrated candidate abstention",
        summary=(
            "Candidate emissions and abstentions under frozen uncertainty, edge, and state rules."
        ),
        question="How often did the governed candidate decline to express a signal, and why?",
        uncertainty=(
            "Abstention frequency depends on the frozen state sample and calibration window."
        ),
        caveat="Candidate emissions have research authority only and no paper or order authority.",
        section="forecast",
        run_commands=("forecast_eval",),
        required_artifacts=("calibrated_origins.parquet",),
        panel_count=2,
        order=223,
    ),
    FigureDefinition(
        figure_id="ensemble_disagreement",
        title="Rank-ensemble disagreement",
        summary="LightGBM and ridge percentile ranks with their cross-sectional disagreement.",
        question="Are the two ensemble members corroborating each other or cancelling out?",
        uncertainty=(
            "Disagreement diagnoses model diversity; it does not establish either member is right."
        ),
        caveat=(
            "Scores are OOS diagnostics until canonical replay and the full research gates pass."
        ),
        section="ml",
        run_commands=("ml_replay",),
        required_artifacts=("ensemble_diagnostics.parquet",),
        panel_count=2,
        order=224,
    ),
    FigureDefinition(
        figure_id="feature_stability",
        title="Feature stability across folds",
        summary="Per-fold LightGBM gain for the most influential Alpha158 features.",
        question=(
            "Does the model rely on the same features across refits, or chase unstable proxies?"
        ),
        uncertainty="Gain importance is model-specific and does not imply a causal contribution.",
        caveat=(
            "Only train-fold fitted importance is shown; no OOS outcome selects the displayed "
            "features."
        ),
        section="ml",
        run_commands=("ml_replay",),
        required_artifacts=("ml_feature_stability.parquet",),
        panel_count=1,
        order=225,
    ),
    FigureDefinition(
        figure_id="ml_cost_sensitivity",
        title="ML replay cost sensitivity",
        summary="Canonical replay return under fixed multiples of the declared transaction costs.",
        question="How quickly does the apparent edge disappear as realistic costs increase?",
        uncertainty=(
            "The scenarios scale declared fees and slippage; they do not model market impact."
        ),
        caveat="Cost robustness is necessary but cannot by itself authorize promotion.",
        section="ml",
        run_commands=("ml_replay",),
        required_artifacts=("ml_cost_sensitivity.parquet",),
        panel_count=2,
        order=226,
    ),
    FigureDefinition(
        figure_id="research_discovery_trace",
        title="Discovery trace and evidence table",
        summary=(
            "Discovery-share prices with the recorded sample, effective sample, and immutable "
            "evidence identities beneath them."
        ),
        question="What data did exploratory D1 inspect, and how much independent evidence exists?",
        uncertainty=(
            "The line is descriptive context; inferential uncertainty lives in the mechanically "
            "verified evidence artifact and its cluster-bootstrap intervals."
        ),
        caveat=(
            "EXPLORATORY D1 only. This figure cannot authorize confirmation, strategy promotion, "
            "paper trading, or orders."
        ),
        section="research",
        run_commands=("research_deep",),
        required_artifacts=("chart-data.json",),
        panel_count=2,
        order=230,
    ),
)


def figure_definition(figure_id: str) -> FigureDefinition:
    for definition in FIGURES:
        if definition.figure_id == figure_id:
            return definition
    raise DataError(f"unknown figure id {figure_id!r}")


def figures_for_command(command: str) -> tuple[FigureDefinition, ...]:
    """Catalogue entries applicable to a run command, in stable display order."""
    matches = [item for item in FIGURES if command in item.run_commands]
    return tuple(sorted(matches, key=lambda item: (item.order, item.figure_id)))


def catalog_document() -> list[dict[str, object]]:
    """JSON projection of the catalogue, for the CLI and the SPA drift guard."""
    return [
        {
            "figure_id": item.figure_id,
            "title": item.title,
            "summary": item.summary,
            "question": item.question,
            "uncertainty": item.uncertainty,
            "caveat": item.caveat,
            "section": item.section,
            "run_commands": list(item.run_commands),
            "required_artifacts": list(item.required_artifacts),
            "optional_artifacts": list(item.optional_artifacts),
            "panel_count": item.panel_count,
            "requires_snapshot": item.requires_snapshot,
            "order": item.order,
        }
        for item in sorted(FIGURES, key=lambda item: (item.order, item.figure_id))
    ]
