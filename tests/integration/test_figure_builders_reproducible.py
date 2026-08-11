"""Every builder, against runs the test itself creates.

`test_figure_builders.py` sweeps the real corpus in ``data/``, which is richer than
anything a fixture can fake -- but that directory is gitignored, so on CI it skips and
proves nothing. This is the reproducible half: synthetic runs written into tmp, carrying
the same artifact schemas, so the renderer and every builder are actually exercised
wherever the suite runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.figures import available_figures, build_figure_spec, resolve_run
from alpha_cli.figures._builders import BUILDERS
from alpha_research.figures import (
    FIGURES,
    RenderOptions,
    default_size,
    load_theme,
    render_figure,
)
from alpha_research.figures.spec import _Y_UNITS
from tests import figure_runs


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("figure-corpus")
    figure_runs.all_runs(root)
    return root


def _render(spec: object) -> bytes:
    payload = render_figure(
        spec,  # type: ignore[arg-type]
        RenderOptions(
            theme=load_theme(),
            size=default_size(spec.panel_count),  # type: ignore[attr-defined]
            fmt="svg",
        ),
    )
    assert payload.startswith(b"<?xml")
    return payload


@pytest.mark.parametrize(
    "run_id",
    [figure_runs.BACKTEST_RUN, figure_runs.VALIDATE_RUN, figure_runs.PORTFOLIO_RUN],
)
def test_every_available_figure_builds_and_renders(synthetic: Path, run_id: str) -> None:
    rdir, manifest = resolve_run(run_id, data_dir=synthetic)
    offered = [item for item in available_figures(rdir, manifest) if item.available]
    assert offered, f"{run_id} offers no figures at all"

    for item in offered:
        spec = build_figure_spec(
            item.definition.figure_id,
            run_id=run_id,
            rdir=rdir,
            manifest=manifest,
            data_dir=synthetic,
        )
        _render(spec)

        # The invariants that make a figure readable rather than merely drawn.
        figure_id = item.definition.figure_id
        assert spec.plain_language_answer.strip(), f"{figure_id} answers nothing"
        assert spec.panels, f"{figure_id} drew nothing"
        for panel in spec.panels:
            assert panel.y_unit in _Y_UNITS, f"{figure_id}/{panel.panel_id}: {panel.y_unit}"
            assert panel.marks, f"{figure_id}/{panel.panel_id} is an empty panel"
            # A measured axis must name its unit; a categorical axis lists labels and
            # carries its quantity on a colourbar instead.
            if panel.y_unit not in {"category", "count", "index"}:
                assert "(" in panel.y_label, (
                    f"{figure_id}/{panel.panel_id} y-label carries no unit: {panel.y_label}"
                )


def test_the_synthetic_corpus_reaches_every_builder_the_stored_one_does(synthetic: Path) -> None:
    """A guard against the fixture quietly drifting behind the catalogue.

    If a new figure applies to a backtest, validate or portfolio run, this fixture must
    grow the artifact that feeds it -- otherwise the builder goes back to being covered
    only on the machine that happens to have a matching stored run.
    """
    reached: set[str] = set()
    for run_id in (figure_runs.BACKTEST_RUN, figure_runs.VALIDATE_RUN, figure_runs.PORTFOLIO_RUN):
        reached |= {
            item.definition.figure_id
            for item in available_figures(*resolve_run(run_id, data_dir=synthetic))
            if item.available
        }

    expected = {
        definition.figure_id
        for definition in FIGURES
        if {"backtest_run", "validate", "backtest_portfolio"} & set(definition.run_commands)
        # price_signal reads bars back through the point-in-time firewall from a frozen
        # snapshot, which means a real store and a real snapshot -- more machinery than a
        # fixture should fake. Its marks are covered directly in the renderer tests, and
        # the stored-corpus sweep exercises it end to end wherever a corpus exists.
        and not definition.requires_snapshot
    }
    assert expected - reached == set(), f"unreached: {sorted(expected - reached)}"


def test_the_catalogue_and_the_builders_agree() -> None:
    assert {definition.figure_id for definition in FIGURES} == set(BUILDERS)


def test_an_unavailable_figure_says_why_in_words(synthetic: Path) -> None:
    absent = [
        item
        for item in available_figures(*resolve_run(figure_runs.BACKTEST_RUN, data_dir=synthetic))
        if not item.available
    ]
    for item in absent:
        assert item.unavailable_reason, (
            f"{item.definition.figure_id} is absent for no stated reason"
        )


def test_rendering_never_touches_the_run_directory(synthetic: Path) -> None:
    """The whole derived-cache design exists to keep the artifact contract at 3."""
    rdir, manifest = resolve_run(figure_runs.VALIDATE_RUN, data_dir=synthetic)
    before = {path.name: path.read_bytes() for path in sorted(rdir.iterdir())}

    for item in available_figures(rdir, manifest):
        if not item.available:
            continue
        _render(
            build_figure_spec(
                item.definition.figure_id,
                run_id=figure_runs.VALIDATE_RUN,
                rdir=rdir,
                manifest=manifest,
                data_dir=synthetic,
            )
        )

    after = {path.name: path.read_bytes() for path in sorted(rdir.iterdir())}
    assert after == before
    # And the manifest still describes exactly what is on disk.
    declared = set(json.loads((rdir / "manifest.json").read_text())["artifacts"])
    assert declared == {name for name in after if name.endswith(".parquet")}


class TestPriceSignal:
    """The flagship figure, with its one non-artifact input stubbed.

    `price_signal` is the only builder whose input is not an immutable artifact: bars come
    back through the point-in-time firewall from a frozen snapshot, which the CLI reads by
    subprocessing `alpha data candles`. That subprocess is a seam, and stubbing it is what
    lets the other 150 lines of this builder -- the annotation polylines, the zone spans,
    the fill markers, the indicator grouping -- be exercised anywhere rather than only on a
    machine that happens to hold a matching snapshot.
    """

    @staticmethod
    def _rows(count: int) -> list[dict[str, float]]:
        start = 1_672_617_600.0  # 2023-01-02T00:00:00Z
        rows = []
        for index in range(count):
            close = 100.0 + index * 0.4
            rows.append(
                {
                    "t": start + index * 86_400.0,
                    "o": close - 0.5,
                    "h": close + 1.2,
                    "l": close - 1.4,
                    "c": close,
                    "v": 1_000.0 + index,
                }
            )
        return rows

    @pytest.fixture
    def snapshotted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[Path, dict[str, Any]]:
        root = tmp_path / "data"
        rdir = figure_runs.validate_run(root)
        manifest = json.loads((rdir / "manifest.json").read_text())
        manifest["metadata"]["snapshot_id"] = "snap-0001"
        return root, manifest

    @pytest.mark.parametrize(("bars", "expected_mark"), [(120, "candle"), (900, "line")])
    def test_it_draws_price_with_the_run_s_own_evidence_over_it(
        self,
        snapshotted: tuple[Path, dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
        bars: int,
        expected_mark: str,
    ) -> None:
        from alpha_cli.figures import _sources

        root, manifest = snapshotted
        rows = self._rows(bars)
        monkeypatch.setattr(_sources, "bars", lambda *a, **k: (rows, None))

        spec = build_figure_spec(
            "price_signal",
            run_id=figure_runs.VALIDATE_RUN,
            rdir=root / "runs" / figure_runs.VALIDATE_RUN,
            manifest=manifest,
            data_dir=root,
        )
        _render(spec)

        price = spec.panels[0]
        kinds = {type(mark).__name__ for mark in price.marks}
        # Above a bar threshold candles become an unreadable smear, so price recedes to a
        # thin line instead. Both branches must actually draw something.
        assert ("CandleMark" in kinds) is (expected_mark == "candle")
        assert ("LineMark" in kinds) is True

        # The strategy's own annotations, which is the entire point of this figure.
        labels = {getattr(mark, "label", None) for mark in price.marks}
        assert "double bottom" in labels
        assert "ZoneMark" in kinds
        assert "ScatterMark" in kinds, "fills must be marked on the price"
        assert price.note is None, "a run WITH annotations must not claim it emitted none"

        # Price-unit indicators overlay price; other units get their own panel.
        assert len(spec.panels) == 2
        assert spec.panels[1].y_unit == "ratio"
        assert "momentum_return" in {mark.label for mark in spec.panels[1].marks}

    def test_missing_bars_fail_loud_rather_than_drawing_an_empty_chart(
        self, snapshotted: tuple[Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from alpha_cli.figures import _sources
        from alpha_core import DataError

        root, manifest = snapshotted
        monkeypatch.setattr(_sources, "bars", lambda *a, **k: ([], "snapshot_unavailable"))
        with pytest.raises(DataError, match="snapshot_unavailable"):
            build_figure_spec(
                "price_signal",
                run_id=figure_runs.VALIDATE_RUN,
                rdir=root / "runs" / figure_runs.VALIDATE_RUN,
                manifest=manifest,
                data_dir=root,
            )
