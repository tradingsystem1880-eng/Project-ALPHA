"""Layer A: deterministic platform probes on planted-truth worlds (no LLM).

Each probe builds a world into a throwaway sandbox, drives the public `alpha` CLI, and classifies
what the platform did about the planted property:

  detected                 the platform's verdict/gate reacts to the planted flaw
  disclosed_only           the platform states the limitation but does not act on it
  silent                   the flaw passes without any signal
  capability_absent        no public seam can express or measure the property
  crashed                  unstructured failure (traceback / non-zero exit without a typed error)
  prevented_by_construction the flaw cannot be expressed through the public seam (a strength)
  as_expected / not_as_expected   for calibration probes (FP rate, power, determinism)
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alpha_eval.platform import (
    CliResult,
    analyze_run,
    build_world,
    read_manifest,
    run_alpha,
)
from alpha_eval.stats import wilson

REDUCED = [
    "--tier1-paths",
    "200",
    "--tier2-paths",
    "32",
    "--n-resamples",
    "500",
    "--max-workers",
    "1",
]
# Reference power = P(one-sided 5% t-test on the OOS-length tail) for an independent LONG-ONLY
# 12-1 momentum rule over 200 independent 10y paths (worlds/build.py power --long-only); the
# platform's default ts_momentum is long-only in a CASH account, so this is the fair comparison.
STRONG_TREND = {"mu": 0.0035, "switch_p": 0.004}  # long-only reference power 0.72 (long/short 0.96)
WEAK_TREND = {"mu": 0.001, "switch_p": 0.004}  # long-only reference power 0.22 -> "insufficient"


@dataclass
class ProbeResult:
    id: str
    title: str
    truth: str
    expected: str
    classification: str
    detail: str
    metrics: dict[str, Any] = field(default_factory=dict)
    runs: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProbeContext:
    workdir: Path
    seeds: int = 20
    parallel: int = 6

    def sandbox(self, name: str) -> tuple[Path, Path]:
        base = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=self.workdir))
        return base / "sb", base / "truth.json"


def _world(ctx: ProbeContext, name: str, symbols: list[dict[str, Any]], seed: int, **extra: Any):  # type: ignore[no-untyped-def]
    sb, truth_path = ctx.sandbox(f"{name}-s{seed}")
    spec = {"name": name, "symbols": symbols, **extra}
    truth = build_world(spec, sb, truth_path, seed)
    return sb, truth


def _validate(sb: Path, symbol: str, *extra: str) -> tuple[CliResult, dict[str, Any] | None]:
    res = run_alpha(sb, ["validate", symbol, *extra, *REDUCED])
    manifest = read_manifest(sb, res.run_id) if res.run_id else None
    return res, manifest


def _vsum(sb: Path, symbol: str, *extra: str) -> dict[str, Any]:
    """validate + summary including independent order-denial accounting."""
    res, m = _validate(sb, symbol, *extra)
    return _summ(res, m, sb)


def _summ(res: CliResult, m: dict[str, Any] | None, sb: Path | None = None) -> dict[str, Any]:
    if m is None:
        return {
            "returncode": res.returncode,
            "stderr_tail": res.stderr[-600:],
            "seconds": res.seconds,
        }
    extra: dict[str, Any] = {}
    if sb is not None:
        stats = analyze_run(sb / "runs" / m["run_id"])
        extra = {
            k: stats.get(k) for k in ("orders", "orders_denied", "orders_filled", "top5_share")
        }
    return {
        **extra,
        "run_id": m["run_id"],
        "passed": m["passed"],
        "grade": m["verdict"]["overall"],
        "oos_sharpe": m["oos_metrics"]["sharpe"],
        "null_pct": [n["percentile"] for n in m["nulls"]],
        "dsr": m["dsr"]["dsr"],
        "dsr_n_trials": m["dsr"]["n_trials"],
        "ci_lower": m["cis"][0]["lower"],
        "cpcv_frac_pos": m["cpcv"]["frac_positive"],
        "gates": {o["name"]: o["passed"] for o in m["outcomes"]}
        if "name" in m["outcomes"][0]
        else {},
        "seconds": res.seconds,
    }


def _map(ctx: ProbeContext, fn: Callable[[int], dict[str, Any]], n: int) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=ctx.parallel) as pool:
        return list(pool.map(fn, range(1, n + 1)))


# --------------------------------------------------------------------------------------------
# Calibration probes


def p01_null_fp(ctx: ProbeContext) -> ProbeResult:
    def one(seed: int) -> dict[str, Any]:
        sb, _ = _world(ctx, "null", [{"symbol": "NULL", "family": "null"}], seed)
        return _vsum(sb, "NULL")

    runs = _map(ctx, one, ctx.seeds)
    fp = sum(1 for r in runs if r.get("passed"))
    lo, hi = wilson(fp, len(runs))
    good_grades = sum(1 for r in runs if r.get("grade") in {"A", "B"})
    return ProbeResult(
        "P01",
        "Null-world false-positive rate of the validation gauntlet",
        "Zero-drift random walk: no edge exists.",
        "Gauntlet PASS rate <= 5% (nominal); verdict grade should not look strong.",
        "as_expected" if hi <= 0.2 and fp / len(runs) <= 0.1 else "not_as_expected",
        f"{fp}/{len(runs)} null worlds PASSED (Wilson 95% [{lo:.3f},{hi:.3f}]); "
        f"{good_grades} received an A/B verdict grade despite no edge.",
        {"fp": fp, "n": len(runs), "wilson": [lo, hi], "ab_grades_on_null": good_grades},
        runs,
    )


def _power(
    ctx: ProbeContext, pid: str, params: dict[str, float], label: str, ref: float
) -> ProbeResult:
    def one(seed: int) -> dict[str, Any]:
        sb, truth = _world(
            ctx, f"trend{pid}", [{"symbol": "TRND", "family": "trend", "params": params}], seed
        )
        out = _vsum(sb, "TRND")
        out["reference_sharpe"] = truth["symbols"]["TRND"]["reference_ts_momentum"]["ann_sharpe"]
        return out

    runs = _map(ctx, one, ctx.seeds)
    hits = sum(1 for r in runs if r.get("passed"))
    lo, hi = wilson(hits, len(runs))
    fails = [r for r in runs if not r.get("passed")]
    blocking: dict[str, int] = {}
    for r in fails:
        for gate, ok in r.get("gates", {}).items():
            if not ok:
                blocking[gate] = blocking.get(gate, 0) + 1
    denied_runs = [r for r in runs if (r.get("orders_denied") or 0) > 0]
    errored = [r for r in runs if "returncode" in r]
    if pid == "P02":
        cls = "as_expected" if hits / len(runs) >= 0.5 else "not_as_expected"
    else:
        cls = "as_expected" if hits / len(runs) <= ref + 0.2 else "not_as_expected"
    return ProbeResult(
        pid,
        f"Planted {label} trend edge: gauntlet power",
        f"Markov-switching drift {params}; independent long-only reference momentum power ~{ref:.2f}.",
        "Power broadly consistent with the reference; failing gates attributable.",
        cls,
        f"{hits}/{len(runs)} PASS (Wilson [{lo:.3f},{hi:.3f}]) vs reference power {ref:.2f}. "
        f"Blocking gates among failures: {blocking}. {len(denied_runs)}/{len(runs)} runs had "
        f"DENIED orders (silently dropped by the engine; not surfaced in the verdict); "
        f"{len(errored)} runs aborted with an engine error. "
        "The gauntlet has no 'insufficient evidence / underpowered' verdict distinct from FAIL.",
        {
            "power": hits / len(runs),
            "wilson": [lo, hi],
            "reference_power": ref,
            "blocking": blocking,
            "runs_with_denied_orders": len(denied_runs),
            "errored_runs": len(errored),
            "power_excluding_denied_or_errored": (
                sum(1 for r in runs if r.get("passed") and not r.get("orders_denied"))
                / max(1, len(runs) - len(denied_runs) - len(errored))
            ),
        },
        runs,
    )


def p02_power(ctx: ProbeContext) -> ProbeResult:
    return _power(ctx, "P02", STRONG_TREND, "strong", 0.72)


def p02w_weak(ctx: ProbeContext) -> ProbeResult:
    return _power(ctx, "P02w", WEAK_TREND, "weak (underpowered)", 0.22)


def p16_determinism(ctx: ProbeContext) -> ProbeResult:
    sb, _ = _world(ctx, "det", [{"symbol": "DETR", "family": "trend", "params": STRONG_TREND}], 3)
    a, ma = _validate(sb, "DETR")
    b, mb = _validate(sb, "DETR")
    same = bool(
        ma
        and mb
        and a.run_id == b.run_id
        and json.dumps(ma, sort_keys=True) == json.dumps(mb, sort_keys=True)
    )
    return ProbeResult(
        "P16",
        "Run identity and manifest determinism",
        "Identical config + data must yield the same content-addressed run.",
        "Same run id and byte-identical manifest.",
        "as_expected" if same else "not_as_expected",
        f"run ids {a.run_id} / {b.run_id}; manifests identical={same}",
        {"identical": same},
    )


def p17_mc_stability(ctx: ProbeContext) -> ProbeResult:
    """Same data, same strategy: does the verdict depend on the Monte Carlo seed/path count?"""
    sb, _ = _world(ctx, "stab", [{"symbol": "STAB", "family": "trend", "params": STRONG_TREND}], 1)
    runs = []
    for seed in range(1, 11):
        res = run_alpha(sb, ["validate", "STAB", "--seed", str(seed), *REDUCED])
        m = read_manifest(sb, res.run_id) if res.run_id else None
        runs.append({"mc_seed": seed, **_summ(res, m)})
    for t1, t2 in ((100, 16), (1000, 64)):
        args = [
            "validate",
            "STAB",
            "--tier1-paths",
            str(t1),
            "--tier2-paths",
            str(t2),
            "--n-resamples",
            "500",
            "--max-workers",
            "2",
        ]
        res = run_alpha(sb, args)
        m = read_manifest(sb, res.run_id) if res.run_id else None
        runs.append({"paths": [t1, t2], **_summ(res, m)})
    verdicts = [r.get("passed") for r in runs]
    mixed = len({v for v in verdicts if v is not None}) > 1
    return ProbeResult(
        "P17",
        "Verdict stability under Monte Carlo seed and null path count",
        "Identical data and strategy; only the null-simulation seed / path count changes.",
        "A verdict that does not flip on simulation noise, or a reported Monte Carlo standard error.",
        "not_as_expected" if mixed else "as_expected",
        f"PASS pattern over 10 MC seeds + 2 path budgets: {verdicts}; null percentiles "
        f"{[r.get('null_pct') for r in runs]}. No Monte Carlo standard error is reported next to "
        "the 0.95 percentile threshold.",
        {"verdicts": verdicts, "mixed": mixed},
        runs,
    )


# --------------------------------------------------------------------------------------------
# Selection / multiple testing


def p03_best_of_k(ctx: ProbeContext) -> ProbeResult:
    lookbacks = [20, 40, 60, 80, 100, 126, 150, 189, 220, 252]
    worlds = max(3, ctx.seeds // 4)

    def one(seed: int) -> dict[str, Any]:
        sb, _ = _world(ctx, "null", [{"symbol": "SRCH", "family": "null"}], 100 + seed)
        per = []
        for lb in lookbacks:
            skip = min(21, lb // 4)
            per.append(_summ(*_validate(sb, "SRCH", "--lookback", str(lb), "--skip", str(skip))))
        best = max(per, key=lambda r: r.get("oos_sharpe", float("-inf")))
        return {
            "any_passed": any(r.get("passed") for r in per),
            "best": best,
            "n_tried": len(per),
            "passes": sum(1 for r in per if r.get("passed")),
        }

    runs = _map(ctx, one, worlds)
    any_pass = sum(1 for r in runs if r["any_passed"])
    trials_seen = {r["best"].get("dsr_n_trials") for r in runs}
    return ProbeResult(
        "P03",
        "Best-of-K repeated validate on a null world (selection across runs)",
        f"Null world; the researcher runs validate over {len(lookbacks)} lookbacks and keeps the best.",
        "Each validate run is deflated for prior attempts on the same data (n_trials > 1).",
        "silent" if trials_seen == {1} else "detected",
        f"{any_pass}/{len(runs)} null worlds produced at least one PASS among {len(lookbacks)} "
        f"tries; the best run's DSR n_trials values = {sorted(trials_seen)} — the gauntlet does not "
        "know about sibling attempts on the same symbol.",
        {
            "worlds_with_a_pass": any_pass,
            "n_worlds": len(runs),
            "best_n_trials": sorted(trials_seen),
        },
        runs,
    )


def p04_optim_failed_trials(ctx: ProbeContext) -> ProbeResult:
    sb, _ = _world(ctx, "null", [{"symbol": "OPTM", "family": "null"}], 11)
    res = run_alpha(
        sb,
        [
            "optim",
            "grid",
            "OPTM",
            "--grid",
            "lookback=20,60,120,252,700",
            "--n-resamples",
            "300",
            "--max-workers",
            "2",
        ],
    )
    run_id = res.run_id
    if not run_id:
        return ProbeResult(
            "P04",
            "Optim deflation vs failed trials",
            "",
            "",
            "crashed",
            res.stderr[-800:],
            runs=[{"stdout": res.stdout[-800:]}],
        )
    m = read_manifest(sb, run_id, "optim")
    keys = {k: m[k] for k in m if any(t in k for t in ("config", "trial", "n_"))}
    configs = m.get("configs") or m.get("trials") or []
    n_total = len(configs) if isinstance(configs, list) else None
    dsr_block = m.get("dsr", {})
    n_trials = dsr_block.get("n_trials") if isinstance(dsr_block, dict) else None
    detected = n_total is not None and n_trials is not None and n_trials >= n_total
    return ProbeResult(
        "P04",
        "Optim grid: do failed/rejected configs count toward deflation?",
        "5 configs requested on a null world; lookback=700 cannot warm up on the training window.",
        "Deflation trial count covers every attempted config (or discloses the exclusion).",
        "detected" if detected else "silent",
        f"configs listed={n_total}, DSR n_trials={n_trials}; manifest count fields={keys}",
        {"n_configs": n_total, "dsr_n_trials": n_trials},
        [{"run_id": run_id, "stdout": res.stdout[-600:]}],
    )


def p11_screen_best_of_many(ctx: ProbeContext) -> ProbeResult:
    syms = [f"N{i:02d}" for i in range(20)]
    sb, _ = _world(
        ctx,
        "nullpanel",
        [{"symbol": s, "family": "null"} for s in syms],
        21,
        snapshots=[{"id": "panel", "symbols": syms, "created_at": "2026-09-26T00:00:00+00:00"}],
    )
    res = run_alpha(
        sb,
        [
            "scan",
            "hypotheses",
            "--as-of",
            "2026-09-25",
            "--snapshot",
            "panel",
            "--symbols",
            ",".join(syms),
            "--json",
        ],
    )
    if res.returncode != 0:
        return ProbeResult(
            "P11",
            "Screening best-of-many on a null panel",
            "",
            "",
            "crashed",
            (res.stderr or res.stdout)[-1200:],
        )
    payload = res.json()
    disclosed = payload.get("selection_adjustment") == "not_performed"
    tstats = [r["ic"]["t_stat"] for r in payload["results"] if r["ic"].get("t_stat") is not None]
    sig = [r for r in payload["results"] if abs(r["ic"].get("t_stat") or 0.0) > 1.96]
    text = json.dumps({k: v for k, v in payload.items() if k != "results"})
    return ProbeResult(
        "P11",
        "Screening lane: best-of-many signals on a null panel",
        "20 zero-edge names; every screened signal x horizon is noise.",
        "Selection-adjusted significance, or at least explicit disclosure that none was applied.",
        "disclosed_only" if disclosed else "silent",
        f"{len(sig)}/{len(tstats)} signal x horizon cells have |IC t| > 1.96 on pure noise "
        f"(plain t, overlapping outcomes uncorrected per caveats); selection_adjustment="
        f"{payload.get('selection_adjustment')}; caveats disclosed={disclosed}.",
        {
            "disclosed": disclosed,
            "n_cells": len(tstats),
            "nominal_hits": len(sig),
            "max_abs_t": max((abs(t) for t in tstats), default=None),
            "hits": [(r["signal"], r["horizon"], r["ic"]["t_stat"]) for r in sig],
        },
        [{"payload_head": text[:3000]}],
    )


# --------------------------------------------------------------------------------------------
# Economic realism


def p05_cost_cliff(ctx: ProbeContext) -> ProbeResult:
    sb, truth = _world(
        ctx, "ar1", [{"symbol": "REVR", "family": "ar1", "params": {"phi": -0.15}}], 5
    )
    base = [
        "--strategy",
        "mean_reversion",
        "--param",
        "window=5",
        "--param",
        "entry_z=1.0",
        "--rebalance-every",
        "1",
    ]
    runs = []
    for fee, slip in ((0, 0), (1, 2), (5, 10), (10, 20)):
        res, m = _validate(sb, "REVR", *base, "--fee-bps", str(fee), "--slippage-bps", str(slip))
        out = _summ(res, m)
        out["cost_bps_one_way"] = fee + slip
        if m:
            text = json.dumps(m)
            out["mentions_breakeven"] = "break_even" in text or "breakeven" in text
            out["mentions_cost_sensitivity"] = "cost_sensitivity" in text
        runs.append(out)
    sharpe = [r.get("oos_sharpe") for r in runs]
    disclosed = any(r.get("mentions_breakeven") or r.get("mentions_cost_sensitivity") for r in runs)
    return ProbeResult(
        "P05",
        "Cost cliff: high-turnover mean reversion",
        "AR(1) phi=-0.15 daily returns; gross edge that should erode quickly with realistic costs.",
        "The run reports cost sensitivity / break-even cost rather than a single-cost verdict.",
        "disclosed_only" if disclosed else "capability_absent",
        f"OOS Sharpe by one-way cost 0/3/15/30 bps: {sharpe}; passed: "
        f"{[r.get('passed') for r in runs]}; any break-even/cost-sensitivity field: {disclosed}.",
        {"sharpe_by_cost": sharpe},
        runs,
    )


def p06_regime(ctx: ProbeContext) -> ProbeResult:
    sb, _ = _world(
        ctx,
        "regime",
        [
            {"symbol": "FULL", "family": "trend", "params": STRONG_TREND},
            {"symbol": "HALF", "family": "regime_half", "params": {**STRONG_TREND, "frac": 0.45}},
        ],
        8,
    )
    full = _summ(*_validate(sb, "FULL"))
    res, m = _validate(sb, "HALF")
    half = _summ(res, m)
    fold_sharpes = [f["oos_sharpe"] or 0.0 for f in m["folds"]] if m else []
    k = len(fold_sharpes)
    early = sum(fold_sharpes[: k // 2]) / max(1, k // 2) if k else 0.0
    late = sum(fold_sharpes[k // 2 :]) / max(1, k - k // 2) if k else 0.0
    flagged = m is not None and ("regime" in json.dumps(m.get("outcomes", [])).lower())
    return ProbeResult(
        "P06",
        "Regime-conditional edge (edge in first 45% of sample only)",
        "Planted trend edge that disappears permanently after 45% of the sample.",
        "A stability/regime gate flags that recent folds have no edge (or the verdict degrades).",
        "detected" if flagged or (half.get("passed") is False and full.get("passed")) else "silent",
        f"FULL passed={full.get('passed')} sharpe={full.get('oos_sharpe')}; HALF passed="
        f"{half.get('passed')} sharpe={half.get('oos_sharpe')}, grade={half.get('grade')}; "
        f"mean fold Sharpe early={early:.2f} late={late:.2f}; regime-specific gate present={flagged}.",
        {"early_fold_sharpe": early, "late_fold_sharpe": late},
        [full, half],
    )


def p07_concentration(ctx: ProbeContext) -> ProbeResult:
    sb, truth = _world(
        ctx, "jumps", [{"symbol": "JUMP", "family": "jumps", "params": {"k": 5, "size": 0.18}}], 4
    )
    res, m = _validate(sb, "JUMP", "--lookback", "126", "--skip", "5")
    out = _summ(res, m)
    stats = analyze_run(sb / "runs" / m["run_id"]) if m else {}
    flagged = bool(m) and "concentration" in json.dumps(m).lower()
    return ProbeResult(
        "P07",
        "Return concentration: result driven by a handful of days",
        "Null walk plus 5 isolated +18% jump days.",
        "Run flags top-k day concentration (drop-the-best / contribution check).",
        "detected" if flagged else "capability_absent",
        f"passed={out.get('passed')} grade={out.get('grade')} sharpe={out.get('oos_sharpe')}; "
        f"independent top-5-day share of OOS log return={stats.get('top5_share')}; "
        f"platform concentration field present={flagged}.",
        {
            "top5_share": stats.get("top5_share"),
            "world_top5_share": truth["symbols"]["JUMP"]["top5_share"],
        },
        [out],
    )


def p10_beta(ctx: ProbeContext) -> ProbeResult:
    sb, _ = _world(
        ctx,
        "beta",
        [
            {"symbol": "MKTX", "family": "drift", "params": {"mu": 0.0005, "sigma": 0.01}},
            {
                "symbol": "LEVR",
                "family": "beta",
                "market": "MKTX",
                "params": {"b": 1.3, "idio": 0.006},
            },
        ],
        6,
    )
    res, m = _validate(sb, "LEVR")
    out = _summ(res, m)
    stats = (
        analyze_run(sb / "runs" / m["run_id"], sb / "store" / "bars" / "MKTX.parquet") if m else {}
    )
    gate = m is not None and any(
        "bench" in json.dumps(o).lower() or "beta" in json.dumps(o).lower()
        for o in m.get("outcomes", [])
    )
    return ProbeResult(
        "P10",
        "Beta masquerading as alpha",
        "LEVR = 1.3 x a drifting market + noise; no timing skill exists.",
        "A benchmark-relative (alpha) gate rejects or discloses that returns are beta.",
        "detected" if gate else "capability_absent",
        f"passed={out.get('passed')} grade={out.get('grade')} sharpe={out.get('oos_sharpe')}; "
        f"independent regression on market: beta={stats.get('beta')}, alpha t={stats.get('alpha_t')}; "
        f"benchmark/beta gate in outcomes={gate} (a benchmark_comparison artifact exists but is not gated).",
        stats,
        [out],
    )


# --------------------------------------------------------------------------------------------
# Data integrity


def p09_bad_data(ctx: ProbeContext) -> ProbeResult:
    sb, _ = _world(
        ctx,
        "bad",
        [
            {"symbol": "DISO", "family": "disordered"},
            {"symbol": "NANX", "family": "nonfinite"},
            {"symbol": "SPIK", "family": "spike"},
        ],
        9,
    )
    out: dict[str, Any] = {}
    for sym in ("DISO", "NANX", "SPIK"):
        res, m = _validate(sb, sym)
        out[sym] = {
            "validate": _summ(res, m),
            "traceback": "Traceback" in res.stderr,
            "typed_usage_error": res.returncode == 2 and "Traceback" not in res.stderr,
            "stderr_tail": res.stderr[-400:],
        }
    # No symbol-level data-quality command exists: `alpha data audit` takes PROVIDER RECEIPT_ID,
    # so data written outside a provider pull is never quality-checked before research use.
    audit_help = run_alpha(sb, ["data", "audit", "--help"]).stdout
    diso_ok = out["DISO"]["typed_usage_error"]
    nan_typed = out["NANX"]["typed_usage_error"]
    spike_flag = "passed" not in out["SPIK"]["validate"] or bool(
        m and "outlier" in json.dumps(m).lower()
    )
    cls = (
        "crashed"
        if out["NANX"]["traceback"]
        else ("detected" if nan_typed and spike_flag else "silent")
    )
    return ProbeResult(
        "P09",
        "Corrupt data: disordered rows, non-finite close, 10x bad print",
        "Three corrupted symbols written to the store (disordered/NaN bypass the write contract).",
        "Typed fail-loud errors (exit 2, DataError) and audit flags; never a silent result.",
        cls,
        f"DISO validate={out['DISO']['validate'].get('passed', out['DISO']['validate'].get('returncode'))}; "
        f"NANX traceback={out['NANX']['traceback']} rc={out['NANX']['validate'].get('returncode')}; "
        f"SPIK validate passed={out['SPIK']['validate'].get('passed')} audit flags spike={spike_flag}; "
        f"disordered handled={diso_ok}",
        {
            "nan_typed_error": nan_typed,
            "spike_flagged": spike_flag,
            "disordered_typed": diso_ok,
            "symbol_level_audit": "RECEIPT" not in audit_help,
        },
        [out],
    )


def p08_survivorship(ctx: ProbeContext) -> ProbeResult:
    syms = [f"S{i:02d}" for i in range(12)]
    dead = syms[:4]
    symbols = []
    for s in syms:
        if s in dead:
            symbols.append({"symbol": s, "family": "drift", "params": {"mu": -0.0015}, "n": 1400})
        else:
            symbols.append({"symbol": s, "family": "drift", "params": {"mu": 0.0003}})
    rows = [
        {
            "symbol": s,
            "effective_to": "2022-06-10" if s in dead else "",
            "delisting_return": "-0.9" if s in dead else "",
            "reason": "delisted" if s in dead else "",
        }
        for s in syms
    ]
    sb, _ = _world(
        ctx,
        "surv",
        symbols,
        12,
        snapshots=[{"id": "all", "symbols": syms, "created_at": "2026-09-26T00:00:00+00:00"}],
        universe={"name": "pit", "rows": rows},
    )
    imp = run_alpha(
        sb, ["data", "universe", "import", "pit", str(sb / "inputs" / "pit.csv"), "--json"]
    )
    common = [
        "scan",
        "hypotheses",
        "--as-of",
        "2026-09-25",
        "--snapshot",
        "all",
        "--json",
        "--horizons",
        "21",
        "--min-names",
        "5",
    ]
    with_pit = run_alpha(sb, [*common, "--universe", "pit"])
    survivors = run_alpha(sb, [*common, "--symbols", ",".join(syms[4:])])

    def spreads(res: CliResult) -> dict[str, float]:
        if res.returncode != 0:
            return {}
        return {r["signal"]: r["quantiles"]["spread"] for r in res.json()["results"]}

    pit_s, surv_s = spreads(with_pit), spreads(survivors)
    xs = run_alpha(sb, ["backtest", "cross-sectional", "--help"])
    xs_has_universe = "--universe" in xs.stdout
    return ProbeResult(
        "P08",
        "Survivorship: PIT universe vs survivor-only list",
        "4 of 12 names decline then delist in June 2022 (delisting return -90%).",
        "Screening honours PIT membership when given; backtests cannot silently use survivors.",
        "capability_absent" if not xs_has_universe else "detected",
        f"universe import rc={imp.returncode}; scan with PIT rc={with_pit.returncode}; survivor-only "
        f"scan rc={survivors.returncode} (accepted without warning={survivors.returncode == 0 and 'surviv' not in survivors.stdout.lower()}); "
        f"`backtest cross-sectional` has a --universe option={xs_has_universe}.",
        {"xs_universe_option": xs_has_universe, "spread_pit": pit_s, "spread_survivors": surv_s},
        [
            {
                "pit": with_pit.stderr[-800:],
                "survivors": survivors.stderr[-800:],
                "import": imp.stdout[:400] or imp.stderr[-400:],
            }
        ],
    )


def p13_p14_static(_: ProbeContext) -> list[ProbeResult]:
    return [
        ProbeResult(
            "P13",
            "Leaky strategy (look-ahead inside a signal)",
            "A user-defined signal reading future bars.",
            "Impossible through the public seam.",
            "prevented_by_construction",
            "Rule strategies are stateless over a fixed trailing window of closes/highs/lows "
            "(packages/alpha-strategies/src/alpha_strategies/rules.py); registered strategies read "
            "through as_of; bias guards cover each unit. Agent-introduced look-ahead is tested in "
            "Layer B (ADV01).",
            evidence=["packages/alpha-strategies/src/alpha_strategies/rules.py:1-20"],
        ),
        ProbeResult(
            "P14",
            "ML label leak (feature equals shifted target)",
            "A feature that is the future label.",
            "Impossible through the public seam.",
            "prevented_by_construction",
            "The ML feature recipe is fixed (alpha158) with available_at stamping and per-fold "
            "purge/embargo, and results return through a hash-locked worker exchange. There is also "
            "no target-permutation leakage test, so a leak introduced upstream of the recipe would "
            "not be detected — recorded as a gap, not a pass.",
            evidence=[
                "apps/alpha-cli/src/alpha_cli/ml_input.py:244",
                "workers/qlib/src/alpha_qlib_worker/contract.py:273",
            ],
        ),
    ]


PROBES: dict[str, Callable[[ProbeContext], ProbeResult]] = {
    "P01": p01_null_fp,
    "P02": p02_power,
    "P02w": p02w_weak,
    "P03": p03_best_of_k,
    "P04": p04_optim_failed_trials,
    "P05": p05_cost_cliff,
    "P06": p06_regime,
    "P07": p07_concentration,
    "P08": p08_survivorship,
    "P09": p09_bad_data,
    "P10": p10_beta,
    "P11": p11_screen_best_of_many,
    "P16": p16_determinism,
    "P17": p17_mc_stability,
}


def run_probes(ctx: ProbeContext, ids: list[str] | None = None) -> list[ProbeResult]:
    selected = ids or list(PROBES)
    results: list[ProbeResult] = []
    for pid in selected:
        try:
            results.append(PROBES[pid](ctx))
        except Exception as exc:  # a probe fault is reported as harness-invalid, never hidden
            results.append(
                ProbeResult(pid, pid, "", "", "harness_invalid", f"{type(exc).__name__}: {exc}")
            )
    if ids is None:
        results.extend(p13_p14_static(ctx))
    return results
