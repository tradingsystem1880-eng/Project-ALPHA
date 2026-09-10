"""Alpha/platform test tiers as a pure function of the test path (Phase A S2).

The fast gate runs ``pytest -m "not platform"``. A test is *platform* when it exercises the
control plane, the serving surfaces, vendor wire parsers, rendering, or the harness itself;
everything else (data PIT, backtest, validation, strategies, patterns, research statistics,
bias guards, oracles, holdout) is the *alpha* tier and stays in the fast selection. The
classifier defaults to alpha and opts out by directory-scoped filename prefix, so a new test is
in the fast tier unless it is explicitly platform-shaped. ``tests/conftest.py`` applies the marker.
"""

from __future__ import annotations

from pathlib import PurePosixPath

PLATFORM_PREFIXES: dict[str, tuple[str, ...]] = {
    "tests/unit": (
        "test_atlas_",
        "test_claude_",
        "test_control_",
        "test_crypto_",
        "test_daily_scheduler",
        "test_documentation_truth",
        "test_durable_job",
        "test_figure",
        "test_forecast_",
        "test_generic_command",
        "test_ibkr_",
        "test_job_capacity",
        "test_keychain_",
        "test_literature_",
        "test_mcp",
        "test_ml_",
        "test_owner_",
        "test_paper_",
        "test_project_",
        "test_provider_",
        "test_public_seams",
        "test_qlib_",
        "test_quantpad_",
        "test_repo_awareness",
        "test_research_",
        "test_run_context_authority",
        "test_run_projection_security",
        "test_study_",
        "test_suite_",
        "test_theme_drift",
        "test_v3_",
        "test_web_",
    ),
    "tests/unit/study": ("test_",),
    "tests/integration": (
        "test_chart_cmds",
        "test_cli_rules",
        "test_cli_scan",
        "test_cli_walking_skeleton",
        "test_control_cli",
        "test_crypto_",
        "test_figures_cli",
        "test_forecast_",
        "test_info_catalog",
        "test_kronos_strategy_cli",
        "test_mcp_",
        "test_ml_cli",
        "test_openapi_",
        "test_options_cli",
        "test_paper",
        "test_provider_",
        "test_report_cli",
        "test_research_",
        "test_screener_cli",
        "test_study_",
        "test_suite_cli",
        "test_web_",
    ),
}

# Statistical modules that share a platform prefix but belong to the alpha tier.
ALPHA_ALLOWLIST: frozenset[str] = frozenset(
    {
        "tests/unit/test_crypto_crowding_composition.py",
        "tests/unit/test_crypto_crowding_research.py",
        "tests/unit/test_crypto_features.py",
        "tests/unit/test_forecast_calibration.py",
        "tests/unit/test_forecast_eval_metrics.py",
        "tests/unit/test_forecast_quantiles.py",
        "tests/unit/test_forecast_signal.py",
        "tests/unit/test_research_comparison.py",
        "tests/unit/test_research_confirmation_power.py",
        "tests/unit/test_research_descriptives.py",
        "tests/unit/test_research_double_bottom.py",
        "tests/unit/test_research_event_study.py",
        "tests/unit/test_research_multiple_testing.py",
    }
)


def classify_platform(path: str) -> bool:
    """Return True when the repo-relative posix ``path`` belongs to the platform tier."""
    posix = PurePosixPath(path)
    rel = posix.as_posix()
    if rel in ALPHA_ALLOWLIST:
        return False
    parent = posix.parent.as_posix()
    prefixes = PLATFORM_PREFIXES.get(parent)
    if prefixes is None:
        return False
    return posix.name.startswith(prefixes)
