"""Live HuggingFace smoke for the Kronos facade (network-marked; ~40MB first-run download).

Asserts the three contracts the offline stubs cannot: real weights load at the pinned ids,
same-seed cpu sampling is bit-reproducible, and the batch-of-copies trick yields distinct
per-sample paths (upstream ``predict`` would have averaged them).
"""

from __future__ import annotations

import pytest

from alpha_forecast.kronos import KronosForecaster
from tests.fixtures.forecast_fixtures import daily_bars

pytestmark = pytest.mark.network


def test_kronos_live_smoke() -> None:
    bars = daily_bars(60)
    f = KronosForecaster(
        model_id="NeoQuasar/Kronos-small",
        model_revision="main",
        tokenizer_id="NeoQuasar/Kronos-Tokenizer-base",
        tokenizer_revision="main",
        device="cpu",
    )
    r1 = f.forecast(bars, horizon=5, sample_count=3, seed=7)
    r2 = f.forecast(bars, horizon=5, sample_count=3, seed=7)

    assert r1 == r2, "same-seed cpu sampling must be bit-reproducible"
    assert len({p.close for p in r1.samples}) > 1, "batch rows must draw independent paths"
    assert r1.horizon == 5 and len(r1.samples) == 3
    assert all(len(p.close) == 5 for p in r1.samples)
