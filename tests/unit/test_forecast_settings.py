"""``AlphaSettings`` forecast knobs: defaults + ``ALPHA_FORECAST_*`` env overrides."""

from __future__ import annotations

from datetime import date

import pytest

from alpha_core.config import AlphaSettings


def test_forecast_settings_defaults() -> None:
    s = AlphaSettings()
    assert s.forecast_model == "NeoQuasar/Kronos-small"
    assert s.forecast_model_revision == "main"
    assert s.forecast_tokenizer == "NeoQuasar/Kronos-Tokenizer-base"
    assert s.forecast_tokenizer_revision == "main"
    assert s.forecast_device == "cpu"
    assert s.forecast_context == 400
    assert s.forecast_pretrain_cutoff == date(2025, 8, 2)


def test_forecast_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_FORECAST_MODEL", "NeoQuasar/Kronos-base")
    monkeypatch.setenv("ALPHA_FORECAST_DEVICE", "mps")
    monkeypatch.setenv("ALPHA_FORECAST_PRETRAIN_CUTOFF", "2025-12-31")
    s = AlphaSettings()
    assert s.forecast_model == "NeoQuasar/Kronos-base"
    assert s.forecast_device == "mps"
    assert s.forecast_pretrain_cutoff == date(2025, 12, 31)
