"""Strict response contracts for the workstation's stable JSON API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunListItem(StrictModel):
    run_id: str
    kind: str
    command: str | None
    label: str | None
    symbol: str | None
    symbols: list[str] | None
    passed: bool | None
    verdict: str | None
    mtime: float


class RunList(StrictModel):
    total: int
    items: list[RunListItem]


class RunDetail(StrictModel):
    run_id: str
    kind: str
    mtime: float
    manifest: dict[str, Any]
    has_equity: bool
    has_trades: bool
    has_tearsheet: bool
    has_forecast: bool
    has_nulls: bool
    has_trials: bool
    has_forecast_paths: bool
    has_propfirm_paths: bool
    has_origins: bool


class EquitySeries(StrictModel):
    ts: list[float]
    equity: list[float]
    drawdown: list[float]


class ForecastSeries(StrictModel):
    history_ts: list[float]
    history: list[float]
    forecast_ts: list[float]
    forecast: list[float]
    q05: list[float]
    q25: list[float]
    q75: list[float]
    q95: list[float]
    mean: list[float]


class ForecastPath(StrictModel):
    sample: int
    closes: list[float]


class ForecastPaths(StrictModel):
    samples: list[ForecastPath]
    ts: list[float]


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


class Candles(StrictModel):
    symbol: str
    snapshot_id: str | None
    bars: list[Candle]


class ParamDefinition(StrictModel):
    name: str
    type: str
    default: float
    min: float | None
    max: float | None
    min_exclusive: bool
    max_exclusive: bool
    help: str


class StrategyDefinition(StrictModel):
    name: str
    params: list[ParamDefinition]
    has_tier1_surrogate: bool


class CommandOption(StrictModel):
    name: str
    flag: str | None
    type: str
    default: str | int | float | bool | list[str] | None
    required: bool
    multiple: bool
    help: str
    choices: list[str] | None


class CommandArgument(StrictModel):
    name: str
    type: str
    required: bool
    nargs: int


class CommandDefinition(StrictModel):
    id: str
    run_type: str | None
    args: list[CommandArgument]
    options: list[CommandOption]


class Symbols(StrictModel):
    symbols: list[str]


class JobStatus(StrictModel):
    job_id: str
    status: str


class JobSummary(StrictModel):
    job_id: str
    command: str
    kind: str | None
    status: str
    created_at: float
    run_id: str | None
    returncode: int | None
    n_lines: int


class JobDetail(JobSummary):
    lines: list[str]


class WorkspaceMeta(StrictModel):
    slug: str
    name: str
    updated: float | None


class WorkspaceSaved(StrictModel):
    slug: str
    name: str


class WorkspaceLinkedContext(StrictModel):
    symbol: str | None = None
    start: str | None = None
    end: str | None = None
    runId: str | None = None


class WorkspaceDocument(StrictModel):
    name: str
    linked_context: WorkspaceLinkedContext
    dockview: dict[str, Any]
    updated: float | None = None


class Deleted(StrictModel):
    deleted: str


class RiskScenario(StrictModel):
    name: str
    sharpe: float | None
    annual_vol: float
    max_drawdown: float
    value_at_risk: float
    expected_shortfall: float
    total_return: float


class RiskReport(StrictModel):
    run_id: str
    confidence: float
    scenarios: list[RiskScenario]


class ScreenerQuote(StrictModel):
    symbol: str
    current: float
    change: float
    percent_change: float
    high: float
    low: float
    open: float
    prev_close: float


class ScreenerNewsItem(StrictModel):
    headline: str
    source: str
    url: str
    datetime: int
    summary: str


class ScreenerNews(StrictModel):
    symbol: str
    items: list[ScreenerNewsItem]


class ResearchRow(StrictModel):
    strategy: str
    total_return: float | None
    final_equity: float | None = None
    n_trades: int | None = None
    error: str | None


class ResearchReport(StrictModel):
    symbol: str
    n_bars: int
    ranked: list[ResearchRow]


class OptionGreeks(StrictModel):
    spot: float
    strike: float
    rate: float
    vol: float
    days: float
    kind: str
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    implied_vol: float | None = None
    market_price: float | None = None


class OptionCurvePoint(StrictModel):
    spot: float
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float


class OptionCurve(StrictModel):
    strike: float
    vol: float
    days: float
    rate: float
    kind: str
    points: list[OptionCurvePoint] = Field(min_length=2)
