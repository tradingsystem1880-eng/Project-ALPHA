"""Run charts, analytics, candles and overlays."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ._base import StrictModel
from .paper import PaperCandleMarker


class EquitySeries(StrictModel):
    ts: list[float]
    equity: list[float]
    drawdown: list[float]


class ForecastHistoryBar(StrictModel):
    t: float
    o: float
    h: float
    low: float = Field(alias="l", serialization_alias="l")
    c: float
    v: float


class ForecastSeries(StrictModel):
    history_ts: list[float]
    history: list[float]
    history_bars: list[ForecastHistoryBar]
    history_ohlcv_available: bool
    forecast_ts: list[float]
    forecast: list[float]
    p10: list[float]
    q25: list[float]
    q75: list[float]
    p90: list[float]
    mean: list[float]


class ForecastPath(StrictModel):
    sample: int
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]


class ForecastPaths(StrictModel):
    samples: list[ForecastPath]
    ts: list[float]


class ChartTrade(StrictModel):
    instrument_id: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    entry_ts: float
    exit_ts: float
    realized_pnl: float
    realized_return: float


class ChartTraceEvent(StrictModel):
    sequence_id: int
    event_type: Literal["decision", "order", "fill", "trade", "execution_rejection"]
    ts: float
    parent_sequence_id: int | None
    instrument_id: str
    side: str | None
    quantity: float | None
    filled_quantity: float | None
    price: float | None
    status: str | None
    signal: int | None
    decision_reason: str | None
    entry_ts: float | None
    exit_ts: float | None
    entry_price: float | None
    exit_price: float | None
    realized_pnl: float | None
    realized_return: float | None


class ChartIndicator(StrictModel):
    sequence_id: int
    decision_sequence_id: int | None
    ts: float
    instrument_id: str
    name: str
    value: float
    unit: str


class ChartAnnotationAnchor(StrictModel):
    anchor_index: int
    ts: float
    value: float


class ChartAnnotation(StrictModel):
    annotation_id: int
    decision_sequence_id: int | None
    kind: Literal["line", "polyline", "zone", "marker"]
    label: str
    unit: str
    reason: str
    anchors: list[ChartAnnotationAnchor]


class ChartTruncation(StrictModel):
    bars: bool
    equity: bool
    trades: bool
    trace: bool
    indicators: bool
    annotations: bool


class ChartProvenance(StrictModel):
    command: str | None
    symbol: str | None
    symbols: list[str] | None
    snapshot_id: str | None
    snapshot_hash: str | None
    timezone: Literal["UTC"]
    price_unit: Literal["native_quote"]
    artifact_contract_version: int | None
    as_of: float | None
    artifact_sha256: dict[str, str]


class ChartBar(StrictModel):
    t: float
    o: float
    h: float
    low: float = Field(alias="l", serialization_alias="l")
    c: float
    v: float


class ChartFold(StrictModel):
    fold: int
    semantics: Literal["fixed_rule_evaluation_no_refit", "fold_by_fold_refit"]
    train_start: float | int
    train_end: float | int
    validation_start: float | None = None
    validation_end: float | None = None
    test_start: float | int
    test_end: float | int


class ChartBundle(StrictModel):
    run_id: str
    trace_status: Literal["available", "trace_unavailable"]
    bars_status: Literal["available", "snapshot_unavailable", "not_applicable"]
    provenance: ChartProvenance
    bars: list[ChartBar]
    equity: EquitySeries
    trades: list[ChartTrade]
    trace: list[ChartTraceEvent]
    decisions: list[ChartTraceEvent]
    orders: list[ChartTraceEvent]
    fills: list[ChartTraceEvent]
    indicators: list[ChartIndicator]
    annotations: list[ChartAnnotation]
    folds: list[ChartFold]
    forecast: ForecastSeries | None
    truncated: ChartTruncation


class NativeCalendarReturn(StrictModel):
    year: int
    month: int
    return_value: float


class NativeYearlyReturn(StrictModel):
    year: int
    return_value: float


class NativeHistogramBin(StrictModel):
    left: float
    right: float
    count: int


class NativeQQPoint(StrictModel):
    probability: float
    theoretical: float
    sample: float


class NativeRollingMetric(StrictModel):
    ts: float
    window: int
    return_value: float
    volatility: float
    sharpe: float | None
    gross_exposure: float | None
    net_exposure: float | None
    turnover: float | None
    exposure_available: bool
    turnover_available: bool


class NativeExposureTurnover(StrictModel):
    start_ts: float
    end_ts: float
    gross_exposure: float | None
    net_exposure: float | None
    turnover: float | None
    exposure_available: bool
    turnover_available: bool
    exposure_unavailable_reason: str | None
    turnover_unavailable_reason: str | None


class NativeBenchmarkComparison(StrictModel):
    ts: float
    strategy_equity: float
    benchmark_equity: float | None
    strategy_return: float | None
    benchmark_return: float | None
    excess_return: float | None
    available: bool
    benchmark_kind: str | None
    unavailable_reason: str | None


class NativeTradeStatistic(StrictModel):
    metric: str
    value: float | None
    unit: str
    available: bool
    unavailable_reason: str | None


class NativeSeriesBound(StrictModel):
    original: int
    returned: int
    truncated: bool
    sampling: Literal["all", "endpoint_uniform"]


class NativeTearSheetBounds(StrictModel):
    point_limit: int
    qq: NativeSeriesBound
    rolling: NativeSeriesBound
    exposure_turnover: NativeSeriesBound
    benchmark: NativeSeriesBound


class NativeTearSheetResponse(StrictModel):
    available: bool
    calendar_returns: list[NativeCalendarReturn]
    yearly_returns: list[NativeYearlyReturn]
    histogram: list[NativeHistogramBin]
    qq: list[NativeQQPoint]
    rolling: list[NativeRollingMetric]
    exposure_turnover: list[NativeExposureTurnover]
    benchmark: list[NativeBenchmarkComparison]
    trade_statistics: list[NativeTradeStatistic]
    exposure_available: bool
    turnover_available: bool
    benchmark_available: bool
    trade_statistics_available: bool
    provenance: dict[str, Any]
    bounds: NativeTearSheetBounds


class PortfolioAllocationRow(StrictModel):
    start_ts: float
    ts: float
    symbol: str
    weight: float
    leg_return: float
    contribution: float
    leg_gross_exposure: float
    leg_net_exposure: float
    weighted_gross_exposure: float
    weighted_net_exposure: float


class PortfolioCorrelationRow(StrictModel):
    asset_a: str
    asset_b: str
    metric_name: Literal["pearson_correlation"]
    metric_unit: Literal["coefficient"]
    correlation: float | None
    sample_count: int
    aligned_oos: Literal[True]
    frequency: Literal["1d"]
    oos_start: str | None
    oos_end: str | None
    association_not_causation: Literal[True]


class PortfolioProjectionBound(StrictModel):
    original: int
    returned: int
    truncated: bool
    sampling: Literal["all", "endpoint_uniform", "canonical_prefix"]


class PortfolioAnalyticsBounds(StrictModel):
    timestamp_limit: int
    symbol_limit: int
    allocation_timestamps: PortfolioProjectionBound
    symbols: PortfolioProjectionBound


class PortfolioAnalyticsProvenance(StrictModel):
    source_run_id: str
    source_command: Literal["backtest_portfolio"]
    snapshot_id: str | None
    snapshot_hash: str | None
    research_cutoff: str | None
    as_of: float | None
    timezone: Literal["UTC"]
    frequency: Literal["1d"]
    metric_namespace: Literal["alpha_validation.portfolio"]
    correlation_alignment: Literal["exact_pairwise_oos_timestamp_intersection"]
    allocation_semantics: Literal["causal_sleeve_weight_at_interval_start"]
    association_label: Literal["association, not causation"]
    artifact_contract_version: int | None
    artifact_sha256: dict[str, str]


class PortfolioAnalyticsResponse(StrictModel):
    symbols: list[str]
    allocations: list[PortfolioAllocationRow]
    correlations: list[PortfolioCorrelationRow]
    exposure: list[NativeExposureTurnover]
    provenance: PortfolioAnalyticsProvenance
    bounds: PortfolioAnalyticsBounds


class NullTier(StrictModel):
    tier: str
    statistics: list[float]


class NullTiers(StrictModel):
    tiers: list[NullTier]


class OptimTrial(StrictModel):
    trial: int
    returns: list[float]


class OptimTrials(StrictModel):
    trials: list[OptimTrial]


class PropfirmPathColumns(StrictModel):
    passed: list[bool]
    busted: list[bool]
    days_to_pass: list[float | None]
    payout: list[float]


class PropfirmPaths(StrictModel):
    paths: PropfirmPathColumns


class ForecastOrigins(StrictModel):
    origin_ts: list[float]
    pre_cutoff: list[bool]
    crps: list[float]
    crps_rw: list[float]
    crps_bootstrap: list[float]
    realized_end_return: list[float]
    median_end_return: list[float]
    hit: list[bool]
    cover50: list[bool]
    cover80: list[bool]
    cover90: list[bool]


class Candle(StrictModel):
    t: float
    o: float
    h: float
    low: float = Field(alias="l", serialization_alias="l")
    c: float
    v: float


class ArchiveChartDataset(StrictModel):
    schema_version: Literal[1]
    provider: Literal["binance", "bybit"]
    venue: Literal["binance", "bybit"]
    market_type: Literal["spot", "linear", "inverse"]
    family: Literal["market_bars", "derivative_bars"]
    instrument: str
    base_asset: str
    quote_asset: str
    frequency: Literal[
        "1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"
    ]
    units: Literal["provider_native_ohlcv", "quote_price"]
    timestamp_convention: Literal["interval_start_utc"]
    manifest_id: str
    manifest_ids: list[str]
    manifest_count: int = Field(ge=1)
    start: str | None
    end: str | None
    row_count: int
    verification: Literal["metadata_only"]


class ArchiveChartDatasets(StrictModel):
    datasets: list[ArchiveChartDataset]
    authority: Literal["none"]
    state: Literal["available", "unconfigured"]


class CandleProvenance(StrictModel):
    source: str
    venue: str | None
    timeframe: Literal[
        "1MIN", "5MIN", "15MIN", "30MIN", "1H", "2H", "4H", "6H", "8H", "12H", "1D", "3D", "1W"
    ]
    manifest_id: str | None = None
    market_type: str | None = None
    volume_unit: Literal["base", "quote"] | None = None
    history_kind: Literal["reconstructed_from_verified_archive"] | None = None
    snapshot_id: str | None
    provenance_sha256: str | None
    receipt_id: str | None
    knowledge_cutoff: str | None
    quality_status: Literal["legacy_unqualified", "qualified", "passed", "owner_approved"]


class Candles(StrictModel):
    symbol: str
    snapshot_id: str | None
    provenance: CandleProvenance
    bars: list[Candle]
    paper_markers: list[PaperCandleMarker]


class OverlaySeries(StrictModel):
    id: str
    name: str
    pane: str  # "price" or one sub-pane per oscillator id (rsi, atr, macd, hawkes, ...)
    style: Literal["line", "histogram"]
    values: list[float | None]
    warmup: int


class ChartOverlays(StrictModel):
    symbol: str
    snapshot_id: str | None
    provenance: CandleProvenance
    authority: Literal["none"]
    t: list[float]
    indicators: list[OverlaySeries]
    annotations: list[ChartAnnotation]
