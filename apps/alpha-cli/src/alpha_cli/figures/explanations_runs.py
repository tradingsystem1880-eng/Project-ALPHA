"""Long plain explanations, part 1: performance, trades and returns figures.

Each entry is four fixed sentences: what the axes are, what each mark is, what to look
for, and what the chart cannot tell. The sentences about this run's own numbers are added
by ``spec_facts`` from the stored data. Readings only: no pass or fail, no advice.
"""

from __future__ import annotations

from typing import Final

Text = tuple[str, str, str, str]

_UNDERWATER: Final[Text] = (
    (
        "The horizontal axis is the date. The upper panel's vertical axis is capital as a"
        " multiple of the start (1.0x is where it began); the lower panel's vertical axis"
        " is the drawdown, the percentage below the highest capital reached so far."
    ),
    (
        "The upper line is the strategy's capital after recorded fees and slippage; the "
        "grey line is its running peak. The lower filled area is how far capital sat "
        "below that peak on each date, so 0.0% means a new high."
    ),
    (
        "Look at how deep the lower area goes, how long it stays below zero before "
        "returning, and whether the deep spells cluster in one period."
    ),
    (
        "The chart cannot tell you whether the same path would repeat, and a drawdown is "
        "measured on the dates shown, not on the days between them."
    ),
)
_PASSIVE: Final[Text] = (
    (
        "The horizontal axis is the date. The upper vertical axis is growth of 1.0 "
        "invested at the start; the lower vertical axis is how far ahead or behind buy "
        "and hold the strategy stood, in percent."
    ),
    (
        "One line is the strategy after recorded fees and slippage and the other is the "
        "same asset held without trading. The lower line is strategy growth divided by "
        "buy-and-hold growth, minus one."
    ),
    (
        "Look at when the lower line rises or falls: a lead that comes from one short "
        "window tells a different story than a lead that builds steadily."
    ),
    (
        "The chart cannot tell you why the two paths differ, and buy and hold here pays "
        "no trading costs."
    ),
)
_ROLLING: Final[Text] = (
    (
        "The horizontal axis is the date. Each vertical axis is one risk measure computed"
        " over a rolling window that ends on that date."
    ),
    (
        "Each line is the stored rolling value of one measure: the Sharpe ratio, the "
        "annualised volatility and the return over the window. A black line marks zero "
        "where it applies."
    ),
    (
        "Look for stretches where a line leaves its usual range, and for whether the "
        "value stays on one side of zero or crosses it often."
    ),
    (
        "The chart cannot tell you what caused a change, and a rolling value is noisy at "
        "the start because its window is still filling."
    ),
)
_MONTHLY: Final[Text] = (
    (
        "The columns are calendar months plus a full-year column; the rows are years. "
        "Colour is the return in that month, in percent."
    ),
    (
        "Each cell is one month's compounded return, and the last column is the whole "
        "year. Green cells are gains, red cells are losses, and the strongest colours are"
        " the largest moves."
    ),
    (
        "Look for a row that is mostly one colour, for a column that is always the same "
        "colour, and for single cells far stronger than their neighbours."
    ),
    (
        "The chart cannot tell you whether a month-of-year pattern is real: each column "
        "holds only one value per year."
    ),
)
_PRICE: Final[Text] = (
    (
        "The horizontal axis is the date. The upper vertical axis is the asset's price in"
        " its quote currency; any lower panels show the strategy's own indicators in "
        "their own units."
    ),
    (
        "Candles or the closing-price line show the market. Triangles mark fills: an up "
        "triangle is a buy and a down triangle is a sell. Coloured lines and shaded spans"
        " are what the strategy chose to draw."
    ),
    (
        "Look at whether the fills sit where the rule says they should, and whether "
        "indicator lines cross their levels just before each fill."
    ),
    "The chart cannot tell you whether a fill was a good trade, only where and when it happened.",
)
_TRADE_PNL: Final[Text] = (
    (
        "The horizontal axis is the trade number in entry order, or the profit and loss "
        "of each trade. The vertical axis is profit or loss per trade, after costs."
    ),
    (
        "Each bar is one closed trade: green for a gain and red for a loss. A second "
        "panel sums the same trades as a running total."
    ),
    (
        "Look at whether a few very tall bars carry the running total, and whether losses"
        " come in groups."
    ),
    (
        "The chart cannot tell you what the next trade will do, and it ignores trades "
        "still open at the end."
    ),
)
_RUNS: Final[Text] = (
    (
        "The horizontal axis is the trade number in entry order. The vertical axis marks "
        "whether each trade won or lost."
    ),
    (
        "Each step is one trade's sign, and a streak is a run of the same sign in a row. "
        "The stored runs z-score compares the number of streaks with the number "
        "independent outcomes would give."
    ),
    (
        "Look for long streaks of one sign, and for sign changes on nearly every trade; "
        "both depart from independent outcomes."
    ),
    (
        "The chart cannot tell you why trades depend on each other, and few trades make "
        "any runs score unreliable."
    ),
)
_HOLDING: Final[Text] = (
    (
        "The horizontal axis is how long a trade was held, in days. The vertical axis is "
        "the number of trades with that holding time."
    ),
    (
        "Each bar counts the trades whose holding time falls in its range. The marked "
        "line shows the typical holding time."
    ),
    (
        "Look at whether the bars cluster near the intended holding horizon, and whether "
        "a long tail of very long trades sits far to the right."
    ),
    "The chart cannot tell you how much each trade earned, only how long it lasted.",
)
_RETURNS: Final[Text] = (
    (
        "The horizontal axis is the daily return as a fraction (0.01 is 1%). The vertical"
        " axis is the number of days with a return in that range."
    ),
    (
        "Each bar counts days in one return range. The marked lines show the mean, and "
        "the stored tail quantiles show how far the extremes reach."
    ),
    (
        "Look at how far the bars extend to each side, whether the left tail is longer "
        "than the right, and how tall the middle is compared with the sides."
    ),
    "The chart cannot tell you the order of the days, so it hides how losses cluster in time.",
)
_QQ: Final[Text] = (
    (
        "The horizontal axis is what a normal distribution would predict for each return "
        "rank. The vertical axis is the return actually observed at that rank."
    ),
    (
        "Each dot is one ranked daily return. The straight line is where the dots would "
        "fall if returns were normal."
    ),
    (
        "Look at the two ends: dots curling away from the line mean tails fatter or "
        "thinner than normal."
    ),
    (
        "The chart cannot tell you how often an extreme day will arrive, only that the "
        "tails differ from normal."
    ),
)
_EPISODES: Final[Text] = (
    (
        "The horizontal axis is the date. The vertical axis is the drawdown, the "
        "percentage below the highest capital reached so far."
    ),
    (
        "Each shaded span is one of the worst drawdown episodes, from its peak through "
        "its trough to its recovery. The line is the drawdown curve itself."
    ),
    (
        "Look at the depth of each episode, its length from peak to recovery, and whether"
        " episodes overlap in time."
    ),
    (
        "The chart cannot tell you what is coming next, and an episode that has not "
        "recovered by the last date has no recovery date yet."
    ),
)
_EXPOSURE: Final[Text] = (
    (
        "The horizontal axis is the date. The upper vertical axis is gross exposure, the "
        "share of capital in the market; the lower vertical axis is turnover, how much "
        "was traded."
    ),
    (
        "The upper line is stored exposure on each date and the lower line is stored "
        "turnover. A flat line at zero means the strategy held no position."
    ),
    (
        "Look at how long exposure stays at zero, how high it reaches, and whether "
        "turnover spikes line up with changes in exposure."
    ),
    (
        "The chart cannot tell you the direction of the positions, and it cannot say what"
        " trading cost."
    ),
)

TEXTS: Final[dict[str, Text]] = {
    "equity_underwater": _UNDERWATER,
    "equity_vs_passive": _PASSIVE,
    "rolling_risk": _ROLLING,
    "monthly_heatmap": _MONTHLY,
    "price_signal": _PRICE,
    "trade_pnl": _TRADE_PNL,
    "trade_runs_test": _RUNS,
    "holding_period": _HOLDING,
    "return_distribution": _RETURNS,
    "qq_normal": _QQ,
    "drawdown_episodes": _EPISODES,
    "exposure_turnover": _EXPOSURE,
    "tradable_equity_underwater": _UNDERWATER,
    "tradable_equity_vs_passive": _PASSIVE,
}
