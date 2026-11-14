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
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from alpha_backtest.portfolio_replay import WeightTarget, run_weight_replay
from alpha_cli.crypto_bulk_store import configured_crypto_bulk_store
from alpha_core import Bar, DataError
from alpha_research.panel import cross_sectional_ic
from alpha_validation.bootstrap import block_bootstrap_ci
from alpha_validation.dsr import deflated_sharpe
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
TRIAL_SCHEMA = "AlphaRdagentFactorTrialV1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _dates(frame: pd.DataFrame, column: str = "date") -> pd.Series:
    dates = pd.to_datetime(frame[column], utc=True)
    if dates.isna().any() or not dates.eq(dates.dt.normalize()).all():
        raise DataError("panel dates must be UTC-midnight days")
    return dates


def validate_panel(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise DataError("empty panel")
    frame = frame.copy()
    frame["date"] = _dates(frame)
    if frame["date"].ge(pd.Timestamp(RESERVED_START, tz="UTC")).any():
        raise DataError("panel reaches reserved window")
    if frame.duplicated(["date", "instrument"]).any():
        raise DataError("overlapping instrument-day artifacts")
    for name, rows in frame.groupby("instrument", sort=True):
        if (
            not rows.date.is_monotonic_increasing
            or not rows.date.diff().dropna().eq(pd.Timedelta(days=1)).all()
        ):
            raise DataError(f"disordered or gapped daily bars for {name}")
    prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    volumes = frame[["volume", "quote_volume"]].to_numpy(dtype=float)
    if (
        not np.isfinite(prices).all()
        or (prices <= 0).any()
        or not np.isfinite(volumes).all()
        or (volumes < 0).any()
    ):
        raise DataError("invalid OHLC or volumes")
    if (frame.low > frame[["open", "close"]].min(axis=1)).any() or (
        frame.high < frame[["open", "close"]].max(axis=1)
    ).any():
        raise DataError("inconsistent OHLC")
    return frame.sort_values(["date", "instrument"]).reset_index(drop=True)


def freeze(data_dir: Path, out: Path) -> dict[str, Any]:
    store = configured_crypto_bulk_store(data_dir)
    frames, manifests, hashes = [], [], set()
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
        frame = pd.read_parquet(io.BytesIO(payload))
        frame["date"] = _dates(frame, "open_time")
        frame = frame.loc[frame.date.lt(pd.Timestamp(RESERVED_START, tz="UTC"))].copy()
        frame["instrument"] = dataset["instrument"]
        frame = frame.rename(columns={"base_volume": "volume"})
        frames.append(
            frame[["date", "instrument", "open", "high", "low", "close", "volume", "quote_volume"]]
        )
    if not frames:
        raise DataError("no qualified Binance spot daily bars")
    # Validate order within each artifact before merging chronological captures.
    for frame in frames:
        if not frame.empty and not frame.date.is_monotonic_increasing:
            raise DataError("disordered artifact")
    panel = validate_panel(pd.concat(frames).sort_values(["date", "instrument"]))
    instruments = {
        str(name): {
            "rows": len(rows),
            "first_day": rows.date.min().date().isoformat(),
            "last_day": rows.date.max().date().isoformat(),
        }
        for name, rows in panel.groupby("instrument")
    }
    panel["date"] = panel.date.dt.date
    for column in ("open", "high", "low", "close", "volume", "quote_volume"):
        panel[column] = panel[column].astype("float64")
    out.mkdir(parents=True, exist_ok=False)
    payload = panel.to_parquet(index=False)
    exclusive(out / "panel.parquet", payload)
    receipt = {
        "schema": "AlphaRdagentFactorPanelV1",
        "manifests": manifests,
        "instruments": instruments,
        "rows": len(panel),
        "panel_sha256": sha(payload),
    }
    exclusive(out / "panel-receipt.json", canonical(receipt))
    return receipt


def screen(signal: pd.DataFrame, outcome: pd.DataFrame, digest: str) -> dict[str, Any]:
    values = signal.to_numpy(dtype=float)
    finite = np.isfinite(values)
    coverage = float(finite.mean())
    ties = sum(
        bool(row.size and np.ptp(row) == 0) for row in (r[np.isfinite(r)] for r in values)
    ) / len(values)
    result: dict[str, Any] = {"coverage": coverage, "tie_share": ties}
    if coverage < 0.8 or ties > 0.05:
        return {**result, "status": "DEGENERATE", "p": 1.0}
    ic = cross_sectional_ic(
        np.where(finite, values, np.nan), outcome.to_numpy(), min_names=MIN_NAMES
    )
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
    panel: pd.DataFrame, signal: pd.DataFrame, direction: int
) -> tuple[dict[str, Any], np.ndarray]:
    start, end = signal.index[0], signal.index[-1] + pd.Timedelta(days=2)
    rows = panel[panel.date.between(start, end)]
    expected = pd.date_range(start, end, freq="D")
    symbols = sorted(panel.instrument.unique())
    bars = {}
    for name in symbols:
        group = rows[rows.instrument.eq(name)]
        if list(group.date) != list(expected):
            raise DataError("replay requires a complete daily session rectangle")
        bars[name] = [
            Bar(
                symbol=name,
                ts=pd.Timestamp(str(r.date)).to_pydatetime(),
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
            )
            for r in group.itertuples()
        ]
    targets, missing, cash_days = [], 0, 0
    for day, row in signal.iterrows():
        available = [s for s in symbols if math.isfinite(float(row[s]))]
        missing += len(symbols) - len(available)
        k = max(1, round(TOP_FRACTION * len(available)))
        ranked = sorted(available, key=lambda s: (-direction * float(row[s]), s))
        selected = set(ranked[:k]) if len(available) >= MIN_NAMES else set()
        cash_days += not selected
        origin = pd.Timestamp(str(day)).to_pydatetime()
        for name in symbols:
            targets.append(
                WeightTarget(
                    symbol=name,
                    origin_ts=origin,
                    available_at=origin + timedelta(hours=23),
                    target_ts=origin + timedelta(days=1),
                    target_weight=1 / k if name in selected else 0.0,
                    score=direction * float(row[name]) if name in available else 0.0,
                    fold=0,
                )
            )
    result = run_weight_replay(bars, targets, fee_bps=FEE_BPS, slippage_bps=SLIPPAGE_BPS)
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
                row["schema"] != TRIAL_SCHEMA
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
        except (ValueError, TypeError, KeyError) as error:
            raise DataError(f"invalid trial ledger line {index}: {error}") from error
        records.append(row)
    return records


