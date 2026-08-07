"""``alpha figures`` -- render, list and prune the derived figure cache.

Heavy imports stay inside command bodies. ``alpha --help`` and every other sub-command
must not pay for matplotlib, because the Workstation subprocesses this CLI on its hot
path and a 1.5s import tax on every projection would be felt.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated, Any

import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings

figures_app = typer.Typer(help="Render publication-quality figures for a stored run.")

_OPT_JSON = Annotated[bool, typer.Option("--json", help="Emit a machine-readable projection.")]


def _data_dir() -> Path:
    return AlphaSettings().data_dir


def _echo(payload: dict[str, Any] | list[Any], *, as_json: bool, human: str) -> None:
    if as_json:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(human)


def _render_one(
    figure_id: str,
    *,
    run_id: str,
    rdir: Path,
    manifest: dict[str, Any],
    data_dir: Path,
    fmt: str,
    force: bool,
) -> dict[str, Any]:
    """Render one figure into the cache, atomically, and return its projection."""
    import matplotlib

    from alpha_cli.figure_cache import (
        CacheKeyInputs,
        figure_paths,
        input_digest,
        is_cached,
        validate_format,
    )
    from alpha_cli.figures import build_figure_spec
    from alpha_research.figures import (
        RENDERER_VERSION,
        RenderOptions,
        default_size,
        figure_definition,
        load_theme,
        render_figure,
    )

    definition = figure_definition(figure_id)
    theme = load_theme()
    size = default_size(definition.panel_count)
    fmt = validate_format(fmt)
    digest, kind = input_digest(
        manifest, rdir, definition.required_artifacts + definition.optional_artifacts
    )
    key = CacheKeyInputs(
        run_id=run_id,
        figure_id=figure_id,
        renderer_version=RENDERER_VERSION,
        matplotlib_version=matplotlib.__version__,
        theme_id=theme.theme_id,
        theme_digest=theme.digest(),
        width_in=size.width_in,
        height_in=size.height_in,
        dpi=size.dpi,
        fmt=fmt,
        background="theme",
        artifact_contract_version=manifest.get("artifact_contract_version"),
        input_digest=digest,
        input_digest_kind=kind,
    ).key()
    image, sidecar = figure_paths(data_dir, run_id, figure_id, key, fmt)
    if is_cached(image, sidecar) and not force:
        return {
            "figure_id": figure_id,
            "cache_key": key,
            "path": str(image),
            "format": fmt,
            "bytes": image.stat().st_size,
            "cached": True,
        }

    spec = build_figure_spec(
        figure_id, run_id=run_id, rdir=rdir, manifest=manifest, data_dir=data_dir
    )
    payload = render_figure(
        spec,
        RenderOptions(theme=theme, size=size, fmt=fmt),
    )
    if force and image.is_file():
        # A re-render at the same key must be byte-identical; if it is not, determinism
        # has regressed and silently overwriting would hide that.
        existing = image.read_bytes()
        if existing != payload:
            raise DataError(
                f"re-rendering {figure_id} at key {key} produced different bytes; "
                "the renderer is no longer deterministic for this input"
            )

    image.parent.mkdir(parents=True, exist_ok=True)
    _publish(image, payload)
    _publish(
        sidecar,
        json.dumps(_sidecar(spec, definition, key, fmt, size), sort_keys=True, indent=2).encode(),
    )
    return {
        "figure_id": figure_id,
        "cache_key": key,
        "path": str(image),
        "format": fmt,
        "bytes": len(payload),
        "cached": False,
    }


def _publish(path: Path, payload: bytes) -> None:
    """Write via a same-directory temp file and rename, so a reader never sees a torn file."""
    import os
    import tempfile

    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".figure-")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _sidecar(spec: Any, definition: Any, key: str, fmt: str, size: Any) -> dict[str, Any]:
    from alpha_research.figures import RENDERER_VERSION

    return {
        "alt_text": definition.summary,
        "cache_key": key,
        "caption": spec.caption,
        "caveat": spec.caveat,
        "figure_id": spec.figure_id,
        "format": fmt,
        "height_in": size.height_in,
        "panels": [
            {
                "panel_id": panel.panel_id,
                "y_label": panel.y_label,
                "y_unit": panel.y_unit,
                "note": panel.note,
                "legend": [mark.label for mark in panel.legend_entries],
            }
            for panel in spec.panels
        ],
        "plain_language_answer": spec.plain_language_answer,
        "question": spec.question,
        "renderer_version": RENDERER_VERSION,
        "source_artifacts": list(spec.source_artifacts),
        "subtitle": spec.subtitle,
        "title": spec.title,
        "truncation_note": spec.truncation_note,
        "uncertainty": spec.uncertainty,
        "width_in": size.width_in,
        "x_label": spec.x_label,
    }


@figures_app.command("list")
def list_figures(
    run: Annotated[str | None, typer.Option("--run", help="Annotate for one stored run.")] = None,
    as_json: _OPT_JSON = False,
) -> None:
    """Show the figure catalogue, optionally with per-run availability."""
    from alpha_research.figures import catalog_document

    if run is None:
        document = catalog_document()
        _echo(
            document,
            as_json=as_json,
            human="\n".join(f"{item['figure_id']:24s} {item['title']}" for item in document),
        )
        return

    from alpha_cli.figures import available_figures, resolve_run

    data_dir = _data_dir()
    rdir, manifest = resolve_run(run, data_dir=data_dir)
    items = [
        {
            "figure_id": entry.definition.figure_id,
            "title": entry.definition.title,
            "summary": entry.definition.summary,
            "section": entry.definition.section,
            "panel_count": entry.definition.panel_count,
            "available": entry.available,
            "unavailable_reason": entry.unavailable_reason,
        }
        for entry in available_figures(rdir, manifest)
    ]
    _echo(
        {"run_id": run, "kind": manifest.get("command"), "items": items},
        as_json=as_json,
        human="\n".join(
            f"{item['figure_id']:24s} {'ok' if item['available'] else item['unavailable_reason']}"
            for item in items
        ),
    )


@figures_app.command("render")
def render(
    run_id: Annotated[str, typer.Argument(help="Stored run id.")],
    figure: Annotated[
        list[str] | None, typer.Option("--figure", help="Render only these ids (repeatable).")
    ] = None,
    fmt: Annotated[str, typer.Option("--format", help="svg or png.")] = "svg",
    force: Annotated[
        bool, typer.Option("--force", help="Re-render and assert byte identity.")
    ] = False,
    as_json: _OPT_JSON = False,
) -> None:
    """Render figures for a run into the derived cache."""
    from alpha_cli.figures import available_figures, resolve_run

    data_dir = _data_dir()
    rdir, manifest = resolve_run(run_id, data_dir=data_dir)
    entries = available_figures(rdir, manifest)
    wanted = set(figure or [])
    if wanted:
        known = {entry.definition.figure_id for entry in entries}
        unknown = sorted(wanted - known)
        if unknown:
            raise typer.BadParameter(f"not applicable to this run: {', '.join(unknown)}")
        entries = tuple(entry for entry in entries if entry.definition.figure_id in wanted)

    rendered: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for entry in entries:
        figure_id = entry.definition.figure_id
        if not entry.available:
            skipped.append(
                {"figure_id": figure_id, "reason": entry.unavailable_reason or "unavailable"}
            )
            continue
        try:
            rendered.append(
                _render_one(
                    figure_id,
                    run_id=run_id,
                    rdir=rdir,
                    manifest=manifest,
                    data_dir=data_dir,
                    fmt=fmt,
                    force=force,
                )
            )
        except DataError as error:
            # A pack render is best-effort across figures: one figure whose input turns
            # out to be unreadable at render time must not cost the caller the other
            # eleven. The failure is reported, never swallowed, and the exit code below
            # still goes non-zero when nothing at all could be drawn.
            failed.append({"figure_id": figure_id, "error": str(error)})
    payload = {"run_id": run_id, "figures": rendered, "skipped": skipped, "failed": failed}
    _echo(
        payload,
        as_json=as_json,
        human=(
            "\n".join(
                f"{item['figure_id']:24s} {'cached' if item['cached'] else 'rendered'} "
                f"{item['bytes']:>8,}B  {item['path']}"
                for item in rendered
            )
            + ("\n" if rendered and (skipped or failed) else "")
            + "\n".join(f"{item['figure_id']:24s} skipped: {item['reason']}" for item in skipped)
            + ("\n" if skipped and failed else "")
            + "\n".join(f"{item['figure_id']:24s} FAILED: {item['error']}" for item in failed)
        ),
    )
    if failed and not rendered:
        raise typer.Exit(code=1)


@figures_app.command("path")
def path(
    run_id: Annotated[str, typer.Argument(help="Stored run id.")],
    figure: Annotated[str, typer.Option("--figure", help="Figure id.")],
    fmt: Annotated[str, typer.Option("--format", help="svg or png.")] = "svg",
    as_json: _OPT_JSON = False,
) -> None:
    """Print a figure's cache key and path without rendering it."""
    import matplotlib

    from alpha_cli.figure_cache import (
        CacheKeyInputs,
        figure_paths,
        input_digest,
        is_cached,
        validate_format,
    )
    from alpha_cli.figures import resolve_run
    from alpha_research.figures import RENDERER_VERSION, default_size, figure_definition, load_theme

    data_dir = _data_dir()
    rdir, manifest = resolve_run(run_id, data_dir=data_dir)
    definition = figure_definition(figure)
    theme = load_theme()
    size = default_size(definition.panel_count)
    digest, kind = input_digest(
        manifest, rdir, definition.required_artifacts + definition.optional_artifacts
    )
    key = CacheKeyInputs(
        run_id=run_id,
        figure_id=figure,
        renderer_version=RENDERER_VERSION,
        matplotlib_version=matplotlib.__version__,
        theme_id=theme.theme_id,
        theme_digest=theme.digest(),
        width_in=size.width_in,
        height_in=size.height_in,
        dpi=size.dpi,
        fmt=validate_format(fmt),
        background="theme",
        artifact_contract_version=manifest.get("artifact_contract_version"),
        input_digest=digest,
        input_digest_kind=kind,
    ).key()
    image, sidecar = figure_paths(data_dir, run_id, figure, key, fmt)
    payload = {
        "run_id": run_id,
        "figure_id": figure,
        "cache_key": key,
        "path": str(image),
        "sidecar": str(sidecar),
        "cached": is_cached(image, sidecar),
    }
    _echo(payload, as_json=as_json, human=f"{key}  {image}")


