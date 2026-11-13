"""Which tests are in the fast local tier, as a pure function of the test path.

``gate.py check --all`` runs ``pytest -m "not platform"``; CI runs every test regardless of this
marker. A test is *platform* (outside the fast tier) when it exercises the control plane, the
serving surfaces, vendor wire parsers, rendering or the harness itself, or when it drives real
processes and lifecycles (native fixtures, daily rules, leases, supervisors) or takes about ten
seconds or more as a file (``SLOW_FILES``, measured on the Linux dev box). Everything else (data
PIT, backtest, validation, strategies, patterns, research statistics, bias guards, oracles,
acceptance tests) stays fast. The classifier defaults to fast and opts out by directory-scoped
filename prefix or exact path. ``tests/conftest.py`` applies the marker.
"""

from __future__ import annotations

from pathlib import PurePosixPath

PLATFORM_PREFIXES: dict[str, tuple[str, ...]] = {
    "tests/unit": (
        "test_ci_backend_bootstrap",
        "test_claude_",
        "test_cloud_setup",
        "test_control_",
        "test_crypto_",
        "test_daily_",
        "test_documentation_truth",
        "test_durable_job",
        "test_figure",
        "test_forecast_",
        "test_frontend_browser_lanes",
        "test_gate_",
        "test_generic_command",
        "test_git_guard",
        "test_harness_repo_fixture",
        "test_ibkr_",
        "test_job_capacity",
        "test_keychain_",
        "test_literature_",
        "test_mcp",
        "test_ml_",
        "test_mutation_",
        "test_native_",
        "test_owner_",
        "test_paper_",
        "test_playwright_",
        "test_project_",
        "test_provider_",
        "test_public_seams",
        "test_qlib_",
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
    "tests/smoke": ("test_",),
    "tests/integration": (
        "test_accounted_backfill_process",
        "test_accounted_http_process",
        "test_bound_http_replay_process",
        "test_chart_cmds",
        "test_cli_rules",
        "test_cli_scan",
        "test_cli_walking_skeleton",
        "test_control_cli",
        "test_crypto_",
        "test_daily_",
        "test_figure_determinism",
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

# Files of about ten seconds or more that no prefix above covers (per-file sums, 2026-11-13).
SLOW_FILES: frozenset[str] = frozenset(
    {
        "tests/integration/test_asset_master_provenance.py",
        "tests/integration/test_c04_web_metric_basis.py",
        "tests/integration/test_monte_carlo_cli.py",
        "tests/integration/test_risk_strict_json.py",
        "tests/integration/test_tearsheet_html.py",
        "tests/integration/test_validate_determinism.py",
        "tests/unit/test_cli_entry_lazy_groups.py",
        "tests/unit/test_investigation_lifecycle.py",
        "tests/unit/test_w09_durable_observations.py",
    }
)

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
    if rel in SLOW_FILES:
        return True
    parent = posix.parent.as_posix()
    prefixes = PLATFORM_PREFIXES.get(parent)
    if prefixes is None:
        return False
    return posix.name.startswith(prefixes)
