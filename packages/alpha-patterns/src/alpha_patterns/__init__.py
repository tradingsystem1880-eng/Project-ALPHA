"""Chart-pattern detection: swing structure, triple taps, trendlines, order blocks, FVGs.

Pure geometry over OHLCV bars. This package deliberately contains **no statistics** — it reports
what it found and when that was knowable, and nothing about whether the finding is significant.
Interval estimation, controls and multiplicity live in ``alpha_validation``; composing the two is
the job of a research driver, which keeps both packages core-only under the architecture DAG.

Every detector records ``confirmed_index`` alongside ``index``: a fractal swing is not knowable
until ``lookback`` bars after it prints, and any entry taken at the swing itself is reading the
future. The ``bias_guard`` tests enforce this.
"""

from __future__ import annotations

from importlib.metadata import version

from alpha_patterns.context import (
    Direction,
    FairValueGap,
    OrderBlock,
    TrendState,
    distance_from_low,
    find_fair_value_gaps,
    find_order_blocks,
    trend_state_ma,
    trend_state_vwap,
)
from alpha_patterns.controls import MatchedControls, sample_matched_controls
from alpha_patterns.head_shoulders import (
    VARIANT_NAMES,
    HSConfig,
    HSEvent,
    ShoulderRule,
    detect_head_shoulders,
)
from alpha_patterns.indicators import (
    BOLLINGER_WINDOW,
    RSI_WINDOW,
    CalendarFeatures,
    LeadLag,
    bollinger_bandwidth,
    calendar_features,
    consolidation_length,
    cross_correlation_lags,
    log_returns,
    percentile_rank,
    realized_volatility,
    rolling_correlation,
    rolling_mean,
    rolling_std,
    rsi,
    volume_ratio,
)
from alpha_patterns.series import (
    OHLCV,
    FloatArray,
    IntArray,
    atr,
    rolling_max,
    rolling_min,
    rolling_vwap,
    true_range,
)
from alpha_patterns.structure import (
    StructureBreak,
    break_of_structure,
    extreme_between,
    last_pivot_before,
    swing_sequence,
)
from alpha_patterns.swings import Swing, SwingKind, find_swings, swings_known_by
from alpha_patterns.synthetic import (
    WedgeTruth,
    geometric_brownian_series,
    inject_descending_trendline,
    inject_head_shoulders,
    inject_triple_tap,
    inject_wedge,
)
from alpha_patterns.trendline import (
    ALL_BREAK_RULES,
    BreakRule,
    Scale,
    Trendline,
    TrendlineBreak,
    TrendlineConfig,
    build_trendlines,
    find_breaks,
)
from alpha_patterns.triple_tap import (
    BandReference,
    Population,
    TripleTap,
    TripleTapConfig,
    detect_nth_taps,
    detect_triple_taps,
)
from alpha_patterns.wedge import (
    KIND_CODES,
    Wedge,
    WedgeConfig,
    WedgeKind,
    WedgePanel,
    detect_wedges,
    wedge_lines,
    wedge_panel,
)

__version__ = version("alpha-patterns")

__all__ = [
    "ALL_BREAK_RULES",
    "BOLLINGER_WINDOW",
    "BandReference",
    "BreakRule",
    "CalendarFeatures",
    "Direction",
    "FairValueGap",
    "FloatArray",
    "HSConfig",
    "HSEvent",
    "IntArray",
    "KIND_CODES",
    "LeadLag",
    "MatchedControls",
    "OHLCV",
    "OrderBlock",
    "Population",
    "RSI_WINDOW",
    "Scale",
    "ShoulderRule",
    "StructureBreak",
    "Swing",
    "SwingKind",
    "TrendState",
    "Trendline",
    "TrendlineBreak",
    "TrendlineConfig",
    "TripleTap",
    "TripleTapConfig",
    "VARIANT_NAMES",
    "Wedge",
    "WedgeConfig",
    "WedgeKind",
    "WedgePanel",
    "WedgeTruth",
    "__version__",
    "atr",
    "bollinger_bandwidth",
    "break_of_structure",
    "build_trendlines",
    "calendar_features",
    "consolidation_length",
    "cross_correlation_lags",
    "detect_head_shoulders",
    "detect_nth_taps",
    "detect_triple_taps",
    "detect_wedges",
    "distance_from_low",
    "extreme_between",
    "find_breaks",
    "find_fair_value_gaps",
    "find_order_blocks",
    "find_swings",
    "geometric_brownian_series",
    "inject_descending_trendline",
    "inject_head_shoulders",
    "inject_triple_tap",
    "inject_wedge",
    "last_pivot_before",
    "log_returns",
    "percentile_rank",
    "realized_volatility",
    "rolling_correlation",
    "rolling_max",
    "rolling_mean",
    "rolling_min",
    "rolling_std",
    "rolling_vwap",
    "rsi",
    "sample_matched_controls",
    "swing_sequence",
    "swings_known_by",
    "trend_state_ma",
    "trend_state_vwap",
    "true_range",
    "volume_ratio",
    "wedge_lines",
    "wedge_panel",
]
