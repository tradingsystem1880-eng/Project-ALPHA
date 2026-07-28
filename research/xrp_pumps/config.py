"""Pre-registration for the XRP pump-condition study: predictors, labels, thresholds, protocol.

This file is written **before** any outcome is inspected, and that ordering is the study's main
defence against itself. Four predictor families times roughly ten predictors times four pump
definitions times four timeframes is on the order of six hundred hypotheses; at alpha = 0.05 that
generates about thirty "significant" cells from pure noise. No post-hoc correction repairs a study
that chose its specification after seeing the answers, so the specification is fixed here and the
protocol below is the only thing allowed to carry a claim.

The discipline, in order of how much work it does:

1. **One primary predictor per family.** Everything else in the family is a stability check.
2. **Benjamini-Hochberg within each family**, where ``m`` is ~10 and correction retains power.
   Never one pooled correction across all six hundred — the families test different mechanisms.
3. **The confirmatory test is out-of-sample only**, split at ``WALK_FORWARD_SPLIT``. Everything
   in-sample is descriptive and is labelled as such in the report.
4. **Effective sample size everywhere.** A 30-day forward window on daily bars overlaps ~30x.
5. **Report the whole distribution of lifts, not the best cells.**

Two claims from the source material are named here so they cannot be quietly dropped if they fail:
``CLAIM_MARKET_BREAKOUT`` and ``CLAIM_CONFLUENCE``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# --------------------------------------------------------------------------- scope

#: Timeframes studied. Daily is primary — the pump horizons are measured in weeks, and a 15-minute
#: bar contributes 96 near-identical observations of the same 30-day forward window.
TIMEFRAMES: tuple[str, ...] = ("1d", "4h")
PRIMARY_TIMEFRAME = "1d"

#: Price sources reused verbatim from the head-and-shoulders study (same mirrors, same SHA pins).
#: XRP is the subject; the rest are run through the identical pipeline as controls, because a
#: finding that appears only on XRP and on no other asset is a property of one price series rather
#: than of the pattern — the distinction the previous two studies both turned on.
PRICE_KEYS: tuple[str, ...] = ("XRP", "BTC", "ETH", "SOL", "LTC", "XRP_BITSTAMP")
SUBJECT_KEY = "XRP"

#: Assets counted in the market-breadth measure. One entry per distinct underlying — including both
#: XRP mirrors would let the subject vote for its own market condition.
#:
#: Two baskets, because the two eras have no common venue: the Binance perp mirrors run 2020-09 to
#: 2026-07, the Bitstamp spot mirrors 2017-07 to 2025-01. A subject is matched to the basket that
#: shares its history, so breadth is measured against contemporaries rather than against a series
#: that did not yet exist.
BREADTH_KEYS: tuple[str, ...] = ("XRP", "BTC", "ETH", "SOL", "LINK")
LEADER_KEY = "BTC"
BREADTH_KEYS_LEGACY: tuple[str, ...] = ("XRP_BITSTAMP", "BTC_BITSTAMP", "ETH_BITSTAMP", "LTC")
LEADER_KEY_LEGACY = "BTC_BITSTAMP"

#: Subjects served by the legacy (Bitstamp) basket.
LEGACY_KEYS: frozenset[str] = frozenset({"XRP_BITSTAMP", "BTC_BITSTAMP", "ETH_BITSTAMP", "LTC"})


def basket_for(subject_key: str) -> tuple[tuple[str, ...], str]:
    """The breadth basket and market leader whose history matches ``subject_key``'s."""
    if subject_key in LEGACY_KEYS:
        return BREADTH_KEYS_LEGACY, LEADER_KEY_LEGACY
    return BREADTH_KEYS, LEADER_KEY


OUT_DIR = "data/xrp_pumps"
RAW_DIR = "data/cache/coinmetrics"

# --------------------------------------------------------------------------- on-chain

#: CoinMetrics community daily CSVs. Reachable from this environment when every market-data API is
#: not; each file is SHA-256 pinned on fetch and the hash is carried into the report.
COINMETRICS_URL = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/{asset}.csv"

#: Assets used for market-wide aggregates (dominance, breadth, total cap). SOL is deliberately
#: **absent**: its community file carries only ``CapMrktEstUSD`` (free-float estimated) where the
#: others carry ``CapMrktCurUSD`` (current supply). Summing the two definitions into one dominance
#: figure would be an apples-to-oranges error that no downstream reader could see.
ONCHAIN_ASSETS: tuple[str, ...] = ("btc", "eth", "xrp", "ada", "doge", "ltc", "link")
ONCHAIN_SUBJECT = "xrp"

