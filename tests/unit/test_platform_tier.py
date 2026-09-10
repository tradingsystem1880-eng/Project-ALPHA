"""Phase A S2: the alpha/platform test tiers are a pure function of the test path.

The fast gate runs ``-m "not platform"``; ``tests/conftest.py`` applies the marker from
``classify_platform``. The classifier defaults to the alpha tier and opts OUT by directory-scoped
filename prefix, so a new test lands in the fast tier unless it is platform-shaped.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from tests._tiers import classify_platform

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    [
        "tests/integration/test_web_api_runs.py",
        "tests/integration/test_mcp_server.py",
        "tests/integration/test_research_program_acceptance.py",
        "tests/integration/test_study_crypto_acceptance.py",
        "tests/unit/test_web_contracts.py",
        "tests/unit/test_claude_harness_gate.py",
        "tests/unit/test_control_store.py",
        "tests/unit/test_crypto_binance.py",
        "tests/unit/test_owner_auth.py",
        "tests/unit/test_forecast_kronos.py",
        "tests/unit/test_figure_catalog.py",
        "tests/unit/test_quantpad_adapter.py",
    ],
)
def test_platform_shaped_paths_are_platform(path: str) -> None:
    assert classify_platform(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "tests/bias_guards/test_pit_reader.py",
        "tests/oracles/test_calibration_known_truth.py",
        "tests/holdout_seed/test_anything.py",
        "tests/unit/test_pit_reader.py",
        "tests/unit/test_cpcv.py",
        "tests/unit/test_ts_momentum_signal.py",
        "tests/unit/test_portfolio_replay_engine.py",
        "tests/unit/test_pattern_double_bottom.py",
        "tests/unit/test_research_event_study.py",
        "tests/integration/test_backtest_cli.py",
        "tests/integration/test_validate_determinism.py",
        # prefixes are scoped per directory: a figure integration test is alpha-relevant
        "tests/integration/test_figure_determinism.py",
    ],
)
def test_alpha_paths_stay_in_the_fast_tier(path: str) -> None:
    assert classify_platform(path) is False


def test_bias_guards_oracles_and_holdout_are_never_platform() -> None:
    for sub in ("bias_guards", "oracles", "holdout_seed"):
        for file in (ROOT / "tests" / sub).rglob("test_*.py"):
            rel = file.relative_to(ROOT).as_posix()
            assert classify_platform(rel) is False, rel


def test_platform_marker_is_registered() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    markers = config["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.startswith("platform:") for m in markers)


def test_conftest_applies_the_marker_from_the_classifier() -> None:
    text = (ROOT / "tests" / "conftest.py").read_text()
    assert "pytest_collection_modifyitems" in text and "classify_platform" in text
