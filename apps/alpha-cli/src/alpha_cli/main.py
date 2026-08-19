"""Project ALPHA CLI. Phase 0 proves cross-package wiring end-to-end."""

from __future__ import annotations

import typer

from alpha_cli.backtest_cmds import backtest_app
from alpha_cli.crypto_data_cmds import crypto_data_app
from alpha_cli.data_cmds import data_app
from alpha_cli.evidence_cmds import evidence_app
from alpha_cli.figures_cmds import figures_app
from alpha_cli.forecast_cmds import forecast_app
from alpha_cli.info_cmds import info_app
from alpha_cli.ml_cmds import ml_app
from alpha_cli.monte_carlo_cmds import monte_carlo_app
from alpha_cli.optim_cmds import optim_app
from alpha_cli.options_cmds import options_app
from alpha_cli.owner_auth_cmds import owner_auth_app
from alpha_cli.paper_cmds import paper_app
from alpha_cli.project_cmds import project_app
from alpha_cli.propfirm_cmds import propfirm_app
from alpha_cli.provider_cmds import provider_app
from alpha_cli.quantpad_data_cmds import quantpad_data_app
from alpha_cli.report_cmds import report as _report
from alpha_cli.research_cmds import research_app
from alpha_cli.risk_cmds import risk_app
from alpha_cli.screener_cmds import screener_app
from alpha_cli.strategy_candidate_cmds import strategy_candidate_app
from alpha_cli.suite_cmds import suite_app
from alpha_cli.validate_cmds import validate as _validate

app = typer.Typer(help="Project ALPHA command-line interface.")
app.add_typer(data_app, name="data")
app.add_typer(crypto_data_app, name="crypto-data")
app.add_typer(backtest_app, name="backtest")
app.add_typer(forecast_app, name="forecast")
app.add_typer(optim_app, name="optim")
app.add_typer(paper_app, name="paper")
app.add_typer(propfirm_app, name="propfirm")
app.add_typer(provider_app, name="provider")
app.add_typer(quantpad_data_app, name="quantpad-data")
app.add_typer(info_app, name="info")
app.add_typer(options_app, name="options")
app.add_typer(owner_auth_app, name="owner-auth")
app.add_typer(risk_app, name="risk")
app.add_typer(screener_app, name="screener")
app.add_typer(research_app, name="research")
app.add_typer(figures_app, name="figures")
app.add_typer(project_app, name="project")
app.add_typer(evidence_app, name="evidence")
app.add_typer(ml_app, name="ml")
app.add_typer(monte_carlo_app, name="monte-carlo")
app.add_typer(suite_app, name="suite")
app.add_typer(strategy_candidate_app, name="strategy-candidate")
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
