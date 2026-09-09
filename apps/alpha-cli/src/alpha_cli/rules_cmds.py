"""``alpha rules`` — save, list, show, validate and delete the owner's rule strategies.

A saved rule is one canonical JSON file at ``data_dir/rules/<name>.json``;
``alpha_strategies.rules`` is the single parser and nothing here interprets a rule.
``alpha backtest run --strategy rules --rules <name>`` and ``alpha validate`` read the file through
:func:`resolve_rules_spec`, and the run manifest then carries the exact canonical bytes, so
overwriting a name never rewrites a past run.
Read/write of the owner's own files only; no authority of any kind.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings

rules_app = typer.Typer(help="Owner rule strategies: save, list, show, validate, delete.")

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def rules_dir(data_dir: Path) -> Path:
    return data_dir / "rules"


def rule_path(data_dir: Path, name: str) -> Path:
    if not _NAME_RE.match(name):
        raise DataError(
            f"rule name {name!r} must be 1-64 lowercase letters, digits, '-' or '_' "
            "(it names a file under data_dir/rules/)"
        )
    return rules_dir(data_dir) / f"{name}.json"


def load_rule_text(data_dir: Path, name: str) -> str:
    path = rule_path(data_dir, name)
    if not path.is_file():
        raise DataError(f"no saved rule {name!r} (expected {path}); run `alpha rules save` first")
    return path.read_text(encoding="utf-8")


def resolve_rules_spec(strategy: str, rules: str | None, data_dir: Path) -> str | None:
    """The canonical spec bytes a ``RunSpec`` should carry for ``--strategy``/``--rules``."""
    from alpha_strategies.rules import canonical_json, rule_spec_from_json

    if rules is None:
        if strategy == "rules":
            raise DataError(
                "--strategy rules needs --rules NAME (a spec saved by `alpha rules save`)"
            )
        return None
    if strategy != "rules":
        raise DataError(f"--rules only applies to --strategy rules, not {strategy!r}")
    return canonical_json(rule_spec_from_json(load_rule_text(data_dir, rules)))


def _record(name: str, text: str, path: Path) -> dict[str, Any]:
    from alpha_strategies.rules import rule_spec_from_json, spec_sha256

    spec = rule_spec_from_json(text)
    return {
        "name": name,
        "sha256": spec_sha256(spec),
        "path": str(path),
        "spec_name": spec.name,
        "history": spec.history,
        "warmup": spec.warmup,
        "long_conditions": [condition.label for condition in spec.long_when],
        "short_conditions": [condition.label for condition in spec.short_when],
        "spec": spec.to_json(),
    }


def _spec_text(file: Path | None, spec: str | None) -> str:
    if (file is None) == (spec is None):
        raise DataError("give exactly one of --file PATH or --spec JSON")
    if file is not None:
        if not file.is_file():
            raise DataError(f"rule spec file not found: {file}")
        return file.read_text(encoding="utf-8")
    return str(spec)


def _emit(payload: dict[str, Any], json_out: bool, text: str) -> None:
    typer.echo(json.dumps(payload) if json_out else text)


@rules_app.command("save")
def save(
    name: str,
    file: Path | None = typer.Option(None, "--file", help="rule spec JSON file"),  # noqa: B008
    spec: str | None = typer.Option(None, "--spec", help="rule spec JSON text"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Validate a rule spec and save it canonically as data_dir/rules/NAME.json (overwrites)."""
    from alpha_strategies.rules import canonical_json, rule_spec_from_json

    data_dir = AlphaSettings().data_dir
    try:
        path = rule_path(data_dir, name)
        canonical = canonical_json(rule_spec_from_json(_spec_text(file, spec)))
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(canonical + "\n", encoding="utf-8")
    os.replace(tmp, path)
    record = _record(name, canonical, path)
    _emit(record, json_out, f"saved rule {name} ({record['sha256'][:12]}) -> {path}")


@rules_app.command("list")
def list_rules(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Every saved rule in name order."""
    data_dir = AlphaSettings().data_dir
    rows: list[dict[str, Any]] = []
    directory = rules_dir(data_dir)
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            rows.append(_record(path.stem, path.read_text(encoding="utf-8"), path))
        except DataError as exc:  # a hand-edited file must not hide the rest of the list
            rows.append({"name": path.stem, "path": str(path), "error": str(exc)})
    if json_out:
        typer.echo(json.dumps({"rules": rows, "authority": "none"}))
    else:
        for row in rows:
            typer.echo(f"{row['name']}: {row.get('spec_name', row.get('error'))}")
        if not rows:
            typer.echo("no saved rules")


@rules_app.command("show")
def show(name: str, json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """One saved rule with its canonical spec and hash."""
    data_dir = AlphaSettings().data_dir
    try:
        record = _record(name, load_rule_text(data_dir, name), rule_path(data_dir, name))
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        record,
        json_out,
        f"{name} ({record['sha256'][:12]}): long when {record['long_conditions']}, "
        f"short when {record['short_conditions']}, history {record['history']}",
    )


@rules_app.command("validate")
def validate(
    file: Path | None = typer.Option(None, "--file", help="rule spec JSON file"),  # noqa: B008
    spec: str | None = typer.Option(None, "--spec", help="rule spec JSON text"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Parse a rule spec strictly without saving it; exit 2 with the defect if it is invalid."""
    from alpha_strategies.rules import canonical_json, rule_spec_from_json

    try:
        text = _spec_text(file, spec)
        canonical = canonical_json(rule_spec_from_json(text))
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    record = _record("(unsaved)", canonical, Path("-"))
    record.pop("path")
    record["valid"] = True
    _emit(record, json_out, f"valid rule spec {record['spec_name']!r} ({record['sha256'][:12]})")


@rules_app.command("delete")
def delete(name: str, json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Remove a saved rule file; runs that used it keep their manifest copy of the spec."""
    data_dir = AlphaSettings().data_dir
    try:
        path = rule_path(data_dir, name)
        if not path.is_file():
            raise DataError(f"no saved rule {name!r}")
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    path.unlink()
    _emit({"name": name, "deleted": True}, json_out, f"deleted rule {name}")