def _inputs(
    run: Path, request_path: Path
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, dict[str, str]]:
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
    panel = validate_panel(pd.read_parquet(io.BytesIO(panel_bytes)))
    value_path = request_path.parent / request["values_file"]
    value_bytes = value_path.read_bytes()
    values = pd.read_parquet(io.BytesIO(value_bytes))
    values["date"] = _dates(values)
    if values.date.ge(pd.Timestamp(RESERVED_START, tz="UTC")).any():
        raise DataError("factor values reach reserved window")
    if values.duplicated(["date", "instrument"]).any():
        raise DataError("duplicate factor value keys")
    if not set(values.instrument) <= set(panel.instrument):
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


def _evaluate_locked(
    run: Path,
    request: dict[str, Any],
    panel: pd.DataFrame,
    values: pd.DataFrame,
    inputs: dict[str, str],
    ledger: Path,
) -> dict[str, Any]:
    history = _read_ledger(ledger)
    family: dict[str, dict[str, Any]] = {}
    for row in history:
        if row["status"] != "REPEAT":
            family.setdefault(row["code_sha256"], row)
    dates = pd.date_range(*EXPLORATION, tz="UTC")
    symbols = sorted(panel.instrument.unique())
    opens = panel.pivot(index="date", columns="instrument", values="open").reindex(
        pd.date_range(EXPLORATION[0], pd.Timestamp(EXPLORATION[1]) + pd.Timedelta(days=2), tz="UTC")
    )
    outcome = (opens.shift(-2) / opens.shift(-1) - 1).reindex(index=dates, columns=symbols)
    rows: list[dict[str, Any]] = []
    signals: dict[str, pd.DataFrame] = {}
    for factor in request["factors"]:
        digest = factor["code_sha256"]
        row = {
            **factor,
            "schema": TRIAL_SCHEMA,
            "trial_index": len(history) + len(rows) + 1,
            "run_id": run.name,
            "iteration": request["iteration"],
            "panel_sha256": inputs["panel_sha256"],
            "windows": WINDOWS,
            "stage": "none",
            "p": 1.0,
            "q": 1.0,
            "screen": {},
            "replay": {},
            "label": LABEL,
            "survivorship": SURVIVORSHIP,
            "authority": AUTHORITY,
        }
        if digest in family:
            row["status"] = "REPEAT"
            row["first_trial"] = {
                k: family[digest][k] for k in ("run_id", "iteration", "name", "status", "screen")
            }
            row["p"] = family[digest]["p"]
        else:
            if factor["status"] == "OK":
                signal = values.pivot(
                    index="date", columns="instrument", values=factor["name"]
                ).reindex(index=dates, columns=symbols)
                signals[digest] = signal
                stats = screen(signal, outcome, digest)
                row.update(status=stats["status"], p=stats["p"], screen=stats, stage="screen")
            family[digest] = row
        rows.append(row)
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
            metrics, net = replay(panel, signals[digest], row["screen"]["direction"])
            row.update(
                stage="replay",
                replay=metrics,
                status="CANDIDATE" if metrics["net"]["annualized_return"] > 0 else "REPLAY_FAIL",
            )
            replay_returns[digest] = net
    trials = [
        row["replay"]["net"]["per_observation_sharpe"]
        for row in [*history, *rows]
        if row["stage"] == "replay"
    ]
    for row in rows:
        row["replayed_trials"] = len(trials)
        if row["stage"] == "replay":
            row["replay"]["deflated_sharpe"] = asdict(
                deflated_sharpe(replay_returns[row["code_sha256"]], trial_sharpes=trials)
            )
        if row["status"] == "REPEAT":
            first = family[row["code_sha256"]]
            row["first_trial"] = {
                k: first[k] for k in ("run_id", "iteration", "name", "status", "screen")
            }
    eligible = [row for row in rows if row["status"] != "REPEAT"]
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
    feedback += f" ALPHA decision: {decision}; admitted/evidence/approval/promotion all false."
    record = {
        "schema": "AlphaRdagentFactorEvaluationV1",
        "iteration": request["iteration"],
        "label": LABEL,
        "authority": AUTHORITY,
        "disclosures": disclosures,
        "inputs": inputs,
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
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freezing = sub.add_parser("freeze")
    freezing.add_argument("--data-dir", type=Path, required=True)
    freezing.add_argument("--out", type=Path, required=True)
    evaluating = sub.add_parser("evaluate")
    for name in ("run-dir", "request", "out", "ledger"):
        evaluating.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.data_dir, args.out)
    else:
        evaluate(args.run_dir, args.request, args.out, args.ledger)


if __name__ == "__main__":
    main()