@figures_app.command("theme")
def theme(as_json: _OPT_JSON = False) -> None:
    """Emit the canonical figure theme document."""
    from alpha_research.figures import load_theme, theme_document

    document = theme_document(load_theme())
    _echo(
        document,
        as_json=as_json,
        human="\n".join(f"{key:16s} {value}" for key, value in sorted(document.items())),
    )


@figures_app.command("export")
def export(
    run_id: Annotated[str, typer.Argument(help="Stored run id.")],
    figure: Annotated[str, typer.Option("--figure", help="Figure id.")],
    out: Annotated[Path, typer.Option("--out", help="Destination file.")],
    fmt: Annotated[str, typer.Option("--format", help="svg or png.")] = "png",
) -> None:
    """Write one figure outside the cache, for a paper or a deck."""
    from alpha_cli.figures import build_figure_spec, resolve_run
    from alpha_research.figures import (
        RenderOptions,
        default_size,
        load_theme,
        render_figure,
    )

    data_dir = _data_dir()
    rdir, manifest = resolve_run(run_id, data_dir=data_dir)
    spec = build_figure_spec(figure, run_id=run_id, rdir=rdir, manifest=manifest, data_dir=data_dir)
    payload = render_figure(
        spec,
        RenderOptions(
            theme=load_theme(),
            size=default_size(spec.panel_count),
            fmt=fmt,  # type: ignore[arg-type]
        ),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    typer.echo(f"wrote {len(payload):,}B -> {out}")


@figures_app.command("clean")
def clean(
    run_id: Annotated[str | None, typer.Argument(help="Prune one run's figures.")] = None,
    all_runs: Annotated[bool, typer.Option("--all", help="Prune the entire cache.")] = False,
    as_json: _OPT_JSON = False,
) -> None:
    """Delete cached figures. Runs and their artifacts are never touched."""
    from alpha_cli.figure_cache import cache_root, validate_run_id

    data_dir = _data_dir()
    root = cache_root(data_dir)
    if not root.is_dir():
        _echo({"removed": []}, as_json=as_json, human="nothing to clean")
        return
    if all_runs:
        targets = sorted(child for child in root.iterdir() if child.is_dir())
    elif run_id is not None:
        targets = [root / validate_run_id(run_id)]
    else:
        raise typer.BadParameter("pass a run id or --all")
    removed = []
    for target in targets:
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(target.name)
    _echo(
        {"removed": removed},
        as_json=as_json,
        human=f"removed {len(removed)} cached run(s)",
    )
