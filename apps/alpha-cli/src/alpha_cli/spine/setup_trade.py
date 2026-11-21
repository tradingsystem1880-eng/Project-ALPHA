"""One counted setup trade study; shared exits for occurrences and controls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from alpha_cli.spine import reserve, setup_context
from alpha_cli.spine.data_health import health_labels
from alpha_cli.spine.errors import SpineError
from alpha_cli.spine.facts import add_study_trial_fact, read_study
from alpha_cli.spine.ledger import append_trial
from alpha_cli.spine.reading import setup_evidence_of
from alpha_cli.spine.setup_controls import (
    RANDOM_DRAWS,
    _comparison,
    _draw_means,
    null_trade_controls,
)
from alpha_cli.spine.setup_costs import SHORT_COST_RULE, asset_costs, daily_carry, round_trip
from alpha_cli.spine.setup_exits import (
    PreparedExits,
    prepare_exits,
    simulate,
    trade_candidates,
    trades_frame,
)
from alpha_cli.spine.setup_find import checked_study_inputs, load_find, outcome_ids
from alpha_cli.spine.setup_reading import extras
from alpha_core import DataError
from alpha_core.atomic import write_text

TRADE_RULE_VERSION = "setup-trade-1"
BASIS = (
    "{direction} trades with frozen trigger-close levels, conservative fills "
    "and per-asset round-trip costs"
)


def trade_controls(
    cache: dict[str, dict[int, Any]],
    chosen: dict[str, list[float]],
    counts: dict[str, int],
    seed: str,
    *,
    tested: bool,
    control_reason: str | None = None,
) -> dict[str, Any]:
    """Exact spaced date sets, then occupancy; asset weights match completed occurrences.

    Tail (b+1)/(m+1): Phipson & Smyth (2010), doi:10.2202/1544-6115.1585.
    """
    import numpy as np

    baseline: list[float] = []
    assets, weights, pooled = {}, [], np.zeros(RANDOM_DRAWS)
    unavailable = control_reason
    all_values = [v for a in sorted(chosen) for v in chosen[a]]
    for asset in sorted(cache):
        values = chosen[asset]
        returns = np.asarray([r["net_return"] for r in cache[asset].values() if r["complete"]])
        means = (
            _draw_means(cache[asset], counts[asset], f"{seed}|{asset}")
            if values and not control_reason
            else None
        )
        if values and means is None:
            unavailable = (
                unavailable
                or "random dates cannot supply a completed mean in every draw, "
                "or spacing is impossible"
            )
        if values and not len(returns):
            unavailable = unavailable or "no eligible completed control trades"
        if values and len(returns):
            baseline.extend(returns)
            weights.extend([len(values) / len(returns)] * len(returns))
        if means is not None:
            pooled += means * len(values)
        # _comparison expects a drift when values exist; use a placeholder then explicitly
        # null every comparison below when the requested control is unavailable.
        drift = returns if len(returns) else np.asarray([0.0])
        result = _comparison(values, (drift, np.ones(len(drift))), means, tested=False)
        if control_reason or not len(returns):
            null_trade_controls(result, control_reason or "no eligible completed control trades")
        assets[asset] = result
    drift = np.asarray(baseline) if baseline else np.asarray([0.0])
    weight = np.asarray(weights) if weights else np.asarray([1.0])
    result = _comparison(
        all_values,
        (drift, weight),
        None if unavailable else pooled / max(1, len(all_values)),
        tested=tested,
    )
    if (
        control_reason
        or not baseline
        or any(chosen[a] and not any(r["complete"] for r in cache[a].values()) for a in cache)
    ):
        null_trade_controls(result, control_reason or "no eligible completed control trades")
    elif unavailable:
        for key in ("random_date_5", "random_date_50", "random_date_95", "random_date_p"):
            result["reasons"][key] = unavailable
    return dict(pooled=result, assets=assets)


def _opposite_control(
    rows: list[dict[str, Any]],
    prepared: dict[str, PreparedExits],
    costs: dict[str, Any],
    direction: str,
    labels: list[str],
) -> dict[str, Any]:
    from alpha_cli.spine.setup_controls import trade_measures

    # Replay exactly the entries the primary side actually opened. Reapplying
    # occupancy on this side would silently change the set of dates.
    mirror = {
        a: replace(p, direction=direction, reflect_levels=True, carry_per_day=daily_carry(costs[a]))
        for a, p in prepared.items()
    }
    trades = [
        simulate(mirror[r["asset"]], r["entry_index"], round_trip(costs[r["asset"]]))
        for r in rows
        if r["exit_index"] is not None
    ]
    measures = trade_measures(trades)
    return dict(
        label="Opposite direction on the same entries (control only, not counted)",
        direction=direction,
        entries=len(trades),
        trades=measures["trades"],
        mean_net_return=measures["mean"],
        mean_r=measures["mean_r"],
        costs=costs,
        labels=labels,
    )


def _summary(
    spec: Any,
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    cache: dict[str, dict[int, Any]],
    trade_id: str,
    control_seed: str,
    costs: dict[str, Any],
    cost_labels: list[str],
    control_reason: str | None,
) -> dict[str, Any]:
    from alpha_cli.spine.setup_controls import (
        trade_evidence,
        trade_labels,
        trade_reading,
        trade_report,
    )

    report = trade_report(rows, cache, control_seed, control_reason)
    primary = report["pooled"]
    labels = trade_labels(manifest, primary, spec, len(cache), len(rows)) + cost_labels
    sentence, outcome = trade_reading(primary, labels)
    direction = spec.exit.direction
    basis = BASIS.format(direction=direction)
    if direction == "short":
        basis += ". " + SHORT_COST_RULE
    fields = dict(
        setup_trades="trades",
        setup_trade_mean_net_return="mean",
        setup_trade_hit_rate="hit_rate",
        setup_trade_mean_bars_held="mean_bars_held",
        setup_trade_excess_over_drift="excess",
        setup_trade_random_date_p="random_date_p",
        setup_trade_mean_r="mean_r",
    )
    facts = [
        dict(
            metric=metric,
            value=primary[field],
            run_id=trade_id,
            basis=basis,
            source=f"summary.json:pooled.{field}",
            labels=labels,
            reason=primary["reasons"].get(field),
        )
        for metric, field in fields.items()
    ]
    return dict(
        trade_id=trade_id,
        find_id=manifest["find_id"],
        spec_sha256=spec.spec_sha256,
        name=spec.setup.name,
        idea=spec.setup.idea,
        assets=list(cache),
        occurrences=len(rows),
        pooled=report["pooled"],
        per_asset=report["assets"],
        labels=labels,
        reading=sentence,
        direction=direction,
        risk_explanation=(
            "A result of +0.4 R means that, risking 1% of the account per trade, "
            "the average trade made 0.4%. No position sizing in currency is simulated."
        ),
        outcome=outcome,
        evidence=trade_evidence(primary, labels),
        facts=facts,
        basis=basis,
        costs=costs,
        controls=dict(
            draws=RANDOM_DRAWS,
            pooling="complete occurrence trade counts per asset; fixed across draws",
            sampling="separate occurrence counts, then one position per asset",
            stability="chronological halves, each against eligible entries in its own years",
        ),
    )


def _publish(
    folder: Path, summary: dict[str, Any], rows: list[dict[str, Any]], manifest: dict[str, Any]
) -> None:
    from alpha_cli.spine.setup_trade_figure import draw_trades

    png = draw_trades(
        rows=rows,
        primary=summary["pooled"],
        direction=summary["direction"],
        title=f"{summary['name']}: {summary['pooled']['trades']} trades from "
        f"{summary['occurrences']} separate occurrences",
    )
    folder.mkdir(parents=True, exist_ok=True)
    trades_frame(rows).write_parquet(folder / "trades.parquet")
    (folder / "trades.png").write_bytes(png)
    write_text(folder / "summary.json", json.dumps(summary, allow_nan=False))
    files = {
        name: dict(
            sha256=hashlib.sha256((folder / name).read_bytes()).hexdigest(),
            size=(folder / name).stat().st_size,
            rows=len(rows) if name.endswith("parquet") else None,
        )
        for name in ("trades.parquet", "summary.json", "trades.png")
    }
    write_text(
        folder / "manifest.json",
        json.dumps(
            dict(
                schema="AlphaSetupTradeV1",
                trade_id=summary["trade_id"],
                find_id=summary["find_id"],
                trade_rule_version=TRADE_RULE_VERSION,
                spec_sha256=summary["spec_sha256"],
                assets=manifest["assets"],
                direction=summary["direction"],
                costs=summary["costs"],
                labels=summary["labels"],
                data_health=summary["data_health"],
                files=files,
            ),
            allow_nan=False,
        ),
    )


@dataclass(frozen=True)
class Inputs:
    """What a trade test reads: the stored find, the bars it may use and the health record."""

    folder: Path
    manifest: dict[str, Any]
    spec: Any
    bars: dict[str, Any]
    spans: dict[str, tuple[int, int | None]]  # control bars [start, stop) per asset
    record: dict[str, Any]
    trade_id: str
    control_seed: str


def read_inputs(
    find_id: str,
    home: Path,
    check_data: bool,
    accept_bad_data: str | None,
    report_time: datetime | None,
) -> Inputs:
    folder, manifest, spec = load_find(home, find_id)
    if spec.exit is None or not any(spec.exit.model_dump(exclude={"direction"}).values()):
        raise SpineError(
            "SPEC_HAS_NO_EXIT",
            "The find's spec has no exit fields.",
            "Add [exit] to the spec, run alpha setup find again, then trade that find.",
        )
    bars, spans, record = checked_study_inputs(
        home,
        manifest,
        spec,
        check_data=check_data,
        accept_bad_data=accept_bad_data,
        report_time=report_time,
    )
    trade_id, control_seed = outcome_ids(manifest, TRADE_RULE_VERSION, record)
    return Inputs(folder, manifest, spec, bars, spans, record, trade_id, control_seed)


def _control_bars(span: tuple[int, int | None], prepared: Any) -> range:
    """Event bars a control trade may start from: the span, the exit warm-up, an entry bar."""
    last = len(prepared.bars) - 1
    stop = last if span[1] is None else min(span[1], last)
    return range(max(span[0], prepared.warmup), stop)


def compute_trade(home: Path, item: Inputs) -> tuple[dict[str, Any], list[Any]]:
    """The summary and trade rows, computed from the stored find. Writes nothing."""
    import polars as pl

    spec, manifest, bars, spans = item.spec, item.manifest, item.bars, item.spans
    direction = spec.exit.direction
    other = "short" if direction == "long" else "long"
    costs, cost_labels = asset_costs(home, list(bars), direction=direction)
    prepared = {
        a: prepare_exits(spec, s, carry_per_day=daily_carry(costs[a])) for a, s in bars.items()
    }
    charges = {a: round_trip(c) for a, c in costs.items()}
    rows = trade_candidates(
        pl.read_parquet(item.folder / "candidates.parquet").to_dicts(), prepared, charges
    )
    cache = {
        a: {p: simulate(s, p + 1, charges[a]) for p in _control_bars(spans[a], s)}
        for a, s in prepared.items()
    }
    reason = next((p.control_reason for p in prepared.values() if p.control_reason), None)
    summary = _summary(
        spec, manifest, rows, cache, item.trade_id, item.control_seed, costs, cost_labels, reason
    )
    control_costs, control_labels = asset_costs(home, list(bars), direction=other)
    summary["controls"]["opposite_direction"] = _opposite_control(
        rows, prepared, control_costs, other, control_labels
    )
    reserve.carry_to_outcome(summary, manifest)
    summary["data_health"] = item.record
    summary["labels"] = [
        label for label in summary["labels"] if not label.startswith("data-health-")
    ] + health_labels(item.record)
    setup_context.annotate(summary, spec, manifest)
    summary["facts"] = [{**fact, "labels": summary["labels"]} for fact in summary["facts"]]
    return summary, rows


def _run(
    find_id: str,
    home: Path,
    check_data: bool,
    accept_bad_data: str | None,
    report_time: datetime | None,
) -> dict[str, Any]:
    item = read_inputs(find_id, home, check_data, accept_bad_data, report_time)
    trade_id, manifest, record = item.trade_id, item.manifest, item.record
    destination = home / "setup-trades" / trade_id
    executed = not (destination / "manifest.json").exists()
    if not executed:
        summary = read_study(destination)
        summary["labels"] = [*summary["labels"], "repeat"]
        summary["facts"] = [{**f, "labels": summary["labels"]} for f in summary["facts"]]
    else:
        summary, rows = compute_trade(home, item)
        add_study_trial_fact(home, summary)
        _publish(destination, summary, rows, manifest)
    primary = summary["pooled"]
    ledger = append_trial(
        home,
        dict(
            kind="setup_trade",
            run_id=trade_id,
            data_health=record,
            **{
                k: summary[k]
                for k in (
                    "trade_id",
                    "find_id",
                    "spec_sha256",
                    "name",
                    "idea",
                    "assets",
                    "labels",
                    "outcome",
                )
            },
            occurrences=primary["trades"],
            mean_net_return=primary["mean"],
            excess_over_drift=primary["excess"],
            random_date_p=primary["random_date_p"],
            evidence=setup_evidence_of(summary)[0],
            verdict=None,
        ),
    )
    return {
        **summary,
        **extras(home, "setup_trade", summary, trade_id),
        "folder": str(destination),
        "trials_total": ledger["total_trials"],
        "executed": executed,
    }


def run_trade(
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
        if isinstance(exc, SpineError):
            raise
        raise SpineError(
            "TRADE_FAILED",
            str(exc),
            "Correct the reported data or trade error, then run alpha setup trade again.",
        ) from exc
