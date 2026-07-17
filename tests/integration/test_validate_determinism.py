"""Reproducibility (spec §11.4): same data + seed -> byte-identical manifest and OOS arrays.

Runs the gauntlet twice with identical inputs and compares the serialized manifest byte-for-byte
(and the OOS equity/returns arrays). The HTML tear sheet carries volatile fields and is excluded.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np

from alpha_cli._gauntlet import GauntletParams, run_gauntlet
from alpha_cli._runner import RunSpec
from alpha_core import Bar
from alpha_validation import report_to_manifest

_SPEC = RunSpec(
    lookback=5,
    skip=1,
    vol_window=3,
    target_vol=0.15,
    rebalance_every=2,
    max_leverage=1.0,
    allow_short=False,  # long-flat: coherent with CASH
    periods_per_year=252,
    fee_bps=0.0,
    slippage_bps=0.0,
    starting_cash=100_000.0,
    account_type="CASH",
    train_size=15,
    test_size=5,
    embargo=1,
    anchored=False,
)
_PARAMS = GauntletParams(seed=7, tier1_paths=40, tier2_paths=8, n_resamples=150, mean_block=5.0)


def _bars(n: int = 60, seed: int = 0) -> list[Bar]:
    closes = 100.0 * np.cumprod(1.0 + 0.002 + np.random.default_rng(seed).normal(0.0, 0.01, n))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        Bar(symbol="SPY", ts=start + timedelta(days=i), open=c, high=c, low=c, close=c, volume=1e3)
        for i, c in enumerate(closes.tolist())
    ]


def test_same_seed_yields_byte_identical_manifest() -> None:
    bars = _bars()
    a = run_gauntlet(bars, _SPEC, _PARAMS, run_id="fixed", snapshot_id=None)
    b = run_gauntlet(bars, _SPEC, _PARAMS, run_id="fixed", snapshot_id=None)

    manifest_a = json.dumps(report_to_manifest(a.report), sort_keys=True, allow_nan=False)
    manifest_b = json.dumps(report_to_manifest(b.report), sort_keys=True, allow_nan=False)
    assert manifest_a == manifest_b  # spec §11.4 — reproducible to the byte

    assert np.array_equal(a.oos.oos_equity, b.oos.oos_equity)
    assert np.array_equal(a.oos.oos_returns, b.oos.oos_returns)


def test_fresh_process_cli_runs_are_byte_identical(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The on-disk manifest must be byte-stable across FRESH interpreter processes.

    In-process re-runs share import state, interned objects, and hash randomization; a fresh
    process is the honest reproducibility check (spec §11.4). Two subprocess invocations of the
    real CLI against the same store must write byte-identical manifest.json files.
    """
    import os
    import subprocess
    import sys

    from tests.fixtures.cli_fixtures import seed_store

    seed_store(tmp_path, symbol="SPY", n=60, seed=0, drift=0.002)
    env = {**os.environ, "ALPHA_DATA_DIR": str(tmp_path), "PYTHONHASHSEED": "random"}
    args = [
        sys.executable,
        "-c",
        "from alpha_cli.main import main; main()",
        "validate",
        "SPY",
        "--lookback",
        "5",
        "--skip",
        "1",
        "--vol-window",
        "3",
        "--rebalance-every",
        "2",
        "--train-size",
        "15",
        "--test-size",
        "5",
        "--embargo",
        "1",
        "--tier1-paths",
        "20",
        "--tier2-paths",
        "4",
        "--n-resamples",
        "50",
        "--fee-bps",
        "0",
        "--slippage-bps",
        "0",
        "--seed",
        "7",
    ]

    def run_once() -> tuple[bytes, bytes]:
        proc = subprocess.run(args, capture_output=True, text=True, env=env, check=False)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        run_id = proc.stdout.split("-> run ")[1].split(":")[0]
        rdir = tmp_path / "runs" / run_id
        # the manifest AND the raw null distributions must both be byte-stable
        return (rdir / "manifest.json").read_bytes(), (rdir / "nulls.parquet").read_bytes()

    assert run_once() == run_once()  # byte-for-byte, across interpreter boundaries
