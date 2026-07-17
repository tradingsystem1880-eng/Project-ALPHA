"""Stress scenarios over a return stream: vol scaling, tail shocks, degenerate handling."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_validation import scenario_metrics
from alpha_validation.scenario import append_shock, scale_volatility


def test_scale_volatility_preserves_mean_and_scales_std() -> None:
    r = np.array([0.01, -0.02, 0.03, -0.01])
    scaled = scale_volatility(r, 2.0)
    assert float(np.mean(scaled)) == pytest.approx(float(np.mean(r)))
    assert float(np.std(scaled, ddof=1)) == pytest.approx(2.0 * float(np.std(r, ddof=1)))


def test_scenario_panel_shape_and_stress_ordering() -> None:
    rng = np.random.default_rng(0)
    returns = rng.normal(0.001, 0.01, 250)
    res = {s.name: s for s in scenario_metrics(returns)}
    assert set(res) == {"base", "vol +50%", "vol +100%", "-3σ shock", "-5σ shock"}
    # mean-preserving 2x vol scaling doubles annualized vol
    assert res["vol +100%"].annual_vol == pytest.approx(2.0 * res["base"].annual_vol, rel=1e-9)
    # a -5σ crash day worsens tail risk and drawdown vs base
    assert res["-5σ shock"].value_at_risk >= res["base"].value_at_risk
    assert res["-5σ shock"].max_drawdown <= res["base"].max_drawdown


def test_degenerate_series_reports_null_sharpe() -> None:
    flat = np.zeros(50)
    base = scenario_metrics(flat)[0]
    assert base.sharpe is None  # zero-variance → undefined, not a crash
    assert base.annual_vol == pytest.approx(0.0)


def test_append_shock_adds_one_day() -> None:
    r = np.array([0.01, -0.01, 0.02])
    assert append_shock(r, 3.0).size == r.size + 1
