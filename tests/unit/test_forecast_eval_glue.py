"""``alpha_cli._forecast_eval``: rolling-origin grid, stride-independent seeds, cutoff split."""

from __future__ import annotations

from datetime import date

import pytest

from alpha_cli._forecast_eval import ForecastEvalOutput, origin_indices, run_forecast_eval
from alpha_core import Bar, DataError
from alpha_forecast import FakeForecaster
from tests.fixtures.forecast_fixtures import daily_bars


def _run(
    bars: list[Bar], *, stride: int, cutoff: date, context: int = 8, horizon: int = 4
) -> ForecastEvalOutput:
    return run_forecast_eval(
        bars,
        forecaster=FakeForecaster(),
        context=context,
        horizon=horizon,
        stride=stride,
        sample_count=16,
        temperature=1.0,
        top_p=0.9,
        top_k=0,
        seed=7,
        cutoff=cutoff,
        mean_block=3.0,
    )


def test_origin_grid_respects_context_horizon_stride() -> None:
    # n=30, context=8, horizon=4: first origin at index 7, last with 7+k*5 <= 25
    assert origin_indices(30, context=8, horizon=4, stride=5) == [7, 12, 17, 22]
    assert origin_indices(30, context=8, horizon=4, stride=100) == [7]
    with pytest.raises(DataError, match="origin"):
        origin_indices(10, context=8, horizon=4, stride=5)  # 7 + 4 > 9 -> none fit
    with pytest.raises(DataError, match="stride"):
        origin_indices(30, context=8, horizon=4, stride=0)


def test_eval_scores_every_origin_and_splits_by_cutoff() -> None:
    bars = daily_bars(30, start=date(2026, 1, 5))
    cutoff = bars[14].ts.date()  # origins at bar indices <= 14 count as pre-cutoff
    out = _run(bars, stride=5, cutoff=cutoff)
    assert [o.origin_index for o in out.origins] == [7, 12, 17, 22]
    assert out.n_pre == 2 and out.n_post == 2
    assert out.summary.n_origins == 4
    assert out.summary_pre is not None and out.summary_pre.n_origins == 2
    assert out.summary_post is not None and out.summary_post.n_origins == 2


def test_origin_scores_are_stride_independent() -> None:
    bars = daily_bars(30, start=date(2026, 1, 5))
    cutoff = date(2019, 1, 1)
    sparse = _run(bars, stride=5, cutoff=cutoff)
    dense = _run(bars, stride=1, cutoff=cutoff)
    dense_by_index = {o.origin_index: o for o in dense.origins}
    for origin in sparse.origins:
        assert origin.score == dense_by_index[origin.origin_index].score


def test_eval_all_pre_cutoff_has_empty_post_split() -> None:
    bars = daily_bars(30, start=date(2020, 1, 6))
    out = _run(bars, stride=5, cutoff=date(2025, 8, 2))
    assert out.n_post == 0 and out.summary_post is None
    assert out.summary_pre is not None and out.summary_pre.n_origins == out.summary.n_origins
