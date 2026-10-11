"""Fixed, non-admitted weekly prediction diagnostic; no selection or promotion authority."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from alpha_core import Bar, DataError

VERSION = "weekly-close-logistic-v1"


def _features(close: np.ndarray, at: int) -> list[float]:
    changes = np.diff(close[at - 14 : at + 1])
    gain, loss = np.maximum(changes, 0).mean(), np.maximum(-changes, 0).mean()
    rsi = float(gain / (gain + loss)) if gain + loss > 0 else 0.5

    def ema(period: int) -> float:
        value = float(close[0])
        for price in close[1 : at + 1]:
            value += 2 / (period + 1) * (float(price) - value)
        return value

    return [
        float(close[at] / close[at - 5] - 1),
        float(close[at] / close[at - 20 : at].mean() - 1),
        rsi,
        (ema(12) - ema(26)) / float(close[at]),
    ]


def _fit(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """L2 logistic loss with unpenalized intercept; fixed penalty 1, no tuning.

    Hastie, Tibshirani, Friedman (2009), Elements of Statistical Learning, §4.4,
    equations 4.20–4.21 (Bernoulli log likelihood and score).
    The fixed L2 penalty is an explicit design choice, with derivative beta.
    Objective is SUM negative log likelihood + 0.5 * sum(beta[1:]**2).
    """

    def objective(beta: np.ndarray) -> tuple[float, np.ndarray]:
        z = x @ beta
        penalty = beta.copy()
        penalty[0] = 0
        loss = float(np.sum(np.logaddexp(0, z) - y * z) + 0.5 * (penalty @ penalty))
        return loss, x.T @ (expit(z) - y) + penalty

    fitted = minimize(
        objective,
        np.zeros(x.shape[1]),
        method="BFGS",
        jac=True,
        options={"gtol": 1e-7, "maxiter": 1000},
    )
    if not fitted.success or not np.all(np.isfinite(fitted.x)):
        raise DataError(f"logistic fit did not converge: {fitted.message}")
    return np.asarray(fitted.x, dtype=float)


def weekly_diagnostic(
    bars: Sequence[Bar], *, sessions: Sequence[date], cost_bps_per_side: float = 2.0
) -> dict[str, Any]:
    """Evaluate next-calendar-week close direction with chronological frozen training.

    Logistic model: Hastie et al. (2009), ESL §4.4. Train-only z scores and fixed L2
    penalty, no hyperparameter search. Brier score: Gneiting & Raftery (2007),
    JASA 102, Example 1 p.363 (doi:10.1198/016214506000001437). Binary loss
    here is mean((p-y)**2), minus half their two-category reward score.
    Accuracy and episode returns
    are descriptive, without significance or independence claims. Features use a
    simple 14-change gain fraction (not Wilder-smoothed RSI), normalized 12/26 EMA
    spread, five-session momentum and deviation from prior 20-session mean.

    Calendar is caller supplied and must include the entire last observed week.
    Drop incomplete weeks; require contiguous observed sessions. Training is first
    60% of eligible weeks, next 20% validation, last 20% test; purge training labels
    ending at the first validation decision. No fitting or selection on either
    evaluation partition. Economics is separate next-open to next-week-next-open
    long/cash episodes, charged both sides on entry notional, even if adjacent
    long episodes could net their orders; not an engine portfolio simulation.
    """
    if not np.isfinite(cost_bps_per_side) or cost_bps_per_side < 0:
        raise DataError("cost must be finite and nonnegative")
    if len(bars) < 2 or not sessions or list(sessions) != sorted(set(sessions)):
        raise DataError("ordered unique bars and calendar sessions required")
    dates = [b.ts.date() for b in bars]
    if dates != sorted(set(dates)) or len({b.symbol for b in bars}) != 1:
        raise DataError("one symbol with ordered unique bars required")
    expected = [d for d in sessions if dates[0] <= d <= dates[-1]]
    if dates != expected:
        raise DataError("missing or non-calendar session bars")
    if sessions[-1].isocalendar()[:2] <= dates[-1].isocalendar()[:2]:
        raise DataError("calendar must extend beyond the final observed week")
    last_by_week = {d.isocalendar()[:2]: d for d in sessions}
    close = np.array([b.close for b in bars])
    week_ends = [i for i, d in enumerate(dates) if last_by_week[d.isocalendar()[:2]] == d]
    rows: list[dict[str, Any]] = []
    for at, nxt in zip(week_ends, week_ends[1:], strict=False):
        if at < 26 or nxt + 1 >= len(bars):
            continue
        rows.append(
            dict(
                decision_date=dates[at].isoformat(),
                label_date=dates[nxt].isoformat(),
                entry_date=dates[at + 1].isoformat(),
                exit_date=dates[nxt + 1].isoformat(),
                target=int(close[nxt] > close[at]),
                features=_features(close, at),
                episode_gross_return=bars[nxt + 1].open / bars[at + 1].open - 1,
            )
        )
    if any(
        not np.all(np.isfinite(r["features"])) or not np.isfinite(r["episode_gross_return"])
        for r in rows
    ):
        raise DataError("derived features and episode returns must be finite")
    if len(rows) < 100:
        raise DataError("need at least 100 complete labelled weeks")
    split = int(len(rows) * 0.6)
    test = int(len(rows) * 0.8)
    train = [r for r in rows[:split] if r["label_date"] < rows[split]["decision_date"]]
    x = np.array([r["features"] for r in train])
    y = np.array([r["target"] for r in train])
    if len(np.unique(y)) != 2:
        raise DataError("training labels must contain both classes")
    mean, scale = x.mean(axis=0), x.std(axis=0)
    if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(scale)):
        raise DataError("training scaler must be finite")
    scale = np.where(scale > 0, scale, 1)
    design = np.column_stack((np.ones(len(x)), (x - mean) / scale))
    if not np.all(np.isfinite(design)):
        raise DataError("scaled features must be finite")
    beta = _fit(design, y)
    majority = float(np.mean(y))
    predictions = []
    for i, r in enumerate(rows[split:], start=split):
        evaluation = np.r_[1.0, (np.array(r["features"]) - mean) / scale]
        logit = float(evaluation @ beta)
        if not np.all(np.isfinite(evaluation)) or not np.isfinite(logit):
            raise DataError("evaluation design and logit must be finite")
        probability = float(expit(logit))
        if not np.isfinite(probability):
            raise DataError("prediction probability must be finite")
        predictions.append(
            {
                **r,
                "probability": probability,
                "majority_probability": majority,
                "momentum_probability": float(r["features"][0] > 0),
                "partition": "validation" if i < test else "test",
            }
        )
    metrics = {}
    for partition in ("validation", "test"):
        subset = [r for r in predictions if r["partition"] == partition]
        target = np.array([r["target"] for r in subset])
        gross = np.array([r["episode_gross_return"] for r in subset])
        scores = {}
        for model, field in [
            ("classifier", "probability"),
            ("majority", "majority_probability"),
            ("momentum", "momentum_probability"),
        ]:
            prob = np.array([r[field] for r in subset])
            long = prob >= 0.5
            net = long * (gross - 2 * (cost_bps_per_side / 10000))
            scores[model] = dict(
                n=len(subset),
                accuracy=float(np.mean(long == target)),
                brier=float(np.mean((prob - target) ** 2)),
                mean_episode_net_return=float(np.mean(net)),
                long_episodes=int(np.sum(long)),
            )
        if any(not np.isfinite(v) for score in scores.values() for v in score.values()):
            raise DataError("diagnostic metrics must be finite")
        metrics[partition] = scores
    return dict(
        version=VERSION,
        status="completed_evidence",
        admitted=False,
        target="next calendar week final close > current week final close",
        train_last_label_date=train[-1]["label_date"],
        train_n=len(train),
        feature_names=[
            "return_5_sessions",
            "prior_sma20_deviation",
            "gain_fraction14",
            "normalized_macd12_26",
        ],
        coefficients=beta.tolist(),
        train_feature_mean=mean.tolist(),
        train_feature_scale=scale.tolist(),
        metrics=metrics,
        predictions=predictions,
        cost_bps_per_side=cost_bps_per_side,
        limitations=[
            "Discovery only; repeated use consumes evaluation data.",
            "No statistical edge claim, dividends, borrow or portfolio simulation.",
            "Costs are assumptions; both sides charged on entry notional for each long episode.",
        ],
    )
