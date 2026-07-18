"""``alpha_cli._forecast`` glue: seed derivation, pretrain overlap, PIT slicing, summaries."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from alpha_cli._forecast import _forecaster_factory, forecast_seed, pretrain_overlap, run_forecast
from alpha_core import DataError
from alpha_forecast import FakeForecaster
from alpha_forecast.kronos import KronosForecaster
from tests.fixtures.forecast_fixtures import daily_bars

_CUTOFF = date(2025, 8, 2)


def test_factory_threads_hub_cache_and_local_only() -> None:
    f = _forecaster_factory(
        model="NeoQuasar/Kronos-base",
        model_revision="rev",
        tokenizer="NeoQuasar/Kronos-Tokenizer-base",
        tokenizer_revision="rev",
        device="cpu",
        hub_cache=Path("/x/models"),
        local_files_only=True,
    )
    assert isinstance(f, KronosForecaster)
    assert f.cache_dir == Path("/x/models")
    assert f.local_files_only is True

    fake = _forecaster_factory(
        model="fake",
        model_revision="rev",
        tokenizer="t",
        tokenizer_revision="rev",
        device="cpu",
        hub_cache=Path("/x/models"),
        local_files_only=True,
    )
    assert isinstance(fake, FakeForecaster)  # the offline double ignores hub knobs


def test_forecast_seed_is_stable_and_derived() -> None:
    assert forecast_seed(7) == forecast_seed(7)
    assert forecast_seed(7) != forecast_seed(8)
    assert forecast_seed(7) != 7  # derived child, not the master itself


def test_pretrain_overlap_ranges() -> None:
    bars = daily_bars(10, start=date(2020, 1, 6))  # all pre-cutoff
    block = pretrain_overlap(bars, _CUTOFF)
    assert block["overlap"] is True
    assert block["cutoff"] == "2025-08-02"
    assert block["overlap_start"] == bars[0].ts.date().isoformat()
    assert block["overlap_end"] == bars[-1].ts.date().isoformat()

    clean = pretrain_overlap(bars, date(2019, 1, 1))
    assert clean["overlap"] is False
    assert clean["overlap_start"] is None and clean["overlap_end"] is None


def test_run_forecast_slices_context_and_summarizes() -> None:
    bars = daily_bars(30)
    out = run_forecast(
        bars,
        forecaster=FakeForecaster(),
        context=8,
        horizon=4,
        sample_count=16,
        temperature=1.0,
        top_p=0.9,
        top_k=0,
        seed=7,
        as_of=None,
        cutoff=_CUTOFF,
    )
    assert out.n_context == 8
    assert out.context_last_ts == bars[-1].ts
    assert out.context_first_ts == bars[-8].ts
    assert out.result.origin_ts == bars[-1].ts
    assert 0.0 <= out.prob_up <= 1.0
    origin_close = bars[-1].close
    assert out.median_end_return == pytest.approx(out.quantiles[0.5][-1] / origin_close - 1.0)
    assert out.p05_end_return == pytest.approx(out.quantiles[0.05][-1] / origin_close - 1.0)
    assert sorted(out.quantiles) == [0.05, 0.25, 0.5, 0.75, 0.95]


def test_run_forecast_respects_as_of() -> None:
    bars = daily_bars(30)
    as_of = bars[19].ts
    full = run_forecast(
        bars,
        forecaster=FakeForecaster(),
        context=8,
        horizon=3,
        sample_count=5,
        temperature=1.0,
        top_p=0.9,
        top_k=0,
        seed=7,
        as_of=as_of,
        cutoff=_CUTOFF,
    )
    sliced = run_forecast(
        bars[:20],
        forecaster=FakeForecaster(),
        context=8,
        horizon=3,
        sample_count=5,
        temperature=1.0,
        top_p=0.9,
        top_k=0,
        seed=7,
        as_of=None,
        cutoff=_CUTOFF,
    )
    assert full.result == sliced.result
    assert full.context_last_ts == as_of


def test_run_forecast_fails_below_context() -> None:
    bars = daily_bars(5)
    with pytest.raises(DataError, match="5"):
        run_forecast(
            bars,
            forecaster=FakeForecaster(),
            context=8,
            horizon=3,
            sample_count=4,
            temperature=1.0,
            top_p=0.9,
            top_k=0,
            seed=7,
            as_of=None,
            cutoff=_CUTOFF,
        )


def test_run_forecast_fails_when_as_of_leaves_nothing() -> None:
    bars = daily_bars(10, start=date(2026, 1, 5))
    with pytest.raises(DataError, match="as-of"):
        run_forecast(
            bars,
            forecaster=FakeForecaster(),
            context=4,
            horizon=2,
            sample_count=3,
            temperature=1.0,
            top_p=0.9,
            top_k=0,
            seed=7,
            as_of=daily_bars(1, start=date(2020, 1, 6))[0].ts,
            cutoff=_CUTOFF,
        )
