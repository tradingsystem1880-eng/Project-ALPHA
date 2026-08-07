"""Publication-quality, byte-stable figures for immutable run artifacts.

This subpackage draws; it never computes. Every number it receives was produced upstream
by ``alpha_validation`` or read from an immutable parquet, which is what makes the output
reproducible and keeps the package genuinely core-only.

Importing this module must not import matplotlib -- the renderer pulls it in lazily so
that CLI startup, which sits on the Workstation's hot path, stays fast.
"""

from __future__ import annotations

from alpha_research.figures.theme import (
    CATEGORICAL_SLOTS,
    Theme,
    load_theme,
    theme_document,
)

__all__ = [
    "CATEGORICAL_SLOTS",
    "Theme",
    "load_theme",
    "theme_document",
]
