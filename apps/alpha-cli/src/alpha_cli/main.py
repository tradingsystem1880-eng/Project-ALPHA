"""Project ALPHA CLI. Phase 0 proves cross-package wiring end-to-end."""

from __future__ import annotations

import typer

from alpha_cli.backtest_cmds import backtest_app
from alpha_cli.data_cmds import data_app
from alpha_cli.forecast_cmds import forecast_app
from alpha_cli.optim_cmds import optim_app
from alpha_cli.paper_cmds import paper_app
from alpha_cli.propfirm_cmds import propfirm_app
from alpha_cli.report_cmds import report as _report
from alpha_cli.validate_cmds import validate as _validate
from alpha_core import __version__ as core_version
from alpha_core.config import AlphaSettings

app = typer.Typer(help="Project ALPHA command-line interface.")
app.add_typer(data_app, name="data")
app.add_typer(backtest_app, name="backtest")
app.add_typer(optim_app, name="optim")
app.add_typer(forecast_app, name="forecast")
app.add_typer(paper_app, name="paper")
app.add_typer(propfirm_app, name="propfirm")
app.command(name="validate")(_validate)
app.command(name="report")(_report)


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    """Project ALPHA. Run a subcommand, e.g. `alpha info`."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def info() -> None:
    """Print resolved configuration and the core version."""
    settings = AlphaSettings()
    typer.echo(f"alpha-core {core_version}")
    typer.echo(f"data_dir={settings.data_dir}")
    typer.echo(f"random_seed={settings.random_seed}")
    typer.echo(f"weights_dir={settings.resolved_weights_dir}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
