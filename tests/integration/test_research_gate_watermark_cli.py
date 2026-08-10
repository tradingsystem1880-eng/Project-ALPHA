"""Runs launched under an owner research-gate override carry the EXPLORATORY watermark.

Spec §15 / ADR-0026 (R6g): the suite injects ``--research-gate-override`` when a governed
project's gate was overridden; the flag only ever downgrades a run's presentation (adds the
watermark), never upgrades it, so accepting it on the public CLI is safe. The marker joins run
identity so a watermarked run can never collide with an unmarked identity-matched run.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_cli.run_store import find_run_dir
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore
from tests.fixtures.cli_fixtures import seed_store

runner = CliRunner()

WATERMARK = "EXPLORATORY / RESEARCH GATE NOT COMPLETED"

_SMALL = [
    "--lookback", "5", "--skip", "1", "--vol-window", "3", "--rebalance-every", "2",
    "--fee-bps", "0", "--slippage-bps", "0", "--starting-cash", "100000",
]  # fmt: skip
_SPLIT = ["--train-size", "15", "--test-size", "5", "--embargo", "1"]


def _run_id(output: str) -> str:
    return output.split("-> run ")[1].split(":")[0].strip()


def _manifest(data_dir: Path, run_id: str) -> dict[str, object]:
    rdir = find_run_dir(data_dir, run_id)
    assert rdir is not None, f"run {run_id} not found"
    return json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))


def test_override_watermarks_manifest_forks_identity_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    plain = runner.invoke(app, ["backtest", "run", "SPY", *_SMALL])
    marked = runner.invoke(app, ["backtest", "run", "SPY", *_SMALL, "--research-gate-override"])
    assert plain.exit_code == 0, plain.output
    assert marked.exit_code == 0, marked.output

    plain_id = _run_id(plain.output)
    marked_id = _run_id(marked.output)
    # The marker joins run identity: a watermarked run is a DIFFERENT immutable run, so it can
    # never byte-conflict with (or silently replace) an unmarked identity-matched run.
    assert marked_id != plain_id

    plain_manifest = _manifest(tmp_path, plain_id)
    marked_manifest = _manifest(tmp_path, marked_id)
    assert "research_gate" not in plain_manifest
    assert marked_manifest["research_gate"] == {
        "state": "overridden",
        "watermark": WATERMARK,
    }

    marked_report = runner.invoke(app, ["report", marked_id])
    assert marked_report.exit_code == 0, marked_report.output
    assert WATERMARK in marked_report.output
    plain_report = runner.invoke(app, ["report", plain_id])
    assert plain_report.exit_code == 0, plain_report.output
    assert WATERMARK not in plain_report.output


def test_every_strategy_run_command_accepts_the_override_watermark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    for index, (symbol, drift) in enumerate(
        {"AAA": 0.012, "BBB": -0.004, "CCC": -0.012, "DDD": 0.004}.items()
    ):
        seed_store(tmp_path, symbol=symbol, n=120, seed=index, drift=drift, sigma=0.012)
    seed_store(tmp_path, symbol="SPY", n=100)
    create_snapshot(
        ParquetStore(tmp_path / "store"),
        tmp_path / "snapshots",
        "frozen",
        ["SPY"],
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 7, 19, tzinfo=UTC),
    )

    commands = [
        [
            "backtest",
            "oos",
            "SPY",
            *_SMALL,
            "--train-size",
            "30",
            "--test-size",
            "10",
            "--embargo",
            "2",
        ],  # fmt: skip
        [
            "validate",
            "SPY",
            *_SMALL,
            *_SPLIT,
            "--tier1-paths",
            "50",
            "--tier2-paths",
            "8",
            "--n-resamples",
            "200",
        ],  # fmt: skip
        [
            "optim",
            "grid",
            "SPY",
            *_SMALL,
            *_SPLIT,
            "--grid",
            "lookback=3,5",
            "--n-resamples",
            "200",
        ],  # fmt: skip
        ["backtest", "portfolio", "AAA", "BBB", *_SMALL, *_SPLIT],
        [
            "backtest",
            "cross-sectional",
            "AAA",
            "BBB",
            "CCC",
            "DDD",
            "--lookback",
            "5",
            "--skip",
            "1",
            "--vol-window",
            "3",
            "--rebalance-every",
            "2",
            "--top-quantile",
            "0.25",
        ],  # fmt: skip
        [
            "backtest",
            "holdout",
            "SPY",
            *_SMALL,
            "--snapshot",
            "frozen",
            "--holdout-start",
            "2020-03-01",
            "--holdout-end",
            "2020-03-30",
            "--holdout-spec-hash",
            "a" * 64,
            "--min-sharpe",
            "-100",
        ],  # fmt: skip
    ]
    for command in commands:
        result = runner.invoke(app, [*command, "--research-gate-override"])
        assert result.exit_code == 0, f"{command}: {result.output}"
        manifest = _manifest(tmp_path, _run_id(result.output))
        assert manifest["research_gate"] == {
            "state": "overridden",
            "watermark": WATERMARK,
        }, command
