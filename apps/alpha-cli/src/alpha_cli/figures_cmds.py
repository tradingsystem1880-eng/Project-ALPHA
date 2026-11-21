"""``alpha figures`` -- render, list and prune the derived figure cache.

Heavy imports stay inside command bodies. ``alpha --help`` and every other sub-command
must not pay for matplotlib, because the Workstation subprocesses this CLI on its hot
path and a 1.5s import tax on every projection would be felt.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Annotated, Any, Final

import typer

from alpha_cli.figure_cache import STYLE_ID, VARIANTS, validate_variant
from alpha_core import DataError
from alpha_core.config import AlphaSettings

_STYLE_DIGEST: Final = hashlib.sha256(STYLE_ID.encode("utf-8")).hexdigest()[:16]
_DARK_NOTE: Final = "Accepted for old callers. Every figure is the same white chart."


figures_app = typer.Typer(help="Render publication-quality figures for a stored run.")

_OPT_JSON = Annotated[bool, typer.Option("--json", help="Emit a machine-readable projection.")]
_OPT_VARIANT = Annotated[
    str, typer.Option("--variant", help="plain (the standard chart) or annotated (explained).")
]


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
    variant: str = "plain",
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
    from alpha_cli.figures.rule_periods import definition as run_definition
    from alpha_cli.figures.variants import explanation, fixed_text, render_variant
    from alpha_research.figures import RENDERER_VERSION, default_size

    definition = run_definition(figure_id)
    variant = validate_variant(variant)
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
        theme_id=STYLE_ID,
        theme_digest=_STYLE_DIGEST,
        width_in=size.width_in,
        height_in=size.height_in,
        dpi=size.dpi,
        fmt=fmt,
        background="theme",
        variant=variant,
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
    payload = render_variant(spec, variant, fmt)
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
        json.dumps(
            _sidecar(
                spec, definition, key, fmt, size, variant, explanation(spec, fixed_text(figure_id))
            ),
            sort_keys=True,
            indent=2,
        ).encode(),
    )
    return {
        "figure_id": figure_id,
        "cache_key": key,
        "path": str(image),
        "format": fmt,
        "bytes": len(payload),
        "cached": False,
    }


def store_rule_figures(rdir: Path, manifest: dict[str, Any], data_dir: Path) -> None:
    """Populate the ordinary immutable figure cache before exposing the completed rule run."""
    from alpha_cli.figures.rule_periods import CHARTS, TRADABLE

    for variant in VARIANTS:
        for figure in (*TRADABLE, *CHARTS):
            _render_one(
                figure,
                run_id=rdir.name,
                rdir=rdir,
                manifest=manifest,
                data_dir=data_dir,
                fmt="svg",
                force=False,
                variant=variant,
            )


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


def _sidecar(
    spec: Any,
    definition: Any,
    key: str,
    fmt: str,
    size: Any,
    variant: str,
    explanation: list[str],
) -> dict[str, Any]:
    from alpha_research.figures import RENDERER_VERSION

    return {
        "alt_text": definition.summary,
        "cache_key": key,
        "caption": spec.caption,
        "caveat": spec.caveat,
        "explanation": explanation,
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
        "variant": variant,
        "width_in": size.width_in,
        "x_label": spec.x_label,
    }


def _catalogue_envelope() -> dict[str, Any]:
    from dataclasses import asdict

    import matplotlib

    from alpha_cli.figures.rule_periods import TRADABLE, definition
    from alpha_cli.figures.variants import fixed_text
    from alpha_research.figures import RENDERER_VERSION, catalog_document, default_size

    figures = []

    for item in [*catalog_document(), *(asdict(definition(name)) for name in TRADABLE)]:
        panel_count = item["panel_count"]
        assert isinstance(panel_count, int)
        size = default_size(panel_count)
        figures.append(
            {
                **item,
                "variants": list(VARIANTS),
                "explanation": list(fixed_text(item["figure_id"])),
                "width_in": size.width_in,
                "height_in": size.height_in,
                "dpi": size.dpi,
            }
        )
    return {
        "renderer_version": RENDERER_VERSION,
        "matplotlib_version": matplotlib.__version__,
        "theme_id": STYLE_ID,
        "theme_digest": _STYLE_DIGEST,
        "variants": list(VARIANTS),
        "figures": figures,
    }


@figures_app.command("list")
def list_figures(
    run: Annotated[str | None, typer.Option("--run", help="Annotate for one stored run.")] = None,
    as_json: _OPT_JSON = False,
) -> None:
    """Show the figure catalogue, optionally with per-run availability.

    Without ``--run`` the projection also carries the *key environment* -- renderer and
    matplotlib versions, the theme digest, and each figure's canvas size and inputs. The
    Workstation caches that once and derives cache keys locally, so a cache hit costs a
    stat instead of spawning a process. It is published here rather than imported because
    the web layer is forbidden from importing the renderer at all.
    """
    if run is None:
        _echo(
            _catalogue_envelope(),
            as_json=as_json,
            human="\n".join(
                f"{item['figure_id']:24s} {item['title']}"
                for item in _catalogue_envelope()["figures"]
            ),
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
    variant: _OPT_VARIANT = "plain",
    dark: bool = typer.Option(False, "--dark", help=_DARK_NOTE),
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
                    variant=variant,
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
    variant: _OPT_VARIANT = "plain",
    dark: bool = typer.Option(False, "--dark", help=_DARK_NOTE),
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
    from alpha_cli.figures.rule_periods import definition as run_definition
    from alpha_research.figures import RENDERER_VERSION, default_size

    data_dir = _data_dir()
    rdir, manifest = resolve_run(run_id, data_dir=data_dir)

    definition = run_definition(figure)
    variant = validate_variant(variant)
    size = default_size(definition.panel_count)
    digest, kind = input_digest(
        manifest, rdir, definition.required_artifacts + definition.optional_artifacts
    )
    key = CacheKeyInputs(
        run_id=run_id,
        figure_id=figure,
        renderer_version=RENDERER_VERSION,
        matplotlib_version=matplotlib.__version__,
        theme_id=STYLE_ID,
        theme_digest=_STYLE_DIGEST,
        width_in=size.width_in,
        height_in=size.height_in,
        dpi=size.dpi,
        fmt=validate_format(fmt),
        background="theme",
        variant=variant,
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


#: Figure-theme roles the SPA mirrors as `--canvas-*` custom properties (chart surfaces only;
#: the light chrome palette is hand-written in index.css and AA-tested separately).
CANVAS_ROLES: Final = (
    "bg",
    "panel",
    "line",
    "grid",
    "ink",
    "ink_dim",
    "muted",
    "faint",
    "accent",
    "up",
    "down",
    "gold",
    "substrate",
)


def theme_css(document: dict[str, object]) -> str:
    """The generated stylesheet for one theme document: `--canvas-*` colour tokens, the canvas
    font stack and the terminal geometry (square corners, 11px UI). Byte-stable by construction
    so `--check` can compare it exactly."""
    lines = [
        f"/* GENERATED by `alpha figures theme-css` from theme {document['theme_id']!s};",
        "   do not edit. Canvas tokens mirror alpha_research/figures/themes; chrome tokens live",
        "   in index.css. */",
        ":root {",
    ]
    for role in CANVAS_ROLES:
        lines.append(f"  --canvas-{role.replace('_', '-')}: {document[role]};")
    lines.append(f'  --canvas-font: 11px Verdana, Tahoma, "{document["font_family"]}", sans-serif;')
    lines.extend(["  --r: 0;", "  --r-lg: 0;", "  --font-size: 11px;", "}"])
    return "\n".join(lines) + "\n"


@figures_app.command("theme-css")
def theme_css_command(
    out: Annotated[Path, typer.Option(help="Stylesheet to write")],
    check: Annotated[bool, typer.Option("--check", help="Fail if the file is not current")] = False,
) -> None:
    """Write (or verify) the SPA's generated theme stylesheet."""
    from alpha_research.figures import load_theme, theme_document

    expected = theme_css(theme_document(load_theme()))
    if check:
        current = out.read_text("utf-8") if out.is_file() else None
        if current != expected:
            raise typer.BadParameter(f"{out} is stale; run `alpha figures theme-css --out {out}`")
        typer.echo(f"{out} is current")
        return
    out.write_text(expected, encoding="utf-8")
    typer.echo(f"wrote {out}")


@figures_app.command("export")
def export(
    run_id: Annotated[str, typer.Argument(help="Stored run id.")],
    figure: Annotated[str, typer.Option("--figure", help="Figure id.")],
    out: Annotated[Path, typer.Option("--out", help="Destination file.")],
    fmt: Annotated[str, typer.Option("--format", help="svg or png.")] = "png",
    variant: _OPT_VARIANT = "plain",
    dark: bool = typer.Option(False, "--dark", help=_DARK_NOTE),
) -> None:
    """Write one figure outside the cache, for a paper or a deck."""
    from alpha_cli.figures import build_figure_spec, resolve_run
    from alpha_cli.figures.variants import render_variant

    data_dir = _data_dir()
    rdir, manifest = resolve_run(run_id, data_dir=data_dir)
    spec = build_figure_spec(figure, run_id=run_id, rdir=rdir, manifest=manifest, data_dir=data_dir)
    payload = render_variant(spec, variant, fmt)
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
