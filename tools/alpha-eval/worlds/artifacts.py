"""Fixture artifacts for realistic scenarios: files the SUT reads, with the planted truth returned
separately (the caller writes it to the hidden truth file).

results_bundle  a completed strategy-results bundle (trades, monthly returns, parameter grid, cost
                sensitivity, summary) with planted issues controlled by ``params``
feature_table   a daily feature table + data dictionary for next-day prediction, where some columns
                were not available at the stated decision time (``leak_set`` A or B)

Every number written is computed from the generated data (no hand-typed headline statistics), so
tables reconcile with each other.
"""

from __future__ import annotations

import csv
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

SECTORS = ["Energy", "Technology", "Health", "Financials", "Industrials", "Consumer"]


def build_artifact(kind: str, out: Path, params: dict[str, Any], seed: int) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    if kind == "results_bundle":
        return _results_bundle(out, params, seed)
    if kind == "feature_table":
        return _feature_table(out, params, seed)
    raise ValueError(f"unknown artifact kind {kind!r}")


def _sharpe(monthly: np.ndarray) -> float:
    sd = float(np.std(monthly, ddof=1))
    return float(np.mean(monthly) / sd * math.sqrt(12)) if sd > 0 else 0.0


def _write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _months(start: date, n: int) -> list[date]:
    out, y, m = [], start.year, start.month
    for _ in range(n):
        out.append(date(y, m, 1))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _results_bundle(out: Path, p: dict[str, Any], seed: int) -> dict[str, Any]:
    rng = np.random.default_rng([seed, 4242])
    months = _months(date(2019, 1, 1), int(p.get("months", 92)))
    n_m = len(months)
    symbols = [(f"{s[:3].upper()}{i}", s) for s in SECTORS for i in range(1, 7)]
    # market volatility state per month (Markov), reported per trade as a number, not a label
    hi = np.zeros(n_m, dtype=bool)
    state = False
    for i in range(n_m):
        if rng.random() < (0.25 if state else 0.12):
            state = not state
        hi[i] = state
    focus_sector = p.get("focus_sector", "Energy")
    focus_symbol = p.get("focus_symbol", "")
    decay_months = int(p.get("decay_months", 12))
    trades: list[list[Any]] = []
    for mi, month in enumerate(months):
        recent = mi >= n_m - decay_months
        for _ in range(int(rng.integers(8, 13))):
            sym, sector = symbols[int(rng.integers(len(symbols)))]
            side = "long" if rng.random() < 0.5 else "short"
            mu = float(p.get("base_bps", 1.0))
            if hi[mi]:
                mu += float(p.get("hivol_boost_bps", 0.0))
            if sector == focus_sector:
                mu += float(p.get("sector_boost_bps", 0.0))
            if sym == focus_symbol:
                mu += float(p.get("symbol_boost_bps", 0.0))
            if recent:
                mu += float(p.get("decay_delta_bps", 0.0))
                if side == "short":
                    mu += float(p.get("recent_short_boost_bps", 0.0))
            vol = (
                rng.uniform(0.27, 0.46) if hi[mi] else rng.uniform(0.10, 0.19)
            )  # annualized, trailing 20d
            day = month + timedelta(days=int(rng.integers(0, 27)))
            while day.weekday() >= 5:
                day += timedelta(days=1)
            hold = int(rng.integers(1, 6))
            pnl = float(rng.normal(mu, float(p.get("noise_bps", 55.0))))
            trades.append(
                [day.isoformat(), (day + timedelta(days=hold)).isoformat(), sym, sector, side,
                 hold, round(pnl, 2), round(vol, 3)]
            )  # fmt: skip
    trades.sort(key=lambda r: (r[0], r[2]))
    for i, row in enumerate(trades, start=1):
        row.insert(0, i)
    header = ["trade_id", "entry_date", "exit_date", "symbol", "sector", "side", "holding_days",
              "pnl_bps_net", "mkt_realized_vol_20d_at_entry"]  # fmt: skip
    _write_csv(out / "trades.csv", header, trades)
    weight = float(p.get("weight", 0.6))  # capital fraction per trade
    pnl = np.array([r[7] for r in trades])
    month_idx = np.array(
        [
            (date.fromisoformat(r[1]).year - 2019) * 12 + date.fromisoformat(r[1]).month - 1
            for r in trades
        ]
    )
    monthly = np.array([pnl[month_idx == i].sum() * weight / 1e4 for i in range(n_m)])
    _write_csv(
        out / "monthly_returns.csv",
        ["month", "net_return"],
        [[m.strftime("%Y-%m"), round(float(r), 5)] for m, r in zip(months, monthly, strict=True)],
    )
    headline = _sharpe(monthly)
    # cost sensitivity: pnl is net of 1.0 bp slippage + 0.5 bp fee per side; re-cost at other slippage
    cost_rows = []
    breakeven = None
    for slip in (0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0):
        adj = pnl - 2 * (slip - 1.0)
        mret = np.array([adj[month_idx == i].sum() * weight / 1e4 for i in range(n_m)])
        sr = _sharpe(mret)
        cost_rows.append([slip, round(sr, 2), round(float(np.mean(mret) * 12), 4)])
        if breakeven is None and sr <= 0:
            breakeven = slip
    _write_csv(
        out / "cost_sensitivity.csv", ["slippage_bps_per_side", "sharpe", "ann_return"], cost_rows
    )
    # parameter grid: the chosen cell reproduces the headline; neighbours are much weaker
    grid_rows = []
    lookbacks, zs = [3, 4, 5, 6, 7], [1.0, 1.5, 2.0, 2.5]
    neighbours = []
    for lb in lookbacks:
        for z in zs:
            if (lb, z) == (5, 2.0):
                sr = headline
            else:
                dist = abs(lb - 5) + abs(z - 2.0) * 2
                sr = headline * float(p.get("neighbour_ratio", 0.4)) / (
                    1 + 0.5 * (dist - 1)
                ) + rng.normal(0, 0.15)
                if dist <= 1.0:
                    neighbours.append(sr)
            grid_rows.append([lb, z, round(sr, 2)])
    _write_csv(out / "param_grid.csv", ["lookback_days", "entry_z", "sharpe_2019_2026"], grid_rows)
    win = float(np.mean(pnl > 0))
    equity = np.cumprod(1 + monthly)
    maxdd = float(np.max(1 - equity / np.maximum.accumulate(equity)))
    (out / "summary.md").write_text(
        "\n".join(
            [
                f"# {p.get('strategy_name', 'Sector-neutral short-term reversal')} — results {months[0]:%Y-%m} to {months[-1]:%Y-%m}",
                "",
                f"Universe: {len(symbols)} US equities across {len(SECTORS)} sectors. Signal: {p.get('signal', 'fade 5-day moves beyond an entry z-score, long and short, hold 1-5 days')}.",
                f"Config: lookback 5 days, entry_z 2.0. Each trade is sized at {weight:.0%} of capital (trades can overlap).",
                "Costs: P&L is net of 1.0 bp slippage + 0.5 bp fees per side.",
                "",
                "| metric | value |",
                "|---|---|",
                f"| Sharpe (monthly, annualised) | {headline:.2f} |",
                f"| annual return | {float(np.mean(monthly) * 12):.1%} |",
                f"| max drawdown (monthly) | {maxdd:.1%} |",
                f"| trades | {len(trades)} |",
                f"| win rate | {win:.0%} |",
                f"| avg net P&L per trade | {float(np.mean(pnl)):.1f} bps |",
                "",
                "Files: trades.csv, monthly_returns.csv, param_grid.csv, cost_sensitivity.csv.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tot = pnl.sum()
    sec_share = {s: float(pnl[np.array([r[4] == s for r in trades])].sum() / tot) for s in SECTORS}
    sym_share = {}
    for sym, _ in symbols:
        sym_share[sym] = float(pnl[np.array([r[3] == sym for r in trades])].sum() / tot)
    vol = np.array([r[8] for r in trades])
    hi_t = vol > 0.25
    recent = month_idx >= n_m - decay_months
    return {
        "headline_sharpe": headline,
        "top_sector": max(sec_share, key=lambda k: sec_share[k]),
        "top_sector_pnl_share": max(sec_share.values()),
        "top_symbol_pnl_share": max(sym_share.values()),
        "hivol_trade_share": float(hi_t.mean()),
        "hivol_pnl_share": float(pnl[hi_t].sum() / tot),
        "last_n_months": decay_months,
        "sharpe_last_n_months": _sharpe(monthly[-decay_months:]),
        "sharpe_before": _sharpe(monthly[:-decay_months]),
        "recent_short_pnl_bps_mean": float(
            pnl[recent & np.array([r[5] == "short" for r in trades])].mean()
        ),
        "recent_long_pnl_bps_mean": float(
            pnl[recent & np.array([r[5] == "long" for r in trades])].mean()
        ),
        "neighbour_sharpe_mean": float(np.mean(neighbours)),
        "breakeven_slippage_bps_per_side": breakeven,
        "cost_table": cost_rows,
    }


def _rsi(close: np.ndarray, n: int = 14) -> np.ndarray:
    d = np.diff(close, prepend=close[0])
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    out = np.full(len(close), np.nan)
    for i in range(n, len(close)):
        u, v = up[i - n + 1 : i + 1].mean(), dn[i - n + 1 : i + 1].mean()
        out[i] = 100.0 if v == 0 else 100 - 100 / (1 + u / v)
    return out


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    ra = np.argsort(np.argsort(a[ok]))
    rb = np.argsort(np.argsort(b[ok]))
    return float(np.corrcoef(ra, rb)[0, 1])


def _feature_table(out: Path, p: dict[str, Any], seed: int) -> dict[str, Any]:
    rng = np.random.default_rng([seed, 5151])
    sym = p.get("symbol", "RIVR")
    leak_set = p.get("leak_set", "A")
    days: list[date] = []
    d = date(2019, 1, 2)
    while d <= date(2026, 9, 25):
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    n = len(days)
    gap = rng.normal(0.0002, 0.006, n)
    intra = rng.normal(0.0001, 0.011, n)
    opens = np.empty(n)
    close = np.empty(n)
    prev = 50.0
    for i in range(n):
        opens[i] = prev * math.exp(gap[i])
        close[i] = opens[i] * math.exp(intra[i])
        prev = close[i]
    ret1 = np.r_[np.nan, close[1:] / close[:-1] - 1]
    fwd1 = np.r_[close[1:] / close[:-1] - 1, np.nan]  # target: close(t) -> close(t+1)
    fwd5 = np.array([close[i + 5] / close[i] - 1 if i + 5 < n else np.nan for i in range(n)])
    ret5 = np.array([close[i] / close[i - 5] - 1 if i >= 5 else np.nan for i in range(n)])
    vol20 = np.array(
        [np.std(ret1[i - 19 : i + 1]) * math.sqrt(252) if i >= 20 else np.nan for i in range(n)]
    )
    rsi = _rsi(close)
    gap_next = np.r_[opens[1:] / close[:-1] - 1, np.nan]

    def future_sum(h: int, lag: int = 1) -> np.ndarray:
        lr = np.log(np.r_[close[1:] / close[:-1], np.nan])
        return np.array(
            [
                np.nansum(lr[i + lag - 1 : i + lag - 1 + h]) if i + h < n else np.nan
                for i in range(n)
            ]
        )

    # leaky constructions (the dictionary states when each column is really available)
    eps = np.full(n, np.nan)
    q_end = [
        i
        for i in range(n)
        if days[i].month in (3, 6, 9, 12) and (i + 1 == n or days[i + 1].month != days[i].month)
    ]
    fut30 = future_sum(30)
    cur = np.nan
    qs = set(q_end)
    for i in range(n):
        if i in qs:
            cur = fut30[i] * 25 + rng.normal(0, 0.5)
        eps[i] = cur
    si = -future_sum(8) * 40 + 4.0 + rng.normal(0, 1.6, n)
    rev = future_sum(5) * 60 + rng.normal(0, 4.5, n)
    close_vs_vwap = intra * 0.4 + rng.normal(0, 0.003, n)  # completed session: safe after close
    sector_rank = np.clip(np.round(5.5 + ret1 * 150 + rng.normal(0, 1.5, n)), 1, 10)
    volume_z = rng.normal(0, 1, n)
    cols: dict[str, tuple[np.ndarray, str, bool]] = {
        "ret_1d": (ret1, "close(t)/close(t-1) - 1.", False),
        "ret_5d": (ret5, "close(t)/close(t-5) - 1.", False),
        "rsi_14": (rsi, "14-day RSI on closes through `date`.", False),
        "vol_20": (
            vol20,
            "20-day realised volatility of daily returns through `date`, annualised.",
            False,
        ),
        "volume_z": (
            volume_z,
            "Session volume z-score vs trailing 60 sessions, through `date`.",
            False,
        ),
        "close_vs_vwap": (
            close_vs_vwap,
            "(close - VWAP)/VWAP for the completed session of `date` (vendor daily VWAP, final at 16:05 ET).",
            False,
        ),
        "sector_rank_eod": (
            sector_rank,
            "Decile rank (1-10) of the stock's `date` return among sector peers, computed from official closes.",
            False,
        ),
        "eps_surprise": (
            eps,
            "Standardised earnings surprise for the fiscal quarter ending on the stamped date; the vendor stamps it on the fiscal quarter-end date and forward-fills. Companies report 25-45 days after quarter end.",
            True,
        ),
        "short_interest_pct": (
            si,
            "Short interest as % of float for settlement date `date`. The exchange publishes short-interest data about 8 business days after each settlement date.",
            True,
        ),
        "analyst_rev_20d": (
            rev,
            "Net analyst EPS-estimate revisions over the 20 days ending `date`, taken from the vendor's current estimates history (history is restated when estimates are corrected or backfilled).",
            True,
        ),
    }
    if leak_set == "A":
        cols["gap_next"] = (
            gap_next,
            "Overnight gap: open(t+1)/close(t) - 1 (added for convenience when building the table).",
            True,
        )
    header = ["date", "open", "close", *cols.keys(), "fwd_ret_1d"]
    rows = []
    for i in range(n):
        vals = [days[i].isoformat(), round(opens[i], 4), round(close[i], 4)]
        for arr, _, _ in cols.values():
            v = arr[i]
            vals.append("" if not np.isfinite(v) else round(float(v), 6))
        vals.append("" if not np.isfinite(fwd1[i]) else round(float(fwd1[i]), 6))
        rows.append(vals)
    _write_csv(out / f"{sym}_features.csv", header, rows)
    ic_rows = [
        [c, round(_spearman(a, fwd1), 3), round(_spearman(a, fwd5), 3)]
        for c, (a, _, _) in cols.items()
    ]
    ic_rows.sort(key=lambda r: -abs(r[1]))
    _write_csv(
        out / "ic_table.csv", ["feature", "spearman_ic_fwd_1d", "spearman_ic_fwd_5d"], ic_rows
    )
    lines = [
        f"# {sym} daily feature table — data dictionary",
        "",
        "One row per trading day, 2019-01-02 to 2026-09-25.",
        "Decision convention: signals are computed after the close of `date`; positions are entered at the next session's open.",
        "Target `fwd_ret_1d` = close(t+1)/close(t) - 1.",
        "`ic_table.csv` has in-sample Spearman ICs from the previous analyst's exploration notebook.",
        "",
        "| column | definition |",
        "|---|---|",
        "| open, close | official session open and close for `date` |",
        *[f"| {c} | {desc} |" for c, (_, desc, _) in cols.items()],
        "| fwd_ret_1d | target, see above |",
    ]
    (out / "FEATURES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "symbol": sym,
        "leak_set": leak_set,
        "leaky_columns": [c for c, (_, _, leak) in cols.items() if leak],
        "safe_columns": [c for c, (_, _, leak) in cols.items() if not leak],
        "target_execution_mismatch": "target is close-to-close but entry is next open: the overnight gap in the target is not capturable",
        "ic_table": ic_rows,
    }
