"""Workflow 6, machine learning: prepare -> real Qlib worker -> import -> evaluate -> replay.

Runs the installed ``alpha`` program against the separately locked ``workers/qlib`` environment
with opt-in feature recipe v3 (upstream Qlib Alpha158 features and processors) on a labelled
synthetic 20-symbol panel. The worker environment is large and is not built by CI's backend job
(the ``qlib-worker`` job runs the worker's own tests), so this check skips, with that reason,
when ``workers/qlib/.venv`` has no ``alpha-qlib-worker`` entry point.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from tests.smoke._harness import alpha

pytestmark = [pytest.mark.smoke, pytest.mark.usefixtures("owned_test_process")]

REPO = Path(__file__).parents[2]
WORKER = REPO / "workers" / "qlib"
SYMBOLS = [f"S{index:02d}" for index in range(20)]  # the contract's minimum universe
SESSIONS = 760  # the contract needs at least 756 aligned sessions


def _require_worker() -> None:
    if not (WORKER / ".venv" / "bin" / "alpha-qlib-worker").is_file():
        pytest.skip(
            "Qlib worker environment not installed; run `uv sync --project workers/qlib --locked`"
        )
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH; the CLI launches the worker through `uv run`")


def _write_inputs(directory: Path) -> tuple[Path, Path]:
    """Synthetic random-walk OHLCV (seeded), labelled as such; no market data."""
    rng = np.random.default_rng(20261114)
    start = datetime(2022, 1, 3, tzinfo=UTC)
    sessions = [start + timedelta(days=index) for index in range(SESSIONS)]  # 24/7 calendar
    closes = 50.0 * np.exp(np.cumsum(rng.normal(0.0, 0.015, (SESSIONS, len(SYMBOLS))), axis=0))
    rows = []
    for t, session in enumerate(sessions):
        for k, symbol in enumerate(SYMBOLS):
            close = float(closes[t, k])
            open_ = close * float(np.exp(rng.normal(0.0, 0.005)))
            rows.append(
                {
                    "symbol": symbol,
                    "session_ts": session,
                    "available_at": session + timedelta(hours=23),
                    "open": open_,
                    "high": max(open_, close) * (1.0 + float(rng.uniform(0.0, 0.01))),
                    "low": min(open_, close) * (1.0 - float(rng.uniform(0.0, 0.01))),
                    "close": close,
                    "volume": float(rng.integers(10_000, 1_000_000)),
                }
            )
    panel = directory / "panel-source.parquet"
    pl.DataFrame(rows).write_parquet(panel)
    lock_hash = hashlib.sha256((WORKER / "uv.lock").read_bytes()).hexdigest()
    spec = {
        "schema_version": 1,
        "snapshot_hash": "5" * 64,
        "universe": SYMBOLS,
        "universe_membership": "current_membership",
        "survivorship_warning": "Synthetic smoke universe; current membership only.",
        "feature_recipe": {"name": "alpha158", "version": 3, "parameters": {}},
        "label_recipe": {
            "name": "next_session_open_to_open",
            "decision": "close_t",
            "fill": "open_t_plus_1",
            "horizon_sessions": 1,
        },
        "model": {
            "name": "lightgbm",
            "parameters": {"num_boost_round": 20, "early_stopping_rounds": 5, "num_threads": 2},
        },
        "portfolio": {"selection": "top_quintile", "weighting": "equal", "long_only": True},
        "costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
        "folds": [
            {
                "fold": 0,
                "train_start": sessions[0].isoformat(),
                "train_end": sessions[503].isoformat(),
                "validation_start": sessions[509].isoformat(),
                "validation_end": sessions[628].isoformat(),
                "test_start": sessions[634].isoformat(),
                "test_end": sessions[-2].isoformat(),
            }
        ],
        "purge_sessions": 5,
        "embargo_sessions": 5,
        "seed": 7,
        "worker_lock_hash": lock_hash,
    }
    spec_path = directory / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    return spec_path, panel


def test_ml_upstream_alpha158_train_import_evaluate_replay(tmp_path: Path) -> None:
    _require_worker()
    home = tmp_path / "home"
    home.mkdir()
    spec, panel = _write_inputs(tmp_path)
    exchange = home / "exchange"
    lock = str(WORKER / "uv.lock")

    prepared = alpha(home, "ml", "prepare", str(spec), str(panel), str(exchange),
                     "--worker-lock", lock, "--json").json()  # fmt: skip
    assert prepared["status"] == "prepared"

    trained = alpha(
        home, "ml", "train", str(exchange), "--mode", "real", "--no-sync", "--json", timeout=900
    ).json()
    assert trained["status"] == "trained" and trained["mode"] == "real"
    assert trained["worker"]["kind"] == "qlib"
    result = json.loads((exchange / "result.json").read_text())
    recipe = result["diagnostics"]["feature_recipe"]
    assert recipe["upstream_alpha158"]["version"] == 3
    assert recipe["upstream_alpha158"]["upstream_columns"] == 158
    assert recipe["vwap_source"] == "causal_typical_price_proxy_not_vendor_vwap"
    assert result["diagnostics"]["folds"][0]["normalization"]["method"] == "qlib_processors_v3"

    imported = alpha(home, "ml", "import", str(exchange), "--json").json()
    assert imported["status"] == "validated" and imported["rows"] == trained["rows"] > 0

    evaluated = alpha(home, "ml", "evaluate", str(exchange), "--json").json()
    assert evaluated["authority"] == "diagnostic_only"

    replayed = alpha(home, "ml", "replay", str(exchange), "--json", timeout=600)
    payload = replayed.json()
    assert payload["status"] == "replayed", replayed.report()
    assert payload["validation"]["promotion_eligible"] is False
    assert payload["n_oos_periods"] > 0
    assert (home / "data" / "runs" / payload["run_id"]).is_dir()
