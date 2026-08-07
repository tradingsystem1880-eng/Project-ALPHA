"""The figure contract: plain, frozen, pre-computed data describing what to draw.

Two invariants make the rest of the system tractable.

**The renderer computes nothing.** Every number arriving here was produced upstream by
``alpha_validation`` or read from an immutable parquet. Histograms arrive pre-binned,
quantiles pre-sorted, statistics pre-calculated. This is what makes byte-stable output
achievable and keeps the package honestly core-only.

**Dual y-axes are structurally impossible.** There is no field that could express a
secondary axis. Two measures of different scale become two stacked panels sharing one
x-axis -- which is also the composition the reference figures use.

Timestamps are epoch seconds as floats, matching the wire convention the run projections
already speak, so no timezone can be smuggled in through a ``datetime``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final, Literal

from alpha_core import DataError

#: What a mark *is* in the figure's argument, which fixes its colour and weight.
#: The grammar is deliberately small: a chart that needs a sixth role is a chart that is
#: trying to say two things at once.
Role = Literal[
    "substrate",  # the recessive backdrop: price, other trials, the null distribution
    "subject",  # the series the figure is about
    "feature",  # the *detected* thing -- always carries an in-place value label
    "up",
    "down",
    "neutral",
    "reference",  # zero rules, 45-degree lines, thresholds, baselines
    "categorical",
]
_ROLES: Final = frozenset(
    ("substrate", "subject", "feature", "up", "down", "neutral", "reference", "categorical")
)

Scale = Literal["linear", "log", "symlog"]
XKind = Literal["time", "numeric", "category"]

#: Units a panel may declare. Closed on purpose: "what am I looking at" must never be a
#: free-text guess, and a test asserts every panel in the catalogue uses one of these.
YUnit = Literal[
    "ratio",
    "multiple",
    "percent",
    "price",
    "account_currency",
    "count",
    "days",
    "sharpe",
    "weight",
    "correlation",
    "probability",
    "z_score",
    "index",
    "seconds",
]
_Y_UNITS: Final = frozenset(
    (
        "ratio",
        "multiple",
        "percent",
        "price",
        "account_currency",
        "count",
        "days",
        "sharpe",
        "weight",
        "correlation",
        "probability",
        "z_score",
        "index",
        "seconds",
    )
)


def _text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"{name} must be a non-empty string")


def _finite(name: str, values: tuple[float, ...]) -> None:
    for value in values:
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise DataError(f"{name} must contain only numbers")
        if not math.isfinite(float(value)):
            raise DataError(f"{name} must be finite; got {value!r}")


def _same_length(name: str, **series: tuple[float, ...]) -> None:
    lengths = {key: len(value) for key, value in series.items()}
    if len(set(lengths.values())) > 1:
        raise DataError(f"{name} series must align, got lengths {lengths}")
    if not any(lengths.values()):
        raise DataError(f"{name} requires at least one point")


@dataclass(frozen=True, slots=True, kw_only=True)
class ValueLabel:
    """An in-place annotation carrying its own value, as the reference figures do.

    Text is pre-formatted. The renderer never formats a number, because number
    formatting is a locale- and taste-dependent decision that belongs with the builder
    that knows the unit.
    """

    text: str
    dx_pt: float = 6.0
    dy_pt: float = 0.0
    ha: Literal["left", "center", "right"] = "left"

    def __post_init__(self) -> None:
        _text("ValueLabel.text", self.text)


@dataclass(frozen=True, slots=True, kw_only=True)
class _MarkBase:
    label: str | None = None  # a legend entry; None keeps the mark out of the legend
    role: Role = "subject"
    palette_index: int | None = None  # only meaningful when role == "categorical"
    alpha: float = 1.0
    z: int = 0

    def _validate_base(self) -> None:
        """Shared mark validation.

        Called explicitly by each subclass rather than through ``super()``: a
        ``slots=True`` dataclass is a freshly built class object, so the zero-argument
        ``super()`` closure cell points at the pre-decoration class and raises.
        """
        if self.role not in _ROLES:
            raise DataError(f"unsupported mark role {self.role!r}")
        if self.label is not None:
            _text("Mark.label", self.label)
        if not 0.0 < self.alpha <= 1.0:
            raise DataError(f"Mark.alpha must be in (0, 1], got {self.alpha}")
        if self.role == "categorical" and self.palette_index is None:
            raise DataError("a categorical mark must declare its palette_index")
        if self.role != "categorical" and self.palette_index is not None:
            raise DataError("palette_index is only meaningful for a categorical mark")


@dataclass(frozen=True, slots=True, kw_only=True)
class LineMark(_MarkBase):
    kind: Literal["line"] = "line"
    x: tuple[float, ...]
    y: tuple[float, ...]
    width: float | None = None  # None -> the role's default weight
    step: bool = False
    dashed: bool = False
    fill_to: float | None = None  # area baseline: underwater, signed net exposure
    end_label: ValueLabel | None = None

    def __post_init__(self) -> None:
        self._validate_base()
        _finite("LineMark.x", self.x)
        _finite("LineMark.y", self.y)
        _same_length("LineMark", x=self.x, y=self.y)


@dataclass(frozen=True, slots=True, kw_only=True)
class BandMark(_MarkBase):
    """A filled interval between two curves: forecast cones, confidence envelopes."""

    kind: Literal["band"] = "band"
    x: tuple[float, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]

    def __post_init__(self) -> None:
        self._validate_base()
        for name, values in (("x", self.x), ("lower", self.lower), ("upper", self.upper)):
            _finite(f"BandMark.{name}", values)
        _same_length("BandMark", x=self.x, lower=self.lower, upper=self.upper)
        if any(low > high for low, high in zip(self.lower, self.upper, strict=True)):
            raise DataError("BandMark.lower must never exceed BandMark.upper")


@dataclass(frozen=True, slots=True, kw_only=True)
class CandleMark(_MarkBase):
    kind: Literal["candle"] = "candle"
    x: tuple[float, ...]
    open: tuple[float, ...]
    high: tuple[float, ...]
    low: tuple[float, ...]
    close: tuple[float, ...]

    def __post_init__(self) -> None:
        self._validate_base()
        for name in ("x", "open", "high", "low", "close"):
            _finite(f"CandleMark.{name}", getattr(self, name))
        _same_length(
            "CandleMark",
            x=self.x,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScatterMark(_MarkBase):
    kind: Literal["scatter"] = "scatter"
    x: tuple[float, ...]
    y: tuple[float, ...]
    marker: Literal["^", "v", "o", "x", "s", "|", "D", "."] = "o"
    size: float = 18.0
    hollow: bool = False  # degenerate observations stay visible instead of vanishing

    def __post_init__(self) -> None:
        self._validate_base()
        _finite("ScatterMark.x", self.x)
        _finite("ScatterMark.y", self.y)
        _same_length("ScatterMark", x=self.x, y=self.y)


@dataclass(frozen=True, slots=True, kw_only=True)
class BarMark(_MarkBase):
    kind: Literal["bar"] = "bar"
    x: tuple[float, ...]
    y: tuple[float, ...]
    width: float | None = None
    horizontal: bool = False
    signed_colour: bool = False  # colour by sign, overriding `role`
    hatched: tuple[bool, ...] = ()  # explicit "this cell failed", never a silent blank

    def __post_init__(self) -> None:
        self._validate_base()
        _finite("BarMark.x", self.x)
        _finite("BarMark.y", self.y)
        _same_length("BarMark", x=self.x, y=self.y)
        if self.hatched and len(self.hatched) != len(self.x):
            raise DataError("BarMark.hatched must align with BarMark.x when supplied")


@dataclass(frozen=True, slots=True, kw_only=True)
class HistogramMark(_MarkBase):
    """Pre-binned counts. Binning is a statistical decision and happens upstream."""

    kind: Literal["histogram"] = "histogram"
    edges: tuple[float, ...]
    counts: tuple[float, ...]

    def __post_init__(self) -> None:
        self._validate_base()
        _finite("HistogramMark.edges", self.edges)
        _finite("HistogramMark.counts", self.counts)
        if len(self.edges) != len(self.counts) + 1:
            raise DataError(
                f"HistogramMark needs len(edges) == len(counts) + 1, "
                f"got {len(self.edges)} and {len(self.counts)}"
            )
        if any(b <= a for a, b in zip(self.edges, self.edges[1:], strict=False)):
            raise DataError("HistogramMark.edges must increase strictly")


@dataclass(frozen=True, slots=True, kw_only=True)
class HeatmapMark(_MarkBase):
    kind: Literal["heatmap"] = "heatmap"
    rows: tuple[str, ...]
    columns: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]  # None -> hatched absent, never zero
    colorbar_label: str  # always carries a unit
    diverging_center: float | None = 0.0
    cell_text: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        self._validate_base()
        _text("HeatmapMark.colorbar_label", self.colorbar_label)
        if not self.rows or not self.columns:
            raise DataError("HeatmapMark requires at least one row and one column")
        if len(self.values) != len(self.rows):
            raise DataError("HeatmapMark.values must hold one entry per row")
        for row in self.values:
            if len(row) != len(self.columns):
                raise DataError("HeatmapMark.values rows must align with columns")
            _finite("HeatmapMark.values", tuple(v for v in row if v is not None))
        if self.cell_text and len(self.cell_text) != len(self.rows):
            raise DataError("HeatmapMark.cell_text must align with rows when supplied")


@dataclass(frozen=True, slots=True, kw_only=True)
class ZoneMark(_MarkBase):
    """A shaded span: an out-of-sample window, a drawdown episode, a pre-cutoff region."""

    kind: Literal["zone"] = "zone"
    x0: float
    x1: float
    y0: float | None = None  # None -> full axis height
    y1: float | None = None
    corner_label: ValueLabel | None = None

    def __post_init__(self) -> None:
        self._validate_base()
        _finite("ZoneMark bounds", (self.x0, self.x1))
        if self.x1 <= self.x0:
            raise DataError("ZoneMark.x1 must exceed ZoneMark.x0")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuleMark(_MarkBase):
    """A reference line: the observed statistic, a threshold, zero, a forecast origin."""

    kind: Literal["rule"] = "rule"
    orientation: Literal["vertical", "horizontal"]
    position: float
    dashed: bool = True
    #: A rule spans the whole panel, so it usually wants a lighter weight than its role's
    #: default -- otherwise a threshold shouts louder than the data it qualifies.
    width: float | None = None
    annotate: ValueLabel | None = None

    def __post_init__(self) -> None:
        self._validate_base()
        _finite("RuleMark.position", (self.position,))


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorBarMark(_MarkBase):
    """A forest plot row set: point estimate plus interval, one per category."""

    kind: Literal["errorbar"] = "errorbar"
    categories: tuple[str, ...]
    point: tuple[float, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]

    def __post_init__(self) -> None:
        self._validate_base()
        for name in ("point", "lower", "upper"):
            _finite(f"ErrorBarMark.{name}", getattr(self, name))
        if not self.categories:
            raise DataError("ErrorBarMark requires at least one category")
        if not len(self.categories) == len(self.point) == len(self.lower) == len(self.upper):
            raise DataError("ErrorBarMark series must align with its categories")
        if any(low > high for low, high in zip(self.lower, self.upper, strict=True)):
            raise DataError("ErrorBarMark.lower must never exceed ErrorBarMark.upper")


@dataclass(frozen=True, slots=True, kw_only=True)
class TableMark(_MarkBase):
    """Pre-formatted strings only. A table in a figure is still a figure element."""

    kind: Literal["table"] = "table"
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    align: tuple[Literal["left", "right"], ...] = ()

    def __post_init__(self) -> None:
        self._validate_base()
        if not self.columns:
            raise DataError("TableMark requires at least one column")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise DataError("TableMark rows must align with columns")
        if self.align and len(self.align) != len(self.columns):
            raise DataError("TableMark.align must align with columns when supplied")


Mark = (
    LineMark
    | BandMark
    | CandleMark
    | ScatterMark
    | BarMark
    | HistogramMark
    | HeatmapMark
    | ZoneMark
    | RuleMark
    | ErrorBarMark
    | TableMark
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Panel:
    """One stacked axes sharing the figure's x-axis with its siblings."""

    panel_id: str
    y_label: str  # must carry a unit, e.g. "Equity (x initial)"
    y_unit: YUnit
    marks: tuple[Mark, ...]
    height_ratio: float = 1.0
    y_scale: Scale = "linear"
    y_zero_rule: bool = False
    y_percent: bool = False
    y_limits: tuple[float, float] | None = None
    legend: bool = True
    note: str | None = None  # "turnover unavailable for this run" -- never draw zeros

    def __post_init__(self) -> None:
        _text("Panel.panel_id", self.panel_id)
        _text("Panel.y_label", self.y_label)
        if self.y_unit not in _Y_UNITS:
            raise DataError(f"Panel.y_unit {self.y_unit!r} is outside the declared vocabulary")
        if not self.marks:
            raise DataError(f"Panel {self.panel_id!r} must draw at least one mark")
        if self.height_ratio <= 0:
            raise DataError("Panel.height_ratio must be positive")
        if self.y_limits is not None and self.y_limits[0] >= self.y_limits[1]:
            raise DataError("Panel.y_limits must be increasing")
        if self.note is not None:
            _text("Panel.note", self.note)

    @property
    def legend_entries(self) -> tuple[Mark, ...]:
        """Legend content is derived, never declared twice."""
        return tuple(mark for mark in self.marks if mark.label is not None)


