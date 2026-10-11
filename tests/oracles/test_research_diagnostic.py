"""Independent analytic oracles for the bounded logistic diagnostic."""

import math

import numpy as np
import pytest
from scipy.special import expit

from alpha_research.weekly_diagnostic import _fit

pytestmark = pytest.mark.oracle


def test_intercept_only_matches_log_odds() -> None:
    beta = _fit(np.ones((4, 1)), np.array([0, 1, 1, 1]))
    # Analytic Bernoulli MLE; tolerance bounds numerical optimizer error, not sampling error.
    assert beta[0] == pytest.approx(math.log(3), abs=1e-6)


def test_penalized_score_is_stationary_and_label_swap_symmetric() -> None:
    x = np.column_stack((np.ones(6), np.array([-3, -2, -1, 1, 2, 3])))
    y = np.array([0, 0, 1, 0, 1, 1])
    beta = _fit(x, y)
    gradient = x.T @ (expit(x @ beta) - y) + np.r_[0, beta[1:]]
    assert np.max(np.abs(gradient)) < 1e-6
    assert _fit(x, 1 - y) == pytest.approx(-beta, abs=1e-6)


def test_features_match_closed_form_exponential_path() -> None:
    from alpha_research.weekly_diagnostic import _features

    q = 1.01
    at = 40
    closes = 100 * np.power(q, np.arange(at + 1))

    def geometric_ema(period: int) -> float:
        a = 2 / (period + 1)
        # Closed-form sum of the geometric EMA weights, including its initial observation.
        r = (1 - a) / q
        return 100 * (1 - a) ** at + a * 100 * q**at * (1 - r**at) / (1 - r)

    expected = [
        q**5 - 1,
        q**at / np.mean(np.power(q, np.arange(at - 20, at))) - 1,
        1.0,
        (geometric_ema(12) - geometric_ema(26)) / (100 * q**at),
    ]
    assert _features(closes, at) == pytest.approx(expected, abs=1e-12)
    flat = _features(np.ones(50) * 100, 40)
    assert flat == pytest.approx([0, 0, 0.5, 0], abs=1e-12)


def test_gain_fraction_uses_exact_trailing_changes_and_ignores_future() -> None:
    from alpha_research.weekly_diagnostic import _features

    prices = np.array([100 + i * 0.07 + (-1) ** i * 0.3 for i in range(60)])
    at = 40
    increments = [prices[i] - prices[i - 1] for i in range(at - 13, at + 1)]
    expected = sum(max(d, 0) for d in increments) / sum(abs(d) for d in increments)
    assert _features(prices, at)[2] == pytest.approx(expected, abs=1e-12)
    original = _features(prices, at)
    prices[at + 1 :] *= 100
    assert _features(prices, at) == pytest.approx(original, abs=1e-12)


def test_report_fit_satisfies_training_score_and_prediction_equation() -> None:
    from alpha_research.weekly_diagnostic import _features, weekly_diagnostic
    from tests.unit.test_research_diagnostic import sample

    bars, days = sample()
    result = weekly_diagnostic(bars, sessions=days)
    closes = np.array([b.close for b in bars])
    ends = [i for i, b in enumerate(bars) if b.ts.weekday() == 4]
    pairs = [(a, b) for a, b in zip(ends, ends[1:], strict=False) if a >= 26 and b + 1 < len(bars)]
    train = pairs[: int(0.6 * len(pairs)) - 1]
    x = np.array([_features(closes, a) for a, b in train])
    y = np.array([int(closes[b] > closes[a]) for a, b in train])
    mean = x.mean(0)
    scale = x.std(0)
    assert result["train_feature_mean"] == pytest.approx(mean, abs=1e-12)
    assert result["train_feature_scale"] == pytest.approx(scale, abs=1e-12)
    assert result["train_last_label_date"] == bars[train[-1][1]].ts.date().isoformat()
    design = np.column_stack((np.ones(len(x)), (x - mean) / scale))
    beta = np.array(result["coefficients"])
    assert np.max(np.abs(design.T @ (expit(design @ beta) - y) + np.r_[0, beta[1:]])) < 1e-6
    for row in result["predictions"]:
        z = np.array(row["features"])
        assert row["probability"] == pytest.approx(
            expit(beta[0] + np.dot((z - mean) / scale, beta[1:])), abs=1e-12
        )
        assert row["momentum_probability"] == float(z[0] > 0)
        assert row["majority_probability"] == pytest.approx(y.mean(), abs=1e-12)
    assert sum(r["partition"] == "validation" for r in result["predictions"]) == int(
        0.8 * len(pairs)
    ) - int(0.6 * len(pairs))


def test_mixed_loss_dominated_gain_fraction_is_not_neutral() -> None:
    from alpha_research.weekly_diagnostic import _features

    prices = 100 + np.cumsum(np.tile([0.2, -0.1, -0.7], 20))
    at = 40
    prices[at] += 0.37
    changes = [prices[i] - prices[i - 1] for i in range(at - 13, at + 1)]
    expected = sum(max(v, 0) for v in changes) / sum(abs(v) for v in changes)
    assert _features(prices, at)[2] == pytest.approx(expected, abs=1e-12)
