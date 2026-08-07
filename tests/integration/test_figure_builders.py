"""Every builder, against every stored run kind, in-process.

The CLI tests drive the same code through a subprocess, which proves the wiring but
tells you nothing about which builders were actually exercised. This runs them directly:
each available figure is built and rendered, and the invariants that make a figure
readable -- a unit on every axis, a legend for every labelled mark, an answer that says
something about *this* run -- are asserted on the result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpha_cli.figures import available_figures, build_figure_spec, resolve_run
from alpha_cli.figures._builders import BUILDERS
from alpha_core import DataError
from alpha_research.figures import (
    FIGURES,
    HeatmapMark,
    RenderOptions,
    default_size,
    load_theme,
    render_figure,
)
from alpha_research.figures.spec import _Y_UNITS

_REPO = Path(__file__).resolve().parents[2]
_DATA = _REPO / "data"

pytestmark = pytest.mark.skipif(not (_DATA / "runs").is_dir(), reason="requires the stored runs")


def _stored_runs() -> list[str]:
    """One run per (kind, command) so every builder family gets a turn."""
    seen: dict[str, str] = {}
    for kind in ("runs", "optim", "portfolio", "cross_sectional", "propfirm", "forecast"):
        directory = _DATA / kind
        if not directory.is_dir():
            continue
        for child in sorted(directory.iterdir()):
            if not (child / "manifest.json").is_file():
                continue
            try:
                _, manifest = resolve_run(child.name, data_dir=_DATA)
            except DataError:
                continue
            command = str(manifest.get("command") or kind)
            seen.setdefault(command, child.name)
    return sorted(seen.values())


_RUNS = _stored_runs()


def test_the_catalogue_and_the_builders_agree() -> None:
    """A catalogue entry with no builder is a promise the UI cannot keep."""
    declared = {item.figure_id for item in FIGURES}
    assert declared == set(BUILDERS), declared.symmetric_difference(set(BUILDERS))


@pytest.mark.parametrize("run_id", _RUNS)
def test_every_available_figure_builds_and_renders(run_id: str) -> None:
    rdir, manifest = resolve_run(run_id, data_dir=_DATA)
    entries = available_figures(rdir, manifest)
    if not entries:
        pytest.skip(f"no figures apply to {manifest.get('command')}")

    built = 0
    claimed = 0
    for entry in entries:
        if not entry.available:
            assert entry.unavailable_reason, "an unavailable figure must say why"
            continue
        claimed += 1
        figure_id = entry.definition.figure_id
        try:
            spec = build_figure_spec(
                figure_id, run_id=run_id, rdir=rdir, manifest=manifest, data_dir=_DATA
            )
        except DataError as error:
            # Legitimate at render time (a missing snapshot, a benchmark this run type
            # never produces). It must be a typed, explained failure -- never a crash.
            assert str(error)
            continue

        assert spec.figure_id == figure_id
        assert spec.panels, f"{figure_id} drew nothing"
        assert spec.plain_language_answer.strip()
        assert spec.question.strip()
        for panel in spec.panels:
            assert panel.y_unit in _Y_UNITS, f"{figure_id}/{panel.panel_id} unit {panel.y_unit}"
            # A measured axis must name its unit; a categorical axis lists labels and
            # carries its quantity on a colourbar instead.
            if panel.y_unit not in {"category", "count", "index"}:
                assert "(" in panel.y_label, (
                    f"{figure_id}/{panel.panel_id} y-label carries no unit: {panel.y_label}"
                )
            assert panel.marks

        payload = render_figure(
            spec,
            RenderOptions(theme=load_theme(), size=default_size(spec.panel_count), fmt="svg"),
        )
        assert payload.startswith(b"<?xml")
        assert b"dc:date" not in payload
        built += 1

    # A legacy run can legitimately have nothing drawable -- that is what the
    # availability reasons are for. What must never happen is a figure claiming to be
    # available and then producing nothing at all.
    if claimed:
        assert built, f"{run_id} claimed {claimed} available figures but built none"


@pytest.mark.parametrize("run_id", _RUNS)
def test_a_heatmap_always_ships_a_unit_bearing_colourbar(run_id: str) -> None:
    """A heat grid without a scale is a decoration, not a measurement."""
    rdir, manifest = resolve_run(run_id, data_dir=_DATA)
    for entry in available_figures(rdir, manifest):
        if not entry.available:
            continue
        try:
            spec = build_figure_spec(
                entry.definition.figure_id,
                run_id=run_id,
                rdir=rdir,
                manifest=manifest,
                data_dir=_DATA,
            )
        except DataError:
            continue
        for panel in spec.panels:
            for mark in panel.marks:
                if isinstance(mark, HeatmapMark):
                    assert mark.colorbar_label.strip()
                    assert "(" in mark.colorbar_label


def test_the_stored_corpus_exercises_a_broad_slice_of_the_catalogue() -> None:
    """Guards the guard: if the corpus shrank, the parametrised test could pass vacuously."""
    drawn: set[str] = set()
    for run_id in _RUNS:
        rdir, manifest = resolve_run(run_id, data_dir=_DATA)
        for entry in available_figures(rdir, manifest):
            if entry.available:
                drawn.add(entry.definition.figure_id)
    assert len(drawn) >= 12, sorted(drawn)


def test_an_unknown_figure_id_is_refused() -> None:
    if not _RUNS:
        pytest.skip("no stored runs")
    rdir, manifest = resolve_run(_RUNS[0], data_dir=_DATA)
    with pytest.raises(DataError, match="no builder implemented"):
        build_figure_spec(
            "not_a_figure", run_id=_RUNS[0], rdir=rdir, manifest=manifest, data_dir=_DATA
        )


def test_an_unknown_run_is_refused() -> None:
    with pytest.raises(DataError, match="unknown completed run"):
        resolve_run("ffffffffffffffff", data_dir=_DATA)


def test_a_malformed_run_id_is_refused() -> None:
    with pytest.raises(DataError, match="invalid run id"):
        resolve_run("../../etc", data_dir=_DATA)
