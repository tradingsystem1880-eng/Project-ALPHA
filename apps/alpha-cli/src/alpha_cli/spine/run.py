"""Compose plain rule trials using the existing validation execution and publication seams."""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from alpha_cli import _artifacts, _gauntlet, _runner
from alpha_cli._identity import RunIdentity
from alpha_cli.spine import cost_classes, idea_card, reserve
from alpha_cli.spine.data_health import health_labels, run_health_record, verify_inputs
from alpha_cli.spine.deflation import (
    TrialFamily,
    count_snapshot,
    family_sharpes,
    spine_test_key,
)
from alpha_cli.spine.diagnose import staged_run, write_diagnostics
from alpha_cli.spine.errors import SpineError
from alpha_cli.spine.facts import build_facts, read_json
from alpha_cli.spine.ledger import append_trial, first_same_test, read_trials
from alpha_cli.spine.reading import build_reading, ledger_fields, stored_reading
from alpha_cli.spine.spec import IdeaSpec
from alpha_cli.spine.stores import annualisation, resolve_asset
from alpha_cli.spine.trial_reader import LedgerSnapshot, spine_snapshot
from alpha_cli.validate_cmds import write_validation_run
from alpha_core import Bar, CorporateAction, DataError
from alpha_data.timeframe import DAILY
from alpha_validation.tearsheet import report_to_manifest


