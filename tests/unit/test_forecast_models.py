"""Model registry, future timestamps, and the training-overlap warning."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest

from alpha_core import DataError
from alpha_forecast import (
    KRONOS_TRAINING_CUTOFF,
    MODEL_SPECS,
    future_timestamps,
    resolve_model,
    training_overlap_warning,
)
from tests.fixtures.forecast_fixtures import daily_bars


def test_registry_has_the_three_open_models() -> None:
    assert sorted(MODEL_SPECS) == ["base", "mini", "small"]
    assert resolve_model("base").model_repo == "NeoQuasar/Kronos-base"
    assert resolve_model("base").max_context == 512
    assert resolve_model("small").max_context == 512
    assert resolve_model("mini").max_context == 2048
    assert resolve_model("mini").tokenizer_repo == "NeoQuasar/Kronos-Tokenizer-2k"
    assert resolve_model("small").tokenizer_repo == "NeoQuasar/Kronos-Tokenizer-base"


def test_specs_pin_hf_revisions() -> None:
    """Spec open item 1: every repo pin is a full commit sha (verified 2026-07-11 pull)."""
    hex40 = re.compile(r"^[0-9a-f]{40}$")
    for spec in MODEL_SPECS.values():
        assert spec.revision is not None and hex40.fullmatch(spec.revision), spec.name
        assert spec.tokenizer_revision is not None and hex40.fullmatch(spec.tokenizer_revision), (
            spec.name
        )
        # model and tokenizer live in different repos: their pins can never be one sha
        assert spec.revision != spec.tokenizer_revision, spec.name
    # small and base share Kronos-Tokenizer-base, so they must share its pin
    assert MODEL_SPECS["small"].tokenizer_repo == MODEL_SPECS["base"].tokenizer_repo
    assert MODEL_SPECS["small"].tokenizer_revision == MODEL_SPECS["base"].tokenizer_revision
    # the shas actually verified on disk by the first networked `alpha forecast pull`
    assert MODEL_SPECS["base"].revision == "2b554741eca47781b64468546e77fef3e85130e6"
    assert MODEL_SPECS["base"].tokenizer_revision == "0e0117387f39004a9016484a186a908917e22426"


def test_unknown_model_fails_loud() -> None:
    with pytest.raises(DataError, match="unknown Kronos model"):
        resolve_model("huge")


def test_future_timestamps_daily_steps_weekdays_only() -> None:
    bars = daily_bars(n=10)  # ends on a weekday
    out = future_timestamps(bars, 7)
    assert len(out) == 7
    assert all(ts.weekday() < 5 for ts in out)
    assert out[0] > bars[-1].ts
    assert sorted(out) == out


def test_future_timestamps_uniform_for_intraday_spacing() -> None:
    bars = daily_bars(n=5)
    hourly = [
        b.model_copy(update={"ts": datetime(2026, 1, 5, i, tzinfo=UTC)}) for i, b in enumerate(bars)
    ]
    out = future_timestamps(hourly, 3)
    assert out[0] - hourly[-1].ts == timedelta(hours=1)
    assert out[2] - out[1] == timedelta(hours=1)


def test_future_timestamps_fail_loud() -> None:
    bars = daily_bars(n=5)
    with pytest.raises(DataError, match="horizon"):
        future_timestamps(bars, 0)
    with pytest.raises(DataError, match=">= 2 bars"):
        future_timestamps(bars[:1], 3)
    with pytest.raises(DataError, match="disordered"):
        future_timestamps(list(reversed(bars)), 3)


def test_overlap_warning_pre_cutoff_window() -> None:
    w = training_overlap_warning(datetime(2020, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC))
    assert w is not None and "UPPER BOUND" in w and "2020-01-01" in w


def test_overlap_warning_straddling_window() -> None:
    w = training_overlap_warning(datetime(2025, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))
    assert w is not None


def test_overlap_warning_none_post_cutoff() -> None:
    start = datetime(
        KRONOS_TRAINING_CUTOFF.year,
        KRONOS_TRAINING_CUTOFF.month,
        KRONOS_TRAINING_CUTOFF.day,
        tzinfo=UTC,
    )
    assert training_overlap_warning(start, start + timedelta(days=100)) is None


def test_overlap_warning_disordered_fails_loud() -> None:
    with pytest.raises(DataError, match="disordered"):
        training_overlap_warning(datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))
