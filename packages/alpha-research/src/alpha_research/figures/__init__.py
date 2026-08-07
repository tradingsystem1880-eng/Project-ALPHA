"""Publication-quality, byte-stable figures for immutable run artifacts.

This subpackage draws; it never computes. Every number it receives was produced upstream
by ``alpha_validation`` or read from an immutable parquet, which is what makes the output
reproducible and keeps the package genuinely core-only.

Importing this module must not import matplotlib -- the renderer pulls it in lazily so
that CLI startup, which sits on the Workstation's hot path, stays fast.
"""

from __future__ import annotations

from alpha_research.figures.render import (
    FigureFormat,
    FigureSize,
    RenderOptions,
    default_size,
    render_figure,
)
from alpha_research.figures.spec import (
    BandMark,
    BarMark,
    CandleMark,
    ErrorBarMark,
    FigureSpec,
    HeatmapMark,
    HistogramMark,
    LineMark,
    Mark,
    Panel,
    Role,
    RuleMark,
    Scale,
    ScatterMark,
    TableMark,
    ValueLabel,
    XKind,
    YUnit,
    ZoneMark,
)
from alpha_research.figures.theme import (
    CATEGORICAL_SLOTS,
    Theme,
    load_theme,
    theme_document,
)
from alpha_research.figures.version import FIGURES_CACHE_VERSION, RENDERER_VERSION

__all__ = [
    "CATEGORICAL_SLOTS",
    "FIGURES_CACHE_VERSION",
    "RENDERER_VERSION",
    "BandMark",
    "BarMark",
    "CandleMark",
    "ErrorBarMark",
    "FigureFormat",
    "FigureSize",
    "FigureSpec",
    "HeatmapMark",
    "HistogramMark",
    "LineMark",
    "Mark",
    "Panel",
    "RenderOptions",
    "Role",
    "RuleMark",
    "Scale",
    "ScatterMark",
    "TableMark",
    "Theme",
    "ValueLabel",
    "XKind",
    "YUnit",
    "ZoneMark",
    "default_size",
    "load_theme",
    "render_figure",
    "theme_document",
]
