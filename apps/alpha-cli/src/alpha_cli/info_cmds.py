"""``alpha info`` — resolved settings, plus machine-readable catalogs for the workstation.

``alpha info`` (no subcommand) prints the resolved settings + core version, exactly as before.
``alpha info strategies`` / ``alpha info commands`` emit JSON projections (with ``--json``) that the
workstation reads to build its strategy picker and its dynamic new-run form — so the CLI stays the
single source of truth for what can be launched and how.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

import typer

from alpha_core import __version__ as core_version
from alpha_core.config import AlphaSettings

info_app = typer.Typer(help="Resolved settings + machine-readable catalogs.")


@info_app.callback(invoke_without_command=True)
def _info_root(ctx: typer.Context) -> None:
    """Print resolved configuration and the core version (when no subcommand is given)."""
    if ctx.invoked_subcommand is not None:
        return
    settings = AlphaSettings()
    typer.echo(f"alpha-core {core_version}")
    typer.echo(f"data_dir={settings.data_dir}")
    typer.echo(f"random_seed={settings.random_seed}")
    typer.echo(f"forecast_model={settings.forecast_model}")


def _strategy_catalog() -> list[dict[str, Any]]:
    from alpha_cli._schemas import STRATEGY_PARAM_SCHEMA
    from alpha_cli._strategies import STRATEGIES, known_strategies

    return [
        {
            "name": name,
            "params": [asdict(p) for p in STRATEGY_PARAM_SCHEMA.get(name, ())],
            "has_tier1_surrogate": STRATEGIES[name].surrogate is not None,
        }
        for name in known_strategies()
    ]


@info_app.command("strategies")
def strategies(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List registered strategies and their tunable ``--param`` axes."""
    catalog = _strategy_catalog()
    if json_out:
        typer.echo(json.dumps(catalog))
        return
    for entry in catalog:
        axes = ", ".join(str(p["name"]) for p in entry["params"]) or "(RunSpec flags only)"
        typer.echo(f"{entry['name']}: {axes}")


def _jsonable(value: Any) -> Any:
    """Coerce a Click default to a JSON-safe value (scalars pass through; lists recurse)."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return str(value)


def _click_type(param: Any) -> str:
    # Typer vendors its own click fork (``typer._click``), so ``isinstance`` against the top-level
    # ``click`` classes fails — duck-type on the stable Parameter attributes instead.
    if getattr(param.type, "choices", None):
        return "choice"
    name = getattr(param.type, "name", "") or ""
    return {"integer": "int", "float": "float", "boolean": "bool", "text": "str"}.get(name, "str")


def _walk_commands(group: Any, prefix: str) -> Iterator[tuple[str, Any]]:
    """Yield ``(path, leaf_command)`` for every leaf command (groups carry a ``.commands`` dict)."""
    for name, cmd in sorted(group.commands.items()):
        path = f"{prefix} {name}".strip()
        if hasattr(cmd, "commands"):
            yield from _walk_commands(cmd, path)
        else:
            yield path, cmd


def _command_catalog() -> list[dict[str, Any]]:
    """Introspect the Typer→Click command tree: id + positional args + options (with defaults)."""
    from alpha_cli.main import app as root_app

    group = typer.main.get_command(root_app)
    catalog: list[dict[str, Any]] = []
    for path, cmd in _walk_commands(group, ""):
        args: list[dict[str, Any]] = []
        options: list[dict[str, Any]] = []
        for param in cmd.params:
            if param.param_type_name == "argument":
                args.append(
                    {
                        "name": param.name,
                        "type": _click_type(param),
                        "required": bool(param.required),
                        "nargs": param.nargs,
                    }
                )
            else:  # option
                choices = getattr(param.type, "choices", None)
                options.append(
                    {
                        "name": param.name,
                        "flag": param.opts[0] if param.opts else None,
                        "type": _click_type(param),
                        "default": _jsonable(param.default),
                        "required": bool(param.required),
                        "multiple": bool(getattr(param, "multiple", False)),
                        "help": param.help or "",
                        "choices": list(choices) if choices else None,
                    }
                )
        catalog.append({"id": path, "args": args, "options": options})
    return catalog


@info_app.command("commands")
def commands(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Introspect the CLI command tree (flags + defaults) for the workstation's new-run form."""
    catalog = _command_catalog()
    if json_out:
        typer.echo(json.dumps(catalog))
        return
    for entry in catalog:
        typer.echo(f"{entry['id']}: {len(entry['options'])} options, {len(entry['args'])} args")
