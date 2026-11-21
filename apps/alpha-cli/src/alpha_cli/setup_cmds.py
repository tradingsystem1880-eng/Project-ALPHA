"""Find and inspect daily setups before looking at their outcomes."""

from __future__ import annotations

import json
import sys
from collections import Counter
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from alpha_cli._cli_json import emit
from alpha_cli.spine.contact_sheet import draw_sheet
from alpha_cli.spine.data_health import health_labels, health_sentence
from alpha_cli.spine.errors import SpineError, fail, setup_error
from alpha_cli.spine.ledger import append_trial
from alpha_core import DataError
from alpha_core.atomic import write_text
from alpha_core.config import AlphaSettings

setup_app = typer.Typer(help="Find every match of a chart setup.", no_args_is_help=True)


@setup_app.callback()
def setup_group() -> None:
    """Inspect setup matches before viewing outcomes."""


def _text(output: dict[str, Any]) -> str:
    from alpha_cli.spine import setup_context

    lines = []
    for asset in output["assets"]:
        if asset["error"]:
            lines.append(f"{asset['asset']}: {asset['error']['code']}: {asset['error']['message']}")
        else:
            reasons = ", ".join(f"{k} {v}" for k, v in asset["rejected_by_reason"].items())
            lines.append(
                f"{asset['asset']}: {asset['accepted_clusters']} separate occurrences "
                f"({asset['accepted']} matching days); {asset['pending']} pending; "
                f"rejected: {reasons or 'none'}"
            )
            if asset.get("context"):
                lines.append(setup_context.sentence(asset["context"], asset["asset"]))
    if "repeat" in output["labels"]:
        lines.append(
            "Repeat of an earlier find on the same spec and data: nothing was redrawn "
            f"(its sheets show {output['context_bars']} bars before each event)."
        )
    return "\n".join(
        [
            *lines,
            *([output["reserve_sentence"]] if output.get("reserve_sentence") else []),
            health_sentence(output.get("data_health")),
            output["folder"],
            (
                "Outcomes have been viewed. "
                if "outcomes-viewed" in output["labels"]
                else "Outcomes were not looked at. "
            )
            + "Next: open the sheets; "
            f"measure outcomes with alpha setup study {output['find_id']}.",
        ]
    )


@setup_app.command("find")
def find_command(
    spec: Path,
    asset: Annotated[list[str] | None, typer.Option("--asset", help="Keep a spec asset.")] = None,
    context_bars: int = typer.Option(60, min=5, max=250, help="Bars before the event."),
    max_sheets: int = typer.Option(10, min=1, max=50, help="Maximum accepted sheets."),
    check_data: bool = typer.Option(
        False, "--check-data", help="Compute missing or out-of-date daily health reports."
    ),
    accept_bad_data: str | None = typer.Option(
        None,
        "--accept-bad-data",
        help="Proceed after a failed health check for this run. Give a reason.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit one JSON result object."),
) -> None:
    """Record every match and draw contact sheets ending at the entry open."""
    from alpha_cli.spine.stores import _stores

    home = AlphaSettings().data_dir
    try:
        with redirect_stdout(sys.stderr if json_out else sys.stdout):
            output = run_find(
                spec,
                home=home,
                assets=asset,
                context_bars=context_bars,
                max_sheets=max_sheets,
                check_data=check_data,
                accept_bad_data=accept_bad_data,
            )
    except (DataError, ValueError, OSError) as exc:
        fail(setup_error(exc, list(_stores(home))), json_out)
    emit(output, json_out=json_out, fallback=_text(output))


BASIS = (
    "setup evaluator: decided at each bar's close using bars up to it; entry is the next "
    "bar's open; no outcome after entry was computed"
)
FOOTER = (
    "Bars up to the entry open only. What happened after entry is not shown: "
    "that is a separate, counted step."
)


def _sheets(
    spec: Any,
    frames: dict[str, Any],
    rows: list[dict[str, Any]],
    folder: Path,
    context_bars: int,
    max_sheets: int,
) -> tuple[list[str], dict[str, Any]]:
    from alpha_cli.figures.rdagent_journey_figures import figure_theme
    from alpha_cli.spine.setup_find import sheet_panels

    batches, counts = sheet_panels(spec, frames, rows, context_bars, max_sheets)
    # Only an unfinished find (no manifest) reaches here: drop sheets an interrupted attempt left.
    for stale in sorted((folder / "sheets").glob("*.png")):
        stale.unlink()
    paths = []
    for index, (title, panels) in enumerate(batches, 1):
        mode = panels[0].mode
        path = folder / "sheets" / f"{mode}-{index if mode == 'accepted' else 1:03d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(draw_sheet(panels, title=title, footer=FOOTER, theme=figure_theme(False)))
        paths.append(str(path.relative_to(folder)))
    return paths, counts


