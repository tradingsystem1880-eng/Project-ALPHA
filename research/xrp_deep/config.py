"""Pre-registration for the deep XRP study: families, outcomes, thresholds, protocol.

This file is fixed **before** any outcome is inspected. That ordering is the only real defence a
study of this size has, because the size is the problem: twenty-four condition families, roughly
a hundred and forty individual conditions, five outcome definitions. That is on the order of
**seven hundred hypotheses**, and at alpha = 0.05 pure noise hands you about thirty-five
"significant" results. A study that picks its specification after seeing the answers cannot be
repaired by any correction applied afterwards.

So the protocol, in order of how much work each part does:

1. **One primary condition per family.** Everything else in a family is a stability check and is
   reported as one, never promoted to a headline.
2. **Benjamini-Hochberg within each family**, where ``m`` is 3-12 and correction retains power.
   Never one pooled correction across all seven hundred — the families test different mechanisms
   and pooling them would destroy power for no epistemic gain.
3. **An empirical null calibration.** BH controls the false-discovery rate under assumptions the
   conditions here violate (they are heavily cross-correlated: MACD, RSI and the stochastic all
   read the same momentum). So the identical battery is run against surrogate series with the same
   marginal distribution and autocorrelation but no genuine predictability, and the report states
   how many discoveries the battery produces on data that by construction contains none. If the
   real run beats the surrogate run by less than its own spread, the whole exercise found nothing.
4. **Effective sample size everywhere.** A 30-day forward window on daily bars overlaps ~30x, so
   3,262 bars carry roughly 109 independent observations, not 3,262.
5. **Out-of-sample confirmation.** Split at :data:`OOS_SPLIT`; in-sample results are descriptive.
6. **Report the whole lift distribution.** A family where most conditions show a small positive
   lift is evidence. One bright cell among twelve is what noise looks like.

The user holds a **live long**, which changes nothing about the statistics and everything about
which outcomes are reported: the downside outcome is given equal billing with the upside, and the
scorecard reports what is true now rather than what was true on average.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- data

#: XRP daily, spliced. Bitstamp carries 2017-07 to 2020-09; Binance carries 2020-09 onward and is
#: the venue the position actually lives on. Validated in ``panel.py``: median close disagreement
#: 0.07% and log-return correlation 0.9965 across 1,597 overlapping days, so the join is a change
#: of venue rather than a change of asset.
SPLICE_AT = "2020-09-02"
PRIMARY_KEY = "XRP"
LONG_HISTORY_KEY = "XRP_BITSTAMP"
#: Run through the identical pipeline. A condition that works on XRP and on nothing else is a
#: property of one price series; a condition that works across the group is a property of crypto.
CONTROL_KEYS: tuple[str, ...] = ("BTC", "ETH", "SOL", "LTC")

#: Everything in-sample from here back; everything after is the confirmatory sample. Chosen as
#: roughly the two-thirds point of the spliced history, before any outcome was computed.
OOS_SPLIT = "2024-01-01"

# --------------------------------------------------------------------------- outcomes

#: Forward horizons in daily bars. Each is also its own overlap factor: a 30-day forward window
#: stamped on every bar double-counts each observation ~30 times.
HORIZONS: tuple[int, ...] = (5, 10, 30, 90)
PRIMARY_HORIZON = 30

#: The move that counts as a win, and the one that counts as a loss. Deliberately asymmetric in
#: neither direction — a long that needs +10% to be right and survives -10% to be wrong is the
#: honest framing, and reporting only the upside is how a study flatters a position it likes.
UP_THRESHOLD = 0.10
DOWN_THRESHOLD = 0.10

#: The triple-barrier outcome: the only one that corresponds to an actual trade, because it asks
#: which barrier was touched *first* rather than whether a level was ever reached.
BARRIER_UP = 0.10
BARRIER_DOWN = 0.07
#: Same-bar collisions resolve to the stop. A trader holding through a bar that touched both cannot
#: know which came first, and the adverse assumption is the one that cannot flatter the result.
BARRIER_PESSIMISTIC = True

# --------------------------------------------------------------------------- thresholds

#: Percentile cut for "compressed" / "expanded" / "extreme" regime conditions. Fixed here so no
#: condition gets to choose the threshold that makes it work.
LOW_PCTILE = 0.20
HIGH_PCTILE = 0.80
#: Trailing window over which every percentile rank is computed. One year of daily bars: long
#: enough to define a regime, short enough that "low volatility" means low *lately*.
PCTILE_WINDOW = 365

#: Fractal lookback for swings feeding the Fibonacci and pattern families.
SWING_LOOKBACK = 5
#: How close to a level counts as "at" it, as a fraction of the swing span / round-number step.
LEVEL_TOLERANCE = 0.05

# --------------------------------------------------------------------------- protocol

FDR_ALPHA = 0.05
#: Surrogate series for the empirical null. Each is a stationary-bootstrap resample of XRP's own
#: returns, which preserves the marginal distribution and short-range autocorrelation while
#: destroying any genuine relationship between a condition and its future.
NULL_SURROGATES = 200
NULL_MEAN_BLOCK = 20.0
SEED = 7

#: A family needs this many condition-true bars before it is reported at all. Below it the interval
#: is wider than the unit line and the row is noise dressed as a result.
MIN_CONDITION_BARS = 60


@dataclass(frozen=True)
class Family:
    """One condition family: a mechanism, its primary test, and why it is here."""

    key: str
    title: str
    #: The single pre-registered primary condition. Everything else in the family supports it.
    primary: str
    rationale: str


#: The twenty-four families. Order is the order they are reported in, grouped by kind: trend and
#: momentum first (the most-watched and least likely to survive), then volatility and flow, then
#: structure, then the genuinely obscure corners where an edge is more likely to still exist.
FAMILIES: tuple[Family, ...] = (
    Family(
        "ma",
        "Moving averages",
        "ma_price_above_200",
        "The most-watched condition in markets, and therefore the least likely to pay.",
    ),
    Family(
        "macd",
        "MACD",
        "macd_hist_positive",
        "Momentum via two EMAs; correlated with everything else in this block by construction.",
    ),
    Family(
        "rsi",
        "RSI",
        "rsi_oversold",
        "Mean-reversion folklore: does an oversold reading actually precede a bounce?",
    ),
    Family(
        "stoch",
        "Stochastic and Williams %R",
        "stoch_oversold",
        "The same question as RSI through a range-position lens rather than a momentum one.",
    ),
    Family(
        "bollinger",
        "Bollinger bands",
        "boll_compressed",
        "The direct test of 'coiling for a breakout' — which the pump study already doubted.",
    ),
    Family(
        "squeeze",
        "Keltner squeeze",
        "squeeze_on",
        "Compression by a second, independent construction; a check on the Bollinger verdict.",
    ),
    Family(
        "donchian",
        "Donchian channel",
        "donch_breakout_up",
        "Classic breakout: does taking out a 20-day high lead anywhere?",
    ),
    Family(
        "adx",
        "ADX and directional movement",
        "adx_trending",
        "Trend strength as a filter — the standard advice is to trade only when ADX is high.",
    ),
    Family(
        "obv",
        "On-balance volume",
        "obv_rising",
        "Volume accumulation, and whether it diverges from price before a turn.",
    ),
    Family(
        "flow",
        "Money-flow proxies",
        "cmf_positive",
        "MFI and CMF: the closest OHLCV gets to order flow, and much weaker than real delta.",
    ),
    Family(
        "volume",
        "Volume regime",
        "volume_dryup",
        "Volume dry-up is half of every 'accumulation' thesis ever written.",
    ),
    Family(
        "volatility",
        "Volatility regime",
        "vol_low",
        "Realized-vol percentile — regime, not direction, and often the only thing that persists.",
    ),
    Family(
        "ichimoku",
        "Ichimoku",
        "ichi_above_cloud",
        "A complete system in one indicator; its cloud is also the trap this repo rebuilt.",
    ),
    Family(
        "fib",
        "Fibonacci retracements",
        "fib_at_level",
        "No mechanism, enormous following. If crowding makes levels real, it shows up here.",
    ),
    Family(
        "round",
        "Round numbers",
        "round_near",
        "The same crowding question with no ambiguity about where the level is.",
    ),
    Family(
        "btc",
        "BTC correlation and lead-lag",
        "btc_up_20d",
        "XRP is a high-beta BTC expression most of the time; does BTC lead it measurably?",
    ),
    Family(
        "ratio",
        "XRP/BTC ratio",
        "ratio_above_ma",
        "Alt strength: is XRP outperforming, and does outperformance persist?",
    ),
    Family(
        "season",
        "Calendar and seasonality",
        "month_q4",
        "The weakest family by construction and read last, because multiplicity bites hardest.",
    ),
    Family(
        "memory",
        "Cycles, memory and mean reversion",
        "vr_trending",
        "Variance ratio, Hurst and spectral peaks: is there any exploitable time structure?",
    ),
    Family(
        "drawdown",
        "Drawdown and range position",
        "deep_drawdown",
        "Where in the cycle price sits — the conditioning variable that survived the pump study.",
    ),
    Family(
        "onchain",
        "On-chain",
        "mvrv_low",
        "Genuinely independent of price geometry, and therefore the best confluence candidate.",
    ),
    Family(
        "pattern",
        "Chart patterns",
        "wedge_confirmed",
        "Wedges, triple taps and H&S — the shapes the position was entered on.",
    ),
    Family(
        "basis",
        "Perp-spot basis",
        "basis_rich",
        "A sound funding proxy: funding exists to close this spread. Direct read on positioning.",
    ),
    Family(
        "bar",
        "Bar structure",
        "inside_bar",
        "Inside bars, NR7 and range expansion — the smallest-scale structure OHLCV supports.",
    ),
)

FAMILY_BY_KEY = {f.key: f for f in FAMILIES}

#: Two claims carried over from the corpus study, named so they cannot be quietly dropped.
CLAIM_MARKET_BREAKOUT = "the whole crypto market is on the verge of a breakout"
CLAIM_CONFLUENCE = "multiple technical factors reinforcing the upside bias"
