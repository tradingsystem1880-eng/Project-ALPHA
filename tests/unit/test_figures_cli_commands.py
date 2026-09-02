"""The `alpha figures` commands, driven in-process.

The end-to-end tests spawn a real CLI, which proves the wiring but leaves the command
bodies invisible to both coverage and to a fast feedback loop. These exercise the same
functions directly against a tiny synthetic run.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from typer.testing import CliRunner, Result

from alpha_cli.figures_cmds import figures_app

_RUN = "00112233445566aa"


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A minimal but genuinely readable v3 run: equity only, no trades, no snapshot."""
    root = tmp_path / "data"
    rdir = root / "runs" / _RUN
    rdir.mkdir(parents=True)
    frame = pl.DataFrame(
        {
            "ts": pl.datetime_range(
                pl.datetime(2024, 1, 1),
                pl.datetime(2024, 4, 9),
                "1d",
                eager=True,
                time_zone="UTC",
            ),
            "equity": [1_000_000.0 * (1.0 + index / 400) for index in range(100)],
        }
    )
    frame.write_parquet(rdir / "equity_curve.parquet")
    (rdir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": _RUN,
                "command": "backtest_run",
                "artifact_contract_version": 3,
                "metadata": {"symbol": "TEST", "strategy_name": "ts_momentum"},
                "artifacts": {"equity_curve.parquet": {"sha256": "a" * 64}},
            }
        )
    )
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    yield root


@pytest.fixture
def run() -> CliRunner:
    return CliRunner()


def _json(result: Result) -> dict[str, Any]:
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


class TestList:
    def test_the_bare_catalogue_publishes_the_key_environment(
        self, run: CliRunner, data_dir: Path
    ) -> None:
        result = run.invoke(figures_app, ["list", "--json"])
        assert result.exit_code == 0, result.output
        payload = _json(result)
        assert payload["renderer_version"] >= 1
        assert payload["theme_digest"]
        assert len(payload["figures"]) >= 20

    def test_a_run_scoped_list_says_why_each_figure_cannot_draw(
        self, run: CliRunner, data_dir: Path
    ) -> None:
        result = run.invoke(figures_app, ["list", "--run", _RUN, "--json"])
        assert result.exit_code == 0, result.output
        items = {item["figure_id"]: item for item in _json(result)["items"]}
        assert items["equity_underwater"]["available"] is True
        assert items["trade_pnl"]["unavailable_reason"] == "artifact_missing:trades.parquet"
        # Missing inputs are reported before the snapshot check, so the first thing wrong
        # is the thing named -- a reader fixes one cause at a time.
        assert (
            items["price_signal"]["unavailable_reason"]
            == "artifact_missing:execution_trace.parquet"
        )

    def test_the_human_rendering_names_every_figure(self, run: CliRunner, data_dir: Path) -> None:
        result = run.invoke(figures_app, ["list"])
        assert result.exit_code == 0
        assert "equity_underwater" in result.output


class TestRender:
    def test_rendering_writes_an_image_and_its_sidecar(
        self, run: CliRunner, data_dir: Path
    ) -> None:
        result = run.invoke(
            figures_app, ["render", _RUN, "--figure", "equity_underwater", "--json"]
        )
        assert result.exit_code == 0, result.output
        entry = _json(result)["figures"][0]
        image = Path(entry["path"])
        assert image.is_file()
        assert image.with_suffix(".json").is_file()
        assert entry["cached"] is False

    def test_an_inapplicable_figure_is_rejected_rather_than_silently_skipped(
        self, run: CliRunner, data_dir: Path
    ) -> None:
        result = run.invoke(figures_app, ["render", _RUN, "--figure", "optim_surface", "--json"])
        assert result.exit_code != 0
        assert "not applicable" in result.output

    def test_png_is_available_alongside_svg(self, run: CliRunner, data_dir: Path) -> None:
        result = run.invoke(
            figures_app,
            ["render", _RUN, "--figure", "equity_underwater", "--format", "png", "--json"],
        )
        assert result.exit_code == 0, result.output
        assert Path(_json(result)["figures"][0]["path"]).suffix == ".png"

    def test_a_pack_render_reports_what_it_could_not_draw(
        self, run: CliRunner, data_dir: Path
    ) -> None:
        result = run.invoke(figures_app, ["render", _RUN, "--json"])
        assert result.exit_code == 0, result.output
        payload = _json(result)
        assert payload["figures"]
        assert {item["figure_id"] for item in payload["skipped"]}


class TestPathAndTheme:
    def test_path_reports_the_key_without_rendering(self, run: CliRunner, data_dir: Path) -> None:
        result = run.invoke(figures_app, ["path", _RUN, "--figure", "equity_underwater", "--json"])
        assert result.exit_code == 0, result.output
        payload = _json(result)
        assert payload["cached"] is False
        assert not Path(payload["path"]).exists()
        assert len(payload["cache_key"]) == 16

    def test_the_path_matches_what_render_actually_writes(
        self, run: CliRunner, data_dir: Path
    ) -> None:
        predicted = _json(
            run.invoke(figures_app, ["path", _RUN, "--figure", "equity_underwater", "--json"])
        )
        rendered = _json(
            run.invoke(figures_app, ["render", _RUN, "--figure", "equity_underwater", "--json"])
        )["figures"][0]
        assert predicted["path"] == rendered["path"]
        assert predicted["cache_key"] == rendered["cache_key"]

    def test_theme_emits_the_shared_token_document(self, run: CliRunner, data_dir: Path) -> None:
        payload = _json(run.invoke(figures_app, ["theme", "--json"]))
        assert payload["theme_id"] == "terminal-classic"
        assert payload["substrate"] != payload["accent"]

    def test_theme_css_writes_then_checks_the_generated_stylesheet(
        self, run: CliRunner, tmp_path: Path
    ) -> None:
        out = tmp_path / "theme.generated.css"
        stale = run.invoke(figures_app, ["theme-css", "--out", str(out), "--check"])
        assert stale.exit_code != 0
        assert run.invoke(figures_app, ["theme-css", "--out", str(out)]).exit_code == 0
        assert "--canvas-bg: #000000;" in out.read_text("utf-8")
        assert run.invoke(figures_app, ["theme-css", "--out", str(out), "--check"]).exit_code == 0


class TestExportAndClean:
    def test_export_writes_outside_the_cache(
        self, run: CliRunner, data_dir: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "deck" / "equity.png"
        result = run.invoke(
            figures_app,
            ["export", _RUN, "--figure", "equity_underwater", "--out", str(target)],
        )
        assert result.exit_code == 0, result.output
        assert target.is_file()
        assert "figures" not in target.parts

    def test_clean_needs_a_target(self, run: CliRunner, data_dir: Path) -> None:
        run.invoke(figures_app, ["render", _RUN, "--figure", "equity_underwater", "--json"])
        assert run.invoke(figures_app, ["clean", "--json"]).exit_code != 0

    def test_clean_all_empties_the_cache_only(self, run: CliRunner, data_dir: Path) -> None:
        run.invoke(figures_app, ["render", _RUN, "--figure", "equity_underwater", "--json"])
        result = run.invoke(figures_app, ["clean", "--all", "--json"])
        assert result.exit_code == 0, result.output
        assert _json(result)["removed"] == [_RUN]
        assert (data_dir / "runs" / _RUN / "equity_curve.parquet").is_file()

    def test_cleaning_an_empty_cache_is_not_an_error(self, run: CliRunner, data_dir: Path) -> None:
        assert run.invoke(figures_app, ["clean", "--all", "--json"]).exit_code == 0
