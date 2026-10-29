"""Project ALPHA CLI. Phase 0 proves cross-package wiring end-to-end."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import typer

# The one command registry: (name, module, attribute). ``app`` mounts every entry; the console
# entry mounts only the invoked group, so a CLI-backed read never imports unrelated engines.
GROUPS: tuple[tuple[str, str, str], ...] = (
    ("data", "alpha_cli.data_cmds", "data_app"),
    ("crypto-data", "alpha_cli.crypto_data_cmds", "crypto_data_app"),
    ("backtest", "alpha_cli.backtest_cmds", "backtest_app"),
    ("forecast", "alpha_cli.forecast_cmds", "forecast_app"),
    ("optim", "alpha_cli.optim_cmds", "optim_app"),
    ("paper", "alpha_cli.paper_cmds", "paper_app"),
    ("propfirm", "alpha_cli.propfirm_cmds", "propfirm_app"),
    ("provider", "alpha_cli.provider_cmds", "provider_app"),
    ("quantpad-data", "alpha_cli.quantpad_data_cmds", "quantpad_data_app"),
    ("info", "alpha_cli.info_cmds", "info_app"),
    ("owner-auth", "alpha_cli.owner_auth_cmds", "owner_auth_app"),
    ("risk", "alpha_cli.risk_cmds", "risk_app"),
    ("research", "alpha_cli.research_cmds", "research_app"),
    ("figures", "alpha_cli.figures_cmds", "figures_app"),
    ("project", "alpha_cli.project_cmds", "project_app"),
    ("evidence", "alpha_cli.evidence_cmds", "evidence_app"),
    ("ml", "alpha_cli.ml_cmds", "ml_app"),
    ("monte-carlo", "alpha_cli.monte_carlo_cmds", "monte_carlo_app"),
    ("chart", "alpha_cli.chart_cmds", "chart_app"),
    ("rules", "alpha_cli.rules_cmds", "rules_app"),
    ("assistant", "alpha_cli.assistant_cmds", "assistant_app"),
    ("scan", "alpha_cli.scan_cmds", "scan_app"),
    ("suite", "alpha_cli.suite_cmds", "suite_app"),
    ("strategy-candidate", "alpha_cli.strategy_candidate_cmds", "strategy_candidate_app"),
)
COMMANDS: tuple[tuple[str, str, str], ...] = (
    ("validate", "alpha_cli.validate_cmds", "validate"),
    ("report", "alpha_cli.report_cmds", "report"),
)


def _group(name: str, module: str, attribute: str) -> typer.Typer:
    group: typer.Typer = getattr(importlib.import_module(module), attribute)
    if name == "research":
        from alpha_cli.local_pdf_cmds import import_pdf_command

        if not any(info.name == "import-pdf" for info in group.registered_commands):
            group.command(name="import-pdf")(import_pdf_command)
    return group


def _root_app(groups: tuple[tuple[str, str, str], ...], *, commands: bool) -> typer.Typer:
    root = typer.Typer(help="Project ALPHA command-line interface.")
    for name, module, attribute in groups:
        root.add_typer(_group(name, module, attribute), name=name)
    if commands:
        for name, module, attribute in COMMANDS:
            root.command(name=name)(getattr(importlib.import_module(module), attribute))

    @root.callback(invoke_without_command=True)
    def _root(ctx: typer.Context) -> None:
        """Project ALPHA. Run a subcommand, e.g. `alpha info`."""
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help())

    return root


_FULL: typer.Typer | None = None

if TYPE_CHECKING:
    app: typer.Typer  # provided by __getattr__; importers keep the precise type


def _full_app() -> typer.Typer:
    """The complete CLI, built from the registry on first use."""
    global _FULL
    if _FULL is None:
        _FULL = _root_app(GROUPS, commands=True)
    return _FULL


def __getattr__(name: str) -> typer.Typer:
    if name == "app":
        return _full_app()
    raise AttributeError(name)


def main() -> None:
    invoked = sys.argv[1] if len(sys.argv) > 1 else None
    selected = tuple(group for group in GROUPS if group[0] == invoked)
    # Root help, completion, root commands and unknown names keep the complete app.
    (_root_app(selected, commands=False) if selected else _full_app())()


if __name__ == "__main__":
    main()