#: Market-wide aggregates are only defined once this many constituents actually report. Without the
#: floor, 2011 shows "100% BTC dominance" — true of the seven-asset basket and meaningless as a
#: market statistic.
MIN_ASSETS_FOR_AGGREGATE = 4

#: Columns kept. Everything else in the file is either derived from these or empty for most assets.
ONCHAIN_COLUMNS: tuple[str, ...] = (
    "PriceUSD",
    "CapMrktCurUSD",
    "CapMVRVCur",
    "AdrActCnt",
    "TxCnt",
    "TxTfrCnt",
    "PriceBTC",
    "volume_reported_spot_usd_1d",
)

#: **The critical point-in-time rule for on-chain data.** A CoinMetrics row stamped ``D`` summarises
#: activity *during* day D and is only published after D closes. Using it to condition a decision
#: taken during D reads the future. Every on-chain series is therefore lagged by this many days
#: before it touches a feature.
ONCHAIN_PUBLICATION_LAG_DAYS = 1

#: The series ends here. Stated as a constant so the scorecard can refuse to carry stale values
#: forward into a live read rather than silently pretending they are current.
ONCHAIN_ENDS = "2026-05-23"

# --------------------------------------------------------------------------- labels


@dataclass(frozen=True)
class PumpDefinition:
    """One definition of "a pump", as a forward return threshold over a horizon.

    Four are swept deliberately. A condition that lifts the odds of a +20%/30d move *and* a
    +50%/90d move *and* a +100%/180d move is describing something real about the market. A condition
    that only lifts one of them has found a threshold, not a mechanism, and the report says so.
    """

    name: str
    horizon_days: int
    threshold: float  # minimum forward return; NaN when the label is a relative quantile
    relative_quantile: float = float("nan")  # top-q of the forward-return distribution instead

    @property
    def is_relative(self) -> bool:
        """A NaN threshold means the label is the top-``relative_quantile`` of forward returns."""
        return math.isnan(self.threshold)

    @property
    def label(self) -> str:
        if self.is_relative:
            return f"top{int(self.relative_quantile * 100)}pct_{self.horizon_days}d"
        return f"up{int(self.threshold * 100)}_{self.horizon_days}d"


PUMPS: tuple[PumpDefinition, ...] = (
    PumpDefinition("modest", 30, 0.20),
    PumpDefinition("large", 90, 0.50),
    PumpDefinition("major", 180, 1.00),
    PumpDefinition("relative", 30, float("nan"), relative_quantile=0.10),
)

#: Also measured, but as a *symmetry check* rather than a headline: a predictor that raises the odds
#: of a +20% move while raising the odds of a -20% move by the same amount has found volatility,
#: not direction. This is the single most common way a "breakout predictor" fools its author.
DRAWDOWN_MIRROR = PumpDefinition("mirror", 30, -0.20)

#: **Declared post-hoc, and reported as such.** The four pre-registered definitions turned out to
#: have almost no statistical power: at 30/90/180-day horizons a decade of daily bars holds only
#: ~71/~23/~11 independent forward windows, so no interval could separate from zero whatever the
#: data said. These two shorter horizons were added afterwards for that reason alone.
#:
#: The addition is defensible because the power calculation depends only on the *horizon*, which is
#: visible without inspecting a single outcome — but it is still a specification chosen after
#: results were seen, so these labels are reported in their own section, never as confirmatory, and
#: their cells are BH-corrected together with everything else in their family.
POWER_PUMPS: tuple[PumpDefinition, ...] = (
    PumpDefinition("fast", 7, 0.10),
    PumpDefinition("swing", 14, 0.25),
)

# --------------------------------------------------------------------------- predictor families


@dataclass(frozen=True)
class Predictor:
    """One pre-registered condition, expressed as a named feature column and a threshold rule."""

    name: str
    family: str
    column: str
    rule: str  # "below" | "above" | "equal" | "between"
    threshold: float
    upper: float = float("nan")
    primary: bool = False
    note: str = ""


#: Family 1 — volatility compression and range. The direct test of "on the verge of a breakout".
FAMILY_COMPRESSION = "compression"
#: Family 2 — BTC lead-lag and market structure. The direct test of "the whole crypto market".
FAMILY_MARKET = "market"
#: Family 3 — on-chain. Genuinely independent of price geometry, and therefore the strongest
#: confluence candidate if anything survives.
FAMILY_ONCHAIN = "onchain"
#: Family 4 — seasonality. Flagged weakest and read last: it is where multiplicity bites hardest
#: and where a finding is least likely to reflect a mechanism.
FAMILY_SEASONAL = "seasonal"

