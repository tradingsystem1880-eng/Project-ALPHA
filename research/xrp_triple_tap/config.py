"""Single source of truth for the XRP triple-tap / trendline studies.

Every number the studies depend on lives here — position parameters, the pre-registered primary
specification, the sweep axes, and the data sources with their provenance. Nothing downstream
carries a magic number.

**Pre-registration.** ``PRIMARY_TRIPLE_TAP`` and ``PRIMARY_TRENDLINE`` are fixed *before* looking at
any outcome, chosen to match the setup described on the user's chart. Only the out-of-sample run of
these two specifications is permitted a significance claim; the full sweep is descriptive. Counted
naively the sweep is ~469,000 hypothesis tests, at which point a Benjamini-Hochberg correction needs
p < 1.1e-07 to declare anything — so multiplicity is controlled by design, not after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- position

# Taken from the exchange screenshot (2026-07-28 19:47), which supersedes the levels given in
# prose. Six fields differ and three of them change the analysis: the size is 6x larger, the
# target is +23% rather than +166%, and the position is 16x isolated with a liquidation price
# only 0.33% below the stop.
ENTRY = 1.0566
STOP = 0.9990  # exchange SL on the entire position
TARGET = 1.3000  # exchange TP
LIQUIDATION = 0.9957
QUANTITY = 60_123.9
LEVERAGE = 16
MARGIN_USDT = 4_003.4005
MAINT_MARGIN_USDT = 356.3876
RISK_CAP_USDT = 44.0  # framework cap; the stop risks ~79x this, a liquidation ~91x

REWARD_RISK = (TARGET - ENTRY) / (ENTRY - STOP)
BREAKEVEN = 1.0 / (1.0 + REWARD_RISK)
STOP_FRACTION = (ENTRY - STOP) / ENTRY
LIQ_FRACTION = (ENTRY - LIQUIDATION) / ENTRY
# The number that dominates the trade: stop-to-liquidation buffer as a fraction of price.
STOP_TO_LIQ_BUFFER = (STOP - LIQUIDATION) / STOP

# --------------------------------------------------------------------------- externally supplied
# Figures from the user's prior analysis. NOT reproduced in this repo and NOT verified here — the
# code that produced them is not present and the source data was not reachable. Carried as context
# only; every table that cites one marks it unverified.
PRIOR_BARRIER_N = 181
PRIOR_BARRIER_HITS = 9  # 4.9% of 181
PRIOR_SWEEP_P50 = 0.0826
PRIOR_SWEEP_P75 = 0.1687
PRIOR_SWEEP_P90 = 0.2875
PRIOR_NOISE_HIT_90D = 0.910

# --------------------------------------------------------------------------- data

BARS_PER_DAY = 6  # 4-hour bars
RAW_DIR = "data/cache/raw_github"


@dataclass(frozen=True)
class Source:
    """One cached dataset plus everything needed to judge whether to trust it."""

    key: str
    symbol: str
    path: str
    url: str
    exchange: str
    market: str
    fmt: str  # "parquet_5m" | "cdd_csv_1h" | "plain_csv_4h"
    note: str = ""


SOURCES: tuple[Source, ...] = (
    Source(
        "XRP",
        "XRP",
        f"{RAW_DIR}/binance_linear_XRPUSDT_5m.parquet",
        "raw.githubusercontent.com/atOCEANO/sample-market-data",
        "binance",
        "linear-perp",
        "parquet_5m",
        "PRIMARY. 2020-09-02 to 2026-07-25, 620k 5m bars, zero gaps. Perp matches the "
        "instrument actually traded.",
    ),
    Source(
        "BTC",
        "BTC",
        f"{RAW_DIR}/binance_linear_BTCUSDT_5m.parquet",
        "raw.githubusercontent.com/atOCEANO/sample-market-data",
        "binance",
        "linear-perp",
        "parquet_5m",
        "Cross-asset control.",
    ),
    Source(
        "ETH",
        "ETH",
        f"{RAW_DIR}/binance_linear_ETHUSDT_5m.parquet",
        "raw.githubusercontent.com/atOCEANO/sample-market-data",
        "binance",
        "linear-perp",
        "parquet_5m",
        "Cross-asset control.",
    ),
    Source(
        "SOL",
        "SOL",
        f"{RAW_DIR}/binance_linear_SOLUSDT_5m.parquet",
        "raw.githubusercontent.com/atOCEANO/sample-market-data",
        "binance",
        "linear-perp",
        "parquet_5m",
        "Cross-asset control, from 2020-09-14.",
    ),
    Source(
        "LTC",
        "LTC",
        f"{RAW_DIR}/Bitstamp_LTCUSD_1h.csv",
        "raw.githubusercontent.com/kam1lg/ML_predykcja_LSTM",
        "bitstamp",
        "spot",
        "cdd_csv_1h",
        "Mid-cap. Different venue and window (2018-05 to 2025-01) — not directly poolable.",
    ),
    Source(
        "LINK",
        "LINK",
        f"{RAW_DIR}/LINKUSDT_4h_binance.csv",
        "raw.githubusercontent.com/SandPearlStone/trading-bot",
        "binance",
        "spot",
        "plain_csv_4h",
        "Mid-cap. Short window (2024-03 to 2026-03); low power by construction.",
    ),
    Source(
        "XRP_BITSTAMP",
        "XRP",
        f"{RAW_DIR}/Bitstamp_XRPUSD_1h.csv",
        "raw.githubusercontent.com/kam1lg/ML_predykcja_LSTM",
        "bitstamp",
        "spot",
        "cdd_csv_1h",
        "Independent venue cross-check of the XRP result (2018-05 to 2025-01).",
    ),
)

PRIMARY_KEY = "XRP"
CROSS_ASSET_KEYS = ("BTC", "ETH", "SOL", "LTC", "LINK")

# Data ends 2026-07-25; the session date is 2026-07-28. The final ~3 days are absent everywhere
# reachable, so the live setup's most recent bars are not in sample.
DATA_ENDS = "2026-07-25T21:15:00Z"

# --------------------------------------------------------------------------- pre-registered specs

PRIMARY_TRIPLE_TAP = {
    "lookback": 5,
    "tolerance": 0.02,
    "band_reference": "mean",
    "gap_min": 12,
    "gap_max": 250,
    "population": "ascending",
    "min_intervening_rally": 0.03,
}

PRIMARY_TRENDLINE = {
    "lookback": 5,
    "min_anchor_gap": 12,
    "max_anchor_gap": 500,
    "max_age": 500,
    "scale": "log",
    "require_third_touch": False,
}

# --------------------------------------------------------------------------- sweeps


@dataclass(frozen=True)
class Sweep:
    """Descriptive sensitivity axes. No significance claims attached to these."""

    lookback: tuple[int, ...] = (3, 5, 8)
    tolerance: tuple[float, ...] = (0.005, 0.01, 0.02, 0.03)
    band_reference: tuple[str, ...] = ("first", "mean", "atr")
    gap_min: tuple[int, ...] = (6, 12, 24)
    gap_max: tuple[int, ...] = (120, 250, 500)
    population: tuple[str, ...] = ("strict", "ascending")


SWEEP = Sweep()

# Barrier configurations. The live trade's 28.8:1 / 90-day cell is included but is known in advance
# to be underpowered (min detectable rate 6-10% against a 3.36% breakeven); the 2R-5R short-horizon
# cells are where the study actually has resolving power.
BARRIER_GRID: tuple[tuple[float, float, int], ...] = (
    # (stop_fraction, target_R, horizon_days)
    (0.03, 2.0, 10),
    (0.03, 2.0, 20),
    (0.03, 3.0, 20),
    (0.06, 2.0, 10),
    (0.06, 2.0, 20),
    (0.06, 3.0, 20),
    (0.06, 5.0, 30),
    (0.10, 2.0, 20),
    (0.10, 3.0, 30),
    (0.10, 5.0, 30),
)

LIVE_TRADE_CELL = (STOP_FRACTION, REWARD_RISK, 90)

# --------------------------------------------------------------------------- splits & controls

WALK_FORWARD_SPLIT = "2023-01-01"  # fit/describe before, confirm after
CONTROL_PER_EVENT = 5
CONTROL_DISTANCE_TOL = 0.25
CONTROL_EXCLUSION_BARS = 60
SEED = 7
N_BOOTSTRAP = 1000
CONFIDENCE = 0.95

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
