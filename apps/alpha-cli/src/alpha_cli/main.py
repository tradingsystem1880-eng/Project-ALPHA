"""Project ALPHA CLI. Phase 0 proves cross-package wiring end-to-end."""

from __future__ import annotations

import typer

from alpha_core import __version__ as core_version
from alpha_core.config import AlphaSettings

app = typer.Typer(help="Project ALPHA command-line interface.")


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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