PREDICTORS: tuple[Predictor, ...] = (
    # ---- compression -------------------------------------------------------
    Predictor(
        "bandwidth_pct<0.10",
        FAMILY_COMPRESSION,
        "bandwidth_pct",
        "below",
        0.10,
        primary=True,
        note="Bollinger bandwidth in the bottom decile of its own trailing year.",
    ),
    Predictor("bandwidth_pct<0.25", FAMILY_COMPRESSION, "bandwidth_pct", "below", 0.25),
    Predictor("realvol_pct<0.10", FAMILY_COMPRESSION, "realvol_pct", "below", 0.10),
    Predictor("realvol_pct<0.25", FAMILY_COMPRESSION, "realvol_pct", "below", 0.25),
    Predictor("atr_pct_rank<0.20", FAMILY_COMPRESSION, "atr_pct_rank", "below", 0.20),
    Predictor("volume_dryup", FAMILY_COMPRESSION, "volume_ratio_20", "below", 0.75),
    Predictor("consolidating_30d", FAMILY_COMPRESSION, "consolidation_bars", "above", 30.0),
    Predictor(
        "wedge_near_apex",
        FAMILY_COMPRESSION,
        "wedge_near_apex",
        "above",
        0.5,
        note="Inside a converging formation with its apex within 30 bars.",
    ),
    Predictor(
        "wedge_past_apex",
        FAMILY_COMPRESSION,
        "wedge_past_apex",
        "above",
        0.5,
        note="THE LIVE CASE: drifted past the apex without breaking.",
    ),
    # ---- market ------------------------------------------------------------
    Predictor(
        "breadth_compressed>=0.5",
        FAMILY_MARKET,
        "breadth_compressed",
        "above",
        0.5,
        primary=True,
        note="CLAIM_MARKET_BREAKOUT: half or more of the majors simultaneously compressed.",
    ),
    Predictor("breadth_compressed>=0.75", FAMILY_MARKET, "breadth_compressed", "above", 0.75),
    Predictor("btc_corr_60<0.3", FAMILY_MARKET, "btc_corr_60", "below", 0.30),
    Predictor("btc_corr_60>0.8", FAMILY_MARKET, "btc_corr_60", "above", 0.80),
    Predictor("btc_lead_30d>0.10", FAMILY_MARKET, "btc_ret_30", "above", 0.10),
    Predictor("btc_lead_30d<-0.10", FAMILY_MARKET, "btc_ret_30", "below", -0.10),
    Predictor("ratio_pct<0.10", FAMILY_MARKET, "ratio_pct", "below", 0.10),
    Predictor("dominance_pct>0.80", FAMILY_MARKET, "dominance_pct", "above", 0.80),
    Predictor("dominance_falling", FAMILY_MARKET, "dominance_chg_30", "below", -0.02),
    # ---- onchain -----------------------------------------------------------
    Predictor(
        "mvrv_pct<0.20",
        FAMILY_ONCHAIN,
        "mvrv_pct",
        "below",
        0.20,
        primary=True,
        note="MVRV in the bottom quintile of its trailing two years — the classic value read.",
    ),
    Predictor("mvrv_pct>0.80", FAMILY_ONCHAIN, "mvrv_pct", "above", 0.80),
    Predictor("adr_growth_30>0.20", FAMILY_ONCHAIN, "adr_growth_30", "above", 0.20),
    Predictor("adr_pct>0.80", FAMILY_ONCHAIN, "adr_pct", "above", 0.80),
    Predictor("tx_growth_30>0.20", FAMILY_ONCHAIN, "tx_growth_30", "above", 0.20),
    Predictor("adr_price_divergence", FAMILY_ONCHAIN, "adr_price_divergence", "above", 0.20),
    Predictor("cm_volume_pct<0.20", FAMILY_ONCHAIN, "cm_volume_pct", "below", 0.20),
    # ---- seasonal ----------------------------------------------------------
    Predictor(
        "q4",
        FAMILY_SEASONAL,
        "month",
        "between",
        10.0,
        upper=12.0,
        primary=True,
        note="October-December. The most-repeated seasonal claim in crypto.",
    ),
    Predictor("january", FAMILY_SEASONAL, "month", "equal", 1.0),
    Predictor("q1", FAMILY_SEASONAL, "month", "between", 1.0, upper=3.0),
    Predictor("summer_q3", FAMILY_SEASONAL, "month", "between", 7.0, upper=9.0),
    Predictor("monday", FAMILY_SEASONAL, "day_of_week", "equal", 0.0),
    Predictor("weekend", FAMILY_SEASONAL, "day_of_week", "above", 4.5),
    Predictor(
        "post_halving_yr1", FAMILY_SEASONAL, "years_since_halving", "between", 0.0, upper=1.0
    ),
    Predictor(
        "post_halving_yr2", FAMILY_SEASONAL, "years_since_halving", "between", 1.0, upper=2.0
    ),
)

