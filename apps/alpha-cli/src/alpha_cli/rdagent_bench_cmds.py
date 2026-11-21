"""`alpha rdagent bench plan|run|report`: compare models on the same stored RD-Agent prompts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from alpha_cli.rdagent_bench_model import (
    BenchError,
    Client,
    FakeClient,
    GatewayClient,
    load_prices,
    load_prompts,
    make_plan,
    month_spent,
    run_bench,
)
from alpha_cli.rdagent_bench_score import score_store

bench_app = typer.Typer(
    help="Replay stored RD-Agent prompts on several models. Not a research trial."
)
PROMPTS = Annotated[Path, typer.Option("--prompts", help="Folder of stored prompt files (.json).")]
MODELS = Annotated[str, typer.Option("--models", help="Model names, separated by commas.")]
SAMPLES = Annotated[int, typer.Option("--samples", help="Replies asked for each prompt and model.")]
STAGES = Annotated[str | None, typer.Option("--stages", help="For example proposal,feedback.")]
STORE = Annotated[Path, typer.Option("--store", help="Output folder, outside git.")]


def _names(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _fail(error: BenchError) -> typer.Exit:
    typer.echo(str(error), err=True)
    return typer.Exit(2)


@bench_app.command("plan")
def plan(
    prompts: PROMPTS,
    models: MODELS,
    prices: Annotated[
        Path, typer.Option("--prices", help="TOML: [model] in_per_mtok, out_per_mtok.")
    ],
    samples: SAMPLES = 1,
    stages: STAGES = None,
    store: Annotated[
        Path | None, typer.Option("--store", help="Counts spend already there.")
    ] = None,
) -> None:
    """Print the number of calls and the cost estimate. Writes nothing and calls no model."""
    try:
        names = _names(models)
        found = load_prompts(prompts, _names(stages) if stages else None)
        spent = month_spent(store, datetime.now(UTC)) if store else 0.0
        result = make_plan(found, names, samples, load_prices(prices, names), spent)
    except BenchError as error:
        raise _fail(error) from error
    typer.echo(
        f"{result.calls} calls ({len(found)} prompts, {len(names)} models, {samples} samples)."
    )
    typer.echo(f"Estimated cost: {result.usd:.4f} USD, from recorded token counts and your prices.")
    for model, (calls, usd) in result.per_model.items():
        typer.echo(f"  {model}: {calls} calls, {usd:.4f} USD")
    typer.echo(
        "Caps: 60 calls and 10 USD per run, 50 USD per month. Nothing was written or called."
    )


@bench_app.command("run")
def run(
    prompts: PROMPTS,
    models: MODELS,
    prices: Annotated[Path, typer.Option("--prices")],
    store: STORE,
    samples: SAMPLES = 1,
    stages: STAGES = None,
    fixture: Annotated[
        Path | None, typer.Option("--fixture", help="Fake client: no network.")
    ] = None,
    gateway: Annotated[
        list[str] | None, typer.Option("--gateway", help="model=http://127.0.0.1:PORT")
    ] = None,
) -> None:
    """Send each stored prompt to each model. A stored output is kept, so a rerun resumes."""
    try:
        names = _names(models)
        found = load_prompts(prompts, _names(stages) if stages else None)
        client: Client
        if fixture is not None:
            client = FakeClient(json.loads(fixture.read_text(encoding="utf-8")))
        else:
            client = GatewayClient(dict(item.split("=", 1) for item in gateway or []))
        done = run_bench(found, names, samples, load_prices(prices, names), client, store)
    except (BenchError, ValueError) as error:
        raise _fail(BenchError(str(error))) from error
    typer.echo(f"Sent {done.new_calls} new calls. Outputs are in {store}/outputs.")
    typer.echo("The live loop's memory and trial ledger were not touched.")


@bench_app.command("report")
def report(
    prompts: PROMPTS,
    models: MODELS,
    store: STORE,
    stages: STAGES = None,
    closed: Annotated[
        str, typer.Option("--closed", help="Closed idea families, separated by commas.")
    ] = "",
    dropped: Annotated[
        str, typer.Option("--dropped", help="Dropped idea names, separated by commas.")
    ] = "",
    samples: SAMPLES = 10,
) -> None:
    """Print readings per model and per pair. They are readings, not a ranking."""
    try:
        found = load_prompts(prompts, _names(stages) if stages else None)
        scored = score_store(
            found,
            _names(models),
            store,
            set(_names(closed)),
            {d.lower() for d in _names(dropped)},
            samples,
        )
    except BenchError as error:
        raise _fail(error) from error
    typer.echo(scored.text())
