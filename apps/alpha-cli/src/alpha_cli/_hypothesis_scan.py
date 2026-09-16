"""Frozen-input, non-authoritative hypothesis screens; never a governed research run."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from alpha_core import DataError, UniverseMembership, members_as_of
from alpha_research import panel

EQUITY_SIGNALS = ("mom_12_1", "mom_6_1", "rev_1m", "vol_63", "range_52w")
CRYPTO_SIGNALS = ("funding_z_30d", "oi_chg_7d", "mom_30d")


def price_signals(closes: np.ndarray, names: Sequence[str]) -> dict[str, np.ndarray]:
    """Fixed trailing-close recipes in session units, with complete-window availability.

    Momentum skips 21 sessions (252/126 lookback), reversal negates 21-session return,
    volatility is sample daily-return std over 63 sessions, and range is the close's
    position in the trailing 252-close range. No annualization or model fitting.
    """
    windows = {
        "mom_12_1": 253,
        "mom_6_1": 127,
        "rev_1m": 22,
        "vol_63": 64,
        "range_52w": 252,
        "mom_30d": 31,
    }
    if closes.ndim != 2 or np.isinf(closes).any():
        raise DataError("signal close panel must be two dimensional and finite or absent")
    if np.any(closes[np.isfinite(closes)] <= 0):
        raise DataError("signal closes must be positive")
    result: dict[str, np.ndarray] = {}
    for name in names:
        if name not in windows:
            raise DataError(f"unknown price signal {name!r}")
        width = windows[name]
        values = np.full(closes.shape, np.nan)
        for t in range(width - 1, len(closes)):
            window = closes[t - width + 1 : t + 1]
            valid = np.isfinite(window).all(axis=0)
            sample = window[:, valid]
            if name.startswith("mom_"):
                end = -22 if name in {"mom_12_1", "mom_6_1"} else -1
                values[t, valid] = sample[end] / sample[0] - 1
            elif name == "rev_1m":
                values[t, valid] = -(sample[-1] / sample[0] - 1)
            elif name == "vol_63":
                values[t, valid] = np.std(sample[1:] / sample[:-1] - 1, axis=0, ddof=1)
            else:
                span = np.max(sample, axis=0) - np.min(sample, axis=0)
                nonflat = span > 0
                columns = np.flatnonzero(valid)[nonflat]
                values[t, columns] = (
                    sample[-1, nonflat] - np.min(sample[:, nonflat], axis=0)
                ) / span[nonflat]
        result[name] = values
    return result


def canonical_bytes(value: object) -> bytes:
    """Screen-only canonical JSON: normalize signed zero and reject nonfinite values."""

    def clean(item: object) -> object:
        if isinstance(item, float) and item == 0:
            return 0.0
        if isinstance(item, dict):
            return {key: clean(val) for key, val in item.items()}
        if isinstance(item, list | tuple):
            return [clean(val) for val in item]
        return item

    return json.dumps(
        clean(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _digest(value: object) -> str:
    try:
        return hashlib.sha256(canonical_bytes(value)).hexdigest()
    except (TypeError, ValueError) as exc:
        raise DataError("screening values must have finite canonical JSON") from exc


def runtime_identity() -> dict[str, str]:
    """Hash installed execution sources without the process cache used by legacy runs."""
    digest = hashlib.sha256()
    for package in ("alpha_core", "alpha_data", "alpha_research", "alpha_cli"):
        spec = importlib.util.find_spec(package)
        if spec is None or spec.submodule_search_locations is None:
            raise DataError(f"cannot fingerprint {package}")
        root = Path(next(iter(spec.submodule_search_locations)))
        paths = (
            [
                root / name
                for name in (
                    "_hypothesis_scan.py",
                    "_crypto_panel.py",
                    "_runner.py",
                    "scan_cmds.py",
                )
            ]
            if package == "alpha_cli"
            else sorted(root.rglob("*.py"))
        )
        for path in paths:
            digest.update(f"{package}/{path.relative_to(root)}\0".encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    lock = Path(__file__).resolve().parents[4] / "uv.lock"
    if not lock.is_file():
        raise DataError("screening requires the workspace uv.lock for replay provenance")
    return {
        "code_hash": digest.hexdigest(),
        "lock_hash": hashlib.sha256(lock.read_bytes()).hexdigest(),
    }


def _storage_path(data_dir: Path, *parts: str) -> Path:
    path = data_dir
    for part in ("", "scans", "hypotheses", *parts):
        path /= part
        if path.is_symlink():
            raise DataError("hypothesis storage must not contain symlinks")
    return path


def _publish(path: Path, payload: object) -> None:
    """Atomic create-only publication; a conflict never overwrites an earlier attempt."""
    raw = canonical_bytes(payload) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != raw:
                raise DataError("immutable hypothesis artifact conflict") from None
    finally:
        temporary.unlink(missing_ok=True)


def _options(request: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "lane",
        "symbols",
        "universe",
        "snapshot",
        "as_of",
        "signals",
        "horizons",
        "min_names",
        "quantiles",
        "cost_bps",
        "category",
    }
    if set(request) != expected:
        raise DataError("hypothesis request fields are incomplete or unknown")
    options = dict(request)
    lane = options["lane"]
    if lane not in {"equity", "crypto"}:
        raise DataError("lane must be equity or crypto")
    try:
        cutoff = date.fromisoformat(options["as_of"])
    except (TypeError, ValueError) as exc:
        raise DataError("as_of must be YYYY-MM-DD") from exc
    if cutoff.isoformat() != options["as_of"]:
        raise DataError("as_of must be canonical YYYY-MM-DD")
    symbols = options["symbols"]
    if not isinstance(symbols, list) or any(
        not isinstance(s, str) or not s.strip() for s in symbols
    ):
        raise DataError("symbols must be a list of nonempty identifiers")
    options["symbols"] = sorted({s.strip() for s in symbols})
    universe = options["universe"]
    if universe is not None and (not isinstance(universe, str) or not universe.strip()):
        raise DataError("universe must be a name")
    if bool(symbols) == bool(universe):
        raise DataError("provide exactly one of symbols or universe")
    if lane == "equity" and not isinstance(options["snapshot"], str):
        raise DataError("equity hypotheses require a frozen snapshot")
    if lane == "crypto" and (universe is not None or options["snapshot"] is not None):
        raise DataError("crypto hypotheses require explicit symbols and no equity snapshot")
    if options["category"] not in {"linear", "inverse"}:
        raise DataError("category must be linear or inverse")
    available = EQUITY_SIGNALS if lane == "equity" else CRYPTO_SIGNALS
    names = options["signals"]
    if not isinstance(names, list) or not names or any(name not in available for name in names):
        raise DataError(f"signals must be selected from {available}")
    if len(set(names)) != len(names):
        raise DataError("duplicate signals are not distinct trials")
    options["signals"] = sorted(names)
    horizons = options["horizons"]
    if (
        not isinstance(horizons, list)
        or not horizons
        or any(type(h) is not int or h < 1 for h in horizons)
    ):
        raise DataError("horizons must be positive integers")
    if len(set(horizons)) != len(horizons):
        raise DataError("duplicate horizons are not distinct trials")
    options["horizons"] = sorted(horizons)
    minimum, quantiles = options["min_names"], options["quantiles"]
    if type(minimum) is not int or minimum < 3:
        raise DataError("min_names must be an integer >= 3")
    if type(quantiles) is not int or not 2 <= quantiles <= minimum:
        raise DataError("quantiles must be between 2 and min_names")
    cost = options["cost_bps"]
    if type(cost) not in {int, float} or not math.isfinite(cost) or cost < 0:
        raise DataError("cost_bps must be finite and nonnegative")
    options["cost_bps"] = float(cost)
    return options


def freeze_spec(data_dir: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve immutable input references before any signal or outcome is evaluated."""
    options = _options(request)
    result = {
        "schema_version": 1,
        "panel_version": panel.PANEL_VERSION,
        "authority": "none",
        "options": options,
        **runtime_identity(),
    }
    if options["lane"] == "crypto":
        from alpha_cli._crypto_panel import freeze_crypto_inputs

        result["crypto_inputs"] = freeze_crypto_inputs(data_dir, options)
        return result
    from alpha_data.snapshot import resolve_snapshot_dir, snapshot_manifest_hash
    from alpha_data.store import ParquetStore

    snapshot = resolve_snapshot_dir(data_dir / "snapshots", options["snapshot"])
    result["snapshot_hash"] = snapshot_manifest_hash(snapshot)
    memberships = []
    if options["universe"] is not None:
        memberships = ParquetStore(data_dir / "store").read_universe(options["universe"])
        memberships.sort(key=lambda item: (item.symbol, item.effective_from))
        options["symbols"] = sorted({item.symbol for item in memberships})
    result["memberships"] = [item.model_dump(mode="json") for item in memberships]
    result["membership_hash"] = _digest(result["memberships"])
    return result


