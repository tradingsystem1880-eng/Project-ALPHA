"""Governed research-study composition seam."""

from __future__ import annotations

from importlib.metadata import version

from alpha_study.values import FeatureInputRefV1, FeatureValueV1

__version__ = version("alpha-study")

__all__ = [
    "FeatureInputRefV1",
    "FeatureValueV1",
    "__version__",
]
