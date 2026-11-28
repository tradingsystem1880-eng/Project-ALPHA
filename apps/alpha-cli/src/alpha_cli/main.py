"""Project ALPHA CLI. Phase 0 proves cross-package wiring end-to-end."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import typer

# The one command registry: (name, module, attribute). ``app`` mounts every entry; the console
# entry mounts only the invoked group, so a CLI-backed read never imports unrelated engines.
GROUPS: tuple[tuple[str, str, str], ...] = (
    ("ledger", "alpha_cli.ledger_cmds", "ledger_app"),
    ("rdagent", "alpha_cli.rdagent_cmds", "rdagent_app"),
    ("partner", "alpha_cli.partner_cmds", "partner_app"),
    ("results", "alpha_cli.results_cmds", "results_app"),
    ("data", "alpha_cli.data_cmds", "data_app"),
    ("context", "alpha_cli.context_cmds", "context_app"),
    ("crypto-data", "alpha_cli.crypto_data_cmds", "crypto_data_app"),
    ("backtest", "alpha_cli.backtest_cmds", "backtest_app"),
    ("forecast", "alpha_cli.forecast_cmds", "forecast_app"),
    ("optim", "alpha_cli.optim_cmds", "optim_app"),
    ("propfirm", "alpha_cli.propfirm_cmds", "propfirm_app"),
    ("provider", "alpha_cli.provider_cmds", "provider_app"),
    ("info", "alpha_cli.info_cmds", "info_app"),
    ("confirm", "alpha_cli.confirm_cmds", "confirm_app"),
    ("risk", "alpha_cli.risk_cmds", "risk_app"),
    ("research", "alpha_cli.research_cmds", "research_app"),
    ("figures", "alpha_cli.figures_cmds", "figures_app"),
    ("project", "alpha_cli.jobs_cmds", "jobs_app"),
    ("ml", "alpha_cli.ml_cmds", "ml_app"),
    ("monte-carlo", "alpha_cli.monte_carlo_cmds", "monte_carlo_app"),
    ("chart", "alpha_cli.chart_cmds", "chart_app"),
    ("rules", "alpha_cli.rules_cmds", "rules_app"),
    ("assistant", "alpha_cli.assistant_cmds", "assistant_app"),
    ("scan", "alpha_cli.scan_cmds", "scan_app"),
    ("setup", "alpha_cli.setup_cmds", "setup_app"),
    ("tool", "alpha_cli.tool_cmds", "tool_app"),
    ("strategy-candidate", "alpha_cli.strategy_candidate_cmds", "strategy_candidate_app"),
    ("labels", "alpha_cli.labels_cmds", "labels_app"),
    ("idea", "alpha_cli.idea_cmds", "idea_app"),
    ("library", "alpha_cli.library_cmds", "library_app"),
    ("nightly", "alpha_cli.nightly_cmds", "nightly_app"),
    ("home", "alpha_cli.home_cmds", "home_app"),
    ("follow", "alpha_cli.follow_cmds", "follow_app"),
    ("options", "alpha_cli.options_cmds", "options_app"),
)
COMMANDS: tuple[tuple[str, str, str], ...] = (
    ("diagnose", "alpha_cli.results_cmds", "diagnose_run"),
    ("validate", "alpha_cli.validate_cmds", "validate"),
    ("test", "alpha_cli.test_cmds", "test_rule"),
    ("lookalike", "alpha_cli.lookalike_cmds", "lookalike"),
    ("unusual", "alpha_cli.lookalike_cmds", "unusual"),
    ("report", "alpha_cli.report_cmds", "report"),
    ("next", "alpha_cli.next_cmds", "next_step"),
)


def _group(name: str, module: str, attribute: str) -> typer.Typer:
    group: typer.Typer = getattr(importlib.import_module(module), attribute)
    if name == "library":
        importlib.import_module("alpha_cli.library_papers_cmds")
    if name == "research":
        from alpha_cli.local_pdf_cmds import import_pdf_command

        if not any(info.name == "import-pdf" for info in group.registered_commands):
            group.command(name="import-pdf")(import_pdf_command)
        from alpha_cli.moved_notice import announce
        from alpha_cli.research_cmds import sources_app

        announce(group, "import-pdf", "alpha library import-pdf")
        announce(sources_app, "discover", "alpha library search")
        announce(sources_app, "acquire", "alpha library import-pdf")
    return group


def _root_app(
    groups: tuple[tuple[str, str, str], ...],
    *,
    commands: bool | tuple[tuple[str, str, str], ...],
) -> typer.Typer:
    root = typer.Typer(help="Project ALPHA command-line interface.")
    for name, module, attribute in groups:
        root.add_typer(_group(name, module, attribute), name=name)
    for name, module, attribute in COMMANDS if commands is True else (commands or ()):
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
    only = tuple(command for command in COMMANDS if command[0] == invoked)
    # Root help, completion, other root commands and unknown names keep the complete app.
    if selected:
        _root_app(selected, commands=())()
    elif only:
        _root_app((), commands=only)()
    else:
        _full_app()()


if __name__ == "__main__":
    main()