def equity_panel(
    data_dir: Path, spec: Mapping[str, Any]
) -> tuple[list[date], np.ndarray, list[str]]:
    from alpha_cli._runner import load_bars
    from alpha_data.snapshot import resolve_snapshot_dir, snapshot_manifest_hash

    options = spec["options"]
    snapshot = resolve_snapshot_dir(data_dir / "snapshots", options["snapshot"])
    if snapshot_manifest_hash(snapshot) != spec["snapshot_hash"]:
        raise DataError("frozen equity snapshot hash changed")
    if _digest(spec["memberships"]) != spec["membership_hash"]:
        raise DataError("frozen membership hash changed")
    cutoff = datetime.combine(date.fromisoformat(options["as_of"]), time.max, tzinfo=UTC)
    # Only manifest-bound names are inputs; an extra unmanifested parquet is not frozen.
    available = set(json.loads((snapshot / "manifest.json").read_text())["symbols"])
    names = options["symbols"]
    missing = sorted(set(names) - available)
    series = {}
    for name in names:
        if name in available:
            bars, _ = load_bars(
                name, data_dir=data_dir, snapshot_id=options["snapshot"], as_of=cutoff
            )
            by_date = {bar.ts.date(): bar.close for bar in bars}
            if len(by_date) != len(bars):
                raise DataError(f"screen requires one daily bar per date for {name}")
            series[name] = by_date
    dates = sorted({day for values in series.values() for day in values})
    if len(dates) < 3:
        raise DataError("equity panel needs at least three dates")
    closes = np.full((len(dates), len(names)), np.nan)
    for column, name in enumerate(names):
        values = series.get(name, {})
        for row, day in enumerate(dates):
            if day in values:
                closes[row, column] = values[day]
        present = np.flatnonzero(np.isfinite(closes[:, column]))
        if len(present) and len(present) != present[-1] - present[0] + 1:
            raise DataError(f"interior missing dates or mixed calendar for {name}")
    return dates, closes, missing


