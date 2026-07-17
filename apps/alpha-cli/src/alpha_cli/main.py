"""Project ALPHA CLI. Phase 0 proves cross-package wiring end-to-end."""

from __future__ import annotations

import typer

from alpha_cli.backtest_cmds import backtest_app
from alpha_cli.data_cmds import data_app
from alpha_cli.forecast_cmds import forecast_app
from alpha_cli.info_cmds import info_app
from alpha_cli.optim_cmds import optim_app
from alpha_cli.options_cmds import options_app
from alpha_cli.paper_cmds import paper_app
from alpha_cli.propfirm_cmds import propfirm_app
from alpha_cli.report_cmds import report as _report
from alpha_cli.research_cmds import research_app
from alpha_cli.risk_cmds import risk_app
from alpha_cli.screener_cmds import screener_app
from alpha_cli.validate_cmds import validate as _validate

app = typer.Typer(help="Project ALPHA command-line interface.")
app.add_typer(data_app, name="data")
app.add_typer(backtest_app, name="backtest")
app.add_typer(optim_app, name="optim")
app.add_typer(forecast_app, name="forecast")
app.add_typer(paper_app, name="paper")
app.add_typer(propfirm_app, name="propfirm")
app.add_typer(options_app, name="options")
app.add_typer(risk_app, name="risk")
app.add_typer(screener_app, name="screener")
app.add_typer(research_app, name="research")
app.add_typer(info_app, name="info")
app.command(name="validate")(_validate)
app.command(name="report")(_report)


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    """Project ALPHA. Run a subcommand, e.g. `alpha info`."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
