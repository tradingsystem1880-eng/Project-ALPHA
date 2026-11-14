"""Fixed holding clocks and trial views for the exploratory RD-Agent judge."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import numpy as np

from alpha_backtest.portfolio_replay import WeightTarget
from alpha_core import DataError

CLOCKS = {"daily": 1, "weekly": 7, "monthly": 28}
SWING_CLOCKS = ("weekly", "monthly")
PHASE = date(2021, 1, 1)
LAST_DECISION = date(2023, 12, 24)
LAST_OPEN = date(2023, 12, 31)


def clock_samples(
    signal: np.ndarray,
    opens: np.ndarray,
    days: list[date],
    open_days: list[date],
    clock: str,
) -> dict[str, Any]:
    """Non-overlapping decide-close/next-open windows, with explicit dated endpoints."""
    h = CLOCKS[clock]
    if any(d > LAST_OPEN for d in [*days, *open_days]):
        raise DataError("clock input reaches reserved window")
    if (
        not days
        or not open_days
        or any(
            (b - a).days != 1
            for dates in (days, open_days)
            for a, b in zip(dates, dates[1:], strict=False)
        )
    ):
        raise DataError("clock inputs require consecutive daily dates")
    if signal.shape != (len(days), opens.shape[1]) or len(opens) != len(open_days):
        raise DataError("clock inputs do not match dated matrices")
    if days[0] != PHASE or days[-1] > LAST_DECISION:
        raise DataError("clock decisions must start at the fixed exploration phase")
    lookup = {day: i for i, day in enumerate(open_days)}
    selected = [
        i
        for i, day in enumerate(days)
        if (day - PHASE).days % h == 0
        and day + timedelta(days=1 + h) <= min(LAST_OPEN, open_days[-1])
    ]
    chosen = [days[i] for i in selected]
    start = [lookup[day + timedelta(days=1)] for day in chosen]
    end = [lookup[day + timedelta(days=1 + h)] for day in chosen]
    used = opens[[*start, *end]]
    if not np.isfinite(used).all() or (used <= 0).any():
        raise DataError("forward windows require finite positive opens")
    return {"days": chosen, "signal": signal[selected], "outcome": opens[end] / opens[start] - 1}


def clock_targets(
    signal: np.ndarray,
    closes: np.ndarray,
    days: list[date],
    symbols: list[str],
    direction: int,
    clock: str,
    *,
    top_fraction: float,
    min_names: int,
) -> tuple[list[WeightTarget], int, int, int]:
    h = CLOCKS[clock]
    targets: list[WeightTarget] = []
    missing, cash_days, rebalances = 0, 0, 0
    base_weights = np.zeros(len(symbols))
    base_closes = closes[0]
    scores = np.zeros(len(symbols))
    for i, (day, row) in enumerate(zip(days, np.asarray(signal, dtype=float), strict=True)):
        if (day - PHASE).days % h == 0:
            available = [j for j, value in enumerate(row) if math.isfinite(value)]
            missing += len(symbols) - len(available)
            k = max(1, round(top_fraction * len(available)))
            ranked = sorted(available, key=lambda j: (-direction * row[j], symbols[j]))
            selected = set(ranked[:k]) if len(available) >= min_names else set()
            cash_days += not selected
            base_weights = np.array([1 / k if j in selected else 0.0 for j in range(len(symbols))])
            base_closes = closes[i]
            scores = np.array(
                [direction * row[j] if j in available else 0.0 for j in range(len(symbols))]
            )
            weights = base_weights
            rebalances += 1
        else:
            weights = base_weights * (closes[i] / base_closes)
            if weights.sum() <= 0:
                raise DataError("drifted holdings have no positive weight")
            weights /= weights.sum()
        origin = datetime.combine(day, time(), UTC)
        for j, name in enumerate(symbols):
            targets.append(
                WeightTarget(
                    symbol=name,
                    origin_ts=origin,
                    available_at=origin + timedelta(hours=23),
                    target_ts=origin + timedelta(days=1),
                    target_weight=float(weights[j]),
                    score=float(scores[j]),
                    fold=0,
                )
            )
    return targets, missing, cash_days, rebalances


def trial_clocks(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Older rows and imported results each contribute exactly one daily trial."""
    if row["status"] == "IMPORTED" or row["schema"] != "AlphaRdagentFactorTrialV3":
        return {"daily": row}
    return {clock: row["clocks"][clock] for clock in CLOCKS}


