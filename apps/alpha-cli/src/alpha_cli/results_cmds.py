"""Read recorded rule trials and quote their stored facts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from alpha_cli._cli_json import emit
from alpha_cli.run_store import RUN_DIRS, find_run_dir, read_manifest, valid_run_id
from alpha_cli.spine import book, reserve
from alpha_cli.spine.check import FlagLookup, check_text, render_check
from alpha_cli.spine.compare import (
    DEFAULT_METRICS,
    Lookup,
    compare_runs,
    render_compare,
    resolve_run,
)
from alpha_cli.spine.data_health import health_sentence
from alpha_cli.spine.errors import SpineError, fail, unreadable_file
from alpha_cli.spine.facts import (
    build_facts,
    plain_basis,
    read_json,
    require_metric,
    tool_fact,
    tool_outputs,
)
from alpha_cli.spine.ledger import read_trials
from alpha_cli.spine.reading import reading_text, stored_reading
from alpha_cli.spine.reading_read import owner_word, run_reading
from alpha_cli.spine.trial_reader import family_counts, spine_snapshot
from alpha_cli.toolbox.registry import METRIC_OUTPUTS
from alpha_core import DataError
from alpha_core.config import AlphaSettings

results_app = typer.Typer(
    help="List rule tests and quote their stored results.", invoke_without_command=True
)


def _run(home: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    rdir = find_run_dir(home, run_id)
    if rdir is None and valid_run_id(run_id):
        for directory in ("setup-studies", "setup-trades"):
            study = home / directory / run_id
            if (study / "manifest.json").is_file():
                return study, read_json(study / "manifest.json")
    if rdir is None:
        raise SpineError(
            "UNKNOWN_RUN",
            f"Unknown completed run {run_id!r}.",
            "Run alpha results --json to list recorded runs.",
        )
    return rdir, read_manifest(rdir)


def _error(exc: ValueError | OSError | DataError, json_out: bool) -> None:
    fail(
        exc
        if isinstance(exc, SpineError)
        else SpineError(
            "INVALID_ARTIFACT",
            str(exc),
            "Run alpha test again from the saved spec after correcting the artifact error.",
        ),
        json_out,
    )


def _row_word(home: Path, row: dict[str, Any], evidence: str | None) -> str:
    """The ledger row's own evidence word; an older row is read from its run, or by its letter."""
    return evidence or owner_word(home, row["run_id"], row["verdict"])