def membership_prices(
    closes: np.ndarray,
    dates: Sequence[date],
    names: Sequence[str],
    memberships: Sequence[UniverseMembership],
) -> np.ndarray:
    """Gate formation/warmup without erasing observed prices after ordinary universe exits."""
    eligible = closes.copy()
    if memberships:
        for row, day in enumerate(dates):
            members = set(members_as_of(memberships, day))
            for column, name in enumerate(names):
                if name not in members:
                    eligible[row, column] = np.nan
    return eligible


def _outcomes(
    closes: np.ndarray,
    dates: Sequence[date],
    names: Sequence[str],
    memberships: Sequence[UniverseMembership],
    horizon: int,
) -> np.ndarray:
    outcomes = panel.forward_outcomes(closes, horizon=horizon)
    for membership in memberships:
        end, terminal = membership.effective_to, membership.delisting_return
        if end is None or terminal is None or membership.symbol not in names:
            continue
        column = names.index(membership.symbol)
        eligible = [
            i
            for i, day in enumerate(dates)
            if membership.effective_from <= day < end and np.isfinite(closes[i, column])
        ]
        if not eligible:
            continue
        last = eligible[-1]
        for row in eligible:
            if row + horizon < len(dates) and dates[row + horizon] >= end:
                outcomes[row, column] = (
                    closes[last, column] / closes[row, column] * (1 + terminal) - 1
                )
    return outcomes


