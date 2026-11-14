"""Suite plan values and shared, deterministic planning helpers."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

from alpha_cli._schemas import specs_for
from alpha_cli.control_store import ControlStore
from alpha_cli.suite_catalog import SuiteActionValue as SuiteAction
from alpha_core import DataError

_STANDARD_DEFINITION_OPTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("lookback", "--lookback"),
    ("skip", "--skip"),
    ("vol_window", "--vol-window"),
    ("target_vol", "--target-vol"),
    ("rebalance_every", "--rebalance-every"),
    ("max_leverage", "--max-leverage"),
    ("starting_cash", "--starting-cash"),
    ("periods_per_year", "--periods-per-year"),
)

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

_SAFE_MODEL = re.compile(r"(?:fake|[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)")

_SAFE_REVISION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")


@dataclass(frozen=True)
class SuiteStep:
    """One internal allowlisted command plus its path-safe public preview."""

    label: str
    argv: tuple[str, ...]
    preview: tuple[str, ...]
    evidence_role: str
    redactions: tuple[tuple[str, str], ...] = ()

    def public(self, index: int) -> dict[str, object]:
        return {
            "index": index,
            "label": self.label,
            "command": list(self.preview),
            "evidence_role": self.evidence_role,
        }


@dataclass(frozen=True)
class SuitePlan:
    schema_version: int
    project_id: str
    experiment_id: str
    action: SuiteAction
    stage: str
    ready: bool
    blockers: tuple[str, ...]
    resolved_experiment: dict[str, object]
    resolved_strategy_version: dict[str, object]
    current_stage_state: str
    estimated_workload: dict[str, object]
    steps: tuple[SuiteStep, ...]
    governance: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "experiment_id": self.experiment_id,
            "action": self.action,
            "stage": self.stage,
            "ready": self.ready,
            "blockers": list(self.blockers),
            "resolved_experiment": self.resolved_experiment,
            "resolved_strategy_version": self.resolved_strategy_version,
            "current_stage_state": self.current_stage_state,
            "estimated_workload": self.estimated_workload,
            "steps": [step.public(index) for index, step in enumerate(self.steps, start=1)],
            "governance": self.governance,
        }


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise DataError(f"invalid immutable {label}: expected an object")
    return cast(dict[str, object], value)


def _number(value: object, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DataError(f"invalid immutable {label}: expected a finite number")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise DataError(f"invalid immutable {label}: expected a finite value >= {minimum}")
    return result


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = 1_000_000,
) -> int:
    number = _number(value, label, minimum=float(minimum))
    if not number.is_integer() or number > maximum:
        raise DataError(f"invalid immutable {label}: expected an integer in {minimum}..{maximum}")
    return int(number)


def _float_text(value: float) -> str:
    return f"{value:g}"


def _cutoff_preview(
    argv: Sequence[str], *, cutoff: str | None, marker: str | None
) -> tuple[str, ...]:
    if cutoff is None or marker is None:
        return tuple(argv)
    return tuple(marker if value == cutoff else value for value in argv)


@dataclass(frozen=True)
class _ResearchWindow:
    """Resolved private/public cutoff pair, shared without repeating redaction assembly."""

    cutoff: str
    public_cutoff: str

    def step(self, label: str, argv: tuple[str, ...], evidence_role: str) -> SuiteStep:
        return SuiteStep(
            label,
            argv,
            _cutoff_preview(argv, cutoff=self.cutoff, marker=self.public_cutoff),
            evidence_role,
            ((self.cutoff, self.public_cutoff),),
        )


def _safe_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise DataError(f"invalid immutable {label}: expected a managed identifier")
    return value


def _managed_qlib_id(experiment_id: str) -> str:
    """Return the opaque, stable control-resource id for one immutable experiment."""
    return hashlib.sha256(
        b"project-alpha-suite-qlib-v1\0" + experiment_id.encode("utf-8")
    ).hexdigest()


def _selected(rows: object, *, id_field: str, item_id: str, label: str) -> dict[str, object]:
    if not isinstance(rows, list):
        raise DataError(f"corrupt control projection: {label} collection")
    result = next(
        (
            _object(row, label)
            for row in rows
            if isinstance(row, dict) and row.get(id_field) == item_id
        ),
        None,
    )
    if result is None:
        raise DataError(f"unknown immutable {label} {item_id!r}")
    return result


def _stage_states(project: Mapping[str, object], experiment_id: str) -> dict[str, str]:
    rows = project.get("stage_states")
    if not isinstance(rows, list):
        raise DataError("corrupt control projection: stage states")
    result: dict[str, str] = {}
    for raw in rows:
        row = _object(raw, "stage state")
        if row.get("experiment_id") == experiment_id:
            result[str(row["stage"])] = str(row["state"])
    return result


def _definition_options(definition: Mapping[str, object]) -> list[str]:
    result: list[str] = []
    for name, flag in _STANDARD_DEFINITION_OPTIONS:
        if name in definition:
            result.extend([flag, _float_text(_number(definition[name], name, minimum=0.0))])
    account_type = definition.get("account_type")
    if account_type is not None:
        if account_type not in {"CASH", "MARGIN"}:
            raise DataError("invalid immutable account_type: expected CASH or MARGIN")
        result.extend(["--account-type", str(account_type)])
    allow_short = definition.get("allow_short")
    if allow_short is not None:
        if not isinstance(allow_short, bool):
            raise DataError("invalid immutable allow_short: expected a boolean")
        result.append("--allow-short" if allow_short else "--no-allow-short")
    return result


def _strategy_options(strategy: str, definition: Mapping[str, object]) -> list[str]:
    schema = specs_for(strategy)
    result: list[str] = []
    for name in sorted(schema):
        if name not in definition:
            continue
        value = schema[name].normalize(_number(definition[name], f"strategy parameter {name}"))
        result.extend(["--param", f"{name}={_float_text(value)}"])
    return result


def _common(
    *,
    symbol: str,
    strategy: str,
    snapshot: str,
    costs: Mapping[str, object],
    definition: Mapping[str, object],
    gate_overridden: bool = False,
) -> list[str]:
    args = [symbol, "--strategy", strategy, "--snapshot", snapshot]
    for name, flag, default in (
        ("fee_bps", "--fee-bps", 1.0),
        ("slippage_bps", "--slippage-bps", 2.0),
    ):
        args.extend([flag, _float_text(_number(costs.get(name, default), name, minimum=0.0))])
    args.extend(_definition_options(definition))
    args.extend(_strategy_options(strategy, definition))
    if gate_overridden:
        # spec §15 / ADR-0026: every strategy run launched under an owner research-gate
        # override is permanently watermarked EXPLORATORY / RESEARCH GATE NOT COMPLETED.
        args.append("--research-gate-override")
    return args


def _split_options(split: Mapping[str, object]) -> list[str]:
    result: list[str] = []
    for names, flag, default, minimum in (
        (("train", "train_size"), "--train-size", 504, 1),
        (("test", "test_size"), "--test-size", 63, 1),
        (("embargo",), "--embargo", 5, 0),
    ):
        raw = next((split[name] for name in names if name in split), default)
        result.extend([flag, str(_integer(raw, names[0], minimum=minimum, maximum=100_000))])
    anchored = split.get("anchored")
    if anchored is not None:
        if not isinstance(anchored, bool):
            raise DataError("invalid immutable anchored: expected a boolean")
        result.append("--anchored" if anchored else "--no-anchored")
    return result


def _seed(seeds: Mapping[str, object]) -> int:
    return _integer(seeds.get("master", 7), "master seed", maximum=2**32 - 1)


def _stage_int(
    config: Mapping[str, object], name: str, default: int, *, minimum: int, maximum: int
) -> int:
    return _integer(config.get(name, default), name, minimum=minimum, maximum=maximum)


def _stage_float(
    config: Mapping[str, object],
    name: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    result = _number(config.get(name, default), name, minimum=minimum)
    if result > maximum:
        raise DataError(f"invalid immutable {name}: expected a value <= {maximum}")
    return result


def _latest_run(
    project: Mapping[str, object], experiment_id: str, stages: Sequence[str]
) -> str | None:
    rows = project.get("stage_run_links")
    if not isinstance(rows, list):
        return None
    for stage in stages:
        candidates = [
            _object(row, "stage run link")
            for row in rows
            if isinstance(row, dict)
            and row.get("experiment_id") == experiment_id
            and row.get("stage") == stage
            and row.get("state") in {"pass", "warning"}
        ]
        if candidates:
            return str(candidates[-1]["run_id"])
    return None


def _latest_run_for_command(
    project: Mapping[str, object],
    experiment_id: str,
    stages: Sequence[str],
    *,
    data_dir: Path,
    commands: frozenset[str],
    states: frozenset[str] = frozenset({"pass", "warning"}),
    null_model: str | None = None,
) -> tuple[str, dict[str, object]] | None:
    from alpha_cli._artifacts import read_manifest
    from alpha_cli.run_store import find_run_dir

    rows = project.get("stage_run_links")
    if not isinstance(rows, list):
        return None
    for stage in stages:
        candidates = [
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("experiment_id") == experiment_id
            and row.get("stage") == stage
            and row.get("state") in states
        ]
        for row in reversed(candidates):
            run_id = str(row["run_id"])
            rdir = find_run_dir(data_dir, run_id)
            if rdir is None:
                continue
            manifest = read_manifest(rdir)
            if manifest.get("command") not in commands:
                continue
            metadata = manifest.get("metadata")
            if null_model is not None and (
                not isinstance(metadata, Mapping) or metadata.get("null_model") != null_model
            ):
                continue
            return run_id, cast(dict[str, object], manifest)
    return None


def _workload(
    action: str, *, commands: int, canonical_runs: int, grid_configurations: int | None = None
) -> dict[str, object]:
    descriptions = {
        "baseline": "one fixed-parameter discovery backtest",
        "inner_oos": "one fixed-rule walk-forward OOS evaluation with no refit",
        "three_null_families": "bootstrap headline plus Student-t and GARCH sensitivities",
        "monte_carlo": "three classical path families plus Kronos full-engine synthetic replay",
        "optimize_grid": "declared deterministic parameter grid with overfit diagnostics",
        "fixed_stress": "fixed scenarios over one cited realized return stream",
        "portfolio_cross_asset": "portfolio and cross-sectional replay over the frozen universe",
        "qlib": "isolated fold-by-fold Qlib training plus canonical ALPHA replay",
        "kronos": "one forecast cone and one rolling-origin evaluation",
        "holdout_reveal": "one audited owner reveal followed by one locked candidate evaluation",
        "paper_preflight": "one offline sandbox wiring preflight; no order placement",
    }
    result: dict[str, object] = {
        "class": "heavyweight" if action in {"qlib", "kronos", "monte_carlo"} else "standard",
        "commands": commands,
        "estimated_canonical_runs": canonical_runs,
        "description": descriptions[action],
    }
    if grid_configurations is not None:
        result["grid_configurations"] = grid_configurations
    return result


@dataclass(frozen=True)
class _PlanContext:
    """Resolved inputs with shared, ordered blocker and governance journals."""

    store: ControlStore
    project_id: str
    experiment_id: str
    action: SuiteAction
    data_dir: Path
    project: dict[str, object]
    experiment: dict[str, object]
    version: dict[str, object]
    stage: str
    states: dict[str, str]
    current_state: str
    resume_reveal: bool
    blockers: list[str]
    universe: list[str] = field(default_factory=list)
    primary: str = ""
    snapshot: str = ""
    strategy: str = ""
    definition: dict[str, object] = field(default_factory=dict)
    hedged_basis: bool = False
    research_contract_id: str | None = None
    parameter_space: dict[str, object] = field(default_factory=dict)
    split: dict[str, object] = field(default_factory=dict)
    costs: dict[str, object] = field(default_factory=dict)
    seeds: dict[str, object] = field(default_factory=dict)
    config: dict[str, object] = field(default_factory=dict)
    holdout: dict[str, object] | None = None
    sealed_spec: dict[str, object] | None = None
    gate_overridden: bool = False
    common: list[str] = field(default_factory=list)
    research_common: list[str] = field(default_factory=list)
    window: _ResearchWindow = _ResearchWindow("", "")
    governance: dict[str, object] = field(default_factory=dict)


_CANDIDATE_SIMPLE_ACTIONS: Final[dict[SuiteAction, tuple[tuple[str, str, str], ...]]] = {
    "baseline": (
        ("baseline", "Sandbox two-leg baseline", "two_leg_return_replay_no_order_authority"),
    ),
    "inner_oos": (
        ("inner_oos", "Ordered inner OOS event groups", "ordered_last_20_percent_event_groups"),
    ),
    "three_null_families": (
        (
            "null_bootstrap",
            "Sign-randomization headline null",
            "candidate_return_stream_null_no_majority_vote",
        ),
        (
            "null_student_t",
            "Student-t sensitivity null",
            "candidate_return_stream_null_no_majority_vote",
        ),
        (
            "null_garch",
            "Conditional-volatility sensitivity null",
            "candidate_return_stream_null_no_majority_vote",
        ),
    ),
    "optimize_grid": (
        (
            "optimize_cost_sensitivity",
            "Frozen cost sensitivity",
            "fixed_20_40_60_bps_no_adaptive_selection",
        ),
    ),
    "portfolio_cross_asset": (
        (
            "portfolio_concentration",
            "Two-leg concentration diagnostic",
            "single_candidate_two_venue_concentration",
        ),
        (
            "cross_asset_scope",
            "Registered cross-asset scope check",
            "completed_not_applicable_no_invented_asset",
        ),
    ),
    "fixed_stress": (
        (
            "fixed_stress",
            "Fixed two-leg stress scenarios",
            "scenario_sensitivity_separate_from_nulls",
        ),
    ),
    "qlib": (
        (
            "qlib_fixture",
            "Qlib interface contract fixture",
            "fixture_only_no_external_model_or_promotion_authority",
        ),
    ),
    "kronos": (
        (
            "kronos_forecast_fixture",
            "Disclosed fake forecast fixture",
            "fake_model_fixture_not_market_oracle",
        ),
        (
            "kronos_eval_fixture",
            "Disclosed fake rolling evaluation",
            "fake_model_fixture_not_market_oracle",
        ),
    ),
}

_CANDIDATE_SIMPLE_GOVERNANCE: Final[dict[SuiteAction, dict[str, object]]] = {
    "baseline": {
        "deployment_scope": "sandbox_only",
        "execution_model": "two_leg_return_replay",
        "places_orders": False,
        "paper_eligible": False,
    },
    "three_null_families": {"aggregation": "no_majority_vote"},
    "optimize_grid": {"optimization_authority": "registered_40_bps_cost_remains_immutable"},
    "fixed_stress": {"separate_from_nulls": True},
    "qlib": {"model_role": "contract_fixture_not_predictive_evidence"},
    "kronos": {"kronos_role": "disclosed_fake_fixture_not_market_oracle"},
}
