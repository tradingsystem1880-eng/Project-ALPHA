"""The fast local tier is a pure function of the test path.

``gate.py check --all`` runs ``-m "not platform"``; ``tests/conftest.py`` applies the marker from
``classify_platform``. CI runs every test whatever its tier.
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
        # real-process and lifecycle families, and files of about ten seconds or more
        "tests/unit/test_native_fixture_lifecycle.py",
        "tests/unit/test_daily_rule_recovery_contracts.py",
        "tests/unit/test_durable_job_lease.py",
        "tests/unit/test_gate_process_supervisor.py",
        "tests/unit/test_git_guard.py",
        "tests/integration/test_daily_rule_report.py",
        "tests/integration/test_figure_determinism.py",
        "tests/integration/test_accounted_backfill_process.py",
        "tests/integration/test_validate_determinism.py",
        "tests/unit/test_cli_entry_lazy_groups.py",
        "tests/smoke/test_web_smoke.py",
    ],
)
def test_platform_shaped_paths_are_platform(path: str) -> None:
    assert classify_platform(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "tests/bias_guards/test_pit_reader.py",
        "tests/oracles/test_calibration_known_truth.py",
        "tests/acceptance/test_anything.py",
        "tests/unit/test_pit_reader.py",
        "tests/unit/test_cpcv.py",
        "tests/unit/test_ts_momentum_signal.py",
        "tests/unit/test_portfolio_replay_engine.py",
        "tests/unit/test_pattern_double_bottom.py",
        "tests/unit/test_research_event_study.py",
        "tests/integration/test_backtest_cli.py",
        # prefixes are scoped per directory: a non-process sibling stays fast
        "tests/integration/test_accounted_backfill.py",
        "tests/unit/test_investigation_lifecycle_unit.py",
    ],
)
def test_alpha_paths_stay_in_the_fast_tier(path: str) -> None:
    assert classify_platform(path) is False


def test_slow_files_exist() -> None:
    from tests._tiers import SLOW_FILES

    assert all((ROOT / rel).is_file() for rel in SLOW_FILES)


def test_ci_does_not_select_by_tier() -> None:
    """Moving a test out of the fast tier must never stop CI from running it."""
    import gate_components

    for name in gate_components.COMPONENTS:
        for _, _, command in gate_components.component_steps(ROOT, name):
            assert not any("platform" in arg for arg in command), (name, command)


def test_bias_guards_oracles_and_acceptance_are_never_platform() -> None:
    for sub in ("bias_guards", "oracles", "acceptance"):
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
