"""Counted forward outcomes from immutable, previously detected setup candidates."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from alpha_cli.spine import reserve, setup_context
from alpha_cli.spine.data_health import health_labels
from alpha_cli.spine.errors import SpineError, study_error
from alpha_cli.spine.event_study_figure import draw_event_study
from alpha_cli.spine.facts import add_study_trial_fact, read_study
from alpha_cli.spine.ledger import append_trial
from alpha_cli.spine.reading import setup_evidence_of
from alpha_cli.spine.setup_controls import (
    RANDOM_DRAWS,
    control_summary,
    eligible_returns,
    horizon_summary,
    reading,
    study_evidence,
    study_labels,
)
from alpha_cli.spine.setup_costs import asset_costs, round_trip
from alpha_cli.spine.setup_find import checked_study_inputs, load_find, outcome_ids
from alpha_cli.spine.setup_reading import extras
from alpha_core import DataError
from alpha_core.atomic import write_text

STUDY_RULE_VERSION = "setup-study-2"
BASIS = (
    "separate accepted occurrences from candidates.parquet; recorded next-open entry to "
    "horizon close, price returns less per-asset round-trip costs; no dividends or spec exits; "
    "controls use all post-warm-up eligible dates, pooled by complete occurrence counts"
)


_LEDGER_KEYS = ("study_id", "find_id", "spec_sha256", "name", "idea", "assets") + (
    "primary_horizon",
    "labels",
    "outcome",
)
_CURVE = dict(mean="mean", drift="drift_mean", lower="random_date_5", upper="random_date_95")


def _outcomes(
    candidates: Any, bars: dict[str, Any], horizons: list[int], cost: dict[str, float]
) -> Any:
    import polars as pl

    rows = []
    positions = {a: {b.ts: i for i, b in enumerate(series)} for a, series in bars.items()}
    for candidate in candidates.iter_rows(named=True):
        if candidate["status"] != "accepted" or not candidate["cluster_first"]:
            continue
        asset, price = candidate["symbol"], candidate["entry_price"]
        start = positions[asset][candidate["entry_ts"]]
        series = bars[asset]
        if not math.isfinite(price) or price <= 0 or price != series[start].open:
            raise ValueError(f"{asset}: recorded entry does not match its bar open")
        # Future closes are measured outcomes only; detection is read from the find folder.
        path = [
            series[start + h - 1].close / price - 1 - cost[asset]
            if start + h <= len(series)
            else None
            for h in range(1, max(horizons) + 1)
        ]
        for horizon in horizons:
            end = start + horizon - 1
            complete = end < len(series)
            rows.append(
                dict(
                    asset=asset,
                    candidate_id=candidate["candidate_id"],
                    cluster_id=candidate["cluster_id"],
                    entry_ts=candidate["entry_ts"],
                    entry_price=price,
                    horizon=horizon,
                    exit_ts=series[end].ts if complete else None,
                    exit_price=series[end].close if complete else None,
                    gross_return=series[end].close / price - 1 if complete else None,
                    net_return=path[horizon - 1],
                    complete=complete,
                    net_path=path,
                )
            )
    schema: dict[str, Any] = dict(
        asset=pl.String,
        candidate_id=pl.Int64,
        cluster_id=pl.Int64,
        entry_ts=pl.Datetime("us", "UTC"),
        entry_price=pl.Float64,
        horizon=pl.Int64,
        exit_ts=pl.Datetime("us", "UTC"),
        exit_price=pl.Float64,
        gross_return=pl.Float64,
        net_return=pl.Float64,
        complete=pl.Boolean,
        net_path=pl.List(pl.Float64),
    )
    return pl.DataFrame(rows, schema=schema)


def _summarise(
    spec: Any,
    manifest: dict[str, Any],
    candidates: Any,
    bars: dict[str, Any],
    spans: dict[str, tuple[int, int | None]],
    study_id: str,
    control_seed: str,
    outcomes: Any,
    costs: dict[str, Any],
) -> dict[str, Any]:
    paths = [r for r in outcomes.to_dicts() if r["horizon"] == spec.study.primary]
    reports, curve = {}, dict(mean=[0.0], drift=[0.0], lower=[0.0], upper=[0.0])
    for h in range(1, max(spec.study.horizons) + 1):
        eligible = {
            a: eligible_returns(
                [b.open for b in s],
                [b.close for b in s],
                spans[a][0],
                h,
                round_trip(costs[a]),
                spans[a][1],
            )
            for a, s in bars.items()
        }
        rows = [
            {**r, "net_return": r["net_path"][h - 1], "complete": r["net_path"][h - 1] is not None}
            for r in paths
        ]
        if h in spec.study.horizons:
            times = {a: [s[p + 1].ts for p in eligible[a][0]] for a, s in bars.items()}
            report = horizon_summary(
                rows, eligible, times, f"{control_seed}|{h}", tested=h == spec.study.primary
            )
            reports[str(h)] = report
        else:  # Figure-only bars: the same pooled controls, no halves and no test.
            chosen = {
                a: [r["net_return"] for r in rows if r["asset"] == a and r["complete"]]
                for a in eligible
            }
            report = control_summary(eligible, chosen, f"{control_seed}|{h}|all", tested=False)
        pooled = report["pooled"]
        for key, field in _CURVE.items():
            curve[key].append(pooled[field])
    primary = reports[str(spec.study.primary)]["pooled"]
    labels = study_labels(manifest, primary, paths, bars, spec.study.primary)
    sentence, outcome = reading(primary, spec.study.primary, labels)
    fields = dict(
        occurrences="occurrences",
        mean_net_return="mean",
        median_net_return="median",
        hit_rate="hit_rate",
        excess_over_drift="excess",
        random_date_p="random_date_p",
    )
    facts = [
        dict(
            metric=f"setup_{metric}",
            value=primary[field],
            run_id=study_id,
            basis=f"primary {spec.study.primary} bars; {BASIS}",
            source=f"summary.json:horizons.{spec.study.primary}.pooled.{field}",
            labels=labels,
            reason=primary["reasons"].get(field),
        )
        for metric, field in fields.items()
    ]
    return dict(
        study_id=study_id,
        find_id=manifest["find_id"],
        spec_sha256=spec.spec_sha256,
        name=spec.setup.name,
        idea=spec.setup.idea,
        primary_horizon=spec.study.primary,
        occurrences=len(paths),
        matching_days=sum(candidates["status"] == "accepted"),
        assets=list(bars),
        labels=labels,
        reading=sentence,
        outcome=outcome,
        evidence=study_evidence(primary, labels),
        basis=BASIS,
        horizons=reports,
        facts=facts,
        curve=curve,
        costs=costs,
        controls=dict(
            draws=RANDOM_DRAWS,
            pooling="complete occurrence counts per asset",
            path_basis="each bar uses its complete occurrences and eligible dates",
            stability="chronological halves, each against controls from its own half",
        ),
    )


def _publish(
    folder: Path, summary: dict[str, Any], outcomes: Any, spec: Any, find_manifest: dict[str, Any]
) -> None:
    paths = [r["net_path"] for r in outcomes.to_dicts() if r["horizon"] == spec.study.primary]
    png = draw_event_study(
        paths=[[0.0, *p] for p in paths],
        **summary["curve"],
        horizons=list(spec.study.horizons),
        primary=spec.study.primary,
        title=(
            f"{spec.setup.name}: {summary['occurrences']} separate occurrences "
            f"({summary['matching_days']} matching days)"
        ),
    )
    folder.mkdir(parents=True, exist_ok=True)
    outcomes.write_parquet(folder / "outcomes.parquet")
    (folder / "event-study.png").write_bytes(png)
    write_text(folder / "summary.json", json.dumps(summary, allow_nan=False))
    files = {
        name: dict(
            sha256=hashlib.sha256((folder / name).read_bytes()).hexdigest(),
            size=(folder / name).stat().st_size,
            rows=outcomes.height if name.endswith("parquet") else None,
        )
        for name in ("outcomes.parquet", "summary.json", "event-study.png")
    }
    write_text(
        folder / "manifest.json",
        json.dumps(
            dict(
                schema="AlphaSetupStudyV1",
                study_id=summary["study_id"],
                find_id=summary["find_id"],
                study_rule_version=STUDY_RULE_VERSION,
                spec_sha256=spec.spec_sha256,
                assets=find_manifest["assets"],
                costs=summary["costs"],
                labels=summary["labels"],
                data_health=summary["data_health"],
                files=files,
            ),
            allow_nan=False,
        ),
    )


def _older_rule_study(home: Path, find_id: str) -> bool:
    return any(
        (m := json.loads(p.read_text())).get("find_id") == find_id
        and m.get("study_rule_version") != STUDY_RULE_VERSION
        for p in sorted((home / "setup-studies").glob("*/manifest.json"))
    )


@dataclass(frozen=True)
class Inputs:
    """What a study reads: the stored find, the bars it may use and the health record."""

    folder: Path
    manifest: dict[str, Any]
    spec: Any
    bars: dict[str, Any]
    spans: dict[str, tuple[int, int | None]]  # control bars [start, stop) per asset
    record: dict[str, Any]
    study_id: str
    control_seed: str


def read_inputs(
    find_id: str,
    home: Path,
    check_data: bool,
    accept_bad_data: str | None,
    report_time: datetime | None,
) -> Inputs:
    folder, manifest, spec = load_find(home, find_id)
    if spec.study is None:
        raise SpineError(
            "SPEC_HAS_NO_STUDY",
            "The find's spec has no [study] table.",
            "Add [study] horizons and primary to the spec, "
            "run alpha setup find again, then study that find.",
        )
    bars, spans, record = checked_study_inputs(
        home,
        manifest,
        spec,
        check_data=check_data,
        accept_bad_data=accept_bad_data,
        report_time=report_time,
    )
    study_id, control_seed = outcome_ids(manifest, STUDY_RULE_VERSION, record)
    return Inputs(folder, manifest, spec, bars, spans, record, study_id, control_seed)


def compute_study(home: Path, find_id: str, item: Inputs) -> tuple[dict[str, Any], Any]:
    """The summary and outcomes of a study, computed from the stored find. Writes nothing."""
    import polars as pl

    spec, manifest, bars = item.spec, item.manifest, item.bars
    candidates = pl.read_parquet(item.folder / "candidates.parquet")
    costs, cost_labels = asset_costs(home, list(bars))
    cost = {a: round_trip(c) for a, c in costs.items()}
    outcomes = _outcomes(candidates, bars, sorted(set(spec.study.horizons)), cost)
    summary = _summarise(
        spec,
        manifest,
        candidates,
        bars,
        item.spans,
        item.study_id,
        item.control_seed,
        outcomes,
        costs,
    )
    summary["labels"].extend(cost_labels)
    if _older_rule_study(home, find_id):
        # Same find, different cost assumption: a new look, so it counts as a trial.
        summary["labels"].append("remeasured-new-cost-rule")
        summary["reading"] += (
            " This re-measures an earlier study of the same find under the new per-asset"
            " cost rule; it counts as one more look, not a new idea."
        )
    reserve.carry_to_outcome(summary, manifest)
    summary["data_health"] = item.record
    summary["labels"] = [
        label for label in summary["labels"] if not label.startswith("data-health-")
    ] + health_labels(item.record)
    setup_context.annotate(summary, spec, manifest)
    summary["facts"] = [{**fact, "labels": summary["labels"]} for fact in summary["facts"]]
    return summary, outcomes


def _run(
    find_id: str,
    home: Path,
    check_data: bool,
    accept_bad_data: str | None,
    report_time: datetime | None,
) -> dict[str, Any]:
    item = read_inputs(find_id, home, check_data, accept_bad_data, report_time)
    study_id, spec, manifest, record = item.study_id, item.spec, item.manifest, item.record
    destination = home / "setup-studies" / study_id
    executed = not (destination / "manifest.json").exists()
    if not executed:
        summary = read_study(destination)
        summary["labels"] = [*summary["labels"], "repeat"]
        summary["facts"] = [{**f, "labels": summary["labels"]} for f in summary["facts"]]
    else:
        summary, outcomes = compute_study(home, find_id, item)
        add_study_trial_fact(home, summary)
        _publish(destination, summary, outcomes, spec, manifest)
    primary = summary["horizons"][str(spec.study.primary)]["pooled"]
    ledger = append_trial(
        home,
        dict(
            kind="setup_study",
            run_id=study_id,
            data_health=record,
            **{k: summary[k] for k in _LEDGER_KEYS},
            occurrences=primary["occurrences"],
            mean_net_return=primary["mean"],
            excess_over_drift=primary["excess"],
            random_date_p=primary["random_date_p"],
            evidence=setup_evidence_of(summary)[0],
            verdict=None,
        ),
    )
    return {
        **summary,
        **extras(home, "setup_study", summary, study_id),
        "folder": str(destination),
        "trials_total": ledger["total_trials"],
        "executed": executed,
    }


def run_study(
    find_id: str,
    *,
    home: Path,
    check_data: bool = False,
    accept_bad_data: str | None = None,
    report_time: datetime | None = None,
) -> dict[str, Any]:
    from polars.exceptions import PolarsError

    try:
        return _run(find_id, home, check_data, accept_bad_data, report_time)
    except (ValueError, OSError, DataError, KeyError, TypeError, PolarsError) as exc:
        raise study_error(exc) from exc