def idea_id(spec_hash: str, data_fingerprint: str) -> str:
    """Link the same spec and data across source versions; never a trial-count key."""
    payload = json.dumps([spec_hash, data_fingerprint], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def headline_manifest(out: _gauntlet.GauntletOutput, result: dict[str, Any]) -> dict[str, Any]:
    """Add the evidence caveat to each stored headline, keeping numeric scores intact."""
    if "too-few-trades" not in result["labels"]:
        return {}
    stored = report_to_manifest(out.report)
    headlines = {}
    for key in ("dsr", "verdict"):
        if stored[key] is not None:
            headlines[key] = {
                **stored[key],
                "labels": ["too-few-trades"],
                "sentence": result["sentence"],
            }
    if "verdict" in headlines and "dsr" in headlines:
        headlines["verdict"].update(
            n_trials=headlines["dsr"]["n_trials"],
            trial_basis=headlines["dsr"].get(
                "trial_basis", "no ledger family: counted as one trial"
            ),
        )
    return headlines


def _fields(obj: Any) -> dict[str, Any]:
    """Instance fields of a dataclass, by declared field name."""
    return {field.name: getattr(obj, field.name) for field in dataclasses.fields(obj)}


def assemble_run_spec(
    idea: IdeaSpec,
    symbol: str,
    ppy: int,
    n_bars: int,
    costs: cost_classes.CostRow | None = None,
) -> _runner.RunSpec:
    """Use the minimum strategy warm-up and near-annual folds covering almost all history.

    `costs` is the class row of a `class-default` spec; any other spec keeps its stated costs.
    """
    if idea.context is not None:
        raise DataError("the gated engine is not built yet: a context spec cannot run ungated")
    params = idea.rule.params
    spec = _runner.RunSpec(
        lookback=params.get("lookback", 252),
        skip=params.get("skip", 21),
        vol_window=63,
        target_vol=0.15,
        rebalance_every=1,
        max_leverage=1.0,
        allow_short=False,
        periods_per_year=ppy,
        fee_bps=costs.fee_bps if costs else idea.costs.fee_bps,
        slippage_bps=costs.slippage_bps if costs else idea.costs.slippage_bps,
        starting_cash=1_000_000.0,
        account_type="MARGIN" if "/" in symbol else "CASH",
        train_size=1,
        test_size=1,
        embargo=5,
        anchored=True,
        strategy_name=idea.rule.strategy,
        strategy_params=tuple(sorted((key, float(value)) for key, value in params.items()))
        if idea.rule.kind != "tsmom"
        else (),
        sizing="all_in",
    )
    warmup = spec.min_train
    if n_bars < warmup + 60:
        raise DataError(f"{symbol}: need at least warm-up + 60 bars ({warmup + 60}), got {n_bars}")
    available = n_bars - 1 - warmup - spec.embargo
    return replace(
        spec, train_size=warmup, test_size=available // max(1, math.ceil(available / ppy))
    )


@dataclass(frozen=True)
class Prepared:
    bars: list[Bar]
    dividends: list[CorporateAction]
    spec: _runner.RunSpec
    identity: RunIdentity


def prepare_asset(
    idea: IdeaSpec,
    asset: str,
    home: Path,
    knobs: _gauntlet.GauntletParams,
    result: dict[str, Any],
    *,
    check_data: bool = False,
    accept_bad_data: str | None = None,
    report_time: datetime | None = None,
) -> Prepared:
    resolved = resolve_asset(asset, data_dir=home)
    record = run_health_record(
        [resolved], check_data=check_data, accept_bad_data=accept_bad_data, report_time=report_time
    )
    result["data_health"] = record
    result["labels"].extend(health_labels(record))
    result.update(symbol=resolved.symbol, store=resolved.store_name, source=resolved.source)
    if resolved.defaulted:
        result["labels"].append("source-defaulted")
    held_back = reserve.held_back_count(resolved)
    if held_back:
        result["labels"].append(reserve.HELD_BACK)
        result["reserve"] = reserve.record(held_back)
    bars, snapshot_id = _runner.load_bars(
        resolved.symbol, data_dir=resolved.data_dir, as_of=reserve.CUTOFF
    )
    dividends = _runner.load_dividends(
        resolved.symbol, data_dir=resolved.data_dir, as_of=reserve.CUTOFF
    )
    verify_inputs([resolved], record)
    result.update(
        first_ts=bars[0].ts.isoformat(), last_ts=bars[-1].ts.isoformat(), n_bars=len(bars)
    )
    if (bars[-1].ts - bars[0].ts).total_seconds() < 3 * 365.25 * 86400:
        result["labels"].append("short-history")
    ppy, basis = annualisation([bar.ts for bar in bars], bar_size=DAILY)
    result["periods_per_year"] = ppy
    result["periods_per_year_basis"] = basis
    klass = cost_classes.asset_class(resolved)
    row, assumed = cost_classes.class_row(klass)
    chosen = row if idea.costs_class_default else None
    if chosen is not None:
        result["labels"].append(cost_classes.CLASS_DEFAULT_LABEL)
        if assumed:
            result["labels"].append(cost_classes.ASSUMED_LABEL)
    spec = assemble_run_spec(idea, resolved.symbol, ppy, len(bars), chosen)
    result["costs"] = {
        "line": cost_classes.cost_line(spec.fee_bps, spec.slippage_bps, chosen, assumed),
        "fee_bps": spec.fee_bps,
        "slippage_bps": spec.slippage_bps,
        "asset_class": klass,
        "periods": cost_classes.periods_line(
            ppy, basis, cost_classes.periods_rule_text(klass) if klass else None
        ),
    }
    identity = _runner.run_identity_for(
        {
            "command": "validate",
            "symbol": resolved.symbol,
            "snapshot_id": snapshot_id,
            "research_cutoff": reserve.CUTOFF_DATE if held_back else None,
            **_fields(spec),
            **{key: value for key, value in _fields(knobs).items() if key != "max_workers"},
            "spec_sha256": idea.spec_sha256,
            "source": resolved.source,
            "store": resolved.store_name,
            "labels": result["labels"],
            "data_health": record,
        },
        source_fingerprint=_runner.source_fingerprint(bars, dividends=dividends),
    )
    result["idea_id"] = idea_id(idea.spec_sha256, identity.source_fingerprint)
    result.update(run_id=identity.run_id, run_dir=str(_artifacts.run_dir(home, identity.run_id)))
    return Prepared(bars, dividends, spec, identity)


def _execute(
    idea: IdeaSpec,
    prepared: Prepared,
    home: Path,
    knobs: _gauntlet.GauntletParams,
    test_id: str,
    result: dict[str, Any],
) -> None:
    rdir = Path(result["run_dir"])
    # `repeat` means the same test as an earlier one; `executed` says the engine ran this time.
    result["executed"] = not (rdir / "manifest.json").exists()
    if not result["executed"]:
        manifest = _artifacts.read_manifest(rdir)
        result["labels"].append("repeat")
    else:
        printed = io.StringIO()
        with staged_run(result) as staged_home, contextlib.redirect_stdout(printed):
            manifest = write_run(idea, prepared, home, staged_home, knobs, test_id, result)
        # The report library names the staging folder; say only where the run really is.
        for line in printed.getvalue().splitlines():
            if not line.startswith("HTML report saved to:"):
                print(line)
        print(f"HTML report saved to: {rdir / 'tearsheet.html'}")
    # The same test again after a code change has a new run folder but is still a repeat.
    if "repeat" not in result["labels"] and first_same_test(
        read_trials(home), {**result, "spec_sha256": idea.spec_sha256, "kind": "rule_test"}
    ):
        result["labels"].append("repeat")
    result["labels"] = list(
        dict.fromkeys([*result["labels"], *manifest.get("spine", {}).get("labels", [])])
    )
    result["sentence"] = manifest.get("spine", {}).get("sentence")
    result["idea_id"] = manifest.get("idea_id")
    result["reading"] = stored_reading(manifest, read_json(rdir / "diagnostics.json"))
    verdict = manifest.get("verdict")
    dsr = manifest.get("dsr")
    result.update(
        resized_entries=manifest.get("resized_entries", 0),
        verdict=verdict.get("overall") if isinstance(verdict, dict) else None,
        oos_sharpe=manifest.get("oos_metrics", {}).get("sharpe"),
        dsr=dsr.get("dsr") if isinstance(dsr, dict) else None,
    )
    diagnostics = read_json(rdir / "diagnostics.json")
    result.update(
        flags=diagnostics.get("flags", []),
        benchmark_sharpe=manifest.get("spine", {})
        .get("periods", {})
        .get("full_history", {})
        .get("benchmark", diagnostics.get("benchmark", {}))
        .get("sharpe"),
        variants_evaluated=diagnostics.get("variants_evaluated", 0),
        facts=build_facts(rdir),
    )

    if result.get("reserve"):
        print(reserve.sentence(result["reserve"]["held_back_bars"]))
    if result.get("sentence"):
        print(f"{result['sentence']} [too-few-trades]")
    if result["resized_entries"] > 0:
        print(
            f"{result['asset']}: {result['resized_entries']} cash entries resized to fit "
            "the opening price including fees."
        )


def write_run(
    idea: IdeaSpec,
    prepared: Prepared,
    home: Path,
    staged_home: Path,
    knobs: _gauntlet.GauntletParams,
    test_id: str,
    result: dict[str, Any],
    *,
    snapshot: LedgerSnapshot | None = None,
    figures: bool = True,
) -> dict[str, Any]:
    """Run the gauntlet and publish into ``staged_home``. A recheck gives the ledger as it was
    and no figures (the figure cache lives in the home)."""
    rdir = Path(result["run_dir"])
    if not prepared.dividends:
        result["labels"].append("benchmark-price-only")
    # One point-in-time ledger read per run: the verdict and the diagnostics count the same rows.
    snapshot = snapshot if snapshot is not None else spine_snapshot(home)
    bars, ppy = prepared.bars, prepared.spec.periods_per_year
    current = spine_test_key(
        idea.spec_sha256,
        bars[0].symbol,
        bars[0].ts.isoformat(),
        bars[-1].ts.isoformat(),
        ppy,
        store=result.get("store"),
        data_id=result.get("idea_id"),
    )
    count = count_snapshot(snapshot, idea.rule.kind, current)
    sharpes = family_sharpes(snapshot, count.family_id, ppy, current)
    n = count.prior_trials + count.this_run + count.unknown_rows
    out = _gauntlet.run_gauntlet(
        prepared.bars,
        prepared.spec,
        knobs,
        run_id=prepared.identity.run_id,
        snapshot_id=None,
        dividends=prepared.dividends,
        trial_sharpes=sharpes,
        trial_family=TrialFamily(count.family_id, n, n, len(sharpes) + 1, count.repeats),
    )
    _artifacts.publish_artifact(
        rdir / "spec.json",
        lambda path: path.write_text(
            json.dumps(
                {**idea.model_dump(mode="json"), "spec_sha256": idea.spec_sha256},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            encoding="utf-8",
        ),
    )
    out = write_diagnostics(
        idea,
        prepared.bars,
        prepared.dividends,
        prepared.spec,
        out,
        prepared.identity,
        home,
        result,
        snapshot=snapshot,
    )
    stored = report_to_manifest(out.report)
    stored.update(
        data_health=result["data_health"],
        spine={
            "labels": result["labels"],
            "periods": result.get("periods", {}),
            "costs": result.get("costs"),
        },
    )
    reading = build_reading(stored, read_json(rdir / "diagnostics.json"))
    # Only a held-back run names its cut-off, so every other run keeps its old identity.
    cutoff: dict[str, Any] = {"as_of": reserve.CUTOFF_DATE} if result.get("reserve") else {}
    _, manifest = write_validation_run(
        staged_home,
        prepared.bars,
        prepared.spec,
        out,
        prepared.identity,
        **cutoff,
        extra_manifest={
            **headline_manifest(out, result),
            "reading": reading,
            "data_health": result["data_health"],
            "idea_id": idea_id(idea.spec_sha256, prepared.identity.source_fingerprint),
            "source": result["source"],
            "resized_entries": out.result.resized_entries,
            "spine": {
                "periods": result.pop("periods", {}),
                "sentence": result.get("sentence"),
                "test_id": test_id,
                "spec_sha256": idea.spec_sha256,
                "name": idea.name,
                "idea": idea.idea,
                "rule": idea.rule.model_dump(),
                "store": result["store"],
                "deflation": result.get("deflation"),
                "labels": list(result["labels"]),
                "costs": result.get("costs"),
                "annualisation": {
                    "periods_per_year": prepared.spec.periods_per_year,
                    "basis": result["periods_per_year_basis"],
                },
                "data_period": {
                    "first_ts": prepared.bars[0].ts.isoformat(),
                    "last_ts": prepared.bars[-1].ts.isoformat(),
                },
                "traded_period": {
                    "first_ts": out.oos.oos_timestamps[0].isoformat(),
                    "last_ts": out.oos.oos_timestamps[-1].isoformat(),
                },
                **({"reserve": result["reserve"]} if result.get("reserve") else {}),
                **idea_card.link_fields(home, idea.idea_card),
            },
        },
    )
    if manifest["spine"]["periods"] and figures:
        from alpha_cli.figures_cmds import store_rule_figures

        store_rule_figures(rdir, manifest, home)
    return manifest


def new_result(asset: str, *, quick: bool, no_diagnose: bool) -> dict[str, Any]:
    """The empty result of one asset, before anything is computed."""
    result: dict[str, Any] = dict.fromkeys(
        (
            "symbol",
            "store",
            "source",
            "run_id",
            "run_dir",
            "periods_per_year",
            "verdict",
            "reading",
            "oos_sharpe",
            "benchmark_sharpe",
            "dsr",
            "error",
            "first_ts",
            "last_ts",
            "n_bars",
        )
    )
    result.update(
        asset=asset,
        labels=[
            "all-in",
            "dev-machine-data",
            *(["quick"] if quick else []),
            *(["no-diagnostics"] if no_diagnose else []),
        ],
        flags=[],
        facts=[],
        variants_evaluated=0,
        executed=False,
    )
    return result


def run_idea(
    idea: IdeaSpec,
    *,
    home: Path,
    seed: int = 7,
    quick: bool = False,
    no_diagnose: bool = False,
    check_data: bool = False,
    accept_bad_data: str | None = None,
    report_time: datetime | None = None,
) -> dict[str, Any]:
    """Run assets independently; ledger failures remain fatal rather than losing trial history."""
    idea_card.require(home, idea.idea_card)
    knobs = _gauntlet.GauntletParams(seed=seed)
    if quick:
        knobs = replace(
            knobs, tier1_paths=20, tier2_paths=4, tier3_paths=4, n_resamples=50, max_workers=1
        )
    results: list[dict[str, Any]] = []
    prepared: list[Prepared | None] = []
    for asset in idea.assets:
        result = new_result(asset, quick=quick, no_diagnose=no_diagnose)
        try:
            prepared.append(
                prepare_asset(
                    idea,
                    asset,
                    home,
                    knobs,
                    result,
                    check_data=check_data,
                    accept_bad_data=accept_bad_data,
                    report_time=report_time,
                )
            )
        except SpineError:
            raise
        except (
            Exception
        ) as exc:  # Each asset failure is reported explicitly; other assets continue.
            result["error"] = f"{type(exc).__name__}: {exc}"
            prepared.append(None)
        results.append(result)
    ids = sorted(item.identity.run_id for item in prepared if item is not None)
    test_id = hashlib.sha256((idea.spec_sha256 + "".join(ids)).encode()).hexdigest()[:16]
    total = 0
    for result, item in zip(results, prepared, strict=True):
        if item is not None:
            try:
                _execute(idea, item, home, knobs, test_id, result)
            except SpineError as exc:
                if exc.payload["code"] == "LEDGER_UNREADABLE":
                    raise
                result["error"] = f"{type(exc).__name__}: {exc}"
            except Exception as exc:  # Preserve the failed attempt as well as successful results.
                result["error"] = f"{type(exc).__name__}: {exc}"
        if result["error"] is not None:
            result["labels"].append("error")
        row = append_trial(
            home,
            {
                "kind": "rule_test",
                "test_id": test_id,
                "name": idea.name,
                "idea": idea.idea,
                "spec_sha256": idea.spec_sha256,
                "rule": idea.rule.kind,
                "params": idea.rule.params,
                "costs": idea.costs.model_dump(),
                **ledger_fields(result.get("reading")),
                **{
                    key: value
                    for key, value in result.items()
                    if key
                    not in {"asset", "run_dir", "error", "facts", "reading", "executed", "costs"}
                },
            },
        )
        result["labels"] = row["labels"]
        total = row["total_trials"]
        if item is not None and result["error"] is None:
            idea_card.note_link(home, idea.idea_card, "rule_test", item.identity.run_id)
        for key in ("first_ts", "last_ts", "n_bars"):
            result.pop(key)
    return {
        "test_id": test_id,
        "spec_sha256": idea.spec_sha256,
        "name": idea.name,
        "trials_total": total,
        "results": results,
    }