def _absent_leavers(signal: np.ndarray, *, minimum: int, quantiles: int) -> int:
    """Count disappeared extreme-bucket names, which the existing turnover excludes."""
    total = 0
    for before, after in zip(signal[:-1], signal[1:], strict=True):
        names = np.flatnonzero(np.isfinite(before))
        if len(names) < minimum:
            continue
        order = names[np.argsort(before[names], kind="stable")]
        width = len(names) // quantiles
        tails = np.concatenate((order[:width], order[-width:]))
        total += int(np.count_nonzero(~np.isfinite(after[tails])))
    return total


def evaluate_spec(
    data_dir: Path,
    spec: Mapping[str, Any],
    record_trial: Callable[[int, str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    options = spec["options"]
    memberships = [UniverseMembership.model_validate(item) for item in spec.get("memberships", [])]
    if options["lane"] == "equity":
        dates, closes, missing = equity_panel(data_dir, spec)
        eligible = membership_prices(closes, dates, options["symbols"], memberships)
        signals = price_signals(eligible, options["signals"])
    else:
        from alpha_cli._crypto_panel import crypto_panel

        dates, closes, signals = crypto_panel(data_dir, spec)
        missing = []
    minimum, quantiles = options["min_names"], options["quantiles"]
    results: list[dict[str, Any]] = []
    trial_index = 0
    for name, signal in signals.items():
        turnover = panel.bucket_turnover(signal, quantiles=quantiles, min_names=minimum)
        absent = _absent_leavers(signal, minimum=minimum, quantiles=quantiles)
        decay = {}
        rows = []
        for horizon in options["horizons"]:
            if record_trial is not None:
                record_trial(trial_index, "started", {"signal": name, "horizon": horizon})
            outcome = _outcomes(closes, dates, options["symbols"], memberships, horizon)
            ic = panel.cross_sectional_ic(signal, outcome, min_names=minimum)
            scored = np.sum(np.isfinite(signal) & np.isfinite(outcome), axis=1) >= minimum
            if int(scored.sum()) < 3:
                raise DataError(f"{name}/{horizon} needs at least three scorable dates")
            quantile = panel.quantile_returns(
                signal, outcome, quantiles=quantiles, min_names=minimum
            )
            decay[horizon] = ic.mean
            rows.append(
                {
                    "signal": name,
                    "horizon": horizon,
                    "ic": asdict(ic),
                    "quantiles": asdict(quantile),
                    "turnover": turnover,
                    "absent_leavers": absent,
                    "truncated_outcomes": int(
                        np.count_nonzero(np.isfinite(signal) & ~np.isfinite(outcome))
                    ),
                    "overlapping_outcomes": horizon > 1,
                    "cost_adjusted_spread": panel.cost_adjusted_spread(
                        quantile.spread, turnover, cost_bps=options["cost_bps"]
                    ),
                }
            )
            if record_trial is not None:
                record_trial(trial_index, "completed", rows[-1])
            trial_index += 1
        half_life = panel.ic_half_life(decay)
        results.extend({**row, "ic_half_life": half_life} for row in rows)
    return {
        "authority": "none",
        "execution_authority": False,
        "results": results,
        "trials": len(signals) * len(options["horizons"]),
        "missing": missing,
        "dates": [day.isoformat() for day in dates],
        "symbols": options["symbols"],
        "selection_adjustment": "not_performed",
        "horizon_unit": "aligned_observed_rows" if options["lane"] == "equity" else "UTC_days",
        "machine_dependent": True,
        "tie_policy": "stable rank over sorted symbol identifiers; Spearman average ranks",
        "caveats": [
            "Exploratory screening only; no evidence or promotion authority.",
            "Plain IC t statistics; overlapping outcomes are not corrected.",
            "Trial count is provenance, not PBO, DSR, SPA or a validation verdict.",
            "Cost-adjusted spread combines daily turnover with horizon returns; "
            "no portfolio simulation.",
            "Disappeared bucket names are excluded by turnover; inspect absent_leavers.",
            "Universe membership gates signal formation and warmup; pre-entry history is excluded.",
            "Forward outcomes retain observed prices after ordinary membership exits.",
            "Equity horizons count aligned observed rows; common-calendar gaps are not validated.",
        ],
    }


def _attempt(
    data_dir: Path, *, request: Mapping[str, Any] | None = None, replay_id: str | None = None
) -> dict[str, Any]:
    attempt_id = uuid4().hex
    root = _storage_path(data_dir, "attempts", attempt_id)
    requested = {
        key: repr(value) if isinstance(value, float) and not math.isfinite(value) else value
        for key, value in (request or {}).items()
    }
    _publish(
        root / "started.json",
        {
            "attempt_id": attempt_id,
            "status": "started",
            "started_at": datetime.now(UTC).isoformat(),
            "request": requested if request is not None else None,
            "replay_id": replay_id,
            "authority": "none",
            "incomplete_interpretation": "No finished.json means incomplete, never successful.",
        },
    )
    scan_id = replay_id
    try:
        if replay_id is None:
            assert request is not None
            spec = freeze_spec(data_dir, request)
            scan_id = _digest(spec)
            _publish(_storage_path(data_dir, "specs", f"{scan_id}.json"), spec)
        else:
            if len(replay_id) != 64 or any(char not in "0123456789abcdef" for char in replay_id):
                raise DataError("scan_id must be a lowercase SHA-256 digest")
            path = _storage_path(data_dir, "specs", f"{replay_id}.json")
            try:
                spec = json.loads(path.read_text())
            except (OSError, ValueError) as exc:
                raise DataError("frozen scan specification is unavailable or corrupt") from exc
            if not isinstance(spec, dict) or _digest(spec) != replay_id:
                raise DataError("frozen scan specification integrity failure")
        if spec.get("schema_version") != 1 or spec.get("panel_version") != panel.PANEL_VERSION:
            raise DataError("unsupported frozen scan version")
        identity = runtime_identity()
        if any(spec.get(key) != value for key, value in identity.items()):
            raise DataError(
                "frozen scan code or lock hash differs; replay requires the original environment"
            )
        _publish(
            root / "resolved.json",
            {
                "scan_id": scan_id,
                "attempt_id": attempt_id,
                "planned_trials": len(spec["options"]["signals"])
                * len(spec["options"]["horizons"]),
                "authority": "none",
            },
        )

        def record_trial(index: int, status: str, values: dict[str, Any]) -> None:
            _publish(
                _storage_path(
                    data_dir, "attempts", attempt_id, "trials", f"{index:06d}-{status}.json"
                ),
                {
                    "trial_index": index,
                    "scan_id": scan_id,
                    "attempt_id": attempt_id,
                    "status": status,
                    "authority": "none",
                    **values,
                },
            )

        result = evaluate_spec(data_dir, spec, record_trial)
        result_digest = _digest(result)
        payload = {
            **result,
            "scan_id": scan_id,
            "attempt_id": attempt_id,
            "result_digest": result_digest,
        }
        _publish(root / "result.json", payload)
    except (KeyboardInterrupt, SystemExit) as exc:
        _publish(
            root / "finished.json",
            {
                "attempt_id": attempt_id,
                "scan_id": scan_id,
                "status": "interrupted",
                "error_type": type(exc).__name__,
                "authority": "none",
            },
        )
        raise
    except Exception as exc:
        _publish(
            root / "finished.json",
            {
                "attempt_id": attempt_id,
                "scan_id": scan_id,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "authority": "none",
            },
        )
        raise
    _publish(
        root / "finished.json",
        {
            "attempt_id": attempt_id,
            "scan_id": scan_id,
            "status": "completed",
            "result_digest": result_digest,
            "trials": result["trials"],
            "authority": "none",
        },
    )
    return payload


def run_hypotheses(data_dir: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    return _attempt(data_dir, request=request)


def replay_hypotheses(data_dir: Path, scan_id: str) -> dict[str, Any]:
    return _attempt(data_dir, replay_id=scan_id)


def verified_screening_reference(
    data_dir: Path, scan_id: str, *, attempt_id: str | None = None
) -> dict[str, str]:
    """Verify historical content bindings, returning only non-authoritative identifiers.

    This checks bytes and completion, not scientific correctness or current runtime
    compatibility. It never re-executes a scan or promotes exploratory measurements.
    """
    if len(scan_id) != 64 or any(char not in "0123456789abcdef" for char in scan_id):
        raise DataError("scan_id must be a lowercase SHA-256 digest")

    def read(*parts: str) -> tuple[dict[str, Any], str]:
        path = _storage_path(data_dir, *parts)
        try:
            raw = path.read_bytes()
            value = json.loads(raw)
        except (OSError, ValueError) as exc:
            raise DataError("screening provenance is unavailable or corrupt") from exc
        if not isinstance(value, dict):
            raise DataError("screening provenance must be a JSON object")
        return value, hashlib.sha256(raw).hexdigest()

    spec, spec_hash = read("specs", f"{scan_id}.json")
    if (
        _digest(spec) != scan_id
        or spec.get("authority") != "none"
        or spec.get("schema_version") != 1
    ):
        raise DataError("screening specification integrity failure")
    if attempt_id is None:
        candidates = []
        directory = _storage_path(data_dir, "attempts")
        for path in sorted(directory.glob("*/finished.json")):
            finished, _ = read("attempts", path.parent.name, "finished.json")
            if finished.get("scan_id") == scan_id and finished.get("status") == "completed":
                candidates.append(path.parent.name)
        if len(candidates) != 1:
            raise DataError(
                "provide an explicit attempt_id: expected exactly one completed attempt"
            )
        attempt_id = candidates[0]
    if len(attempt_id) != 32 or any(char not in "0123456789abcdef" for char in attempt_id):
        raise DataError("attempt_id must be a lowercase 32-hex identifier")
    started, _ = read("attempts", attempt_id, "started.json")
    resolved, _ = read("attempts", attempt_id, "resolved.json")
    finished, _ = read("attempts", attempt_id, "finished.json")
    result, result_hash = read("attempts", attempt_id, "result.json")
    if (
        started.get("attempt_id") != attempt_id
        or started.get("status") != "started"
        or finished.get("status") != "completed"
    ):
        raise DataError("screening attempt lacks a matching completion receipt")
    for value in (resolved, finished, result):
        if (
            value.get("attempt_id") != attempt_id
            or value.get("scan_id") != scan_id
            or value.get("authority") != "none"
        ):
            raise DataError("screening attempt provenance binding mismatch")
    digest = _digest(
        {
            key: value
            for key, value in result.items()
            if key not in {"scan_id", "attempt_id", "result_digest"}
        }
    )
    if (
        result.get("result_digest") != digest
        or finished.get("result_digest") != digest
        or result.get("execution_authority") is not False
    ):
        raise DataError("screening result integrity failure")
    return {
        "authority": "none",
        "scan_id": scan_id,
        "spec_sha256": spec_hash,
        "attempt_id": attempt_id,
        "result_sha256": result_hash,
        "result_digest": digest,
    }
