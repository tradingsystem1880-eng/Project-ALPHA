"""Builders whose run kinds the stored corpus cannot reach.

The optim, prop-firm and forecast runs on disk are mostly pre-hardening manifests with no
sidecars, so the integration sweep never exercises those six builders. Synthetic runs
close that gap and, unlike the stored corpus, let the degenerate cases be constructed
deliberately: a sweep where every trial failed, paths that never cleared, a forecast whose
origins are all pre-cutoff.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_cli.figures import build_figure_spec
from alpha_core import DataError
from alpha_research.figures import RenderOptions, default_size, load_theme, render_figure

_RUN = "0f0f0f0f0f0f0f0f"


def _run_dir(tmp_path: Path, command: str, **metadata: object) -> Path:
    rdir = tmp_path / command
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": _RUN,
                "command": command,
                "artifact_contract_version": 3,
                "metadata": {"symbol": "TEST", "strategy_name": "ts_momentum"},
                **metadata,
            }
        )
    )
    return rdir


def _build(rdir: Path, figure_id: str, tmp_path: Path) -> object:
    manifest = json.loads((rdir / "manifest.json").read_text())
    spec = build_figure_spec(
        figure_id, run_id=_RUN, rdir=rdir, manifest=manifest, data_dir=tmp_path
    )
    payload = render_figure(
        spec, RenderOptions(theme=load_theme(), size=default_size(spec.panel_count), fmt="svg")
    )
    assert payload.startswith(b"<?xml")
    return spec


def _stamps(count: int) -> list[datetime]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return [start + timedelta(days=index) for index in range(count)]


class TestOptim:
    def _ledger(self, rdir: Path, statuses: list[str]) -> None:
        pl.DataFrame(
            {
                "trial": list(range(len(statuses))),
                "status": statuses,
                "config_json": [
                    json.dumps(
                        [["lookback", 20.0 + 20 * (i % 3)], ["target_vol", 0.1 + 0.05 * (i // 3)]]
                    )
                    for i in range(len(statuses))
                ],
                "config_fingerprint": ["f" * 16] * len(statuses),
                "error": [None] * len(statuses),
                "annualized_sharpe": [
                    None if state != "passed" else 0.4 + index / 20
                    for index, state in enumerate(statuses)
                ],
                "n_oos": [60] * len(statuses),
                "oos_returns": [[0.001] * 5] * len(statuses),
            }
        ).write_parquet(rdir / "trial_ledger.parquet")

    def test_the_parameter_surface_marks_failures_rather_than_leaving_gaps(
        self, tmp_path: Path
    ) -> None:
        rdir = _run_dir(tmp_path, "optim_grid")
        self._ledger(rdir, ["passed"] * 7 + ["failed", "pruned"])
        spec = _build(rdir, "optim_surface", tmp_path)
        assert "7 of 9" in spec.plain_language_answer  # type: ignore[attr-defined]

    def test_a_sweep_where_everything_failed_still_draws_and_says_so(self, tmp_path: Path) -> None:
        """A blank grid would read as "all bad"; it must read as "none completed"."""
        rdir = _run_dir(tmp_path, "optim_grid")
        self._ledger(rdir, ["failed"] * 6)
        spec = _build(rdir, "optim_surface", tmp_path)
        assert "None of the 6" in spec.plain_language_answer  # type: ignore[attr-defined]

    def test_a_sweep_with_nothing_varying_is_refused(self, tmp_path: Path) -> None:
        rdir = _run_dir(tmp_path, "optim_grid")
        pl.DataFrame(
            {
                "trial": [0, 1],
                "status": ["passed", "passed"],
                "config_json": [json.dumps([["lookback", 20.0]])] * 2,
                "config_fingerprint": ["f" * 16] * 2,
                "error": [None, None],
                "annualized_sharpe": [0.5, 0.6],
                "n_oos": [60, 60],
                "oos_returns": [[0.001]] * 2,
            }
        ).write_parquet(rdir / "trial_ledger.parquet")
        with pytest.raises(DataError, match="no parameter varied"):
            _build(rdir, "optim_surface", tmp_path)

    def test_trial_curves_light_the_selected_configuration(self, tmp_path: Path) -> None:
        rdir = _run_dir(tmp_path, "optim_grid", best_trial=1)
        pl.DataFrame(
            {
                "trial": [0] * 5 + [1] * 5,
                "step": list(range(5)) * 2,
                "oos_return": [0.001] * 5 + [0.004] * 5,
            }
        ).write_parquet(rdir / "trials.parquet")
        spec = _build(rdir, "optim_trials", tmp_path)
        labels = [mark.label for mark in spec.panels[0].marks]  # type: ignore[attr-defined]
        assert "Selected configuration" in labels


class TestPropFirm:
    def test_paths_that_never_cleared_are_excluded_and_counted(self, tmp_path: Path) -> None:
        """Silently dropping them would turn "most attempts failed" into a tidy success curve."""
        rdir = _run_dir(tmp_path, "propfirm_run")
        pl.DataFrame(
            {
                "path_index": list(range(10)),
                "passed": [True] * 4 + [False] * 6,
                "busted": [False] * 4 + [True] * 6,
                "days_to_pass": [30.0, 45.0, 51.0, 62.0, *[None] * 6],
                "payout": [1200.0, 900.0, 1500.0, 300.0, *[0.0] * 6],
            }
        ).write_parquet(rdir / "propfirm_paths.parquet")
        spec = _build(rdir, "propfirm_outcomes", tmp_path)
        assert "40%" in spec.plain_language_answer  # type: ignore[attr-defined]
        notes = [panel.note for panel in spec.panels if panel.note]  # type: ignore[attr-defined]
        assert any("never cleared" in str(note) for note in notes)

    def test_a_sweep_where_none_cleared_still_draws_the_payout_panel(self, tmp_path: Path) -> None:
        rdir = _run_dir(tmp_path, "propfirm_run")
        pl.DataFrame(
            {
                "path_index": [0, 1, 2],
                "passed": [False] * 3,
                "busted": [True] * 3,
                "days_to_pass": [None] * 3,
                "payout": [0.0, 0.0, 0.0],
            }
        ).write_parquet(rdir / "propfirm_paths.parquet")
        spec = _build(rdir, "propfirm_outcomes", tmp_path)
        assert spec.panel_count == 1  # type: ignore[attr-defined]


class TestForecast:
    def _origins(self, rdir: Path, pre_cutoff: list[bool]) -> None:
        count = len(pre_cutoff)
        pl.DataFrame(
            {
                "origin_index": list(range(count)),
                "origin_ts": _stamps(count),
                "pre_cutoff": pre_cutoff,
                "crps": [0.02 + index / 500 for index in range(count)],
                "crps_rw": [0.03] * count,
                "crps_bootstrap": [0.035] * count,
                "realized_end_return": [0.01] * count,
                "median_end_return": [0.008] * count,
                "hit": [True, False] * (count // 2),
                "cover50": [True, False] * (count // 2),
                "cover80": [True] * count,
                "cover90": [True] * count,
            }
        ).write_parquet(rdir / "origins.parquet")

    def test_the_outcome_cone_reports_its_median_move_and_width(self, tmp_path: Path) -> None:
        rdir = _run_dir(tmp_path, "forecast_run")
        history = _stamps(30)
        pl.DataFrame(
            {
                "ts": history,
                "open": [100.0] * 30,
                "high": [101.0] * 30,
                "low": [99.0] * 30,
                "close": [100.0 + index / 10 for index in range(30)],
                "volume": [1000.0] * 30,
            }
        ).write_parquet(rdir / "history.parquet")
        future = [history[-1] + timedelta(days=index + 1) for index in range(10)]
        pl.DataFrame(
            {
                "ts": future,
                "step": list(range(10)),
                "q05": [100.0 - index for index in range(10)],
                "q25": [101.0 - index / 2 for index in range(10)],
                "q50": [103.0] * 10,
                "q75": [105.0 + index / 2 for index in range(10)],
                "q95": [107.0 + index for index in range(10)],
                "mean": [103.0] * 10,
            }
        ).write_parquet(rdir / "quantiles.parquet")
        spec = _build(rdir, "forecast_fan", tmp_path)
        assert "median path ends" in spec.plain_language_answer  # type: ignore[attr-defined]

    def test_skill_shades_the_pre_cutoff_region_it_cannot_vouch_for(self, tmp_path: Path) -> None:
        rdir = _run_dir(tmp_path, "forecast_eval")
        self._origins(rdir, [True] * 4 + [False] * 8)
        spec = _build(rdir, "forecast_skill", tmp_path)
        labels = [mark.label for mark in spec.panels[0].marks]  # type: ignore[attr-defined]
        assert any(label and "Pre-cutoff" in label for label in labels)

    def test_skill_omits_the_shading_when_nothing_is_pre_cutoff(self, tmp_path: Path) -> None:
        rdir = _run_dir(tmp_path, "forecast_eval")
        self._origins(rdir, [False] * 12)
        spec = _build(rdir, "forecast_skill", tmp_path)
        labels = [mark.label for mark in spec.panels[0].marks]  # type: ignore[attr-defined]
        assert not any(label and "Pre-cutoff" in label for label in labels)

    def test_calibration_reports_the_worst_gap_across_stored_levels(self, tmp_path: Path) -> None:
        rdir = _run_dir(tmp_path, "forecast_eval")
        self._origins(rdir, [False] * 12)
        spec = _build(rdir, "forecast_calibration", tmp_path)
        assert "Realised coverage differs" in spec.plain_language_answer  # type: ignore[attr-defined]


def test_a_wiped_out_passive_index_fails_loud_rather_than_dividing_by_zero(
    tmp_path: Path,
) -> None:
    """The relative lead is undefined when the benchmark ends at zero.

    A ZeroDivisionError here would escape the per-figure handler and abort the whole pack;
    a DataError leaves the rest of the report intact and says why this one is missing.
    """
    rdir = _run_dir(tmp_path, "backtest_run")
    stamps = _stamps(4)
    pl.DataFrame(
        {
            "ts": stamps,
            "strategy_equity": [1.0, 1.1, 1.2, 1.3],
            "benchmark_equity": [1.0, 0.5, 0.1, 0.0],
            "available": [True] * 4,
            "unavailable_reason": [None] * 4,
        }
    ).write_parquet(rdir / "benchmark_comparison.parquet")
    with pytest.raises(DataError, match="at or below zero"):
        _build(rdir, "equity_vs_passive", tmp_path)


@pytest.mark.parametrize(
    ("figure_id", "command"),
    [
        ("optim_surface", "optim_grid"),
        ("propfirm_outcomes", "propfirm_run"),
        ("forecast_skill", "forecast_eval"),
    ],
)
def test_a_missing_artifact_fails_loud_rather_than_drawing_nothing(
    tmp_path: Path, figure_id: str, command: str
) -> None:
    rdir = _run_dir(tmp_path, command)
    with pytest.raises(DataError, match="missing or empty"):
        _build(rdir, figure_id, tmp_path)


def test_every_synthetic_builder_is_one_the_catalogue_declares() -> None:
    """Guards against a test that quietly exercises a builder no longer offered."""
    from alpha_research.figures import FIGURES

    declared = {item.figure_id for item in FIGURES}
    exercised: set[str] = {
        "optim_surface",
        "optim_trials",
        "propfirm_outcomes",
        "forecast_fan",
        "forecast_skill",
        "forecast_calibration",
    }
    assert exercised <= declared
