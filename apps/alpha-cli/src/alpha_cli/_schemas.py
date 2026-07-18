"""Canonical strategy-parameter definitions, validation, defaults, and UI metadata."""

from __future__ import annotations

import math
from dataclasses import dataclass

from alpha_core import DataError


@dataclass(frozen=True)
class ParamSpec:
    """One tunable strategy parameter, as advertised to the UI form builder."""

    name: str
    type: str  # "int" | "float"
    default: float
    min: float | None = None
    max: float | None = None
    min_exclusive: bool = False
    max_exclusive: bool = False
    help: str = ""

    def normalize(self, value: float) -> float:
        """Validate and return the stable float representation stored in ``RunSpec``."""
        if not math.isfinite(value):
            raise DataError(f"strategy param {self.name!r} must be finite, got {value!r}")
        if self.type == "int" and not value.is_integer():
            raise DataError(f"strategy param {self.name!r} must be an integer, got {value!r}")
        if self.min is not None and (
            value < self.min or (self.min_exclusive and value == self.min)
        ):
            relation = "greater than" if self.min_exclusive else "at least the minimum"
            raise DataError(
                f"strategy param {self.name!r} must be {relation} {self.min:g}, got {value!r}"
            )
        if self.max is not None and (
            value > self.max or (self.max_exclusive and value == self.max)
        ):
            relation = "less than" if self.max_exclusive else "at most the maximum"
            raise DataError(
                f"strategy param {self.name!r} must be {relation} {self.max:g}, got {value!r}"
            )
        return value


STRATEGY_PARAM_SCHEMA: dict[str, tuple[ParamSpec, ...]] = {
    "ts_momentum": (),
    "ma_crossover": (
        ParamSpec("fast", "int", 21, min=1, help="fast moving-average window"),
        ParamSpec("slow", "int", 100, min=2, help="slow moving-average window"),
    ),
    "mean_reversion": (
        ParamSpec("window", "int", 20, min=2, help="z-score lookback window"),
        ParamSpec(
            "entry_z",
            "float",
            1.5,
            min=0.0,
            min_exclusive=True,
            help="entry z-score threshold",
        ),
    ),
    "breakout": (ParamSpec("window", "int", 55, min=2, help="Donchian channel window"),),
    "kronos": (
        ParamSpec("context", "int", 400, min=2, help="trailing context bars"),
        ParamSpec("horizon", "int", 21, min=1, help="forecast horizon (bars)"),
        ParamSpec("samples", "int", 30, min=1, help="Monte-Carlo sample paths"),
        ParamSpec("temperature", "float", 1.0, min=0.0, help="sampling temperature"),
        ParamSpec("top_p", "float", 0.9, min=0.0, max=1.0, help="nucleus-sampling p"),
        ParamSpec("top_k", "int", 0, min=0, help="top-k sampling cap (0 = off)"),
        ParamSpec("min_edge", "float", 0.0, min=0.0, help="min forecast edge to trade"),
        ParamSpec("band", "int", 0, min=0, max=1, help="require q25/q75 band agreement (0/1)"),
    ),
}


def specs_for(strategy_name: str) -> dict[str, ParamSpec]:
    """Return the canonical name-to-definition map, failing loud on an unknown strategy."""
    try:
        return {spec.name: spec for spec in STRATEGY_PARAM_SCHEMA[strategy_name]}
    except KeyError:
        raise DataError(
            f"unknown strategy {strategy_name!r}; known: {sorted(STRATEGY_PARAM_SCHEMA)}"
        ) from None


def default_for(strategy_name: str, name: str) -> float:
    """Return a strategy parameter's canonical runtime default."""
    try:
        return specs_for(strategy_name)[name].default
    except KeyError:
        raise DataError(f"unknown strategy param {name!r} for {strategy_name!r}") from None


def normalize_params(
    strategy_name: str, params: tuple[tuple[str, float], ...]
) -> tuple[tuple[str, float], ...]:
    """Validate names/values and return the existing sorted float-pair serialization."""
    schema = specs_for(strategy_name)
    normalized: dict[str, float] = {}
    for name, value in params:
        if name in normalized:
            raise DataError(f"duplicate strategy param {name!r}")
        try:
            spec = schema[name]
        except KeyError:
            raise DataError(
                f"unknown strategy param {name!r} for {strategy_name!r}; known: {sorted(schema)}"
            ) from None
        normalized[name] = spec.normalize(float(value))
    return tuple(sorted(normalized.items()))