@results_app.callback()
def list_results(
    ctx: typer.Context,
    limit: int = typer.Option(20, min=1, help="Maximum rows, newest first."),
    symbol: str | None = None,
    name: str | None = None,
    idea_id: str | None = None,
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """List recorded trials, including failed attempts, and the total count."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        rows = read_trials(AlphaSettings().data_dir)
        if not rows:
            raise SpineError(
                "EMPTY_LEDGER",
                "No rule trials are recorded.",
                "Run alpha test with a saved spec or rule flags.",
            )
        # Older ledger rows have no idea id; use their completed manifest if available.
        for row in rows:
            if row.get("run_id") and not row.get("idea_id"):
                rdir = find_run_dir(AlphaSettings().data_dir, row["run_id"])
                row["idea_id"] = read_manifest(rdir).get("idea_id") if rdir is not None else None
        selected = [
            row
            for row in reversed(rows)
            if (symbol is None or row.get("symbol") == symbol)
            and (name is None or row.get("name") == name)
            and (idea_id is None or row.get("idea_id") == idea_id)
        ][:limit]
        items = [
            {
                **{
                    key: row.get(key)
                    for key in (
                        "trial_index",
                        "recorded_at",
                        "kind",
                        "name",
                        "symbol",
                        "verdict",
                        "oos_sharpe",
                        "benchmark_sharpe",
                        "labels",
                        "run_id",
                        "idea_id",
                    )
                },
                "flags_count": len(row["flags"]) if isinstance(row.get("flags"), list) else None,
            }
            for row in selected
        ]
        home = AlphaSettings().data_dir
        lines = [
            "\t".join(
                _row_word(home, row, found.get("evidence")) if key == "verdict" else str(row[key])
                for key in row
            )
            for row, found in zip(items, selected, strict=True)
        ]
        for row, found in zip(items, selected, strict=True):
            row["reading"] = run_reading(home, row["run_id"])
            row.update(evidence=found.get("evidence"), aim_relation=found.get("aim_relation"))
        for row in items:
            row["reasons"] = {
                key: "an investigation-tool row; see alpha results show for its output"
                if str(row["kind"]).startswith("tool:")
                else "unavailable in the stored ledger row"
                for key in ("oos_sharpe", "benchmark_sharpe", "flags_count")
                if row[key] is None
            }
        lines.append(f"Total trials: {len(rows)}")
        emit(
            {"items": items, "total_trials": len(rows)},
            json_out=json_out,
            fallback="\n".join(lines),
        )
    except (ValueError, OSError, DataError) as exc:
        _error(exc, json_out)


def _show(home: Path, run_id: str) -> dict[str, Any]:
    from alpha_cli.figures import available_figures

    try:
        rdir, manifest = _run(home, run_id)
    except SpineError as exc:
        # Finds have a summary to show, but no citable outcome metrics.
        folder = home / "setups" / run_id
        if (
            exc.payload["code"] != "UNKNOWN_RUN"
            or not valid_run_id(run_id)
            or not (folder / "manifest.json").is_file()
        ):
            raise
        manifest = read_json(folder / "manifest.json")
        if manifest.get("schema") != "AlphaSetupFindV1":
            raise ValueError("invalid setup find manifest") from exc
        summary = read_json(folder / "summary.json")
        if summary.get("find_id") != run_id or manifest.get("find_id") != run_id:
            raise ValueError("setup find summary or manifest identity mismatch") from exc
        return dict(run_id=run_id, **summary)
    if manifest.get("schema") in {"AlphaSetupStudyV1", "AlphaSetupTradeV1"}:
        from alpha_cli.spine.facts import read_study

        return dict(run_id=run_id, **read_study(rdir))
    from alpha_cli.toolbox import declarations
    from alpha_cli.toolbox.store import history

    diagnostics = read_json(rdir / "diagnostics.json")
    rule = manifest.get("spine", {}).get("rule", {}).get("kind")
    family_id = f"spine:{rule}" if rule else None
    counts = family_counts(spine_snapshot(home))
    current = next(
        (row for row in counts if row["family_id"] == family_id),
        {"reader_trials": 0, "rows": 0, "outcomes": {}},
    )
    at_run = diagnostics.get("trials", {}).get("family", {}).get("n_trials_used")
    labels = reserve.read_labels(manifest)
    # A run is a repeat when its first ledger row says so (the same test after a code change has
    # a new run folder); the label lives in the ledger row only, never in the stored manifest.
    first = next(
        (
            row
            for row in read_trials(home)
            if row.get("run_id") == run_id and row.get("kind", "rule_test") == "rule_test"
        ),
        None,
    )
    if first is not None and "repeat" in (first.get("labels") or ()) and "repeat" not in labels:
        labels.append("repeat")
    stored_tools = tool_outputs(home, run_id)
    return {
        **({"reserve_sentence": reserve.SEEN_SENTENCE} if reserve.SEEN in labels else {}),
        "family": {
            "family_id": family_id,
            "trials_at_run": at_run,
            "now": {key: current[key] for key in ("reader_trials", "rows", "outcomes")},
            "reason": None if at_run is not None else "recorded before family counts were used",
        },
        "run_id": run_id,
        "reading": stored_reading(manifest, diagnostics),
        "idea_id": manifest.get("idea_id"),
        "data_health": manifest.get("data_health"),
        "facts": build_facts(rdir),
        "labels": labels,
        "flags": diagnostics.get("flags", []),
        "audit": diagnostics.get("audit", []),
        "diagnostics_reason": None
        if diagnostics
        else "diagnostics.json is unavailable; re-run alpha test for this spec",
        # Investigation-tool outputs live outside the immutable run directory.
        "tool_history": history(home, run_id),
        "tools": [
            {
                **{
                    key: item[key]
                    for key in ("tool", "id", "params", "recorded_at", "file", "labels", "reading")
                },
                "status": declarations.word_of(item["labels"] or []),
            }
            for item in stored_tools
        ],
        "tool_counts": declarations.counts(item["labels"] or [] for item in stored_tools),
        "charts": [
            entry.definition.figure_id
            for entry in available_figures(rdir, manifest)
            if entry.available
        ],
    }


def _show_text_fields(row: dict[str, Any]) -> dict[str, Any]:
    """The details printed as text: the reading is a sentence above; the old letter stays out."""
    hidden = {"data_health", "data_health_sentence"}
    if isinstance(row.get("reading"), dict):
        hidden.add("reading")
    shown = {k: v for k, v in row.items() if k not in hidden}
    if isinstance(shown.get("facts"), list):
        shown["facts"] = [f for f in shown["facts"] if f.get("metric") != "verdict"]
    return _plain_audit(shown)


@results_app.command("show")
def show_results(run_id: str, json_out: bool = typer.Option(False, "--json")) -> None:
    """Show sourced facts, observations, audit checks, tool outputs and chart names."""
    try:
        home = AlphaSettings().data_dir
        failed: list[dict[str, Any]] = []
        if find_run_dir(home, run_id) is not None or (
            valid_run_id(run_id)
            and any(
                (home / directory / run_id / "manifest.json").is_file()
                for directory in ("setup-studies", "setup-trades", "setups")
            )
        ):
            ids = [run_id]
        else:
            # A test id: show every asset that completed and report each one that did not.
            # Rows written before investigation tools existed carry no kind: they are rule tests.
            rows = [
                row
                for row in spine_snapshot(home).raw_rows.values()
                if row.get("test_id") == run_id and row.get("kind", "rule_test") == "rule_test"
            ]
            ids = list(
                dict.fromkeys(
                    row["run_id"]
                    for row in rows
                    if row.get("run_id") and find_run_dir(home, row["run_id"]) is not None
                )
            )
            failed = [
                {
                    "symbol": row.get("symbol"),
                    "run_id": row.get("run_id"),
                    "trial_index": row.get("trial_index"),
                    "reason": "this asset's trial did not complete; no run is stored for it",
                }
                for row in rows
                if not row.get("run_id") or row["run_id"] not in ids
            ]
        if not ids and not failed:
            raise SpineError(
                "UNKNOWN_RUN",
                f"Unknown run or test {run_id!r}.",
                "Run alpha results --json to list recorded runs.",
            )
        if ids == [run_id]:
            runs = [_show(home, run_id)]  # one named run: an unreadable artifact fails loud
        else:
            runs = []
            for value in ids:
                try:
                    runs.append(_show(home, value))
                except (ValueError, OSError, DataError) as exc:
                    # One unreadable asset must not hide the others; report it by name.
                    row = next(item for item in rows if item.get("run_id") == value)
                    failed.append(
                        {
                            "symbol": row.get("symbol"),
                            "run_id": value,
                            "trial_index": row.get("trial_index"),
                            "reason": f"stored run could not be read: {exc}",
                        }
                    )
        for run in runs:
            run["data_health_sentence"] = health_sentence(run.get("data_health"))
        output = {"runs": runs, "failed": failed}
        lines = [
            (f"{row['run_id']} — " if len(runs) > 1 else "")
            + row["data_health_sentence"]
            + (f"\n{reading_text(row['reading'])}" if isinstance(row.get("reading"), dict) else "")
            for row in runs
        ]
        details = [_show_text_fields(row) for row in runs]
        lines.append(json.dumps({"runs": details, "failed": failed}, indent=2, allow_nan=False))
        emit(output, json_out=json_out, fallback="\n".join(lines))
    except (ValueError, OSError, DataError) as exc:
        _error(exc, json_out)


@results_app.command("cite")
def cite_result(
    run_id: str,
    metric: str,
    tool_output: str | None = typer.Option(
        None, "--tool-output", help="Id of one stored tool output, when a tool ran more than once."
    ),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Quote exactly one stored fact; never recompute a metric."""
    try:
        require_metric(metric)
        home = AlphaSettings().data_dir
        rdir, _ = _run(home, run_id)
        citation = f"{metric}@{tool_output}" if metric in METRIC_OUTPUTS and tool_output else metric
        fact = fact_lookup(home)(run_id, citation)
        value = "null" if fact["value"] is None else str(fact["value"])
        if metric == "verdict":  # the letter stays in the JSON; the text shows the reading
            value = f"{owner_word(home, run_id, fact['value'])}" + (
                f" (old grade: {fact['value']})" if fact["value"] else ""
            )
        caveat = " [too-few-trades]" if "too-few-trades" in fact["labels"] else ""
        tag = f"{metric}@{tool_output}" if tool_output else metric
        settings = (
            f" (1 of {fact['settings_count']} settings tried)" if "settings_count" in fact else ""
        )
        emit(
            fact,
            json_out=json_out,
            fallback=f"{value} [{run_id}:{tag}]{settings} ({plain_basis(fact['basis'])}){caveat}",
        )
    except (ValueError, OSError, DataError) as exc:
        _error(exc, json_out)


def _plain_audit(output: dict[str, Any]) -> dict[str, Any]:
    """Audit states in owner words: ok, flagged, not checked; the stored file keeps its codes."""
    words = {"PASS": "ok", "FLAG": "flagged", "NOT-CHECKED": "not checked"}
    audit = [
        {**item, "status": words.get(item.get("status"), item.get("status"))}
        for item in output.get("audit", [])
    ]
    return {**output, "audit": audit}


def diagnose_run(run_id: str, json_out: bool = typer.Option(False, "--json")) -> None:
    """Read the automatic diagnostic pass and audit stored with a rule test."""
    try:
        rdir, manifest = _run(AlphaSettings().data_dir, run_id)
        if not (rdir / "diagnostics.json").exists():
            raise SpineError(
                "NO_DIAGNOSTICS",
                f"Run {run_id} has no diagnostics.json.",
                f"Re-run alpha test with diagnostics enabled using the original spec for {run_id}.",
            )
        output = read_json(rdir / "diagnostics.json")
        found = stored_reading(manifest, output)
        text = json.dumps(_plain_audit(output), indent=2, allow_nan=False)
        emit(
            {**output, "reading": found},
            json_out=json_out,
            fallback=f"{found['sentence']}\n{text}",
        )
    except (ValueError, OSError, DataError) as exc:
        _error(exc, json_out)


def _run_paths(home: Path) -> dict[str, Path]:
    """Discover completed runs in the same precedence order as run lookup."""
    paths: dict[str, Path] = {}
    for directory in (*RUN_DIRS, "setup-studies", "setup-trades"):
        for manifest in (home / directory).glob("*/manifest.json"):
            if valid_run_id(manifest.parent.name):
                paths.setdefault(manifest.parent.name, manifest.parent)
    return paths


def flag_lookup(home: Path) -> FlagLookup:
    """Read stored diagnostic flags for cited runs; missing diagnostics have none."""
    paths = _run_paths(home)

    def lookup(run_id: str) -> list[dict[str, str]]:
        flags: list[dict[str, str]] = read_json(
            paths[resolve_run(run_id, paths)] / "diagnostics.json"
        ).get("flags", [])
        return flags

    return lookup


def fact_lookup(home: Path) -> Lookup:
    """Discover completed runs; read each cited run's facts once, on demand."""
    paths = _run_paths(home)
    cache: dict[str, dict[str, dict[str, Any]]] = {}

    def lookup(prefix: str, metric: str) -> dict[str, Any]:
        metric, _, output_id = metric.partition("@")
        require_metric(metric)
        run_id = resolve_run(prefix, paths)
        if metric in METRIC_OUTPUTS:
            fact = tool_fact(home, run_id, metric, output_id or None)
            manifest = read_json(paths[run_id] / "manifest.json")
            labels = manifest.get("spine", {}).get("labels", [])
            health = [label for label in labels if label.startswith("data-health-")]
            return {**fact, "labels": list(dict.fromkeys([*fact.get("labels", []), *health]))}
        if output_id:
            raise SpineError(
                "INVALID_CITATION", "Only tool facts take an output id.", "Run alpha results cite."
            )
        if run_id not in cache:
            cache[run_id] = {fact["metric"]: fact for fact in build_facts(paths[run_id])}
        if metric not in cache[run_id]:
            raise SpineError(
                "METRIC_NOT_STORED",
                f"Run {run_id} has no stored fact {metric} in its run folder.",
                "Cite tool facts with alpha results cite <run_id> <metric> --tool-output <id>.",
            )
        return cache[run_id][metric]

    return lookup


@results_app.command("check")
def check_answer(
    path: Path,
    json_out: bool = typer.Option(False, "--json"),
    allow_untagged: int = typer.Option(
        0, min=0, help="Tolerate this many untagged numbers as warnings."
    ),
) -> None:
    """Check a draft's tagged numbers, required labels and flags against stored facts."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail(unreadable_file(path, exc), json_out)
    try:
        home = AlphaSettings().data_dir
        result = check_text(text, fact_lookup(home), allow_untagged, flag_lookup(home))
        emit(result, json_out=json_out, fallback=render_check(result))
        if not result["ok"]:
            raise typer.Exit(1)
    except (ValueError, OSError, DataError) as exc:
        _error(exc, json_out)


@results_app.command("compare")
def compare_results(
    run_ids: Annotated[list[str], typer.Argument(help="Two to eight runs; first is base.")],
    metric: Annotated[
        list[str] | None, typer.Option("--metric", help="Metric; repeatable.")
    ] = None,
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Compare stored values, differences and ratios, with bases and run labels."""
    try:
        result = compare_runs(
            run_ids, fact_lookup(AlphaSettings().data_dir), metric or DEFAULT_METRICS
        )
        emit(result, json_out=json_out, fallback=render_compare(result))
    except (ValueError, OSError, DataError) as exc:
        _error(exc, json_out)


def _daily_series(home: Path, run_id: str) -> book.DailySeries:
    """One stored rule test's walk-forward equity and exposure. No bar is read, nothing is run."""
    import polars as pl

    from alpha_cli.toolbox import inputs

    target = inputs.resolve(home, run_id)
    frame = target.table("stored_equity", "ts", "equity")
    stamps = target.dates(frame, "stored_equity")
    held: tuple[bool, ...] | None = None
    path = target.directory / "exposure_turnover.parquet"
    if path.is_file():
        try:
            rows = pl.read_parquet(
                path, columns=["start_ts", "end_ts", "net_exposure", "exposure_available"]
            )
        except pl.exceptions.PolarsError as exc:
            raise ValueError(f"Cannot read exposure_turnover.parquet: {exc}") from exc
        if rows["start_ts"].to_list() != stamps[:-1] or rows["end_ts"].to_list() != stamps[1:]:
            raise ValueError(
                f"Run {run_id}: stored exposure does not match the stored equity dates"
            )
        if all(rows["exposure_available"].to_list()):
            net = rows["net_exposure"].to_list()
            if any(value is None or value != value for value in net):
                raise ValueError(f"Run {run_id}: stored exposure has a missing value")
            held = (False, *(value != 0 for value in net))
    return book.DailySeries(
        run_id,
        tuple(ts.date() for ts in stamps),
        tuple(float(value) for value in frame["equity"].to_list()),
        held,
        tuple(reserve.read_labels(target.manifest)),
    )


@results_app.command("correlate")
def correlate_results(
    run_ids: Annotated[list[str], typer.Argument(help="Two to eight rule-test runs.")],
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """How stored runs moved together: correlation of daily returns, common days, overlap.

    Reads the stored walk-forward equity and exposure of each run. It runs no test and reads
    no bar. Under 60 common days it gives no correlation. Readings only, not advice."""
    try:
        home = AlphaSettings().data_dir
        if not 2 <= len(run_ids) <= 8:
            raise SpineError(
                "INVALID_RUN_COUNT",
                "Correlate needs 2 to 8 runs.",
                "Run alpha results correlate with 2 to 8 run ids.",
            )
        paths = _run_paths(home)
        ids = [resolve_run(run_id, paths) for run_id in run_ids]
        if len(set(ids)) != len(ids):
            raise SpineError(
                "DUPLICATE_RUN",
                "A run is named twice.",
                "Run alpha results correlate with different run ids.",
            )
        result = book.correlate([_daily_series(home, run_id) for run_id in ids])
        for run in result["runs"]:
            if reserve.SEEN in run["labels"]:
                run["reserve_sentence"] = reserve.SEEN_SENTENCE
        result["basis"] = "stored walk-forward equity (net of fees) and exposure of each run"
        emit(result, json_out=json_out, fallback=book.render_correlate(result))
    except (ValueError, OSError, DataError) as exc:
        _error(exc, json_out)
