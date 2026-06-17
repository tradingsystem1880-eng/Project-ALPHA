"""quantstats-lumi renders the tear sheet; confirm it's installed and importable in CI.

The original ``quantstats`` is numpy-2 incompatible (it calls the removed ``np.product``); the
maintained ``quantstats-lumi`` fork imports as ``quantstats_lumi`` and is numpy-2 safe. This test
fails loud the moment that fork regresses or the import name changes, before a render is attempted.
"""

from __future__ import annotations

import pandas as pd
import quantstats_lumi


def test_quantstats_lumi_available_with_html_report() -> None:
    major, minor, *_ = (int(x) for x in quantstats_lumi.__version__.split(".")[:2])
    assert (major, minor) >= (1, 1)
    # the single API the tear sheet renderer depends on
    assert callable(quantstats_lumi.reports.html)


def test_pandas_is_library_edge_compatible() -> None:
    # pandas is allowed only at library edges (CLAUDE.md); the 2.x line satisfies both
    # quantstats-lumi (>=2.0) and nautilus (<3).
    assert int(pd.__version__.split(".")[0]) == 2
