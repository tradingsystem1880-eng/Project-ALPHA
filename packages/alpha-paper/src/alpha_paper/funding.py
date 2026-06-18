"""Estimate the short-financing cost the sandbox does NOT model (spec §13).

A short position incurs a borrow/funding cost on a real venue. The backtest models none, and the
sandbox's matching engine does not either — so paper PnL is *optimistic for shorts*. Rather than
hide that, we estimate the accrual here so it can be logged and reported (Phase 4h), making the gap
visible and quantified before any real-money phase.

Pure functions only (no nautilus): callers pass plain floats.
"""

from __future__ import annotations

from alpha_paper.errors import PaperError


def estimate_short_funding_cost(
    short_notional: float, annual_rate_bps: float, days: float
) -> float:
    """Approximate borrow cost for a short held ``days`` days: notional × rate × days/365.

    ``short_notional`` is the absolute notional of the short (>= 0); a long position has no borrow
    cost here (pass 0). Returns a positive cost in the notional's currency.
    """
    if short_notional < 0.0:
        raise PaperError(f"short_notional must be non-negative, got {short_notional}")
    if annual_rate_bps < 0.0:
        raise PaperError(f"annual_rate_bps must be non-negative, got {annual_rate_bps}")
    if days < 0.0:
        raise PaperError(f"days must be non-negative, got {days}")
    return short_notional * (annual_rate_bps / 10_000.0) * (days / 365.0)