def run_find(
    path: Path,
    *,
    home: Path,
    assets: list[str] | None = None,
    context_bars: int = 60,
    max_sheets: int = 10,
    check_data: bool = False,
    accept_bad_data: str | None = None,
    report_time: datetime | None = None,
) -> dict[str, Any]:
    """A find counts one exploratory look; completed folders are never rewritten."""
    import polars as pl

    from alpha_cli.spine import reserve
    from alpha_cli.spine.idea_card import link_fields, note_link, require
    from alpha_cli.spine.setup_find import (
        _counts,
        health_find_id,
        load_spec,
        outcome_labels,
        prepare_assets,
    )

    if not 5 <= context_bars <= 250 or not 1 <= max_sheets <= 50:
        raise ValueError("context-bars must be 5–250 and max-sheets 1–50")
    spec = load_spec(path, assets)
    require(home, spec.idea_card)
    results, candidates, frames, record = prepare_assets(
        spec,
        home,
        assets,
        check_data=check_data,
        accept_bad_data=accept_bad_data,
        report_time=report_time,
    )
    for result, rows in zip((r for r in results if r["error"] is None), candidates, strict=True):
        result.update(_counts(rows))
    if not candidates:
        raise SpineError(
            "FIND_FAILED",
            json.dumps(results),
            "Correct the asset errors and run alpha setup find again.",
        )
    find_id = health_find_id(home, spec.spec_sha256, results, context_bars, record)
    identity = dict(find_id=find_id, spec_sha256=spec.spec_sha256, name=spec.setup.name)
    folder = home / "setups" / find_id
    labels = ["exploratory", "outcomes-not-viewed", "dev-machine-data", "daily-only"]
    held_back = sum(r.get("held_back_bars", 0) for r in results)
    block = {"reserve": reserve.record(held_back)} if held_back else {}
    labels += [*health_labels(record), *sorted({label for r in results for label in r["labels"]})]
    executed = not (folder / "manifest.json").exists()
    if not executed:
        summary = json.loads((folder / "summary.json").read_text())
        manifest = json.loads((folder / "manifest.json").read_text())
        labels = [*summary["labels"], "repeat"]
        sheets, context_bars = manifest["files"]["sheets"], manifest["context_bars"]
    else:
        combined = pl.concat(candidates)
        totals = {
            k: sum(r.get(k, 0) for r in results)
            for k in ("events", "accepted", "pending", "rejected", "clusters", "accepted_clusters")
        }
        totals["rejected_by_reason"] = dict(
            sum((Counter(r.get("rejected_by_reason", {})) for r in results), Counter())
        )
        if totals["pending"]:
            labels.append("pending-at-end")
        sheets, sheet_counts = _sheets(
            spec, frames, combined.to_dicts(), folder, context_bars, max_sheets
        )
        if sheet_counts["accepted_not_drawn"]:
            labels.append("sheets-truncated")
        facts = [
            dict(
                metric=f"setup_{k}",
                value=totals[k],
                run_id=find_id,
                basis=BASIS,
                source=f"summary.json:totals.{k}",
                labels=labels,
                reason=None,
            )
            for k in ("events", "accepted", "pending", "rejected", "clusters", "accepted_clusters")
        ]
        summary = dict(
            **identity,
            data_health=record,
            labels=labels,
            basis=BASIS,
            totals=totals,
            assets=results,
            sheets=sheet_counts,
            facts=facts,
            **block,
        )
        folder.mkdir(parents=True, exist_ok=True)
        write_text(
            folder / "spec.json",
            json.dumps({**spec.model_dump(mode="json"), "spec_sha256": spec.spec_sha256}),
        )
        combined.write_parquet(folder / "candidates.parquet")
        write_text(folder / "summary.json", json.dumps(summary, default=str, allow_nan=False))
        manifest = dict(
            schema="AlphaSetupFindV1",
            **identity,
            data_health=record,
            idea=spec.setup.idea,
            recorded_at=datetime.now(UTC).isoformat(),
            context_bars=context_bars,
            labels=labels,
            assets=results,
            **block,
            **link_fields(home, spec.idea_card),
            files=dict(candidates="candidates.parquet", summary="summary.json", sheets=sheets),
        )
        write_text(folder / "manifest.json", json.dumps(manifest, default=str, allow_nan=False))
    labels = outcome_labels(home, find_id, labels)
    ledger = append_trial(
        home,
        dict(
            kind="setup_find",
            run_id=None,
            **identity,
            data_health=record,
            idea=spec.setup.idea,
            assets=[r["asset"] for r in results],
            labels=labels,
            verdict=None,
            **{
                k: summary["totals"][k]
                for k in ("accepted", "pending", "rejected", "accepted_clusters")
            },
        ),
    )
    note_link(home, spec.idea_card, "setup_find", find_id)
    return dict(
        find_id=find_id,
        **({"reserve_sentence": reserve.sentence(held_back)} if held_back else {}),
        folder=str(folder),
        data_health=record,
        labels=labels,
        context_bars=context_bars,
        trials_total=ledger["total_trials"],
        executed=executed,
        totals=summary["totals"],
        assets=json.loads(json.dumps(results, default=str)),
        sheets=[str((folder / s).relative_to(home)) for s in sheets],
        facts=[{**f, "labels": labels} for f in summary["facts"]],
    )


