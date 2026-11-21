"""The stored series behind the interactive tear sheet of one run."""

from __future__ import annotations

from ._base import StrictModel


class SeriesTrade(StrictModel):
    entry_ts: float
    exit_ts: float
    side: str
    entry_price: float
    exit_price: float
    realized_return: float


class SeriesPeriod(StrictModel):
    first_ts: str
    last_ts: str


class SeriesFold(StrictModel):
    index: int
    start_ts: str
    end_ts: str


class SeriesBands(StrictModel):
    tradable: SeriesPeriod | None
    scored: SeriesPeriod | None
    folds: list[SeriesFold]


class SeriesPrice(StrictModel):
    status: str
    ts: list[float]
    close: list[float]


class SeriesPointBounds(StrictModel):
    original: int
    returned: int
    truncated: bool
    sampling: str


class SeriesTradeBounds(StrictModel):
    original: int
    returned: int
    truncated: bool
    cap: int


class SeriesBounds(StrictModel):
    points: SeriesPointBounds
    trades: SeriesTradeBounds


class SeriesProvenance(StrictModel):
    artifact_sha256: dict[str, str]


class RunSeries(StrictModel):
    run_id: str
    ts: list[float]
    equity: list[float]
    drawdown: list[float]
    benchmark: list[float | None] | None
    exposure: list[float | None] | None
    trades: list[SeriesTrade]
    bands: SeriesBands
    price: SeriesPrice | None
    bounds: SeriesBounds
    provenance: SeriesProvenance
