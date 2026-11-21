"""Long plain explanations, part 2: portfolio, simulation, forecast and model figures.

Same shape as ``explanations_runs``: four fixed sentences per figure. Readings only.
"""

from __future__ import annotations

from typing import Final

from alpha_cli.figures.explanations_runs import Text

TEXTS: Final[dict[str, Text]] = {
    "portfolio_weights": (
        (
            "The horizontal axis is the date. The vertical axis is each sleeve's weight, the "
            "share of capital it held."
        ),
        (
            "Each coloured area is one sleeve, stacked so the areas add up to the total held."
            " The second panel shows the total or the cash share."
        ),
        "Look at whether one colour dominates, and whether the mix changes slowly or in jumps.",
        "The chart cannot tell you how each sleeve performed, only how much was allocated to it.",
    ),
    "portfolio_correlations": (
        (
            "Both axes list the sleeves. The colour is the correlation between two sleeves' "
            "aligned out-of-sample returns, from -1 to 1."
        ),
        (
            "Each cell is one pair; the diagonal is each sleeve with itself and is always 1. "
            "Warm colours are moving together, cool colours are moving apart."
        ),
        "Look for cells near 1 outside the diagonal: those sleeves behave like one bet.",
        (
            "The chart cannot tell you how correlations behave in a crisis, and it uses only "
            "the dates all sleeves share."
        ),
    ),
    "propfirm_outcomes": (
        (
            "The horizontal axis is the outcome class or the simulated path. The vertical "
            "axis is how many resampled futures ended in it."
        ),
        (
            "Each bar counts simulated evaluation paths that ended in one stored outcome, "
            "such as target reached, rule broken or still open. The second panel shows the "
            "same paths over time."
        ),
        "Look at the share of paths in each class and how long the typical path took.",
        (
            "The chart cannot tell you what a real evaluation will do: the futures are "
            "resampled from the stored history."
        ),
    ),
    "monte_carlo_equity_fans": (
        (
            "The horizontal axis is the step along each simulated path. The vertical axis is "
            "simulated account equity as a multiple of the start. Each panel is one path-"
            "generation family."
        ),
        (
            "Each thin coloured line is one simulated path. The thick red line, labelled "
            "Original, is the real run's path. A black line marks 1.0x."
        ),
        (
            "Look at where the red line sits inside the bundle of simulated paths, and how "
            "wide the bundle becomes."
        ),
        (
            "The chart cannot tell you what will happen: simulated paths follow the stated "
            "generator's assumptions only."
        ),
    ),
    "monte_carlo_terminal_returns": (
        (
            "The horizontal axis is the final return of a simulated path in percent. The "
            "vertical axis is the number of paths that ended in that range. Each panel is one"
            " family."
        ),
        (
            "Each bar counts simulated paths with a final return in its range. The marked "
            "line is the real run's final return."
        ),
        "Look at where the marked line falls, and at how much of each histogram lies below zero.",
        (
            "The chart cannot tell you how likely the real future is, because the simulation "
            "reuses recorded behaviour."
        ),
    ),
    "monte_carlo_drawdown_ruin": (
        (
            "The horizontal axis is the worst drawdown of a simulated path in percent. The "
            "vertical axis is the number of paths with that worst drawdown. Each panel is one"
            " family."
        ),
        (
            "Each bar counts simulated paths by their deepest drawdown. The marked line is "
            "the ruin level, and the share beyond it is the stored ruin rate."
        ),
        (
            "Look at how much of the histogram lies past the ruin line and how deep the "
            "typical path goes."
        ),
        (
            "The chart cannot tell you the real risk of ruin, because ruin depends on the "
            "stated generator and level."
        ),
    ),
    "monte_carlo_regimes": (
        (
            "The horizontal axis is the date. The upper vertical axis is the causal "
            "volatility state; the lower vertical axis is how long each state lasted."
        ),
        (
            "Each step line is the state estimated using only past data on each date. Bars "
            "show how long each state ran before switching."
        ),
        "Look at whether both states occur and whether one lasts far longer than the other.",
        "The chart cannot tell you why the state changed, and a state is a label, not a forecast.",
    ),
    "kronos_monte_carlo_calibration": (
        (
            "The horizontal axis is the stated probability or horizon. The vertical axis is "
            "the observed frequency or the skill score."
        ),
        (
            "Each line or bar compares the generator with simple baselines. The diagonal line"
            " is perfect calibration."
        ),
        (
            "Look at how far the points sit from the diagonal and whether the model's score "
            "is above each baseline."
        ),
        "The chart cannot tell you whether calibration holds in a different market state.",
    ),
    "forecast_fan": (
        (
            "The horizontal axis is the date. The vertical axis is the price or return the "
            "model forecasts. The line to the left is what was known at the forecast origin."
        ),
        (
            "The shaded cone is the range of outcomes the model considers plausible, wider "
            "for the outer band. The line inside is its central forecast."
        ),
        "Look at how fast the cone widens, and where the recorded outcome falls against it.",
        (
            "The chart cannot tell you that the cone is correct: coverage is checked in the "
            "calibration figure."
        ),
    ),
    "forecast_skill": (
        (
            "The horizontal axis is the forecast horizon or origin date. The vertical axis is"
            " a skill score against a random-walk baseline; zero means no better than the "
            "baseline."
        ),
        (
            "Each bar or line is the stored out-of-sample skill of the model. A dashed line "
            "at zero marks the baseline."
        ),
        "Look at whether the values stay above zero across horizons or only at one of them.",
        "The chart cannot tell you whether the skill is large enough to trade after costs.",
    ),
    "forecast_calibration": (
        (
            "The horizontal axis is the nominal probability the model stated. The vertical "
            "axis is the share of outcomes that really fell inside that range."
        ),
        (
            "Each dot is one stated level. The diagonal is perfect calibration, where 80% "
            "stated means 80% observed."
        ),
        (
            "Look at whether the dots sit above the diagonal (too cautious) or below it (too "
            "confident)."
        ),
        (
            "The chart cannot tell you how many forecasts each dot is based on, so a dot from"
            " few cases is noisy."
        ),
    ),
    "state_conditioned_performance": (
        (
            "The horizontal axis is the market state. The vertical axis is the forecast error"
            " or coverage in that state."
        ),
        (
            "Each bar is one state's stored result with and without calibration. A dashed "
            "line marks the target."
        ),
        "Look at whether calibration helps in every state or only in one.",
        (
            "The chart cannot tell you how states will arrive in the future, and a rare state"
            " has few cases."
        ),
    ),
    "calibrated_reliability": (
        (
            "The horizontal axis is the stated probability after calibration. The vertical "
            "axis is the observed frequency out of sample."
        ),
        (
            "Each dot is one stated level after the calibration frozen on validation data. "
            "The diagonal is perfect reliability."
        ),
        "Look at whether the frozen calibration stays near the diagonal out of sample.",
        "The chart cannot tell you what a different freezing date would give.",
    ),
    "forecast_abstention": (
        (
            "The horizontal axis is the date or the reason. The vertical axis is the number "
            "of candidates that were declined or accepted."
        ),
        (
            "Each bar counts candidates by outcome. Declined means the calibrated model chose"
            " not to express a signal."
        ),
        "Look at what share declined and which reason is most common.",
        "The chart cannot tell you whether declining was right; it counts decisions only.",
    ),
    "ensemble_disagreement": (
        (
            "The horizontal axis is the date. The vertical axis is each ensemble member's "
            "rank score, and the second panel is how far apart the two members were."
        ),
        "Each line is one member's stored rank. The lower line is the gap between them.",
        "Look at whether the members move together and how often the gap is large.",
        "The chart cannot tell you which member is right when they disagree.",
    ),
    "feature_stability": (
        (
            "The horizontal axis is the refit or fold number. The vertical axis is each "
            "feature's stored importance."
        ),
        (
            "Each line or bar is one feature's importance at one refit. A stable feature "
            "keeps a similar value."
        ),
        "Look at features whose importance jumps between refits.",
        "The chart cannot tell you what a feature means, and importance is not a causal effect.",
    ),
    "ml_cost_sensitivity": (
        (
            "The horizontal axis is the assumed trading cost per trade. The vertical axis is "
            "the stored net result at that cost."
        ),
        (
            "Each point is the same replay run at a higher cost. A dashed line at zero marks "
            "no net result."
        ),
        "Look at how quickly the line falls and at which cost it crosses zero.",
        (
            "The chart cannot tell you the real cost you would pay, and it holds the trades "
            "themselves fixed."
        ),
    ),
    "lookalike": (
        (
            "The horizontal axis counts bars from the last bar of each stretch. The upper "
            "vertical axis "
            "is the stretch's shape, rescaled to mean 0 and spread 1; the lower vertical "
            "axis is the "
            "change in price after the stretch, in percent."
        ),
        (
            "Each thin line is one earlier stretch that matched the latest window's outline. "
            "The upper "
            "panel shows the match itself and the lower panel shows what followed it. A line "
            "marks the "
            "median when enough matches exist."
        ),
        (
            "Look at how close the outlines are to each other, and whether the paths after "
            "them spread "
            "in one direction or fan out both ways."
        ),
        (
            "The chart cannot tell you what happens next: past lookalikes describe history, "
            "and more "
            "looks in the ledger mean more chance finds."
        ),
    ),
    "unusual": (
        (
            "The horizontal axis is the date. The vertical axis is how far each stretch of "
            "bars is "
            "from its closest earlier stretch; a higher value means a more unusual shape."
        ),
        (
            "Each point is one stretch scored only against earlier bars. The line joins the "
            "scores in "
            "date order and the last point is the latest stretch."
        ),
        "Look at where the last point sits against the rest of the line, and whether "
        "high scores cluster.",
        "The chart cannot tell you why a stretch was unusual, and it is not a forecast.",
    ),
}
