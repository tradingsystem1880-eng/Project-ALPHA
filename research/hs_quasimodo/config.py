"""Single source of truth for the head-and-shoulders / Quasimodo study.

Everything the study depends on lives here: the source × timeframe matrix with its **native
resolution floors**, the pre-registered primary specifications, the sweep axes, the barrier grid,
and the live position constants.

**Pre-registration.** ``PRIMARY`` fixes one specification per variant *before* any outcome is
inspected. Only the out-of-sample run of those specs may carry a significance claim; the sweep is a
descriptive stability surface. This is the same discipline the triple-tap study used, and it exists
because a naive sweep across every axis generates enough hypotheses that an honest multiplicity
correction would annihilate the study's own power.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Timeframe = Literal["15m", "1h", "4h", "1d"]

#: Bars per calendar day, used to convert horizons in days to horizons in bars.
BARS_PER_DAY: dict[str, int] = {"15m": 96, "1h": 24, "4h": 6, "1d": 1}

#: Ordering for "is this timeframe reachable from that source?" checks.
TF_MINUTES: dict[str, int] = {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}

RAW_DIR = "data/cache/raw_github"
OUT_DIR = "data/hs"

# --------------------------------------------------------------------------- live position
# From the exchange screenshot (2026-07-28 19:47) — supersedes the levels given in prose.
ENTRY = 1.0566
STOP = 0.9990
TARGET = 1.3000
LIQUIDATION = 0.9957
QUANTITY = 60_123.9
LEVERAGE = 16
MARGIN_USDT = 4_003.4005
RISK_CAP_USDT = 44.0

REWARD_RISK = (TARGET - ENTRY) / (ENTRY - STOP)
BREAKEVEN = 1.0 / (1.0 + REWARD_RISK)
STOP_FRACTION = (ENTRY - STOP) / ENTRY
STOP_TO_LIQ_BUFFER = (STOP - LIQUIDATION) / STOP

# --------------------------------------------------------------------------- sources


@dataclass(frozen=True)
class Source:
    """One cached dataset, with the finest timeframe it can honestly produce."""

    key: str
    symbol: str
    path: str
    url: str
    exchange: str
    market: str
    fmt: str  # parquet_5m | cdd_csv_1h | plain_csv_4h
    native_minutes: int  # requesting anything finer must fail loud, never upsample
    extends: str = ""  # optional earlier-history file spliced in front
    note: str = ""

    def supports(self, timeframe: str) -> bool:
        return TF_MINUTES[timeframe] >= self.native_minutes


SOURCES: tuple[Source, ...] = (
    Source(
        "XRP",
        "XRP",
        f"{RAW_DIR}/binance_linear_XRPUSDT_5m.parquet",
        "raw.githubusercontent.com/atOCEANO/sample-market-data",
        "binance",
        "linear-perp",
        "parquet_5m",
        5,
        note="PRIMARY. 2020-09 to 2026-07-25, zero gaps, perp matches the traded instrument.",
    ),
    Source(
        "BTC",
        "BTC",
        f"{RAW_DIR}/binance_linear_BTCUSDT_5m.parquet",
        "raw.githubusercontent.com/atOCEANO/sample-market-data",
        "binance",
        "linear-perp",
        "parquet_5m",
        5,
        note="Cross-asset control.",
    ),
    Source(
        "ETH",
        "ETH",
        f"{RAW_DIR}/binance_linear_ETHUSDT_5m.parquet",
        "raw.githubusercontent.com/atOCEANO/sample-market-data",
        "binance",
        "linear-perp",
        "parquet_5m",
        5,
        note="Cross-asset control.",
    ),
    Source(
        "SOL",
        "SOL",
        f"{RAW_DIR}/binance_linear_SOLUSDT_5m.parquet",
        "raw.githubusercontent.com/atOCEANO/sample-market-data",
        "binance",
        "linear-perp",
        "parquet_5m",
        5,
        note="Cross-asset control, from 2020-09-14.",
    ),
    Source(
        "XRP_BITSTAMP",
        "XRP",
        f"{RAW_DIR}/Bitstamp_XRPUSD_1h.csv",
        "raw.githubusercontent.com/kam1lg/ML_predykcja_LSTM",
        "bitstamp",
        "spot",
        "cdd_csv_1h",
        60,
        extends=f"{RAW_DIR}/Bitstamp_XRPUSD_1h_2017.csv",
        note="Independent venue + 2017 extension. Different exchange from the primary XRP series.",
    ),
    Source(
        "BTC_BITSTAMP",
        "BTC",
        f"{RAW_DIR}/Bitstamp_BTCUSD_1h.csv",
        "raw.githubusercontent.com/kam1lg/ML_predykcja_LSTM",
        "bitstamp",
        "spot",
        "cdd_csv_1h",
        60,
        extends=f"{RAW_DIR}/Bitstamp_BTCUSD_1h_2017.csv",
        note="2017-07 onward.",
    ),
    Source(
        "ETH_BITSTAMP",
        "ETH",
        f"{RAW_DIR}/Bitstamp_ETHUSD_1h.csv",
        "raw.githubusercontent.com/kam1lg/ML_predykcja_LSTM",
        "bitstamp",
        "spot",
        "cdd_csv_1h",
        60,
        extends=f"{RAW_DIR}/Bitstamp_ETHUSD_1h_2017.csv",
        note="2017-09 onward.",
    ),
    Source(
        "LTC",
        "LTC",
        f"{RAW_DIR}/Bitstamp_LTCUSD_1h.csv",
        "raw.githubusercontent.com/kam1lg/ML_predykcja_LSTM",
        "bitstamp",
        "spot",
        "cdd_csv_1h",
        60,
        extends=f"{RAW_DIR}/Bitstamp_LTCUSD_1h_2017.csv",
        note="Mid-cap, 2017-07 onward.",
    ),
    Source(
        "LINK",
        "LINK",
        f"{RAW_DIR}/LINKUSDT_4h_binance.csv",
        "raw.githubusercontent.com/SandPearlStone/trading-bot",
        "binance",
        "spot",
        "plain_csv_4h",
        240,
        note="Mid-cap. Short window (2024-03 to 2026-03); low power by construction.",
    ),
)

TIMEFRAMES: tuple[Timeframe, ...] = ("15m", "1h", "4h", "1d")
PRIMARY_KEY = "XRP"
DATA_ENDS = "2026-07-25T21:15:00Z"

# --------------------------------------------------------------------------- pre-registered specs

#: One primary specification per variant, fixed before any outcome was inspected. Chosen to match
#: the structure on the user's chart: a moderately deep head, tolerant shoulder symmetry (their
#: right shoulder is visibly higher than the left), and a neckline allowed to slope.
PRIMARY: dict[str, dict[str, object]] = {
    "inverse_head_shoulders": {
        "direction": "bullish",
        "lookback": 5,
        "head_prominence": 0.03,
        "shoulder_tol": 0.75,
        "time_symmetry_tol": 0.25,
        "max_neckline_slope": 0.20,
        "gap_min": 10,
        "gap_max": 250,
        "shoulder_rule": "any",
        "require_bos": False,
    },
    "head_shoulders": {
        "direction": "bearish",
        "lookback": 5,
        "head_prominence": 0.03,
        "shoulder_tol": 0.75,
        "time_symmetry_tol": 0.25,
        "max_neckline_slope": 0.20,
        "gap_min": 10,
        "gap_max": 250,
        "shoulder_rule": "any",
        "require_bos": False,
    },
    "bullish_quasimodo": {
        "direction": "bullish",
        "lookback": 5,
        "head_prominence": 0.03,
        "shoulder_tol": 0.75,
        "time_symmetry_tol": 0.25,
        "max_neckline_slope": 0.20,
        "gap_min": 10,
        "gap_max": 250,
        "shoulder_rule": "any",
        "require_bos": True,
    },
    "bearish_quasimodo": {
        "direction": "bearish",
        "lookback": 5,
        "head_prominence": 0.03,
        "shoulder_tol": 0.75,
        "time_symmetry_tol": 0.25,
        "max_neckline_slope": 0.20,
        "gap_min": 10,
        "gap_max": 250,
        "shoulder_rule": "any",
        "require_bos": True,
    },
}

#: The base populations actually detected. QM is a flag on these, not a separate run — detecting it
#: separately would give the BOS comparison incomparable denominators.
BASE_VARIANTS: tuple[str, ...] = ("inverse_head_shoulders", "head_shoulders")


@dataclass(frozen=True)
class Sweep:
    """Descriptive sensitivity axes — no significance claims attached."""

    lookback: tuple[int, ...] = (3, 5, 8)
    head_prominence: tuple[float, ...] = (0.02, 0.03, 0.05, 0.08)
    shoulder_tol: tuple[float, ...] = (0.4, 0.75, 1.2)
    time_symmetry_tol: tuple[float, ...] = (0.0, 0.25, 0.5)
    max_neckline_slope: tuple[float, ...] = (0.10, 0.20, 0.40)
    shoulder_rule: tuple[str, ...] = ("any", "higher", "lower")


SWEEP = Sweep()

# --------------------------------------------------------------------------- outcomes

FORWARD_HORIZONS_DAYS: tuple[int, ...] = (5, 10, 20, 30, 60)

#: (stop_fraction, target_R, horizon_days). Chosen so the study has power: short horizons keep
#: forward windows from overlapping, and modest R multiples keep breakeven far from the extremes.
BARRIER_GRID: tuple[tuple[float, float, int], ...] = (
    (0.03, 1.0, 10),
    (0.03, 2.0, 10),
    (0.03, 2.0, 20),
    (0.03, 3.0, 20),
    (0.05, 1.0, 10),
    (0.05, 2.0, 20),
    (0.05, 3.0, 30),
    (0.08, 2.0, 30),
    (0.08, 3.0, 30),
)

#: Entry conventions evaluated per event. "tap_close" analogues are deliberately absent — every one
#: of these is reachable at or after the event's confirmation bar.
ENTRIES: tuple[str, ...] = ("confirm", "neckline_break", "neckline_retest", "qm_line")

#: Stop conventions supplied by the pattern's own geometry.
STOPS: tuple[str, ...] = ("head", "right_shoulder")

VOLUME_CONFIRM_MULTIPLE = 1.5  # the "73% vs 54%" claim under test

# --------------------------------------------------------------------------- protocol

WALK_FORWARD_SPLIT = "2023-01-01"
CONTROL_PER_EVENT = 5
CONTROL_DISTANCE_TOL = 0.25
CONTROL_EXCLUSION_BARS = 60
SEED = 7
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


def cells() -> list[tuple[Source, str]]:
    """Every (source, timeframe) pair the data actually supports.

    The grid has holes by construction — only the 5-minute Parquet sources reach 15m — and this is
    the one place that fact is encoded.
    """
    return [(s, tf) for s in SOURCES for tf in TIMEFRAMES if s.supports(tf)]
