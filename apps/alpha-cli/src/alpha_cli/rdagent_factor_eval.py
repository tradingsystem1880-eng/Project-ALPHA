"""Exploratory RD-Agent factor screen and ALPHA replay; no admission authority."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import math
import os
import re
import subprocess
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from alpha_backtest.portfolio_replay import WeightTarget, run_weight_replay
from alpha_cli.crypto_bulk_store import configured_crypto_bulk_store
from alpha_core import Bar, DataError
from alpha_research.panel import cross_sectional_ic
from alpha_validation.bootstrap import block_bootstrap_ci
from alpha_validation.dsr import (
    deflated_sharpe,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from alpha_validation.proportion import autocorrelation_effective_size, benjamini_hochberg

RESERVED_START = "2024-01-01"
PANEL_END = "2023-12-31"
EXPLORATION = ("2021-01-01", "2023-12-24")
CUTS = (
    ("2020-12-31",)
    + tuple(
        f"{year}-{day}"
        for year in (2021, 2022, 2023)
        for day in ("03-31", "06-30", "09-30", "12-31")
        if f"{year}-{day}" <= "2023-09-30"
    )
    + ("2023-12-24",)
)
FEE_BPS, SLIPPAGE_BPS = 10.0, 6.0
TOP_FRACTION, ANNUAL_DAYS, MIN_NAMES = 1 / 3, 365, 5
Q_THRESHOLD, BOOTSTRAP_RESAMPLES = 0.10, 2000
LABEL = "exploratory, not admitted, not yet confirmed"
SURVIVORSHIP = (
    "15 coins chosen in 2026-11 from today's survivors; coins that were delisted or collapsed "
    "(for example LUNA, FTT) are absent, which biases results upward"
)
AUTHORITY = dict.fromkeys(("admitted", "evidence", "approval", "promotion"), False)
WINDOWS = {
    "history": ["2017-08-17", "2020-12-31"],
    "exploration": list(EXPLORATION),
    "panel_end": PANEL_END,
    "reserved_start": RESERVED_START,
}
CONFIG = {
    "windows": WINDOWS,
    "cuts": CUTS,
    "fee_bps": FEE_BPS,
    "slippage_bps": SLIPPAGE_BPS,
    "top_fraction": TOP_FRACTION,
    "annual_days": ANNUAL_DAYS,
    "min_names": MIN_NAMES,
    "q_threshold": Q_THRESHOLD,
    "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
}
TRIAL_SCHEMA = "AlphaRdagentFactorTrialV2"
LOOP_UNIVERSE = (
    "ADAUSDT",
    "ATOMUSDT",
    "AVAXUSDT",
    "BCHUSDT",
    "BNBUSDT",
    "BTCUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "ETHUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "SOLUSDT",
    "TRXUSDT",
    "XLMUSDT",
    "XRPUSDT",
)
STATUSES = frozenset(
    {
        "FAILED",
        "LOOKAHEAD",
        "DEGENERATE",
        "ERROR",
        "SCREEN_FAIL",
        "REPLAY_FAIL",
        "CANDIDATE",
        "REPEAT",
        "IMPORTED",
    }
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plain_name(name: str) -> str:
    glossary = {
        "vol": "volatility",
        "ret": "return",
        "vwap": "volume-weighted average price",
        "ic": "information coefficient",
        "xs": "cross-sectional",
        "ma": "moving average",
        "sma": "moving average",
        "std": "standard deviation",
        "atr": "average true range",
        "pct": "percent",
        "zscore": "z-score",
    }
    tokens = name.lower().split("_")
    words = [glossary.get(token, token) for token in tokens]
    if re.fullmatch(r"[0-9]+d", tokens[-1]):
        words[-1] = f"over {tokens[-1][:-1]} days"
    return " ".join(words).capitalize()


def canonical(value: Any) -> bytes:
    # RD-Agent's Series contract explicitly represents unreplayed metrics as NaN.
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def outside_git(path: Path) -> None:
    if not path.is_absolute():
        raise DataError("trial ledger must be absolute and outside every git work tree")
    if not path.parent.is_dir():
        raise DataError("trial ledger parent must exist")
    result = subprocess.run(
        ["git", "-C", str(path.parent.resolve()), "rev-parse", "--is-inside-work-tree"],
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip() == "true":
        raise DataError("trial ledger must be outside every git work tree")
    if result.returncode not in (0, 128):
        raise DataError("cannot determine trial ledger git location")


RESERVED_DAY = date.fromisoformat(RESERVED_START)
PRICE_COLUMNS = ("open", "high", "low", "close")
PANEL_COLUMNS = ("date", "instrument", *PRICE_COLUMNS, "volume", "quote_volume")


def _days(frame: pl.DataFrame, column: str = "date") -> pl.Series:
    """The column as calendar days; a timestamp must be exactly UTC midnight."""
    values = frame[column]
    if values.dtype == pl.Date:
        days = values
    elif isinstance(values.dtype, pl.Datetime):
        stamps = (
            values.dt.replace_time_zone("UTC")
            if values.dtype.time_zone is None
            else values.dt.convert_time_zone("UTC")
        )
        if (stamps != stamps.dt.truncate("1d")).any():
            raise DataError("panel dates must be UTC-midnight days")
        days = stamps.dt.date()
    else:
        raise DataError(f"{column} must be a date or timestamp column")
    if days.null_count():
        raise DataError("panel dates must be UTC-midnight days")
    return days.alias(column)


def validate_panel(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        raise DataError("empty panel")
    frame = frame.with_columns(_days(frame)).sort(["date", "instrument"])
    if (frame["date"] >= RESERVED_DAY).any():
        raise DataError("panel reaches reserved window")
    if frame.select(["date", "instrument"]).is_duplicated().any():
        raise DataError("overlapping instrument-day artifacts")
    gaps = frame.group_by("instrument").agg(
        pl.col("date").diff().drop_nulls().dt.total_days().alias("step")
    )
    for name, steps in gaps.iter_rows():
        if any(step != 1 for step in steps):
            raise DataError(f"disordered or gapped daily bars for {name}")
    prices = frame.select(PRICE_COLUMNS).to_numpy().astype(float)
    volumes = frame.select(["volume", "quote_volume"]).to_numpy().astype(float)
    if (
        not np.isfinite(prices).all()
        or (prices <= 0).any()
        or not np.isfinite(volumes).all()
        or (volumes < 0).any()
    ):
        raise DataError("invalid OHLC or volumes")
    low, high, open_, close = (frame[c].to_numpy() for c in ("low", "high", "open", "close"))
    if (low > np.minimum(open_, close)).any() or (high < np.maximum(open_, close)).any():
        raise DataError("inconsistent OHLC")
    return frame


def freeze(data_dir: Path, out: Path) -> dict[str, Any]:
    store = configured_crypto_bulk_store(data_dir)
    frames: list[pl.DataFrame] = []
    manifests, hashes = [], set()
    selector = {
        "family": "market_bars",
        "venue": "binance",
        "market_type": "spot",
        "frequency": "1d",
        "timestamp_convention": "interval_start_utc",
    }
    for path in sorted((data_dir / "crypto/manifests").glob("*.json")):
        manifest = json.loads(path.read_bytes())
        if manifest.get("artifact_kind") != "normalized" or any(
            manifest.get("dataset", {}).get(k) != v for k, v in selector.items()
        ):
            continue
        verified, payload = store.read_verified_normalized(path.stem, max_bytes=32 * 1024 * 1024)
        quality: Any = verified["quality"]
        dataset: Any = verified["dataset"]
        if quality["state"] != "qualified" or quality["failures"]:
            raise DataError(f"unqualified normalized artifact: {path.stem}")
        digest = str(verified["artifact_sha256"])
        manifests.append({"manifest_id": path.stem, "artifact_sha256": digest})
        if digest in hashes:
            continue
        hashes.add(digest)
        raw = pl.read_parquet(io.BytesIO(payload))
        days = _days(raw, "open_time")
        # Validate order within each artifact before merging chronological captures.
        if not days.is_sorted():
            raise DataError("disordered artifact")
        frame = (
            raw.with_columns(
                days.alias("date"), pl.lit(str(dataset["instrument"])).alias("instrument")
            )
            .rename({"base_volume": "volume"})
            .filter(pl.col("date") < RESERVED_DAY)
            .select(PANEL_COLUMNS)
            .with_columns(pl.col(PANEL_COLUMNS[2:]).cast(pl.Float64))
        )
        frames.append(frame)
    if not frames:
        raise DataError("no qualified Binance spot daily bars")
    panel = validate_panel(pl.concat(frames))
    summary = panel.group_by("instrument").agg(
        pl.len().alias("rows"),
        pl.col("date").min().alias("first"),
        pl.col("date").max().alias("last"),
    )
    instruments = {
        str(name): {"rows": int(rows), "first_day": first.isoformat(), "last_day": last.isoformat()}
        for name, rows, first, last in summary.sort("instrument").iter_rows()
    }
    out.mkdir(parents=True, exist_ok=False)
    buffer = io.BytesIO()
    panel.write_parquet(buffer)
    payload = buffer.getvalue()
    exclusive(out / "panel.parquet", payload)
    receipt = {
        "schema": "AlphaRdagentFactorPanelV1",
        "manifests": manifests,
        "instruments": instruments,
        "rows": panel.height,
        "panel_sha256": sha(payload),
    }
    exclusive(out / "panel-receipt.json", canonical(receipt))
    return receipt


def matrix(frame: pl.DataFrame, value: str, days: list[date], symbols: list[str]) -> np.ndarray:
    """Dense days x symbols float matrix of one column; absent cells are NaN."""
    wide = frame.select(["date", "instrument", value]).pivot(
        on="instrument", index="date", values=value
    )
    grid = pl.DataFrame({"date": days}, schema={"date": pl.Date}).join(wide, on="date", how="left")
    columns = [
        grid[name].cast(pl.Float64).fill_null(float("nan")).to_numpy()
        if name in grid.columns
        else np.full(len(days), np.nan)
        for name in symbols
    ]
    return np.column_stack(columns).astype(float)


def screen(
    signal: np.ndarray,
    outcome: np.ndarray,
    digest: str,
    *,
    series: dict[str, Any] | None = None,
) -> dict[str, Any]:
    values = np.asarray(signal, dtype=float)
    finite = np.isfinite(values)
    coverage = float(finite.mean())
    ties = sum(
        bool(row.size and np.ptp(row) == 0) for row in (r[np.isfinite(r)] for r in values)
    ) / len(values)
    thin_days = int((finite.sum(axis=1) < MIN_NAMES).sum())
    result: dict[str, Any] = {"coverage": coverage, "tie_share": ties, "thin_days": thin_days}
    if coverage < 0.8 or ties > 0.05 or thin_days:
        # thin_days: the canonical replay needs a full weight cross-section every day and
        # cannot hold cash, so a factor with any day under MIN_NAMES names cannot be replayed.
        return {**result, "status": "DEGENERATE", "p": 1.0}
    ic = cross_sectional_ic(values, np.asarray(outcome, dtype=float), min_names=MIN_NAMES)
    if series is not None:
        series.update(daily_ic=ic.values, names=(finite & np.isfinite(outcome)).sum(axis=1))
    daily = np.asarray([v for v in ic.values if v is not None], dtype=float)
    effective = autocorrelation_effective_size(daily)
    mean, sd = float(daily.mean()), float(daily.std(ddof=1))
    z = mean / (sd / math.sqrt(effective))
    interval = block_bootstrap_ci(
        daily,
        lambda x: float(np.mean(x)),
        seed=int(digest[:8], 16),
        n_resamples=BOOTSTRAP_RESAMPLES,
    )
    return {
        **result,
        "status": "OK",
        "mean_ic": mean,
        "n": len(daily),
        "effective_n": effective,
        "z": z,
        "p": math.erfc(abs(z) / math.sqrt(2)),
        "mean_ci_95": asdict(interval),
        "direction": 1 if mean > 0 else -1 if mean < 0 else 0,
        "direction_selection": "chosen in-sample",
    }


def _return_metrics(values: np.ndarray) -> dict[str, float]:
    sd = float(values.std(ddof=1))
    if not np.isfinite(values).all() or sd <= 0:
        raise DataError("degenerate replay excess return series")
    curve = np.concatenate(([1.0], np.cumprod(1 + values)))
    return {
        "annualized_return": float(values.mean()) * ANNUAL_DAYS,
        "compounded_return": float(curve[-1] - 1),
        "sharpe": float(values.mean()) / sd * math.sqrt(ANNUAL_DAYS),
        "per_observation_sharpe": float(values.mean()) / sd,
        "max_drawdown": float(np.min(curve / np.maximum.accumulate(curve) - 1)),
    }


def replay(
    panel: pl.DataFrame,
    signal: np.ndarray,
    days: list[date],
    direction: int,
    *,
    series: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], np.ndarray]:
    sessions = [days[0] + timedelta(days=n) for n in range((days[-1] - days[0]).days + 3)]
    rows = panel.filter(pl.col("date").is_between(sessions[0], sessions[-1]))
    symbols = sorted(panel["instrument"].unique().to_list())
    bars = {}
    for name in symbols:
        group = rows.filter(pl.col("instrument") == name).sort("date")
        if group["date"].to_list() != sessions:
            raise DataError("replay requires a complete daily session rectangle")
        bars[name] = [
            Bar(
                symbol=name,
                ts=datetime.combine(r["date"], time(), UTC),
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=r["volume"],
            )
            for r in group.iter_rows(named=True)
        ]
    targets, missing, cash_days = [], 0, 0
    for day, row in zip(days, np.asarray(signal, dtype=float), strict=True):
        values = dict(zip(symbols, map(float, row), strict=True))
        available = [s for s in symbols if math.isfinite(values[s])]
        missing += len(symbols) - len(available)
        k = max(1, round(TOP_FRACTION * len(available)))
        ranked = sorted(available, key=lambda s: (-direction * values[s], s))
        selected = set(ranked[:k]) if len(available) >= MIN_NAMES else set()
        cash_days += not selected
        origin = datetime.combine(day, time(), UTC)
        for name in symbols:
            targets.append(
                WeightTarget(
                    symbol=name,
                    origin_ts=origin,
                    available_at=origin + timedelta(hours=23),
                    target_ts=origin + timedelta(days=1),
                    target_weight=1 / k if name in selected else 0.0,
                    score=direction * values[name] if name in available else 0.0,
                    fold=0,
                )
            )
    result = run_weight_replay(bars, targets, fee_bps=FEE_BPS, slippage_bps=SLIPPAGE_BPS)
    if series is not None:
        series.update(periods=result.periods, targets=targets)
    net = np.array([p.excess_return for p in result.periods])
    gross = np.array([p.gross_return - p.benchmark_return for p in result.periods])
    return {
        "net": _return_metrics(net),
        "gross": _return_metrics(gross),
        "mean_turnover": float(np.mean([p.turnover for p in result.periods])),
        "missing_coin_days": missing,
        "cash_days": cash_days,
        "tie_break": "instrument name ascending",
        "available_at": (
            "origin session + 23h (ALPHA canonical daily close stamp; bar d contains the full "
            "UTC day)"
        ),
    }, net


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise DataError("incomplete trial ledger line")
    records = []
    for index, line in enumerate(raw.splitlines(), 1):
        try:
            row = json.loads(line)
            if (
                row["schema"] not in {"AlphaRdagentFactorTrialV1", TRIAL_SCHEMA}
                or row["trial_index"] != index
                or not re.fullmatch("[0-9a-f]{64}", row["code_sha256"])
            ):
                raise ValueError("invalid schema or trial identity")
            for key in (
                "name",
                "run_id",
                "iteration",
                "panel_sha256",
                "windows",
                "stage",
                "status",
                "p",
                "q",
                "family_size",
                "screen",
                "replay",
                "label",
                "survivorship",
                "authority",
                "total_trials",
            ):
                if key not in row:
                    raise ValueError(f"missing {key}")
            if not 0 <= row["p"] <= 1 or not 0 <= row["q"] <= 1 or row["authority"] != AUTHORITY:
                raise ValueError("invalid trial metrics or authority")
            if row["status"] not in STATUSES or row["stage"] not in {"none", "screen", "replay"}:
                raise ValueError("invalid trial status or stage")
            if row["schema"] == TRIAL_SCHEMA and (
                not isinstance(row["instruments"], list)
                or not row["instruments"]
                or any(not isinstance(s, str) or not s.strip() for s in row["instruments"])
                or not isinstance(row["exposure"], dict)
                or not {"previously_exposed", "worst_status", "matches"} <= row["exposure"].keys()
            ):
                raise ValueError("invalid V2 instruments or exposure")
            if row["status"] == "IMPORTED":
                _validate_imported(row["imported"])
                if row["schema"] != TRIAL_SCHEMA or row["stage"] != "none" or row["p"] != 1.0:
                    raise ValueError("invalid imported trial")
        except (ValueError, TypeError, KeyError) as error:
            raise DataError(f"invalid trial ledger line {index}: {error}") from error
        records.append(row)
    return records


def _validate_imported(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"evaluated_by", "result_summary", "source", "code_path"}
        or any(not isinstance(v, str) or not v.strip() for v in value.values())
        or not Path(value["code_path"]).is_absolute()
    ):
        raise ValueError("invalid imported provenance")


def _historical_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict) or set(item) != {
        "name",
        "code_path",
        "run_id",
        "iteration",
        "windows",
        "evaluated_by",
        "result_summary",
        "source",
    }:
        raise ValueError("invalid historical item fields")
    provenance = {k: item[k] for k in ("evaluated_by", "result_summary", "source", "code_path")}
    _validate_imported(provenance)
    if (
        any(not isinstance(item[k], str) or not item[k].strip() for k in ("name", "run_id"))
        or type(item["iteration"]) is not int
        or item["iteration"] < 0
        or not isinstance(item["windows"], dict)
        or set(item["windows"]) != set(WINDOWS)
    ):
        raise ValueError("invalid historical trial metadata")
    windows = item["windows"]
    for key in ("history", "exploration"):
        bounds = windows[key]
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError("invalid historical window bounds")
        if any(
            not isinstance(d, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", d)
            for d in bounds
        ):
            raise ValueError("invalid historical window date")
        if date.fromisoformat(bounds[0]) > date.fromisoformat(bounds[1]):
            raise ValueError("reversed historical window")
    for key in ("panel_end", "reserved_start"):
        if not isinstance(windows[key], str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}", windows[key]
        ):
            raise ValueError("invalid historical window date")
        date.fromisoformat(windows[key])
    if windows["reserved_start"] != RESERVED_START:
        # The exposure label is computed from this date; it must be the ledger's protected start.
        raise ValueError(f"historical reserved_start must be {RESERVED_START}")
    return provenance


def import_historical(ledger: Path, source: Path) -> list[dict[str, Any]]:
    from alpha_cli.rdagent_exposure import label_for, read_entries

    outside_git(ledger)
    try:
        items = json.loads(source.read_bytes())
    except (ValueError, UnicodeError) as error:
        raise DataError(f"invalid historical input: {error}") from error
    if not isinstance(items, list):
        raise DataError("historical input must be a list")
    with Path(str(ledger) + ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        history = _read_ledger(ledger)
        identities = {r["code_sha256"] for r in history}
        entries = read_entries(ledger)
        rows: list[dict[str, Any]] = []
        for item in items:
            try:
                provenance = _historical_item(item)
                digest = sha(Path(item["code_path"]).read_bytes())
                if digest in identities:
                    raise ValueError("historical code hash already in trial ledger or batch")
            except (ValueError, TypeError, KeyError, OSError) as error:
                raise DataError(f"invalid historical item {len(rows) + 1}: {error}") from error
            row = {
                "schema": TRIAL_SCHEMA,
                "trial_index": len(history) + len(rows) + 1,
                "name": item["name"],
                "plain_name": plain_name(item["name"]),
                "code_sha256": digest,
                "run_id": item["run_id"],
                "iteration": item["iteration"],
                "windows": item["windows"],
                "status": "IMPORTED",
                "stage": "none",
                "p": 1.0,
                "q": 1.0,
                "screen": {},
                "replay": {},
                "panel_sha256": "0" * 64,
                "instruments": list(LOOP_UNIVERSE),
                "imported": provenance,
                "label": LABEL,
                "survivorship": SURVIVORSHIP,
                "authority": AUTHORITY,
            }
            row["exposure"] = label_for(row, entries)
            rows.append(row)
            identities.add(digest)
        for row in rows:
            row.update(family_size=len(identities), total_trials=len(history) + len(rows))
        with ledger.open("ab", buffering=0) as stream:
            for row in rows:
                line = canonical(row)
                if stream.write(line) != len(line):
                    raise DataError("short trial ledger write")
                os.fsync(stream.fileno())
    return rows


def _inputs(
    run: Path, request_path: Path
) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame, dict[str, str]]:
    request_bytes = request_path.read_bytes()
    request = json.loads(request_bytes)
    if (
        request.get("schema") != "AlphaRdagentFactorRequestV1"
        or type(request.get("iteration")) is not int
        or request["iteration"] < 0
        or not request.get("factors")
    ):
        raise DataError("invalid factor request")
    names = []
    for factor in request["factors"]:
        if factor["status"] not in {"OK", "FAILED", "LOOKAHEAD"} or not re.fullmatch(
            "[0-9a-f]{64}", factor["code_sha256"]
        ):
            raise DataError("invalid factor status or identity")
        names.append(factor["name"])
    if len(set(names)) != len(names) or any(not isinstance(n, str) or not n for n in names):
        raise DataError("factor names must be distinct non-empty strings")
    panel_bytes = (run / "panel/panel.parquet").read_bytes()
    receipt = json.loads((run / "panel/panel-receipt.json").read_bytes())
    if sha(panel_bytes) != receipt["panel_sha256"]:
        raise DataError("panel sha256 differs from receipt")
    if any(item["last_day"] >= RESERVED_START for item in receipt["instruments"].values()):
        raise DataError("panel receipt reaches reserved window")
    panel = validate_panel(pl.read_parquet(io.BytesIO(panel_bytes)))
    value_path = request_path.parent / request["values_file"]
    value_bytes = value_path.read_bytes()
    values = pl.read_parquet(io.BytesIO(value_bytes))
    if values.height:
        values = values.with_columns(_days(values))
    if values.height and (values["date"] >= RESERVED_DAY).any():
        raise DataError("factor values reach reserved window")
    if values.height and values.select(["date", "instrument"]).is_duplicated().any():
        raise DataError("duplicate factor value keys")
    if not set(values["instrument"].to_list()) <= set(panel["instrument"].to_list()):
        raise DataError("factor instruments outside panel")
    fingerprint = sha(
        Path(__file__).read_bytes() + (Path(__file__).resolve().parents[4] / "uv.lock").read_bytes()
    )
    return (
        request,
        panel,
        values,
        {
            "panel_sha256": sha(panel_bytes),
            "request_sha256": sha(request_bytes),
            "factors_sha256": sha(value_bytes),
            "evaluator_fingerprint": fingerprint,
            "configuration_sha256": sha(canonical(CONFIG)),
        },
    )


def _deflate(
    rows: list[dict[str, Any]],
    history: list[dict[str, Any]],
    family: dict[str, dict[str, Any]],
    replay_returns: dict[str, np.ndarray],
) -> list[float]:
    """Deflated Sharpe for this request's replays; returns every replayed trial's Sharpe."""
    trials = [
        row["replay"]["net"]["per_observation_sharpe"]
        for row in [*history, *rows]
        if row["stage"] == "replay" and "net" in row["replay"]
    ]
    for row in rows:
        row["replayed_trials"] = len(trials)
        if row["code_sha256"] in replay_returns:
            returns = replay_returns[row["code_sha256"]]
            row["replay"]["deflated_sharpe"] = asdict(
                deflated_sharpe(returns, trial_sharpes=trials)
            )
            # Replayed factors passed the screen, so the replayed set alone understates the
            # search. Also deflate against the expected maximum of the whole family's size.
            if len(trials) >= 2:
                benchmark = expected_max_sharpe(float(np.var(trials, ddof=1)), len(family))
                row["replay"]["deflated_sharpe_family"] = {
                    "n_trials": len(family),
                    "benchmark_sharpe": benchmark,
                    "psr": probabilistic_sharpe_ratio(returns, benchmark_sr=benchmark),
                }
            else:
                row["replay"]["deflated_sharpe_family"] = {
                    "n_trials": len(family),
                    "psr": None,
                    "reason": "fewer than two replayed trials: no cross-trial variance",
                }
        if row["status"] == "REPEAT":
            earliest = family[row["code_sha256"]]
            row["first_trial"] = {
                k: earliest[k] for k in ("run_id", "iteration", "name", "status", "screen")
            }
    return trials


def _report(
    rows: list[dict[str, Any]],
    history: list[dict[str, Any]],
    family: dict[str, dict[str, Any]],
    trials: list[float],
) -> tuple[dict[str, Any] | None, dict[str, float], dict[str, Any], bool, str]:
    """Lead factor, RD-Agent's result keys, disclosures, ALPHA's decision and feedback text."""
    # The lead is the best candidate when there is one, so RD-Agent's stored result matches the
    # decision; otherwise the lowest q among this request's new factors.
    candidates = [row for row in rows if row["status"] == "CANDIDATE"]
    eligible = candidates or [row for row in rows if row["status"] != "REPEAT"]
    lead = min(eligible, key=lambda r: (r["q"], r["name"])) if eligible else None
    legacy = {"IC": lead["screen"].get("mean_ic", float("nan")) if lead else float("nan")}
    for cost, key in (("without", "gross"), ("with", "net")):
        for metric in ("annualized_return", "max_drawdown"):
            legacy[f"1day.excess_return_{cost}_cost.{metric}"] = (
                lead["replay"].get(key, {}).get(metric, float("nan")) if lead else float("nan")
            )
    disclosures = {
        "survivorship": SURVIVORSHIP,
        "multiple_testing": "screening only, adaptive family, no error rate claimed",
        "direction": "chosen in-sample",
        "replay_engine": "ALPHA canonical synchronized replay, not Nautilus",
        "close_stamp": "origin + 23h; full UTC day bar known at its close",
        "lookahead_scope": (
            "prefix invariance at fixed cuts only; not proof against leakage within cuts"
        ),
        **CONFIG,
    }
    decision = any(row["status"] == "CANDIDATE" for row in rows)
    feedback = (
        f"{LABEL}. {SURVIVORSHIP}. Ledger trials: {len(history) + len(rows)}; distinct family: "
        f"{len(family)}; replayed trials: {len(trials)}. Screening only, adaptive family, no "
        "error rate claimed. Direction chosen in-sample. Exploration "
        f"{EXPLORATION[0]}..{EXPLORATION[1]}; history 2017-08-17..2020-12-31; panel ends "
        f"{PANEL_END}; {RESERVED_START}+ reserved, never evaluated. Decide at close, fill next "
        "open, exit following open; ALPHA canonical synchronized replay, not Nautilus; 10 bps "
        "fee + 6 bps slippage per side. Prefix invariance is a fixed-cut check, not proof. "
    )
    feedback += " ".join(
        f"{r['name']}: {r['status']}, mean rank IC {r['screen'].get('mean_ic')}, "
        f"q={r['q']:.6g}, net annual excess "
        f"{r['replay'].get('net', {}).get('annualized_return')}."
        for r in rows
    )
    for row in rows:
        exposure = row["exposure"]
        if exposure["previously_exposed"]:
            families = ", ".join(f"{m['family_id']} ({m['status']})" for m in exposure["matches"])
            feedback += (
                f" {row['name']}: protected window {exposure['protected_window_start']}+ "
                f"previously exposed for family {families}; it cannot give fresh confirmation."
            )
    feedback += f" ALPHA decision: {decision}; admitted/evidence/approval/promotion all false."
    return lead, legacy, disclosures, decision, feedback


def _bucket_frames(
    signal: np.ndarray, outcome: np.ndarray, days: list[date], symbols: list[str], direction: int
) -> tuple[pl.DataFrame, pl.DataFrame]:
    observations: dict[int, list[float]] = {bucket: [] for bucket in (1, 2, 3)}
    daily = []
    for day, scores, returns in zip(days, signal, outcome, strict=True):
        available = [i for i, score in enumerate(scores) if math.isfinite(score)]
        ranked = sorted(available, key=lambda i: (-direction * scores[i], symbols[i]))
        k = max(1, round(TOP_FRACTION * len(available)))
        groups: dict[int, list[float]] = {bucket: [] for bucket in (1, 2, 3)}
        for rank, i in enumerate(ranked):
            if math.isfinite(returns[i]):
                bucket = 3 if rank < k else 1 if rank >= len(ranked) - k else 2
                groups[bucket].append(float(returns[i]))
        for bucket, outcomes in groups.items():
            observations[bucket].extend(outcomes)
            daily.append(
                {
                    "clock": "daily",
                    "date": day,
                    "bucket": bucket,
                    "mean_outcome": math.fsum(outcomes) / len(outcomes) if outcomes else None,
                }
            )
    # Explicit ordered sums avoid floating-point reductions depending on worker scheduling.
    buckets = [
        {
            "clock": "daily",
            "bucket": bucket,
            "mean_outcome": math.fsum(outcomes) / len(outcomes) if outcomes else None,
            "observations": len(outcomes),
        }
        for bucket, outcomes in observations.items()
    ]
    return (
        pl.DataFrame(buckets).with_columns(pl.col("mean_outcome").cast(pl.Float64)),
        pl.DataFrame(daily).with_columns(pl.col("mean_outcome").cast(pl.Float64)),
    )


def _series_frames(
    row: dict[str, Any],
    data: dict[str, Any],
    signal: np.ndarray,
    outcome: np.ndarray,
    days: list[date],
    symbols: list[str],
) -> Iterator[tuple[str, pl.DataFrame]]:
    if "daily_ic" in data:
        yield (
            "screen",
            pl.DataFrame(
                {
                    "clock": ["daily"] * len(days),
                    "date": days,
                    "rank_ic": pl.Series(data["daily_ic"], dtype=pl.Float64),
                    "names": data["names"],
                }
            ),
        )
    if row["screen"].get("status") == "OK":
        buckets, daily = _bucket_frames(signal, outcome, days, symbols, row["screen"]["direction"])
        yield "buckets", buckets
        yield "buckets_daily", daily
    if "periods" in data:
        periods = [
            {"clock": "daily", **{k: v for k, v in asdict(p).items() if k != "fold"}}
            for p in data["periods"]
        ]
        yield "replay", pl.DataFrame(periods).sort(["clock", "target_ts", "exit_ts"])
        yield (
            "holdings",
            pl.DataFrame(
                [
                    {
                        "clock": "daily",
                        "date": t.origin_ts.date(),
                        "instrument": t.symbol,
                        "target_weight": t.target_weight,
                        "score": t.score,
                    }
                    for t in data["targets"]
                ]
            ).sort(["clock", "date", "instrument"]),
        )


def _series_file(path: Path, payload: bytes) -> None:
    try:
        exclusive(path, payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise DataError(f"conflicting series file: {path.name}") from None


def _write_series(
    run: Path,
    iteration: int,
    rows: list[dict[str, Any]],
    series: dict[str, dict[str, Any]],
    signals: dict[str, np.ndarray],
    outcome: np.ndarray,
    days: list[date],
    symbols: list[str],
) -> tuple[str, str, set[str]]:
    relative = f"evaluations/iter-{iteration}/series/series.json"
    folder = (run / relative).parent
    folder.mkdir(parents=True, exist_ok=True)
    factors = []
    written = set()
    for row in rows:
        digest = row["code_sha256"]
        if digest not in series or row["stage"] == "none":
            continue
        files = []
        try:
            for kind, frame in _series_frames(
                row, series[digest], signals[digest], outcome, days, symbols
            ):
                name = f"{digest}.{kind}.parquet"
                buffer = io.BytesIO()
                frame.write_parquet(buffer)
                payload = buffer.getvalue()
                _series_file(folder / name, payload)
                files.append({"name": name, "sha256": sha(payload)})
        except Exception as error:  # Series must not change evaluation outcomes.
            row["series_note"] = f"{type(error).__name__}: {error}"
        if files:
            factors.append({"code_sha256": digest, "files": files})
            written.add(digest)
    payload = canonical({"schema": "AlphaRdagentTrialSeriesV1", "factors": factors})
    _series_file(run / relative, payload)
    return relative, sha(payload), written


def _record_series(
    run: Path,
    iteration: int,
    rows: list[dict[str, Any]],
    series: dict[str, dict[str, Any]],
    signals: dict[str, np.ndarray],
    outcome: np.ndarray,
    days: list[date],
    symbols: list[str],
    inputs: dict[str, Any],
) -> str | None:
    try:
        relative, digest, written = _write_series(
            run, iteration, rows, series, signals, outcome, days, symbols
        )
    except Exception as error:  # Evidence failures are recorded, never scoring failures.
        return f"{type(error).__name__}: {error}"
    inputs["series_sha256"] = digest
    for row in rows:
        if row["code_sha256"] in written and row["stage"] != "none":
            row["evidence"] = {"series_manifest": relative, "sha256": digest}
    return None


def _screen_factors(
    run: Path,
    request: dict[str, Any],
    values: pl.DataFrame,
    inputs: dict[str, str],
    history: list[dict[str, Any]],
    family: dict[str, dict[str, Any]],
    entries: Any,
    days: list[date],
    symbols: list[str],
    outcome: np.ndarray,
    series: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    from alpha_cli.rdagent_exposure import label_for

    rows: list[dict[str, Any]] = []
    signals: dict[str, np.ndarray] = {}
    for factor in request["factors"]:
        digest = factor["code_sha256"]
        row = {
            **factor,
            "schema": TRIAL_SCHEMA,
            "plain_name": plain_name(factor["name"]),
            "trial_index": len(history) + len(rows) + 1,
            "run_id": run.name,
            "iteration": request["iteration"],
            "panel_sha256": inputs["panel_sha256"],
            "windows": WINDOWS,
            "instruments": symbols,
            "stage": "none",
            "p": 1.0,
            "q": 1.0,
            "screen": {},
            "replay": {},
            "label": LABEL,
            "survivorship": SURVIVORSHIP,
            "authority": AUTHORITY,
        }
        row["exposure"] = label_for(row, entries)
        if digest in family:
            row["status"] = "REPEAT"
            row["first_trial"] = {
                k: family[digest][k] for k in ("run_id", "iteration", "name", "status", "screen")
            }
            row["p"] = family[digest]["p"]
        else:
            if factor["status"] == "OK":
                try:
                    if factor["name"] not in values.columns:
                        raise DataError(f"no value column for factor {factor['name']!r}")
                    signal = matrix(values, factor["name"], days, symbols)
                    signals[digest] = signal
                    stats = screen(signal, outcome, digest, series=series.setdefault(digest, {}))
                except (DataError, ValueError, ZeroDivisionError, FloatingPointError) as error:
                    stats = {
                        "status": "ERROR",
                        "p": 1.0,
                        "error": f"{type(error).__name__}: {error}",
                    }
                row.update(status=stats["status"], p=stats["p"], screen=stats, stage="screen")
            family[digest] = row
        rows.append(row)
    return rows, signals


def _evaluate_locked(
    run: Path,
    request: dict[str, Any],
    panel: pl.DataFrame,
    values: pl.DataFrame,
    inputs: dict[str, str],
    ledger: Path,
) -> dict[str, Any]:
    from alpha_cli.rdagent_exposure import snapshot

    entries, exposure_bytes = snapshot(ledger)
    record_inputs: dict[str, Any] = {
        **inputs,
        "exposure_log_sha256": sha(exposure_bytes) if exposure_bytes is not None else None,
    }
    history = _read_ledger(ledger)
    family: dict[str, dict[str, Any]] = {}
    for row in history:
        if row["status"] != "REPEAT":
            family.setdefault(row["code_sha256"], row)
    first, last = (date.fromisoformat(d) for d in EXPLORATION)
    days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    symbols = sorted(panel["instrument"].unique().to_list())
    # opens[i] is the open of day days[0] + i, for i up to len(days) + 1.
    opens = matrix(
        panel, "open", [first + timedelta(days=n) for n in range(len(days) + 2)], symbols
    )
    outcome = opens[2:] / opens[1:-1] - 1  # decision day d: open(d+2) / open(d+1) - 1
    series: dict[str, dict[str, Any]] = {}
    rows, signals = _screen_factors(
        run, request, values, inputs, history, family, entries, days, symbols, outcome, series
    )
    q = benjamini_hochberg([f["p"] for f in family.values()], alpha=Q_THRESHOLD).qvalues
    qvalues = dict(zip(family, map(float, q), strict=True))
    replay_returns = {}
    for row in rows:
        digest = row["code_sha256"]
        row.update(
            q=qvalues[digest], family_size=len(family), total_trials=len(history) + len(rows)
        )
        if row["status"] != "OK":
            continue
        row["status"] = "SCREEN_FAIL"
        if row["q"] < Q_THRESHOLD:
            try:
                metrics, net = replay(
                    panel,
                    signals[digest],
                    days,
                    row["screen"]["direction"],
                    series=series.setdefault(digest, {}),
                )
            except (DataError, ValueError, ZeroDivisionError, FloatingPointError) as error:
                row.update(
                    stage="replay",
                    status="ERROR",
                    replay={"error": f"{type(error).__name__}: {error}"},
                )
                continue
            row.update(
                stage="replay",
                replay=metrics,
                status="CANDIDATE" if metrics["net"]["annualized_return"] > 0 else "REPLAY_FAIL",
            )
            replay_returns[digest] = net
    series_note = _record_series(
        run, request["iteration"], rows, series, signals, outcome, days, symbols, record_inputs
    )
    trials = _deflate(rows, history, family, replay_returns)
    lead, legacy, disclosures, decision, feedback = _report(rows, history, family, trials)
    record = {
        "schema": "AlphaRdagentFactorEvaluationV1",
        "iteration": request["iteration"],
        "label": LABEL,
        "authority": AUTHORITY,
        "disclosures": disclosures,
        "inputs": record_inputs,
        "factors": rows,
        "family_size": len(family),
        "total_trials": len(history) + len(rows),
        "replayed_trials": len(trials),
        "qvalues": qvalues,
        "decision": decision,
        "lead_factor": lead["name"] if lead else None,
        "legacy_result": legacy,
        "feedback_text": feedback,
    }
    if series_note is not None:
        record["series_note"] = series_note
    with ledger.open("ab", buffering=0) as stream:
        for row in rows:
            line = canonical(row)
            if stream.write(line) != len(line):
                raise DataError("short trial ledger write")
            os.fsync(stream.fileno())
    return record


def evaluate(run: Path, request_path: Path, out: Path, ledger: Path) -> dict[str, Any]:
    outside_git(ledger)
    if out.exists():
        raise DataError("evaluation output already exists")
    request, panel, values, inputs = _inputs(run, request_path)
    with Path(str(ledger) + ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        record = _evaluate_locked(run, request, panel, values, inputs, ledger)
        rendered = canonical(record)
        exclusive(out, rendered)
        with (run / "evaluations.jsonl").open("ab", buffering=0) as stream:
            if stream.write(rendered) != len(rendered):
                raise DataError("short evaluation write")
            os.fsync(stream.fileno())
    return record


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exploratory RD-Agent factor screen and ALPHA replay; no admission authority."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    freezing = sub.add_parser("freeze")
    freezing.add_argument("--data-dir", type=Path, required=True)
    freezing.add_argument("--out", type=Path, required=True)
    evaluating = sub.add_parser("evaluate")
    for name in ("run-dir", "request", "out", "ledger"):
        evaluating.add_argument(f"--{name}", type=Path, required=True)
    importing = sub.add_parser("import-historical")
    importing.add_argument("--ledger", type=Path, required=True)
    importing.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.data_dir, args.out)
    elif args.command == "import-historical":
        import_historical(args.ledger, args.file)
    else:
        evaluate(args.run_dir, args.request, args.out, args.ledger)


if __name__ == "__main__":
    main()