@dataclass(frozen=True, slots=True, kw_only=True)
class FigureSpec:
    """A complete, self-describing figure.

    The four teaching fields are not decoration. A chart that cannot say what question it
    answers, in plain language, with its uncertainty and its caveat, is a chart the reader
    has to guess at -- and guessing is how a backtest gets believed for the wrong reason.
    """

    figure_id: str
    title: str
    subtitle: str
    x_label: str  # must carry a unit: "Date (UTC)", "Trade #", "Sharpe ratio"
    x_kind: XKind
    panels: tuple[Panel, ...]
    question: str
    plain_language_answer: str
    uncertainty: str
    caveat: str
    caption: str = ""
    footnotes: tuple[str, ...] = ()
    source_artifacts: tuple[str, ...] = ()
    x_categories: tuple[str, ...] = ()
    x_limits: tuple[float, float] | None = None
    truncation_note: str | None = None  # a figure must never lie by omission
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("figure_id", "title", "x_label", "question", "plain_language_answer"):
            _text(f"FigureSpec.{name}", getattr(self, name))
        if not self.panels:
            raise DataError("FigureSpec requires at least one panel")
        seen = [panel.panel_id for panel in self.panels]
        if len(set(seen)) != len(seen):
            raise DataError(f"FigureSpec.panels have duplicate ids: {seen}")
        if self.x_kind == "category" and not self.x_categories:
            raise DataError("a category x-axis must declare x_categories")
        if self.x_kind != "category" and self.x_categories:
            raise DataError("x_categories is only meaningful for a category x-axis")
        if self.x_limits is not None and self.x_limits[0] >= self.x_limits[1]:
            raise DataError("FigureSpec.x_limits must be increasing")

    @property
    def panel_count(self) -> int:
        return len(self.panels)
