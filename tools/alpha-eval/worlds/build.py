"""Planted-truth synthetic market worlds for the alpha-eval benchmark.

This is the ONLY benchmark file that imports ``alpha_*``: it runs in the platform environment
(``uv run --project <repo> python tools/alpha-eval/worlds/build.py ...``) and writes bars through
the public ``alpha_data`` store/snapshot APIs into an isolated sandbox data directory.

The sandbox receives ONLY market data under neutral tickers. The ground truth (family, planted
parameters, reference statistics) is written to a separate ``--truth-out`` file that the system
under test never sees.

Families (daily business-day bars; open/close split so the close(t)->open(t+1) fill is realistic):
  null          zero-drift Gaussian random walk (no edge of any kind)
  drift         constant drift (a "market"; buy-and-hold beta, no timing edge)
  trend         Markov-switching +/-mu drift regimes (time-series momentum edge)
  regime_half   trend regimes for the first ``frac`` of the sample, null afterwards
  ar1           AR(1) daily returns (phi<0: short-horizon mean reversion edge before costs)
  jumps         null walk plus ``k`` large positive jump days (return concentration)
  beta          ``b`` x a referenced market symbol + idiosyncratic noise (beta, not alpha)
  spike         null walk with one corrupt 10x close print that reverts next day (bad data)
  vol_regime    Markov high-vol trending (+/-mu) / low-vol mean-reverting (AR(1) phi) states
  ar1_regime    AR(1) reversal (phi) during the first ``frac`` of the sample, null afterwards
  dipcrash      mildly reverting noise with upward drift plus ``k`` multi-day crash clusters
Any family accepts ``factor`` (a symbol) + ``loading``: adds loading x that symbol's returns.
Spec options: ``calendar: "all"`` (7-day crypto bars, per symbol or world), ``bar_split:
"independent"`` (overnight/intraday innovations drawn independently; the legacy split makes the
intraday move a fixed multiple of the opening gap), ``artifacts`` (fixture files, artifacts.py).
Raw (bypass the store's write contract, to probe the READ path):
  disordered    rows written in shuffled order
  nonfinite     one NaN close
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling module, any invocation path
from artifacts import build_artifact  # noqa: E402

TRADING_DAYS = 252


def business_days(start: date, n: int, all_days: bool = False) -> list[datetime]:
    out: list[datetime] = []
    day = start
    while len(out) < n:
        if all_days or day.weekday() < 5:
            out.append(datetime(day.year, day.month, day.day, tzinfo=UTC))
        day += timedelta(days=1)
    return out


@dataclass(frozen=True)
class Series:
    log_returns: np.ndarray  # length n, r[0] = 0
    regime: np.ndarray | None = None  # planted state (+1/-1/0) for truth only


def _markov_regimes(rng: np.random.Generator, n: int, switch_p: float) -> np.ndarray:
    state = np.empty(n)
    s = 1.0 if rng.random() < 0.5 else -1.0
    for i in range(n):
        if rng.random() < switch_p:
            s = -s
        state[i] = s
    return state


def generate(
    family: str,
    params: dict[str, float],
    n: int,
    rng: np.random.Generator,
    market: np.ndarray | None = None,
) -> Series:
    sigma = params.get("sigma", 0.012)
    eps = rng.normal(0.0, sigma, n)
    if family in {"null", "spike", "disordered", "nonfinite"}:
        r = eps
        regime = None
    elif family == "drift":
        r = params["mu"] + eps
        regime = None
    elif family == "trend":
        regime = _markov_regimes(rng, n, params.get("switch_p", 1 / 120))
        r = regime * params["mu"] + eps
    elif family == "regime_half":
        regime = _markov_regimes(rng, n, params.get("switch_p", 1 / 120))
        cut = int(n * params.get("frac", 0.5))
        regime[cut:] = 0.0
        r = regime * params["mu"] + eps
    elif family == "ar1":
        r = np.empty(n)
        prev = 0.0
        for i in range(n):
            prev = params["phi"] * prev + eps[i]
            r[i] = prev
        regime = None
    elif family == "jumps":
        r = eps.copy()
        idx = rng.choice(np.arange(300, n - 1), size=int(params["k"]), replace=False)
        r[idx] += params["size"]
        regime = None
    elif family == "vol_regime":
        state = _markov_regimes(rng, n, params.get("switch_p", 1 / 90))  # +1 high-vol, -1 low
        trend = _markov_regimes(rng, n, params.get("trend_switch_p", 1 / 60))
        hi = params.get("sigma_hi", 0.02) * rng.standard_normal(n) + trend * params["mu"]
        lo_eps = params.get("sigma_lo", 0.007) * rng.standard_normal(n)
        lo = np.empty(n)
        prev = 0.0
        for i in range(n):
            prev = params.get("phi", -0.25) * prev + lo_eps[i]
            lo[i] = prev
        r = np.where(state > 0, hi, lo)
        regime = state
    elif family == "ar1_regime":
        cut = int(n * params.get("frac", 0.3))
        r = np.empty(n)
        prev = 0.0
        for i in range(n):
            phi = params["phi"] if i < cut else 0.0
            prev = phi * prev + eps[i]
            r[i] = prev
        regime = np.where(np.arange(n) < cut, 1.0, 0.0)
    elif family == "dipcrash":
        r = np.empty(n)
        prev = 0.0
        for i in range(n):
            prev = params.get("phi", -0.2) * prev + eps[i]
            r[i] = prev + params.get("mu", 0.0004)
        length = int(params.get("crash_len", 6))
        starts = rng.choice(np.arange(300, n - length - 1), size=int(params["k"]), replace=False)
        regime = np.zeros(n)
        for s in starts:
            r[s : s + length] += params.get("crash", -0.03)
            regime[s : s + length] = -1.0
    elif family == "beta":
        if market is None:
            raise ValueError("beta family needs a market series")
        r = params["b"] * market + rng.normal(0.0, params.get("idio", 0.006), n)
        regime = None
    else:
        raise ValueError(f"unknown world family {family!r}")
    r = np.asarray(r, dtype=float)
    if "loading" in params and market is not None and family != "beta":
        r = r + params["loading"] * market
    r[0] = 0.0
    return Series(log_returns=r, regime=regime)


def to_bars(
    series: Series, days: list[datetime], rng: np.random.Generator, split: str = "legacy"
) -> pl.DataFrame:
    """Split each day's log return into an overnight gap and an intraday move.

    legacy: 30% / 70% of the same draw (the intraday move is then a fixed multiple of the gap).
    independent: gap and intraday get an extra offsetting innovation, so the daily return is
    unchanged but the opening gap no longer determines the intraday direction.
    """
    r = series.log_returns
    gap, intra = 0.3 * r, 0.7 * r
    if split == "independent":
        shock = rng.normal(0.0, 0.5 * float(np.std(r)) or 1e-4, len(r))
        gap, intra = gap + shock, intra - shock
    closes = 100.0 * np.exp(np.cumsum(r))
    prev_close = np.concatenate([[100.0], closes[:-1]])
    opens = prev_close * np.exp(gap)
    closes = opens * np.exp(intra)
    wick = np.abs(rng.normal(0.0, 0.004, (2, len(r))))
    highs = np.maximum(opens, closes) * (1.0 + wick[0])
    lows = np.minimum(opens, closes) * (1.0 - wick[1])
    return pl.DataFrame(
        {
            "ts": days,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": np.full(len(r), 1_000_000.0),
        }
    )


def reference_ts_momentum(
    log_returns: np.ndarray,
    lookback: int = 252,
    skip: int = 21,
    cost_bps: float = 0.0,
    long_only: bool = False,
) -> dict[str, float]:
    """Platform-independent reference: long/short sign(trailing return) held next day.

    Deliberately NOT the platform's implementation — it is an independent oracle for the planted
    world's edge, so a disagreement with the platform is informative rather than circular.
    """
    r = log_returns
    n = len(r)
    csum = np.concatenate([[0.0], np.cumsum(r)])
    pos = np.zeros(n)
    for t in range(lookback, n - 1):
        trailing = csum[t - skip + 1] - csum[t - lookback + 1]
        pos[t + 1] = 1.0 if trailing > 0 else (0.0 if long_only else -1.0)
    turnover = np.abs(np.diff(np.concatenate([[0.0], pos])))
    pnl = pos * r - turnover * cost_bps / 1e4
    live = pnl[lookback + 1 :]
    return _sharpe_stats(live)


def _sharpe_stats(x: np.ndarray) -> dict[str, float]:
    sd = float(np.std(x, ddof=1)) if len(x) > 1 else 0.0
    sr = float(np.mean(x) / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0
    return {"ann_sharpe": sr, "n": float(len(x)), "t_stat": sr * math.sqrt(len(x) / TRADING_DAYS)}


def top_k_share(log_returns: np.ndarray, k: int = 5) -> float:
    """Share of total positive log return contributed by the k largest days."""
    pos = np.sort(log_returns[log_returns > 0])[::-1]
    total = float(np.sum(log_returns))
    return float(np.sum(pos[:k]) / total) if total > 0 else float("inf")


def build(spec: dict[str, Any], out: Path, seed: int) -> dict[str, Any]:
    n = int(spec.get("n", 2520))
    start = date.fromisoformat(spec.get("start", "2017-01-30"))
    split = spec.get("bar_split", "legacy")
    store = ParquetStore(out / "store")
    truth: dict[str, Any] = {"world": spec.get("name", "unnamed"), "seed": seed, "symbols": {}}
    generated: dict[str, Series] = {}
    for index, sym in enumerate(spec["symbols"]):
        rng = np.random.default_rng([seed, index, 7919])
        family = sym["family"]
        params = {k: float(v) for k, v in sym.get("params", {}).items()}
        length = int(sym.get("n", n))
        all_days = sym.get("calendar", spec.get("calendar", "business")) == "all"
        days = business_days(
            date.fromisoformat(sym.get("start", start.isoformat())), length, all_days
        )
        ref = sym.get("market") or sym.get("factor")
        market = generated[ref].log_returns[:length] if ref else None
        series = generate(family, params, length, rng, market)
        generated[sym["symbol"]] = series
        frame = to_bars(series, days[:length], rng, split)
        if family == "spike":
            at = int(params.get("at", length // 2))
            frame = frame.with_columns(
                pl.when(pl.int_range(pl.len()) == at)
                .then(pl.col(c) * 10.0)
                .otherwise(pl.col(c))
                .alias(c)
                for c in ("high", "close")
            )
        if family == "nonfinite":
            at = int(params.get("at", length // 2))
            frame = frame.with_columns(
                pl.when(pl.int_range(pl.len()) == at)
                .then(float("nan"))
                .otherwise(pl.col("close"))
                .alias("close")
            )
        if family == "disordered":
            path = out / "store" / "bars" / f"{sym['symbol']}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.sample(fraction=1.0, shuffle=True, seed=seed).write_parquet(path)
        elif family == "nonfinite":
            path = out / "store" / "bars" / f"{sym['symbol']}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.write_parquet(path)
        else:
            store.write_bars(sym["symbol"], frame)
        realized = np.log(frame["close"].to_numpy() / frame["close"].shift(1).to_numpy())[1:]
        truth["symbols"][sym["symbol"]] = {
            "family": family,
            "params": params,
            "n_bars": length,
            "first": days[0].date().isoformat(),
            "last": days[length - 1].date().isoformat(),
            "buy_hold": _sharpe_stats(series.log_returns[1:]),
            "reference_ts_momentum": reference_ts_momentum(series.log_returns),
            "reference_ts_momentum_15bps": reference_ts_momentum(series.log_returns, cost_bps=15),
            "reference_ts_momentum_long_only": reference_ts_momentum(
                series.log_returns, long_only=True
            ),
            "top5_share": top_k_share(series.log_returns),
            "regime_share_positive": (
                float(np.mean(series.regime > 0)) if series.regime is not None else None
            ),
            "realized_has_nonfinite": bool(not np.all(np.isfinite(realized))),
        }
    for snap in spec.get("snapshots", []):
        create_snapshot(
            store,
            out / "snapshots",
            snap["id"],
            list(snap["symbols"]),
            source="local_file",
            adapter_version="1",
            parser_version="1",
            created_at=datetime.fromisoformat(snap.get("created_at", "2026-09-26T00:00:00+00:00")),
        )
    for art in spec.get("artifacts", []):
        truth.setdefault("artifacts", {})[art["dir"]] = build_artifact(
            art["kind"], out / art["dir"], art.get("params", {}), seed
        )
    universe = spec.get("universe")
    if universe:
        csv_path = out / "inputs" / f"{universe['name']}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["symbol", "effective_from", "effective_to", "delisting_return", "reason"]
            )
            for row in universe["rows"]:
                writer.writerow(
                    [
                        row["symbol"],
                        row.get("effective_from", start.isoformat()),
                        row.get("effective_to", ""),
                        row.get("delisting_return", ""),
                        row.get("reason", ""),
                    ]
                )
        truth["universe_csv"] = str(csv_path.relative_to(out))
    return truth


def reference_power(
    family: str,
    params: dict[str, float],
    n: int,
    paths: int,
    seed: int,
    oos_frac: float = 0.8,
    long_only: bool = False,
) -> dict[str, float]:
    """Monte Carlo population Sharpe and one-sided 5% power of the reference momentum rule.

    Power is P(t_stat > 1.645) on the OOS-length tail, estimated over independent paths.
    """
    srs, hits = [], 0
    for p in range(paths):
        rng = np.random.default_rng([seed, p, 104729])
        series = generate(family, params, n, rng)
        stats = reference_ts_momentum(series.log_returns, long_only=long_only)
        srs.append(stats["ann_sharpe"])
        t_oos = stats["ann_sharpe"] * math.sqrt(stats["n"] * oos_frac / TRADING_DAYS)
        hits += t_oos > 1.645
    return {
        "population_sharpe": float(np.mean(srs)),
        "sharpe_sd": float(np.std(srs, ddof=1)),
        "power_5pct": hits / paths,
        "paths": float(paths),
    }


def analyze(run_dir: Path, market_bars: Path | None) -> dict[str, Any]:
    """Independent stats on a run's OOS equity curve: concentration and (optionally) beta."""
    eq = pl.read_parquet(run_dir / "equity_curve.parquet").sort("ts")
    value_col = [c for c in eq.columns if c != "ts"][0]
    values = eq[value_col].to_numpy().astype(float)
    rets = np.diff(np.log(values))
    rets = rets[np.isfinite(rets)]
    out: dict[str, Any] = {
        "n_days": int(len(rets)),
        "total_log_return": float(np.sum(rets)),
        "top5_share": top_k_share(rets, 5),
        "top10_share": top_k_share(rets, 10),
        "active_day_frac": float(np.mean(np.abs(rets) > 1e-12)) if len(rets) else 0.0,
    }
    orders_path = run_dir / "orders.parquet"
    if orders_path.exists():
        orders = pl.read_parquet(orders_path)
        out["orders"] = int(orders.height)
        out["orders_denied"] = int((orders["status"] == "DENIED").sum())
        out["orders_filled"] = int((orders["filled_quantity"] > 0).sum())
    if market_bars is not None:
        mk = pl.read_parquet(market_bars).sort("ts").select("ts", "close")
        mk = mk.with_columns(pl.col("close").log().diff().alias("m")).drop_nulls()
        joined = (
            eq.with_columns(pl.col(value_col).log().diff().alias("s"))
            .drop_nulls()
            .join(mk, on="ts", how="inner")
        )
        s_ret, m_ret = joined["s"].to_numpy(), joined["m"].to_numpy()
        active = np.abs(s_ret) > 1e-12
        if active.sum() > 30:
            beta, alpha = np.polyfit(m_ret[active], s_ret[active], 1)
            resid = s_ret[active] - (alpha + beta * m_ret[active])
            se = float(np.std(resid, ddof=2) / math.sqrt(active.sum()))
            out.update(
                {
                    "beta": float(beta),
                    "alpha_daily": float(alpha),
                    "alpha_t": float(alpha / se) if se > 0 else 0.0,
                    "alpha_ann_sharpe": float(
                        alpha / np.std(resid, ddof=2) * math.sqrt(TRADING_DAYS)
                    ),
                }
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--spec", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--truth-out", type=Path, required=True)
    b.add_argument("--seed", type=int, required=True)
    p = sub.add_parser("power")
    p.add_argument("--family", required=True)
    p.add_argument("--params", default="{}")
    p.add_argument("--n", type=int, default=2520)
    p.add_argument("--paths", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--long-only", action="store_true")
    a = sub.add_parser("analyze")
    a.add_argument("--run-dir", type=Path, required=True)
    a.add_argument("--market-bars", type=Path, default=None)
    args = parser.parse_args()
    if args.cmd == "analyze":
        print(json.dumps(analyze(args.run_dir, args.market_bars)))
        return
    if args.cmd == "build":
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        args.out.mkdir(parents=True, exist_ok=True)
        truth = build(spec, args.out, args.seed)
        args.truth_out.parent.mkdir(parents=True, exist_ok=True)
        args.truth_out.write_text(json.dumps(truth, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"built": sorted(truth["symbols"]), "out": str(args.out)}))
    else:
        params = {k: float(v) for k, v in json.loads(args.params).items()}
        print(
            json.dumps(
                reference_power(
                    args.family, params, args.n, args.paths, args.seed, long_only=args.long_only
                )
            )
        )


if __name__ == "__main__":
    main()
