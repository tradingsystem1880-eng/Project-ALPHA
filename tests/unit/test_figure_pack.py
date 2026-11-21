"""The figure pack: readable on a full screen, honest about its data, one theme rule."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from alpha_cli.figures import build_figure_spec
from alpha_cli.spine.run import run_idea
from alpha_cli.spine.spec import load_spec
from alpha_data.store import ParquetStore
from alpha_research.figures import RuleMark
from tests.fixtures.cli_fixtures import seed_store


@pytest.fixture(scope="module")
def rule_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any], Path]:
    home = tmp_path_factory.mktemp("pack")
    seed_store(home, symbol="SPY", n=400)
    ParquetStore(home / "store").write_provenance(
        "SPY", source="fixture", adapter_version="1", parser_version="1"
    )
    idea = load_spec(None, rule="ma_cross", param=["fast=5", "slow=20"], asset=["SPY"])
    result = run_idea(idea, home=home, quick=True)["results"][0]
    assert result["error"] is None, result["error"]
    rdir = Path(result["run_dir"])
    return rdir, json.loads((rdir / "manifest.json").read_bytes()), rdir.parent.parent


def test_return_distribution_mean_is_the_mean_of_the_stored_daily_returns(
    rule_run: tuple[Path, dict[str, Any], Path],
) -> None:
    rdir, manifest, data_dir = rule_run
    equity = pl.read_parquet(rdir / "equity_curve.parquet")["equity"].to_numpy()
    stored_mean = float(np.mean(equity[1:] / equity[:-1] - 1.0))
    spec = build_figure_spec(
        "return_distribution", run_id=rdir.name, rdir=rdir, manifest=manifest, data_dir=data_dir
    )
    rule = next(m for m in spec.panels[0].marks if isinstance(m, RuleMark))
    assert rule.position == pytest.approx(stored_mean, abs=1e-12)


def test_return_distribution_mean_does_not_come_from_bin_centres(tmp_path: Path) -> None:
    """Bins start at the minimum, so a centre-weighted mean can flip sign; stored returns cannot."""
    rng = np.random.default_rng(3)
    returns = np.sort(np.append(rng.normal(0.0008, 0.004, 1500), [-0.12, 0.09]))
    counts, edges = np.histogram(returns, bins=20)
    rows: list[dict[str, Any]] = [
        {
            "kind": "histogram",
            "index": i,
            "left": float(edges[i]),
            "right": float(edges[i + 1]),
            "count": int(c),
            "probability": None,
            "theoretical": None,
            "sample": None,
        }
        for i, c in enumerate(counts)
    ] + [
        {
            "kind": "qq",
            "index": i,
            "left": None,
            "right": None,
            "count": None,
            "probability": (i + 0.5) / len(returns),
            "theoretical": float(i) / len(returns),
            "sample": float(v),
        }
        for i, v in enumerate(returns)
    ]
    schema = {
        "kind": pl.String,
        "index": pl.Int64,
        "left": pl.Float64,
        "right": pl.Float64,
        "count": pl.Int64,
        "probability": pl.Float64,
        "theoretical": pl.Float64,
        "sample": pl.Float64,
    }
    pl.DataFrame(rows, schema=schema).write_parquet(tmp_path / "return_distribution.parquet")
    spec = build_figure_spec(
        "return_distribution", run_id="fixture", rdir=tmp_path, manifest={}, data_dir=tmp_path
    )
    marks = spec.panels[0].marks
    rule = next(m for m in marks if isinstance(m, RuleMark))
    assert rule.position == pytest.approx(float(returns.mean()), abs=1e-12)
    hist = marks[0]
    # range follows the data quantiles, not the two outliers; bins are finer than 20-over-range
    assert hist.edges[0] > -0.05 and hist.edges[-1] < 0.05  # type: ignore[union-attr]
    assert len(hist.counts) >= 15  # type: ignore[union-attr]