def _recheck(
    kind: str, find_id: str, check_data: bool, accept_bad_data: str | None, json_out: bool
) -> None:
    """Computed again and compared with the stored result. Writes no ledger row or file."""
    from alpha_cli.spine.recheck_compare import MISMATCH_EXIT
    from alpha_cli.spine.setup_recheck import recheck_study, recheck_trade

    try:
        if check_data:
            raise SpineError(
                "BAD_OPTION",
                "--recheck cannot be used with --check-data: a health report writes a file, "
                "and a recheck writes nothing.",
                "Run alpha data health first, then the command with --recheck.",
            )
        with redirect_stdout(sys.stderr if json_out else sys.stdout):
            run = recheck_study if kind == "study" else recheck_trade
            output = run(find_id, home=AlphaSettings().data_dir, accept_bad_data=accept_bad_data)
    except SpineError as exc:
        fail(exc, json_out)
    found = output["recheck"]
    if found["match"] is None:
        words = f"{found['reason']}. Run `alpha setup {kind} {find_id}` once first."
    elif found["match"]:
        words = f"Computed again in {found['seconds']:.1f} s: the same result as the stored one."
    else:
        words = f"Computed again: a different result ({found['differences_total']} differences)."
        words += "".join(
            f"\n  {d['field']}: stored {d['stored']}, recomputed {d['recomputed']}"
            for d in found["differences"]
        )
    emit(output, json_out=json_out, fallback=words)
    if found["match"] is False:
        raise typer.Exit(MISMATCH_EXIT)


@setup_app.command("study")
def study_command(
    find_id: str,
    check_data: bool = typer.Option(
        False, "--check-data", help="Compute missing or out-of-date daily health reports."
    ),
    accept_bad_data: str | None = typer.Option(
        None,
        "--accept-bad-data",
        help="Proceed after a failed health check for this run. Give a reason.",
    ),
    recheck: bool = typer.Option(
        False,
        "--recheck",
        help="Compute again and compare with the stored result. Writes nothing. "
        "Exit 4 if the two differ.",
    ),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Measure forward returns and honest controls; record one exploratory trial."""
    from alpha_cli.spine.setup_study import run_study
    from alpha_cli.spine.setup_trade_figure import study_text

    if recheck:
        _recheck("study", find_id, check_data, accept_bad_data, json_out)
        return
    try:
        with redirect_stdout(sys.stderr if json_out else sys.stdout):
            output = run_study(
                find_id,
                home=AlphaSettings().data_dir,
                check_data=check_data,
                accept_bad_data=accept_bad_data,
            )
    except SpineError as exc:
        fail(exc, json_out)
    emit(
        output,
        json_out=json_out,
        fallback=study_text(output) + "\n" + health_sentence(output.get("data_health")),
    )


@setup_app.command("trade")
def trade_command(
    find_id: str,
    check_data: bool = typer.Option(
        False, "--check-data", help="Compute missing or out-of-date daily health reports."
    ),
    accept_bad_data: str | None = typer.Option(
        None,
        "--accept-bad-data",
        help="Proceed after a failed health check for this run. Give a reason.",
    ),
    recheck: bool = typer.Option(
        False,
        "--recheck",
        help="Compute again and compare with the stored result. Writes nothing. "
        "Exit 4 if the two differ.",
    ),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Trade recorded occurrences with their exits and matched controls; one counted test."""
    from alpha_cli.spine.setup_trade import run_trade
    from alpha_cli.spine.setup_trade_figure import trade_text

    if recheck:
        _recheck("trade", find_id, check_data, accept_bad_data, json_out)
        return
    try:
        with redirect_stdout(sys.stderr if json_out else sys.stdout):
            output = run_trade(
                find_id,
                home=AlphaSettings().data_dir,
                check_data=check_data,
                accept_bad_data=accept_bad_data,
            )
    except SpineError as exc:
        fail(exc, json_out)
    emit(
        output,
        json_out=json_out,
        fallback=trade_text(output) + "\n" + health_sentence(output.get("data_health")),
    )


@setup_app.command("show")
def show_command(
    run_ids: Annotated[list[str], typer.Argument(help="One or more study or trade ids.")],
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Read stored studies or trades: each evidence word and its place in the setup's family."""
    from alpha_cli.spine.setup_reading import owner_lines, stored_readings

    try:
        readings = stored_readings(AlphaSettings().data_dir, run_ids)
    except SpineError as exc:
        fail(exc, json_out)
    blocks = [
        f"{item['id']}\n" + "\n".join(owner_lines(item))
        if item["evidence"] and item["family"]
        else f"{item['id']}\nNo evidence word or family is stored for this record."
        for item in readings
    ]
    emit({"readings": readings}, json_out=json_out, fallback="\n\n".join(blocks))
