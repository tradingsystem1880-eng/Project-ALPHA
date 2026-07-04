"""Future session timestamps for daily forecasts (weekday vs calendar cadence)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from alpha_core import DataError


def future_session_ts(recent_ts: Sequence[datetime], horizon: int) -> list[datetime]:
    """The next ``horizon`` session timestamps after ``recent_ts[-1]``.

    Cadence rule: if any bar in ``recent_ts`` falls on a Saturday/Sunday the series trades
    calendar days (crypto) -> +1d steps; otherwise Mon-Fri weekdays. No holiday calendar —
    a documented approximation: steps mean "next sessions", and the Kronos temporal
    embedding consumes weekday/day/month features, not exchange calendars.
    """
    if horizon < 1:
        raise DataError(f"horizon must be >= 1, got {horizon}")
    if not recent_ts:
        raise DataError("recent_ts is empty — need at least one trailing bar timestamp")
    for t in recent_ts:
        if t.tzinfo is None:
            raise DataError(f"recent_ts must be tz-aware, got naive {t.isoformat()}")
    if any(b <= a for a, b in zip(recent_ts, recent_ts[1:], strict=False)):
        raise DataError("recent_ts must be sorted strictly ascending")
    calendar = any(t.weekday() >= 5 for t in recent_ts)
    out: list[datetime] = []
    t = recent_ts[-1]
    while len(out) < horizon:
        t = t + timedelta(days=1)
        if calendar or t.weekday() < 5:
            out.append(t)
    return out