FAMILIES: tuple[str, ...] = (
    FAMILY_COMPRESSION,
    FAMILY_MARKET,
    FAMILY_ONCHAIN,
    FAMILY_SEASONAL,
)

#: The two claims under direct test, named so a null result on either is reported rather than lost.
CLAIM_MARKET_BREAKOUT = "breadth_compressed>=0.5"
CLAIM_CONFLUENCE = "confluence_count"

#: Conditions counted toward the confluence score. One per family plus the wedge, so the stack tests
#: *independent* mechanisms rather than four rescalings of the same volatility reading.
CONFLUENCE_MEMBERS: tuple[str, ...] = (
    "bandwidth_pct<0.10",
    "breadth_compressed>=0.5",
    "mvrv_pct<0.20",
    "wedge_near_apex",
    "btc_corr_60>0.8",
)

# --------------------------------------------------------------------------- feature windows


@dataclass(frozen=True)
class Windows:
    """Lookback windows in **days**, converted to bars per timeframe by ``bars(...)``."""

    bandwidth: int = 20
    realvol: int = 30
    atr: int = 14
    rank: int = 365  # percentile-rank window: one year of the asset's own history
    mvrv_rank: int = 730  # two years — MVRV cycles are slower than volatility
    correlation: int = 60
    consolidation: int = 20
    consolidation_threshold: float = 0.15
    volume: int = 20
    momentum: int = 30
    compression_quantile: float = 0.25  # "compressed" for the breadth count


WINDOWS = Windows()

# --------------------------------------------------------------------------- protocol

WALK_FORWARD_SPLIT = "2023-01-01"
SEED = 7
CONFIDENCE = 0.95
FDR_ALPHA = 0.05

#: Bitcoin halvings, used for the ``years_since_halving`` seasonal feature. Dates are the block
#: events, which are public and fixed; the 2028 entry is the scheduled estimate and is only used to
#: bound the final cycle.
HALVINGS: tuple[str, ...] = (
    "2012-11-28",
    "2016-07-09",
    "2020-05-11",
    "2024-04-20",
    "2028-04-01",
)

BARS_PER_DAY: dict[str, int] = {"15m": 96, "1h": 24, "4h": 6, "1d": 1}


def bars(days: int, timeframe: str) -> int:
    """Convert a window in days to bars on ``timeframe`` (never below 2)."""
    return max(2, days * BARS_PER_DAY[timeframe])


# --------------------------------------------------------------------------- live position
# Carried from the head-and-shoulders study so the scorecard can price the live setup without
# importing that package. From the exchange screenshot (2026-07-28), which supersedes prose.

ENTRY = 1.0566
STOP = 0.9990
TARGET = 1.3000
LIQUIDATION = 0.9957
QUANTITY = 60_123.9
LEVERAGE = 16
RISK_CAP_USDT = 44.0

#: The two structural calls under test, with the dates they were made.
ACE_CALLS_FILE = "research/xrp_pumps/calls.csv"
WEEKLY_WEDGE_NOTE = "michaelmt 2026-07-01: falling wedge at apex, targets 1.85-2.40"
ACE_IHS_NOTE = "Ace 2026-07-21: inverse head and shoulders, 'multiple technical factors'"

# --------------------------------------------------------------------------- presentation

BG = "#0d1117"
FG = "#c9d1d9"
GRID = "#21262d"
PANEL = "#161b22"
UP = "#3fb950"
DOWN = "#f85149"
ACCENT = "#58a6ff"
WARN = "#d29922"
MUTED = "#8b949e"

#: Per-family plot colour, so a chart and a table can be read together.
FAMILY_COLOURS: dict[str, str] = {
    FAMILY_COMPRESSION: ACCENT,
    FAMILY_MARKET: UP,
    FAMILY_ONCHAIN: WARN,
    FAMILY_SEASONAL: MUTED,
}


def predictors_in(family: str) -> tuple[Predictor, ...]:
    """Every predictor in one family, in declaration order (primary first by convention)."""
    return tuple(p for p in PREDICTORS if p.family == family)


def primary_of(family: str) -> Predictor:
    """The one pre-registered predictor a family's confirmatory claim rests on."""
    for p in PREDICTORS:
        if p.family == family and p.primary:
            return p
    raise KeyError(f"no primary predictor declared for family {family!r}")
