"""One command from an owner's idea to recorded, visible multi-asset rule trials."""

from __future__ import annotations

import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import typer

from alpha_cli._cli_json import emit
from alpha_cli.spine.data_health import health_sentence
from alpha_cli.spine.errors import SpineError, fail, test_error
from alpha_cli.spine.reading import reading_text, reading_word
from alpha_cli.spine.recheck import MISMATCH_EXIT, recheck_idea
from alpha_cli.spine.run import run_idea
from alpha_cli.spine.spec import IdeaSpec, load_spec
from alpha_cli.spine.stores import _stores
from alpha_core import DataError
from alpha_core.config import AlphaSettings


def _recheck_lines(output: dict[str, Any]) -> list[str]:
    lines = []
    for result in output["results"]:
        found, asset = result["recheck"], result["asset"]
        if result["error"]:
            lines.append(f"{asset}: {result['error']}")
        elif found["match"] is None:
            lines.append(
                f"{asset}: {found['reason']}. Run `alpha test <spec>` once first; "
                "a recheck never creates the stored result."
            )
        else:
            code = "the code changed since" if found["code_changed"] else "the code is the same as"
            if found["match"]:
                exact = "bit for bit" if found["bit_identical"] else "within the tolerance"
                head = f"the same result, {exact}"
            else:
                head = f"a different result ({found['differences_total']} differences)"
            lines.append(
                f"{asset}: computed again in {found['seconds']:.1f} s and compared with run "
                f"{found['compared_with']}: {head}; {code} the stored run."
            )
            lines.extend(
                f"  {d['field']}: stored {d['stored']}, recomputed {d['recomputed']}"
                for d in found["differences"]
            )
    return lines


def _recheck(
    parsed: IdeaSpec,
    settings: AlphaSettings,
    quick: bool,
    accept_bad_data: str | None,
    check_data: bool,
    json_out: bool,
) -> None:
    """`recheck`: computed again and compared with the stored result. Never writes."""
    if check_data:
        fail(
            SpineError(
                "BAD_OPTION",
                "--recheck cannot be used with --check-data: a health report writes a file, "
                "and a recheck writes nothing.",
                "Run alpha data health first, then alpha test --recheck.",
            ),
            json_out,
        )
    with redirect_stdout(sys.stderr if json_out else sys.stdout):
        output = recheck_idea(
            parsed,
            home=settings.data_dir,
            seed=settings.random_seed,
            quick=quick,
            accept_bad_data=accept_bad_data,
        )
    if all(result["error"] is not None for result in output["results"]):
        fail(
            test_error(
                "; ".join(result["error"] for result in output["results"]),
                list(_stores(settings.data_dir)),
            ),
            json_out,
        )
    emit(output, json_out=json_out, fallback="\n".join(_recheck_lines(output)))
    if any(r["recheck"]["match"] is False for r in output["results"]):
        raise typer.Exit(MISMATCH_EXIT)


def _plan_only(
    parsed: IdeaSpec, plan: bool, recheck: bool, settings: AlphaSettings, json_out: bool
) -> None:
    """`--plan`, and the refusal of a context spec without it. Never runs the engine."""
    from alpha_cli._context_plan import REFUSAL, plan_idea, plan_lines

    if not plan:
        fail(SpineError("GATED_ENGINE_MISSING", REFUSAL, "Run alpha test <spec> --plan."), json_out)
    if parsed.context is None or recheck:
        message = (
            "--plan describes a context gate; this spec has none."
            if parsed.context is None
            else "--plan cannot be used with --recheck."
        )
        fail(SpineError("BAD_OPTION", message, "Run alpha test without --plan."), json_out)
    output = plan_idea(parsed, home=settings.data_dir)
    if all(result["error"] is not None for result in output["results"]):
        errors = "; ".join(result["error"] for result in output["results"])
        fail(test_error(errors, list(_stores(settings.data_dir))), json_out)
    emit(output, json_out=json_out, fallback="\n".join(plan_lines(output)))


def test_rule(
    spec: Path | None = typer.Argument(None, help="Idea spec (.toml or .json)."),  # noqa: B008
    rule: str | None = typer.Option(None, help="ma_cross | breakout | tsmom"),
    param: list[str] | None = typer.Option(None, help="Rule parameter name=value (repeatable)."),  # noqa: B008
    asset: list[str] | None = typer.Option(None, help="Symbol or symbol@store (repeatable)."),  # noqa: B008
    name: str | None = None,
    idea: str | None = None,
    idea_card: str | None = typer.Option(None, help="Id of the idea card for this test."),
    fee_bps: float | None = None,
    slippage_bps: float | None = None,
    quick: bool = typer.Option(
        False, help="Small gauntlet (20/4/4 paths, 50 resamples); labelled quick."
    ),
    no_diagnose: bool = typer.Option(
        False, "--no-diagnose", help="Skip automatic diagnostics; labelled no-diagnostics."
    ),
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
        help="Compute the test again and compare it with the stored result. Writes nothing. "
        "Exit 4 if the two differ.",
    ),
    plan: bool = typer.Option(
        False,
        "--plan",
        help="For a spec with a context gate: describe the gate per asset. Runs no engine, "
        "writes nothing.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit one JSON result object."),
) -> None:
    """Test a long/flat trading rule on several assets and record every trial."""
    settings = AlphaSettings()
    try:
        parsed = load_spec(
            spec,
            rule=rule,
            param=param,
            asset=asset,
            name=name,
            idea=idea,
            idea_card=idea_card,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
        if plan or parsed.context is not None:
            _plan_only(parsed, plan, recheck, settings, json_out)
            return
        if recheck:
            _recheck(parsed, settings, quick, accept_bad_data, check_data, json_out)
            return
        with redirect_stdout(sys.stderr if json_out else sys.stdout):
            output = run_idea(
                parsed,
                home=settings.data_dir,
                seed=settings.random_seed,
                quick=quick,
                check_data=check_data,
                accept_bad_data=accept_bad_data,
                no_diagnose=no_diagnose,
            )
        if all(result["error"] is not None for result in output["results"]):
            fail(
                test_error(
                    "; ".join(result["error"] for result in output["results"]),
                    list(_stores(settings.data_dir)),
                ),
                json_out,
            )
    except SpineError as exc:
        fail(exc, json_out)
    except (ValueError, OSError, DataError) as exc:
        fail(test_error(str(exc)), json_out)
    lines = [
        f"Test {output['test_id']} — {output['name']} (trials total: {output['trials_total']})",
        "ASSET\tRUN\tREADING\tOOS SHARPE\tLABELS / ERROR",
    ]
    for result in output["results"]:
        sharpe = result["oos_sharpe"]
        lines.append(
            "\t".join(
                (
                    result["asset"],
                    result["run_id"] or "—",
                    reading_word(result["reading"]) if result.get("reading") else "—",
                    f"{sharpe:.3f}" if sharpe is not None else "—",
                    result["error"] or ", ".join(result["labels"]),
                )
            )
        )
        if result.get("reading"):
            lines.append(reading_text(result["reading"]))
        if result.get("data_health"):
            lines.append(health_sentence(result["data_health"]))
        if not result.get("executed", True) and result["run_id"]:
            lines.append("The engine did not run: the stored run for this test was returned.")
    emit(output, json_out=json_out, fallback="\n".join(lines))