def trial_family(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    family: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if row["status"] != "REPEAT":
            for clock, trial in trial_clocks(row).items():
                family.setdefault((row["code_sha256"], clock), trial)
    return family


def overall_status(clocks: dict[str, dict[str, Any]]) -> tuple[str, str]:
    passing = [c for c in SWING_CLOCKS if clocks[c]["status"] == "PASS"]
    lead = min(passing or list(CLOCKS), key=lambda c: clocks[c]["q"])
    statuses = [trial["status"] for trial in clocks.values()]
    if passing:
        status = "CANDIDATE"
    elif clocks["daily"]["status"] == "PASS":
        status = "FAST_ONLY"
    elif "REPLAY_FAIL" in statuses or any(t["q"] < 0.10 for t in clocks.values()):
        status = "REPLAY_FAIL"
    elif all(s == "DEGENERATE" for s in statuses):
        status = "DEGENERATE"
    elif all(s == "ERROR" for s in statuses):
        status = "ERROR"
    else:
        status = "SCREEN_FAIL"
    return status, lead


def clock_feedback(row: dict[str, Any]) -> str:
    parts = [f"{row['name']}: {row['status']}."]
    for clock, trial in trial_clocks(row).items():
        screen, replay = trial["screen"], trial["replay"]
        parts.append(
            f"{clock}: {trial['status']}, mean rank IC {screen.get('mean_ic')}, "
            f"q={trial['q']:.6g}, net annual excess "
            f"{replay.get('net', {}).get('annualized_return')}, turnover per day "
            f"{replay.get('mean_turnover')}."
        )
        parts.extend(screen.get("warnings", []))
    reason = {
        "CANDIDATE": "A swing clock passed the screen and replay; confirmation is still required.",
        "FAST_ONLY": (
            "Only the daily clock passed; only a weekly or monthly pass can be a candidate."
        ),
        "REPLAY_FAIL": (
            "A clock passed the screen but no clock retained positive excess after costs; "
            "only a weekly or monthly pass can be a candidate."
        ),
        "SCREEN_FAIL": (
            "No swing clock passed both the screen and replay; "
            "only a weekly or monthly pass can be a candidate."
        ),
        "DEGENERATE": "Every clock has degenerate signal coverage, ties or thin decision days.",
        "ERROR": "Evaluation failed; the recorded clock errors require investigation.",
        "FAILED": "Factor execution failed.",
        "LOOKAHEAD": "The factor failed the look-ahead check.",
        "REPEAT": "This code was already evaluated and supplies no new evidence.",
    }
    parts.append(reason[row["status"]])
    return " ".join(parts)


def validate_clock_row(row: dict[str, Any]) -> None:
    """Reject malformed V3 trial families before they affect inference."""
    if set(row["clocks"]) != set(CLOCKS) or row["lead_clock"] not in CLOCKS:
        raise ValueError("invalid V3 clocks or lead")
    if not 1 <= row["distinct_factors"] <= row["family_size"]:
        raise ValueError("invalid V3 family counts")
    statuses = {"SCREEN_FAIL", "REPLAY_FAIL", "PASS", "DEGENERATE", "ERROR"}
    for trial in row["clocks"].values():
        if not 0 <= trial["p"] <= 1 or not 0 <= trial["q"] <= 1:
            raise ValueError("invalid V3 clock metrics")
        if row["status"] != "REPEAT" and trial["status"] not in statuses:
            raise ValueError("invalid V3 clock status")
        if not isinstance(trial["screen"], dict) or not isinstance(trial["replay"], dict):
            raise ValueError("invalid V3 clock results")
    if any(row[k] != row["clocks"]["daily"][k] for k in ("p", "q", "screen", "replay")):
        raise ValueError("V3 daily mirror differs")
