"""Session-valid synthetic MTM fixture, separate from immutable legacy bundle generation.

Marks are explicitly synthetic linear price paths, not observed executable quotes. Fixed
initial-equity notionals permit overlapping exposures; no leverage/financing claim is made.
Daily account returns use actual prior equity, and monthly returns compound daily returns.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import numpy as np
from artifacts import SECTORS, _months, _sharpe, _write_csv


def build_results_bundle(out: Path, params: dict[str, Any], seed: int) -> dict[str, Any]:
    """Build disclosed synthetic accounting and descriptive return summaries.

    Ratio convention: Sharpe (1994), The Sharpe Ratio, Time Dependence,
    https://www-leland.stanford.edu/~wfsharpe/art/sr/sr.htm . The sqrt(12)
    rescaling is only a heuristic here; serial dependence is not corrected.
    """
    weight = float(params.get("weight", 0.6))
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError("weight must be finite and positive")
    out.mkdir(parents=True, exist_ok=True)
    originals = _trade_recipe(params, seed)
    start = min(date.fromisoformat(t["entry_date"]) for t in originals).replace(day=1)
    end = max(date.fromisoformat(t["entry_date"]) for t in originals) + timedelta(days=20)
    calendar = xcals.get_calendar(
        "XNYS",
        start=(start - timedelta(days=7)).isoformat(),
        end=(end + timedelta(days=7)).isoformat(),
    )
    sessions = [
        s.date().isoformat() for s in calendar.sessions_in_range(start.isoformat(), end.isoformat())
    ]
    trades: list[dict[str, Any]] = []
    for row in originals:
        entry = next(i for i, s in enumerate(sessions) if s >= row["entry_date"])
        hold = int(row["holding_days"])
        trades.append(
            {
                **row,
                "entry_date": sessions[entry],
                "exit_date": sessions[entry + hold],
                "holding_sessions": hold,
                "notional_initial_equity": weight,
                "pnl_bps_gross": float(row["pnl_bps_net"]) + 3.0,
            }
        )
    sessions = sessions[: max(sessions.index(t["exit_date"]) for t in trades) + 1]
    header = [
        "trade_id",
        "entry_date",
        "exit_date",
        "symbol",
        "sector",
        "side",
        "holding_sessions",
        "notional_initial_equity",
        "pnl_bps_gross",
        "pnl_bps_net",
        "mkt_realized_vol_20d_at_entry",
    ]
    _write_csv(out / "trades.csv", header, [[t[k] for k in header] for t in trades])
    daily, monthly = _account(trades, sessions, 1.0)
    _write_csv(
        out / "daily_equity.csv",
        [
            "date",
            "gross_pnl",
            "cost",
            "net_pnl",
            "equity",
            "net_return",
            "gross_exposure_initial_equity",
        ],
        daily,
    )
    _write_csv(out / "monthly_returns.csv", ["month", "net_return"], monthly)
    costs = []
    for slip in (0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0):
        _, m = _account(trades, sessions, slip)
        returns = np.array([r[1] for r in m], dtype=float)
        costs.append([slip, _sharpe(returns), float(np.mean(returns) * 12)])
    _write_csv(
        out / "cost_sensitivity.csv",
        ["slippage_bps_per_side", "sharpe", "annual_arithmetic_return"],
        costs,
    )
    # Stress paths are observable scenario assumptions, not claimed independent backtests.
    stress = []
    for scale in (0.25, 0.5, 0.75, 1.0):
        altered = [{**t, "pnl_bps_gross": float(t["pnl_bps_gross"]) * scale} for t in trades]
        _, m = _account(altered, sessions, 1.0)
        stress.append([scale, _sharpe(np.array([r[1] for r in m], dtype=float))])
    _write_csv(
        out / "scenario_stress.csv", ["gross_pnl_multiplier", "annualized_monthly_ratio"], stress
    )
    returns = np.array([r[1] for r in monthly], dtype=float)
    eq = np.array([1.0] + [r[4] for r in daily], dtype=float)
    drawdown = float(np.max(1 - eq / np.maximum.accumulate(eq)))
    (out / "summary.md").write_text(
        "# Synthetic results bundle V2\n\n"
        "Accounting fixture, not a historical strategy backtest. XNYS sessions. "
        "Ratio annualization is sqrt(12) times monthly mean/sample SD, zero benchmark. "
        "Serial dependence is not adjusted; this is descriptive, not an inferential Sharpe. "
        "Costs are 1 bp slippage plus 0.5 bp fees per side. "
        "Per-trade gross P&L is marked linearly over "
        "holding sessions using synthetic marks; "
        "no observed fills, quotes or financing are supplied. "
        "Notionals are fractions of initial equity, not rebalanced fractions of current equity. "
        "Overlapping exposure can exceed capital and is disclosed daily.\n\n"
        f"Trades: {len(trades)}. Annualized monthly ratio: {_sharpe(returns):.6f}. "
        f"Final equity: {eq[-1]:.12f}. Daily max drawdown: {drawdown:.6f}.\n\n"
        "monthly_returns.csv compounds daily account returns. "
        "trades.csv reconciles to daily_equity.csv. "
        "scenario_stress.csv is an assumed gross-P&L stress, not a fitted parameter grid. "
        "Net profitability and deployability require independently observed execution evidence.\n"
    )
    return {
        "fixture_version": 2,
        "calendar": "XNYS",
        "accounting": "synthetic_daily_mtm",
        "final_equity": float(eq[-1]),
        "annualized_monthly_ratio": _sharpe(returns),
    }


def _account(
    trades: list[dict[str, Any]], sessions: list[str], slip: float
) -> tuple[list[list[Any]], list[list[Any]]]:
    positions = {s: i for i, s in enumerate(sessions)}
    gross = np.zeros(len(sessions))
    costs = np.zeros(len(sessions))
    exposure = np.zeros(len(sessions))
    for t in trades:
        a, b = positions[t["entry_date"]], positions[t["exit_date"]]
        weight = float(t["notional_initial_equity"])
        pnl = weight * float(t["pnl_bps_gross"]) / 10000
        gross[a + 1 : b + 1] += pnl / (b - a)
        costs[a] += weight * (slip + 0.5) / 10000
        costs[b] += weight * (slip + 0.5) / 10000
        exposure[a:b] += weight
    equity = 1.0
    daily = []
    monthly: dict[str, float] = {}
    for i, s in enumerate(sessions):
        net = float(gross[i] - costs[i])
        ret = net / equity
        equity += net
        if equity <= 0 or not math.isfinite(equity):
            raise ValueError("synthetic account equity is non-positive or non-finite")
        monthly[s[:7]] = monthly.get(s[:7], 1.0) * (1 + ret)
        daily.append([s, float(gross[i]), float(costs[i]), net, equity, ret, float(exposure[i])])
    return daily, [[m, v - 1] for m, v in monthly.items()]


def _trade_recipe(p: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    """Versioned planted trade recipe; no legacy aggregation or summary is invoked."""
    n = int(p.get("months", 92))
    if n < 2:
        raise ValueError("months must be at least two")
    rng = np.random.default_rng([seed, 4242])
    months = _months(date(2019, 1, 1), n)
    symbols = [(f"{s[:3].upper()}{i}", s) for s in SECTORS for i in range(1, 7)]
    states = []
    high = False
    for _ in months:
        if rng.random() < (0.25 if high else 0.12):
            high = not high
        states.append(high)
    trades = []
    for mi, month in enumerate(months):
        recent = mi >= n - int(p.get("decay_months", 12))
        for _ in range(int(rng.integers(8, 13))):
            symbol, sector = symbols[int(rng.integers(len(symbols)))]
            side = "long" if rng.random() < 0.5 else "short"
            mean = float(p.get("base_bps", 1.0))
            if states[mi]:
                mean += float(p.get("hivol_boost_bps", 0.0))
            if sector == p.get("focus_sector", "Energy"):
                mean += float(p.get("sector_boost_bps", 0.0))
            if symbol == p.get("focus_symbol", ""):
                mean += float(p.get("symbol_boost_bps", 0.0))
            if recent:
                mean += float(p.get("decay_delta_bps", 0.0))
                if side == "short":
                    mean += float(p.get("recent_short_boost_bps", 0.0))
            vol = rng.uniform(0.27, 0.46) if states[mi] else rng.uniform(0.10, 0.19)
            day = month + timedelta(days=int(rng.integers(0, 27)))
            hold = int(rng.integers(1, 6))
            pnl = float(rng.normal(mean, float(p.get("noise_bps", 55.0))))
            if not math.isfinite(pnl):
                raise ValueError("trade recipe produced non-finite P&L")
            trades.append(
                dict(
                    entry_date=day.isoformat(),
                    symbol=symbol,
                    sector=sector,
                    side=side,
                    holding_days=hold,
                    pnl_bps_net=round(pnl, 2),
                    mkt_realized_vol_20d_at_entry=round(float(vol), 3),
                )
            )
    trades.sort(key=lambda t: (t["entry_date"], t["symbol"]))
    return [{"trade_id": i, **t} for i, t in enumerate(trades, 1)]
