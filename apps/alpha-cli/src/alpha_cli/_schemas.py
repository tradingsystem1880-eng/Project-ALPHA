"""Declarative catalog of each strategy's tunable ``--param`` axes (the one place that names them).

The strategy registry (:mod:`alpha_cli._strategies`) reads these knobs via ``spec.param(name,
default)``; this table mirrors those names / defaults / ranges as *data* so ``alpha info strategies
--json`` can advertise them to the workstation's dynamic new-run form. ``ts_momentum`` has no extra
params — it tunes only first-class ``RunSpec`` flags (lookback/skip/vol_window/…) — so its tuple is
empty. Keep a param here in lockstep with the ``spec.param(...)`` default in ``_strategies.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamSpec:
    """One tunable strategy parameter, as advertised to the UI form builder."""

    name: str
    type: str  # "int" | "float"
    default: float
    min: float | None = None
    max: float | None = None
    help: str = ""


STRATEGY_PARAM_SCHEMA: dict[str, tuple[ParamSpec, ...]] = {
    "ts_momentum": (),
    "ma_crossover": (
        ParamSpec("fast", "int", 21, min=1, help="fast moving-average window"),
        ParamSpec("slow", "int", 100, min=2, help="slow moving-average window"),
    ),
    "mean_reversion": (
        ParamSpec("window", "int", 20, min=2, help="z-score lookback window"),
        ParamSpec("entry_z", "float", 1.5, min=0.0, help="entry z-score threshold"),
    ),
    "breakout": (ParamSpec("window", "int", 55, min=2, help="Donchian channel window"),),
    "kronos_forecast": (
        ParamSpec("model", "int", 2, min=0, max=2, help="0=mini, 1=small, 2=base"),
        ParamSpec("context", "int", 400, min=2, help="trailing context bars"),
        ParamSpec("horizon", "int", 30, min=1, help="forecast horizon (bars)"),
        ParamSpec("deadband", "float", 25.0, min=0.0, help="signal deadband (bps)"),
        ParamSpec("temperature", "float", 1.0, min=0.0, help="sampling temperature"),
        ParamSpec("top_p", "float", 0.9, min=0.0, max=1.0, help="nucleus-sampling p"),
        ParamSpec("sample_count", "int", 1, min=1, help="Monte-Carlo sample paths"),
    ),
}
