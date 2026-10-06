"""Lightweight suite vocabulary shared by orchestration and its bounded surfaces."""

from typing import Final, Literal, get_args

# Keep the existing OpenAPI component name and enum order byte-compatible.
type SuiteActionValue = Literal[
    "baseline",
    "inner_oos",
    "three_null_families",
    "monte_carlo",
    "optimize_grid",
    "fixed_stress",
    "portfolio_cross_asset",
    "qlib",
    "kronos",
    "holdout_reveal",
    "paper_preflight",
]

SUITE_ACTIONS: Final[frozenset[str]] = frozenset(get_args(SuiteActionValue.__value__))
