"""Long plain explanations, part 3: validation and search figures. Readings only."""

from __future__ import annotations

from typing import Final

from alpha_cli.figures.explanations_runs import Text

_NULL: Final[Text] = (
    (
        "The horizontal axis is a performance statistic such as the Sharpe ratio. The "
        "vertical axis is how many randomised runs produced a value in that range."
    ),
    (
        "The bars are the same strategy run on price series that were randomised to "
        "destroy any real pattern. The marked line is the value the real run reached."
    ),
    (
        "Look at where the marked line falls: inside the bars it is a value luck produced"
        " often, far to the right of the bars it is a value luck rarely produced."
    ),
    (
        "The chart cannot tell you that the strategy has an edge, only how rare the real "
        "value is among the randomised ones."
    ),
)

_FOLDS: Final[Text] = (
    (
        "The horizontal axis is the walk-forward fold in time order. The vertical axis is"
        " the Sharpe ratio measured on that fold's out-of-sample window."
    ),
    (
        "Each bar is one fold's out-of-sample Sharpe ratio, and the dashed line is zero. "
        "The second panel shows the same folds' sample sizes or dates."
    ),
    "Look at how many folds are above zero and whether one tall bar carries the average.",
    (
        "The chart cannot tell you whether fold results are independent, and a short fold"
        " gives a noisy Sharpe ratio."
    ),
)

_CI: Final[Text] = (
    "The horizontal axis is the value of each statistic. Each row is one statistic.",
    (
        "Each dot is the stored estimate and the line through it is its bootstrap "
        "confidence interval. A dashed line marks zero."
    ),
    (
        "Look at whether an interval reaches across zero and how wide each interval is "
        "compared with its estimate."
    ),
    (
        "The chart cannot tell you that the interval is exact: a bootstrap interval "
        "reflects only the sample that was resampled."
    ),
)

_SURFACE: Final[Text] = (
    (
        "The horizontal axis is one parameter and the vertical axis is another. The "
        "colour is the stored result for each pair of values."
    ),
    (
        "Each cell is one tried configuration. Marked cells show the selected "
        "configuration; hatched cells are trials that failed."
    ),
    "Look at whether the selected cell is surrounded by similar colours or sits alone on a spike.",
    (
        "The chart cannot tell you what lies between the tried values, and it shows only "
        "the parameters that were swept."
    ),
)

_TRIALS: Final[Text] = (
    "The horizontal axis is the date. The vertical axis is capital as a multiple of the start.",
    (
        "Each thin grey line is the out-of-sample equity of one tried configuration. The "
        "highlighted line is the selected one."
    ),
    (
        "Look at where the highlighted line sits among the others, and whether many grey "
        "lines end near it."
    ),
    (
        "The chart cannot tell you how many other configurations were tried and dropped "
        "before this sweep."
    ),
)

_MCPT: Final[Text] = (
    (
        "The horizontal axis is the best in-sample Sharpe ratio found over the parameter "
        "grid. The vertical axis is the number of permutations that reached it."
    ),
    (
        "Each bar counts permutations of the bars in which the whole grid was searched "
        "again. The marked line is the real search's best value."
    ),
    "Look at where the marked line falls among the bars and at the stored percentile in the label.",
    (
        "The chart cannot tell you how the selection would do out of sample; it checks "
        "only for in-sample overfitting."
    ),
)

_DISCOVERY: Final[Text] = (
    (
        "The horizontal axis is the bar end time. The vertical axis is the recorded "
        "value. The lower panel is a table of evidence records."
    ),
    (
        "The line is what the exploratory run inspected. The table lists stored counts "
        "and file hashes."
    ),
    "Look at how much data the run looked at and how few independent evidence records exist.",
    "The chart cannot tell you whether the idea works; it records only what was looked at.",
)

TEXTS: Final[dict[str, Text]] = {
    "null_distribution": _NULL,
    "fold_sharpe": _FOLDS,
    "confidence_intervals": _CI,
    "optim_surface": _SURFACE,
    "optim_trials": _TRIALS,
    "mcpt_null_histogram": _MCPT,
    "research_discovery_trace": _DISCOVERY,
}
