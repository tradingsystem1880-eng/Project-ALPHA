"""Bounded Strategy Development suite planning and durable execution.

The public plan contains only immutable project inputs and allowlisted command previews.  Actual
execution stays in ``alpha_cli`` and launches existing ``alpha`` commands; web/MCP surfaces never
construct engine flags or accept a filesystem path.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import selectors
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final, Literal, cast

from alpha_cli._schemas import specs_for
from alpha_cli.control_store import AttemptStatus, ControlStore, StageState
from alpha_cli.run_store import RESEARCH_GATE_OVERRIDE_WATERMARK
from alpha_core import DataError

type SuiteAction = Literal[
    "baseline",
    "inner_oos",
    "three_null_families",
    "optimize_grid",
    "fixed_stress",
    "portfolio_cross_asset",
    "qlib",
    "kronos",
    "holdout_reveal",
    "paper_preflight",
]

SUITE_ACTIONS: Final = frozenset(
    {
        "baseline",
        "inner_oos",
        "three_null_families",
        "optimize_grid",
        "fixed_stress",
        "portfolio_cross_asset",
        "qlib",
        "kronos",
        "holdout_reveal",
        "paper_preflight",
    }
)

_ACTION_STAGE: Final[dict[str, str]] = {
    "baseline": "baseline",
    "inner_oos": "oos",
    "three_null_families": "robustness",
    "optimize_grid": "optimization",
    "fixed_stress": "robustness",
    "portfolio_cross_asset": "portfolio",
    "qlib": "ml",
    "kronos": "kronos",
    "holdout_reveal": "holdout",
    "paper_preflight": "paper",
}

_RUN_BACKED_STAGE_ACTIONS: Final = frozenset(
    {
        "baseline",
        "inner_oos",
        "three_null_families",
        "optimize_grid",
        "portfolio_cross_asset",
        "qlib",
        "kronos",
        "holdout_reveal",
    }
)
_GOVERNED_STAGE_ACTIONS: Final = _RUN_BACKED_STAGE_ACTIONS | {"paper_preflight"}
_PRE_REVEAL_RESEARCH_ACTIONS: Final = frozenset(
    {
        "baseline",
        "inner_oos",
        "three_null_families",
        "optimize_grid",
        "fixed_stress",
        "portfolio_cross_asset",
        "qlib",
        "kronos",
    }
)

_PREREQUISITES: Final[dict[str, tuple[str, ...]]] = {
    "baseline": (),
    "inner_oos": ("baseline",),
    "three_null_families": ("oos",),
    "optimize_grid": ("oos",),
    "fixed_stress": ("baseline",),
    "portfolio_cross_asset": ("robustness", "optimization"),
    "qlib": ("data", "strategy"),
    "kronos": ("data",),
    "holdout_reveal": ("baseline", "oos", "robustness", "optimization", "portfolio", "candidate"),
    "paper_preflight": ("holdout",),
}

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
_RUN_RE = re.compile(r"->\s+run\s+([0-9a-f]{16})\b")
_JSON_RUN_RE = re.compile(r'"run_id"\s*:\s*"([0-9a-f]{16})"')
_PROCESS_TERM_GRACE_SECONDS: Final = 2.0
_PROCESS_REAP_TIMEOUT_SECONDS: Final = 2.0
_PROCESS_GROUP_POLL_SECONDS: Final = 0.05
_SUITE_HEARTBEAT_INTERVAL_SECONDS: Final = 5.0


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


@dataclass(frozen=True)
class StepExecution:
    returncode: int
    run_ids: tuple[str, ...]


class SuiteProcessCleanupError(DataError):
    """An isolated suite process group could not be verified stopped."""


type StepRunner = Callable[[SuiteStep, str, ControlStore, Callable[[], bool]], StepExecution]


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


def _workload(
    action: str, *, commands: int, canonical_runs: int, grid_configurations: int | None = None
) -> dict[str, object]:
    descriptions = {
        "baseline": "one fixed-parameter discovery backtest",
        "inner_oos": "one fixed-rule walk-forward OOS evaluation with no refit",
        "three_null_families": "bootstrap headline plus Student-t and GARCH sensitivities",
        "optimize_grid": "declared deterministic parameter grid with overfit diagnostics",
        "fixed_stress": "fixed scenarios over one cited realized return stream",
        "portfolio_cross_asset": "portfolio and cross-sectional replay over the frozen universe",
        "qlib": "isolated fold-by-fold Qlib training plus canonical ALPHA replay",
        "kronos": "one forecast cone and one rolling-origin evaluation",
        "holdout_reveal": "one audited owner reveal followed by one locked candidate evaluation",
        "paper_preflight": "one offline sandbox wiring preflight; no order placement",
    }
    result: dict[str, object] = {
        "class": "heavyweight" if action in {"qlib", "kronos"} else "standard",
        "commands": commands,
        "estimated_canonical_runs": canonical_runs,
        "description": descriptions[action],
    }
    if grid_configurations is not None:
        result["grid_configurations"] = grid_configurations
    return result


def _grid_steps(
    *,
    primary: str,
    strategy: str,
    snapshot: str,
    costs: Mapping[str, object],
    definition: Mapping[str, object],
    parameter_space: Mapping[str, object],
    split: Mapping[str, object],
    seeds: Mapping[str, object],
    config: Mapping[str, object],
    research_cutoff: str,
    cutoff_marker: str,
    gate_overridden: bool = False,
) -> tuple[SuiteStep, int]:
    schema = specs_for(strategy)
    allowed = set(schema) | {name for name, _ in _STANDARD_DEFINITION_OPTIONS}
    axes: list[str] = []
    combinations = 1
    for name in sorted(parameter_space):
        if name not in allowed:
            raise DataError(f"unsupported immutable optimization axis {name!r}")
        raw = parameter_space[name]
        if not isinstance(raw, list) or not 1 <= len(raw) <= 256:
            raise DataError(f"optimization axis {name!r} must contain 1..256 numeric values")
        normalized: list[float] = []
        for value in raw:
            number = _number(value, f"optimization axis {name}")
            if name in schema:
                number = schema[name].normalize(number)
            normalized.append(number)
        combinations *= len(normalized)
        if combinations > 4096:
            raise DataError("deterministic grid exceeds the 4096-configuration workload cap")
        axes.extend(["--grid", f"{name}={','.join(_float_text(v) for v in normalized)}"])
    if not axes:
        raise DataError("deterministic grid requires a declared parameter_space")
    args = [
        "optim",
        "grid",
        *_common(
            symbol=primary,
            strategy=strategy,
            snapshot=snapshot,
            costs=costs,
            definition=definition,
            gate_overridden=gate_overridden,
        ),
        *axes,
        *_split_options(split),
        "--as-of",
        research_cutoff,
        "--seed",
        str(_seed(seeds)),
    ]
    for name, flag, default, minimum, maximum in (
        ("pbo_blocks", "--pbo-blocks", 10, 4, 100),
        ("n_resamples", "--n-resamples", 2000, 100, 100_000),
    ):
        args.extend(
            [flag, str(_stage_int(config, name, default, minimum=minimum, maximum=maximum))]
        )
    for float_name, float_flag, float_default, float_minimum, float_maximum in (
        ("mean_block", "--mean-block", 5.0, 1.0, 10_000.0),
        ("dsr_threshold", "--dsr-threshold", 0.95, 0.0, 1.0),
        ("optim_alpha", "--alpha", 0.05, 0.000001, 1.0),
    ):
        args.extend(
            [
                float_flag,
                _float_text(
                    _stage_float(
                        config,
                        float_name,
                        float_default,
                        minimum=float_minimum,
                        maximum=float_maximum,
                    )
                ),
            ]
        )
    if "max_workers" in config:
        args.extend(
            [
                "--max-workers",
                str(_stage_int(config, "max_workers", 1, minimum=1, maximum=64)),
            ]
        )
    step = SuiteStep(
        label="Deterministic grid optimization",
        argv=tuple(args),
        preview=_cutoff_preview(args, cutoff=research_cutoff, marker=cutoff_marker),
        evidence_role="selection_with_pbo_dsr_reality_check_spa",
        redactions=((research_cutoff, cutoff_marker),),
    )
    return step, combinations


def build_suite_plan(
    store: ControlStore,
    project_id: str,
    experiment_id: str,
    action: SuiteAction,
    *,
    data_dir: Path,
    resume_job_id: str | None = None,
) -> SuitePlan:
    """Resolve one action solely from immutable, linked control-plane records."""
    if action not in SUITE_ACTIONS:
        raise DataError(f"unsupported suite action {action!r}; known: {sorted(SUITE_ACTIONS)}")
    project = store.get_project(project_id)
    experiment = _selected(
        project.get("experiments"),
        id_field="experiment_id",
        item_id=experiment_id,
        label="experiment",
    )
    version_id = str(experiment["strategy_version_id"])
    version = _selected(
        project.get("versions"),
        id_field="version_id",
        item_id=version_id,
        label="strategy version",
    )
    stage = _ACTION_STAGE[action]
    states = _stage_states(project, experiment_id)
    current_state = states.get(stage, "not_started")
    resume_reveal = bool(
        action == "holdout_reveal"
        and resume_job_id is not None
        and store.holdout_reveal_resume_authorized(
            project_id,
            experiment_id,
            resume_job_id,
            require_terminal=True,
        )
    )
    blockers: list[str] = []
    if project.get("current_experiment_id") != experiment_id:
        blockers.append("experiment is not the project's current immutable specification")
    if current_state in {"queued", "running", "fail", "stale"} and not resume_reveal:
        blockers.append(f"{stage} stage is {current_state}")
    for prerequisite in _PREREQUISITES[action]:
        if states.get(prerequisite) not in {"pass", "warning"}:
            blockers.append(f"{prerequisite} stage must be pass or warning")

    universe_raw = experiment.get("universe")
    if not isinstance(universe_raw, list) or not universe_raw:
        raise DataError("invalid immutable experiment universe")
    universe = sorted(str(symbol) for symbol in universe_raw)
    primary = universe[0]
    snapshot = _safe_id(experiment.get("snapshot_id"), "snapshot_id")
    strategy = str(version.get("strategy_name"))
    specs_for(strategy)  # fail closed before building any argv
    definition = _object(version.get("definition"), "strategy definition")
    parameter_space = _object(version.get("parameter_space"), "parameter space")
    split = _object(experiment.get("split_policy"), "split policy")
    costs = _object(experiment.get("costs"), "costs")
    seeds = _object(experiment.get("seeds"), "seeds")
    config = _object(experiment.get("stage_config"), "stage configuration")

    holdouts = project.get("holdouts")
    holdout = (
        next(
            (
                _object(row, "holdout state")
                for row in holdouts
                if isinstance(holdouts, list)
                and isinstance(row, dict)
                and row.get("experiment_id") == experiment_id
            ),
            None,
        )
        if isinstance(holdouts, list)
        else None
    )
    sealed_spec = store.get_holdout_spec(project_id, experiment_id)
    research_cutoff: str | None = None
    cutoff_marker: str | None = None
    if action in _PRE_REVEAL_RESEARCH_ACTIONS:
        if sealed_spec is None or holdout is None:
            blockers.append("dated final holdout must be sealed before research begins")
        elif holdout.get("revealed_at") is not None:
            blockers.append("research cannot resume after the final holdout is revealed")
        elif holdout.get("contaminated_at") is not None:
            blockers.append("final holdout is contaminated for this lineage")
        else:
            holdout_start = date.fromisoformat(str(sealed_spec["start_date"]))
            research_cutoff = (holdout_start - timedelta(days=1)).isoformat()
            cutoff_marker = f"<sealed-pre-holdout:{sealed_spec['spec_hash']}>"

    # spec §15 / ADR-0026: an owner override is the only unlinked path through a governed gate;
    # every strategy run launched under it carries the permanent EXPLORATORY watermark.
    gate_overridden = project.get("research_gate_state") == "overridden"
    common = _common(
        symbol=primary,
        strategy=strategy,
        snapshot=snapshot,
        costs=costs,
        definition=definition,
        gate_overridden=gate_overridden,
    )
    cutoff_value = research_cutoff or "<sealed-research-cutoff-required>"
    public_cutoff = cutoff_marker or "<sealed-research-cutoff-required>"
    research_common = [*common]
    if action in _PRE_REVEAL_RESEARCH_ACTIONS:
        research_common.extend(["--as-of", cutoff_value])
    steps: list[SuiteStep] = []
    workload: dict[str, object]
    governance: dict[str, object] = {
        "paper_only": True,
        "holdout_visible_to_optimization": False,
        "command_construction": "allowlisted",
    }
    if gate_overridden:
        governance["research_gate"] = {
            "state": "overridden",
            "watermark": RESEARCH_GATE_OVERRIDE_WATERMARK,
        }
    if action in _PRE_REVEAL_RESEARCH_ACTIONS:
        governance.update(
            {
                "sealed_holdout_required_before_research": True,
                "research_window": public_cutoff,
                "sealed_dates_visible": False,
            }
        )

    if action == "baseline":
        args = ("backtest", "run", *research_common)
        steps.append(
            SuiteStep(
                "Baseline discovery",
                args,
                _cutoff_preview(args, cutoff=cutoff_value, marker=public_cutoff),
                "discovery_only",
                ((cutoff_value, public_cutoff),),
            )
        )
        workload = _workload(action, commands=1, canonical_runs=1)
    elif action == "inner_oos":
        args = ("backtest", "oos", *research_common, *_split_options(split))
        steps.append(
            SuiteStep(
                "Inner walk-forward OOS",
                args,
                _cutoff_preview(args, cutoff=cutoff_value, marker=public_cutoff),
                "fixed_rule_no_refit",
                ((cutoff_value, public_cutoff),),
            )
        )
        governance["oos_semantics"] = "fixed_rule_evaluation_no_refit"
        workload = _workload(action, commands=1, canonical_runs=1)
    elif action == "three_null_families":
        validation = [
            "validate",
            *research_common,
            *_split_options(split),
            "--seed",
            str(_seed(seeds)),
            "--tier1-paths",
            str(_stage_int(config, "tier1_paths", 1000, minimum=100, maximum=100_000)),
            "--tier2-paths",
            str(_stage_int(config, "tier2_paths", 64, minimum=1, maximum=10_000)),
            "--n-resamples",
            str(_stage_int(config, "n_resamples", 2000, minimum=100, maximum=100_000)),
            "--mean-block",
            _float_text(_stage_float(config, "mean_block", 5.0, minimum=1.0, maximum=10_000.0)),
            "--threshold",
            _float_text(_stage_float(config, "null_threshold", 0.95, minimum=0.0, maximum=1.0)),
            "--tier1-divergence-tol",
            _float_text(
                _stage_float(
                    config,
                    "tier1_divergence_tol",
                    0.25,
                    minimum=0.0,
                    maximum=100.0,
                )
            ),
        ]
        if "max_workers" in config:
            validation.extend(
                [
                    "--max-workers",
                    str(_stage_int(config, "max_workers", 1, minimum=1, maximum=64)),
                ]
            )
        for family, label, role in (
            ("bootstrap", "Stationary bootstrap headline", "headline_tier1_plus_tier2"),
            (
                "student_t",
                "Student-t sensitivity",
                "tier1_sensitivity_tier2_repeated_non_governing",
            ),
            (
                "garch",
                "GARCH sensitivity",
                "tier1_sensitivity_tier2_repeated_non_governing",
            ),
        ):
            args = (*validation, "--null-model", family)
            steps.append(
                SuiteStep(
                    label,
                    args,
                    _cutoff_preview(args, cutoff=cutoff_value, marker=public_cutoff),
                    role,
                    ((cutoff_value, public_cutoff),),
                )
            )
        governance.update(
            {
                "aggregation": "no_majority_vote",
                "headline": "bootstrap Tier-1 paired with full-engine Tier-2",
                "sensitivities": ["student_t Tier-1", "garch Tier-1"],
                "sensitivity_tier2_execution": (
                    "the canonical validate command currently repeats full-engine Tier-2 for "
                    "Student-t and GARCH; those repeated checks are recorded but are non-governing"
                ),
            }
        )
        workload = _workload(action, commands=3, canonical_runs=3)
    elif action == "optimize_grid":
        step, combinations = _grid_steps(
            primary=primary,
            strategy=strategy,
            snapshot=snapshot,
            costs=costs,
            definition=definition,
            parameter_space=parameter_space,
            split=split,
            seeds=seeds,
            config=config,
            research_cutoff=cutoff_value,
            cutoff_marker=public_cutoff,
            gate_overridden=gate_overridden,
        )
        steps.append(step)
        workload = _workload(action, commands=1, canonical_runs=1, grid_configurations=combinations)
    elif action == "fixed_stress":
        source_run = _latest_run(project, experiment_id, ("oos", "baseline"))
        if source_run is None:
            blockers.append("fixed stress requires a cited baseline or OOS run")
            source_run = "<required-run>"
        args = ("risk", "scenario", "--from-run", source_run, "--json")
        steps.append(SuiteStep("Fixed stress scenarios", args, args, "scenario_sensitivity"))
        governance["separate_from_nulls"] = True
        workload = _workload(action, commands=1, canonical_runs=0)
    elif action == "portfolio_cross_asset":
        if len(universe) < 2:
            blockers.append("portfolio/cross-asset analysis requires at least two frozen symbols")
        base = [
            *universe,
            "--strategy",
            strategy,
            "--snapshot",
            snapshot,
            "--fee-bps",
            _float_text(_number(costs.get("fee_bps", 1.0), "fee_bps", minimum=0.0)),
            "--slippage-bps",
            _float_text(_number(costs.get("slippage_bps", 2.0), "slippage_bps", minimum=0.0)),
            *_definition_options(definition),
            *_strategy_options(strategy, definition),
            *_split_options(split),
            "--seed",
            str(_seed(seeds)),
            "--as-of",
            cutoff_value,
            *(["--research-gate-override"] if gate_overridden else []),
        ]
        weighting = config.get("portfolio_weighting", "equal")
        if weighting not in {"equal", "inverse_vol"}:
            raise DataError("portfolio_weighting must be equal or inverse_vol")
        portfolio_args = ("backtest", "portfolio", *base, "--weighting", str(weighting))
        cross_args = ("backtest", "cross-sectional", *base)
        steps.extend(
            [
                SuiteStep(
                    "Portfolio OOS analysis",
                    portfolio_args,
                    _cutoff_preview(portfolio_args, cutoff=cutoff_value, marker=public_cutoff),
                    "portfolio_allocation",
                    ((cutoff_value, public_cutoff),),
                ),
                SuiteStep(
                    "Cross-asset OOS analysis",
                    cross_args,
                    _cutoff_preview(cross_args, cutoff=cutoff_value, marker=public_cutoff),
                    "cross_asset_association",
                    ((cutoff_value, public_cutoff),),
                ),
            ]
        )
        workload = _workload(action, commands=2, canonical_runs=2)
    elif action == "qlib":
        if len(universe) < 20:
            blockers.append("Qlib starter requires at least 20 frozen symbols")
        managed_id = _managed_qlib_id(experiment_id)
        ml_root = data_dir / "control" / "ml"
        input_bundle = ml_root / "inputs" / managed_id
        exchange = ml_root / "exchanges" / managed_id
        worker_lock = Path(__file__).resolve().parents[4] / "workers" / "qlib" / "uv.lock"
        if input_bundle.exists() or exchange.exists():
            blockers.append(
                "managed Qlib resources already exist for this immutable experiment; "
                "inspect the existing ML experiment or create a new ExperimentSpec"
            )
        if worker_lock.is_symlink() or not worker_lock.is_file():
            blockers.append("isolated Qlib worker lock is unavailable")
        input_marker = f"<managed-input:{managed_id}>"
        exchange_marker = f"<managed-exchange:{managed_id}>"
        lock_marker = "<isolated-worker-lock>"
        redactions = (
            (str(input_bundle), input_marker),
            (str(exchange), exchange_marker),
            (str(worker_lock), lock_marker),
            (cutoff_value, public_cutoff),
        )
        export = (
            "ml",
            "export-input",
            project_id,
            experiment_id,
            str(input_bundle),
            "--as-of",
            cutoff_value,
            "--json",
        )
        prepare = (
            "ml",
            "prepare",
            str(input_bundle / "spec.json"),
            str(input_bundle / "panel.parquet"),
            str(exchange),
            "--worker-lock",
            str(worker_lock),
            "--json",
        )
        train = ("ml", "train", str(exchange), "--mode", "real", "--json")
        replay = (
            "ml",
            "replay",
            str(exchange),
            "--as-of",
            cutoff_value,
            "--json",
        )
        steps.extend(
            [
                SuiteStep(
                    "Generate immutable Qlib input",
                    export,
                    (
                        "ml",
                        "export-input",
                        project_id,
                        experiment_id,
                        input_marker,
                        "--as-of",
                        public_cutoff,
                        "--json",
                    ),
                    "immutable_snapshot_bound_input",
                    redactions,
                ),
                SuiteStep(
                    "Prepare isolated Qlib exchange",
                    prepare,
                    (
                        "ml",
                        "prepare",
                        f"{input_marker}/spec.json",
                        f"{input_marker}/panel.parquet",
                        exchange_marker,
                        "--worker-lock",
                        lock_marker,
                        "--json",
                    ),
                    "validated_portable_worker_contract",
                    redactions,
                ),
                SuiteStep(
                    "Qlib fold training",
                    train,
                    ("ml", "train", exchange_marker, "--mode", "real", "--json"),
                    "fold_refit",
                    redactions,
                ),
                SuiteStep(
                    "Canonical ALPHA ML replay",
                    replay,
                    (
                        "ml",
                        "replay",
                        exchange_marker,
                        "--as-of",
                        public_cutoff,
                        "--json",
                    ),
                    "oos_replay_model_not_recomputed_under_counterfactual",
                    redactions,
                ),
            ]
        )
        governance.update(
            {
                "isolated_worker": True,
                "counterfactual_refit": False,
                "promotion_eligible": False,
                "managed_resource_id": managed_id,
                "minimum_aligned_sessions": 756,
                "minimum_aligned_sessions_enforced_by": "immutable input export",
            }
        )
        workload = _workload(action, commands=4, canonical_runs=1)
    elif action == "kronos":
        model = config.get("kronos_model")
        model_args: list[str] = []
        if model is None:
            blockers.append("Kronos requires a pinned model id in the immutable experiment")
        elif not isinstance(model, str) or _SAFE_MODEL.fullmatch(model) is None:
            raise DataError("kronos_model must be 'fake' or a managed repository id")
        else:
            model_args = ["--model", model]
        if isinstance(model, str) and model != "fake" and "kronos_model_revision" not in config:
            blockers.append("Kronos repository models require a pinned model revision")
        for key, flag in (
            ("kronos_model_revision", "--model-revision"),
            ("kronos_tokenizer_revision", "--tokenizer-revision"),
        ):
            value = config.get(key)
            if value is not None:
                if not isinstance(value, str) or _SAFE_REVISION.fullmatch(value) is None:
                    raise DataError(f"{key} must be a safe immutable revision id")
                model_args.extend([flag, value])
        tokenizer = config.get("kronos_tokenizer")
        if tokenizer is not None:
            if not isinstance(tokenizer, str) or _SAFE_MODEL.fullmatch(tokenizer) is None:
                raise DataError("kronos_tokenizer must be a managed repository id")
            model_args.extend(["--tokenizer", tokenizer])
        device = config.get("kronos_device", "cpu")
        if device not in {"cpu", "mps", "cuda"}:
            raise DataError("kronos_device must be cpu, mps, or cuda")
        model_args.extend(["--device", str(device)])
        horizon = _stage_int(config, "kronos_horizon", 21, minimum=1, maximum=512)
        samples = _stage_int(config, "kronos_samples", 100, minimum=1, maximum=1000)
        eval_samples = _stage_int(config, "kronos_eval_samples", 30, minimum=1, maximum=200)
        context = _stage_int(config, "kronos_context", 400, minimum=2, maximum=100_000)
        stride = _stage_int(config, "kronos_stride", 21, minimum=1, maximum=10_000)
        temperature = _stage_float(config, "kronos_temperature", 1.0, minimum=0.0, maximum=10.0)
        top_p = _stage_float(config, "kronos_top_p", 0.9, minimum=0.0, maximum=1.0)
        top_k = _stage_int(config, "kronos_top_k", 0, minimum=0, maximum=1_000_000)
        forecast = (
            "forecast",
            "run",
            primary,
            "--snapshot",
            snapshot,
            "--horizon",
            str(horizon),
            "--samples",
            str(samples),
            "--context",
            str(context),
            "--temperature",
            _float_text(temperature),
            "--top-p",
            _float_text(top_p),
            "--top-k",
            str(top_k),
            "--seed",
            str(_seed(seeds)),
            "--as-of",
            cutoff_value,
            *model_args,
        )
        evaluate = (
            "forecast",
            "eval",
            primary,
            "--snapshot",
            snapshot,
            "--horizon",
            str(horizon),
            "--samples",
            str(eval_samples),
            "--context",
            str(context),
            "--stride",
            str(stride),
            "--temperature",
            _float_text(temperature),
            "--top-p",
            _float_text(top_p),
            "--top-k",
            str(top_k),
            "--seed",
            str(_seed(seeds)),
            "--as-of",
            cutoff_value,
            *model_args,
        )
        steps.extend(
            [
                SuiteStep(
                    "Kronos forecast cone",
                    forecast,
                    _cutoff_preview(forecast, cutoff=cutoff_value, marker=public_cutoff),
                    "forecast_samples",
                    ((cutoff_value, public_cutoff),),
                ),
                SuiteStep(
                    "Kronos rolling evaluation",
                    evaluate,
                    _cutoff_preview(evaluate, cutoff=cutoff_value, marker=public_cutoff),
                    "rolling_evaluation",
                    ((cutoff_value, public_cutoff),),
                ),
            ]
        )
        governance["pretraining_overlap_warning_permanent"] = True
        workload = _workload(action, commands=2, canonical_runs=2)
    elif action == "holdout_reveal":
        if holdout is None:
            blockers.append("final holdout must be sealed before owner reveal")
        elif holdout.get("revealed_at") is not None and not resume_reveal:
            blockers.append("final holdout was already revealed")
        elif holdout.get("contaminated_at") is not None:
            blockers.append("final holdout is contaminated for this lineage")
        sealed_spec = store.get_holdout_spec(project_id, experiment_id)
        if sealed_spec is None:
            blockers.append("final holdout must include a sealed evaluation window")
        preview = (
            "project",
            "reveal-holdout",
            project_id,
            experiment_id,
            "--actor",
            "<owner>",
            "--reason",
            "<owner-confirmed>",
        )
        steps.append(
            SuiteStep(
                "One-shot final holdout reveal",
                ("__holdout__",),
                preview,
                "owner_only_irreversible_audit",
            )
        )
        if sealed_spec is not None:
            spec_hash = str(sealed_spec["spec_hash"])
            threshold = _stage_float(
                config,
                "holdout_min_sharpe",
                0.0,
                minimum=-100.0,
                maximum=100.0,
            )
            evaluation = (
                "backtest",
                "holdout",
                *common,
                "--holdout-start",
                str(sealed_spec["start_date"]),
                "--holdout-end",
                str(sealed_spec["end_date"]),
                "--holdout-spec-hash",
                spec_hash,
                "--min-sharpe",
                _float_text(threshold),
            )
            public_evaluation = (
                "backtest",
                "holdout",
                *common,
                "--holdout-window",
                f"<sealed:{spec_hash}>",
                "--min-sharpe",
                _float_text(threshold),
            )
            steps.append(
                SuiteStep(
                    "Locked final holdout evaluation",
                    evaluation,
                    public_evaluation,
                    "one_shot_fixed_candidate_holdout",
                )
            )
        governance.update(
            {
                "owner_only": True,
                "available_to_mcp": False,
                "one_shot": True,
                "resume_same_job_after_interruption": resume_reveal,
                "sealed_window_redacted_until_reveal": True,
            }
        )
        workload = _workload(action, commands=2, canonical_runs=1)
    else:
        paper_symbol_raw = config.get("paper_symbol")
        paper_symbol = (
            str(paper_symbol_raw)
            if paper_symbol_raw is not None
            else next((symbol for symbol in universe if "/" in symbol), "")
        )
        if paper_symbol not in universe or "/" not in paper_symbol:
            blockers.append("paper preflight requires a frozen BASE/QUOTE symbol")
            paper_symbol = "<required-base/quote>"
        paper_args = ["paper", "preflight", paper_symbol, "--strategy", strategy]
        if "starting_cash" in definition:
            paper_args.extend(
                [
                    "--starting-cash",
                    _float_text(_number(definition["starting_cash"], "starting_cash", minimum=1.0)),
                ]
            )
        paper_args.extend(_strategy_options(strategy, definition))
        steps.append(
            SuiteStep(
                "Sandbox paper preflight",
                tuple(paper_args),
                tuple(paper_args),
                "sandbox_preflight_only",
            )
        )
        governance.update({"sandbox": True, "places_orders": False, "owner_only_launch": True})
        workload = _workload(action, commands=1, canonical_runs=0)

    return SuitePlan(
        schema_version=1,
        project_id=project_id,
        experiment_id=experiment_id,
        action=action,
        stage=stage,
        ready=not blockers,
        blockers=tuple(blockers),
        resolved_experiment=experiment,
        resolved_strategy_version=version,
        current_stage_state=current_state,
        estimated_workload=workload,
        steps=tuple(steps),
        governance=governance,
    )


def _fingerprint(plan: SuitePlan, step: SuiteStep, index: int) -> str:
    payload = {
        "schema_version": plan.schema_version,
        "experiment_id": plan.experiment_id,
        "action": plan.action,
        "step": index,
        "command": list(step.preview),
        "evidence_role": step.evidence_role,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "suite:" + hashlib.sha256(canonical.encode()).hexdigest()


def _redact(line: str, step: SuiteStep) -> str:
    result = line
    for source, replacement in step.redactions:
        result = result.replace(source, replacement)
    return result[:8000]


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - the suite owns its child group.
        return True
    return True


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate the isolated step session, then force-kill and reap after a fixed grace."""
    process_group_id = process.pid
    with suppress(ProcessLookupError):
        os.killpg(process_group_id, signal.SIGTERM)
    deadline = time.monotonic() + _PROCESS_TERM_GRACE_SECONDS
    while _process_group_exists(process_group_id):
        process.poll()  # Reap a cooperative group leader while descendants wind down.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(_PROCESS_GROUP_POLL_SECONDS, remaining))
    if _process_group_exists(process_group_id):
        with suppress(ProcessLookupError):
            os.killpg(process_group_id, signal.SIGKILL)
        kill_deadline = time.monotonic() + _PROCESS_REAP_TIMEOUT_SECONDS
        while _process_group_exists(process_group_id):
            process.poll()
            remaining = kill_deadline - time.monotonic()
            if remaining <= 0:
                raise SuiteProcessCleanupError("suite process group still exists after SIGKILL")
            time.sleep(min(_PROCESS_GROUP_POLL_SECONDS, remaining))
    try:
        process.wait(timeout=_PROCESS_REAP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - SIGKILL should be final.
        raise SuiteProcessCleanupError(
            "suite subprocess could not be reaped after SIGKILL"
        ) from exc


def _verified_process_group_exists(process: subprocess.Popen[str]) -> bool:
    """Reap an exited leader and fail closed if group liveness cannot be established."""
    try:
        process.poll()
        return _process_group_exists(process.pid)
    except Exception as exc:
        raise SuiteProcessCleanupError(
            f"suite process-group liveness could not be verified: {exc}"
        ) from exc


def _cleanup_process_group(process: subprocess.Popen[str]) -> None:
    """Verify post-spawn cleanup and normalize every ordinary cleanup failure."""
    try:
        if _verified_process_group_exists(process):
            _terminate_process_group(process)
    except SuiteProcessCleanupError:
        raise
    except Exception as exc:
        raise SuiteProcessCleanupError(
            f"suite process-group cleanup could not be verified: {exc}"
        ) from exc


def _default_step_runner(
    step: SuiteStep,
    job_id: str,
    store: ControlStore,
    cancelled: Callable[[], bool],
) -> StepExecution:
    process = subprocess.Popen(
        ["alpha", *step.argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    stdout = process.stdout
    selector: selectors.BaseSelector | None = None
    run_ids: list[str] = []
    last_heartbeat = time.monotonic()
    termination_requested = False

    def record(raw: str) -> None:
        line = _redact(raw.rstrip("\n"), step)
        store.append_job_event(job_id, event_type="log", payload={"line": line})
        for pattern in (_RUN_RE, _JSON_RUN_RE):
            match = pattern.search(line)
            if match is not None and match.group(1) not in run_ids:
                run_ids.append(match.group(1))

    try:
        if stdout is None:  # pragma: no cover - PIPE guarantees stdout.
            raise DataError("suite subprocess did not expose stdout")
        selector = selectors.DefaultSelector()
        selector.register(stdout, selectors.EVENT_READ)
        stdout_open = True
        group_alive = _verified_process_group_exists(process)
        while stdout_open or group_alive:
            if cancelled() and group_alive and not termination_requested:
                _terminate_process_group(process)
                termination_requested = True
            if stdout_open:
                events = selector.select(timeout=0.5)
            else:
                time.sleep(0.5)
                events = []
            for _key, _ in events:
                raw = stdout.readline()
                if not raw:
                    selector.unregister(stdout)
                    stdout_open = False
                    break
                record(raw)
            group_alive = _verified_process_group_exists(process)
            if (
                group_alive
                and time.monotonic() - last_heartbeat >= _SUITE_HEARTBEAT_INTERVAL_SECONDS
            ):
                store.append_job_event(job_id, event_type="heartbeat", payload={"step": step.label})
                last_heartbeat = time.monotonic()
    finally:
        cleanup_error: SuiteProcessCleanupError | None = None
        close_error: Exception | None = None
        try:
            _cleanup_process_group(process)
        except SuiteProcessCleanupError as exc:
            cleanup_error = exc
        finally:
            if selector is not None:
                try:
                    selector.close()
                except Exception as exc:
                    close_error = exc
            if stdout is not None:
                try:
                    stdout.close()
                except Exception as exc:
                    if close_error is None:
                        close_error = exc
        if cleanup_error is not None:
            if close_error is not None:
                cleanup_error.add_note(f"resource close also failed: {close_error}")
            raise cleanup_error
        if close_error is not None:
            raise close_error
    return StepExecution(returncode=int(process.wait()), run_ids=tuple(run_ids))


def _prepare_stage(store: ControlStore, plan: SuitePlan) -> None:
    state = plan.current_stage_state
    if state == "not_started":
        store.append_experiment_stage_state(
            plan.project_id,
            plan.experiment_id,
            plan.stage,
            "ready",
            reason=f"suite plan {plan.action} resolved",
        )
        state = "ready"
    if state == "ready":
        store.append_experiment_stage_state(
            plan.project_id,
            plan.experiment_id,
            plan.stage,
            "queued",
            reason=f"suite action {plan.action} queued",
        )
        store.append_experiment_stage_state(
            plan.project_id,
            plan.experiment_id,
            plan.stage,
            "running",
            reason=f"suite action {plan.action} started",
        )


def _finish_stage(
    store: ControlStore,
    plan: SuitePlan,
    state: StageState,
    reason: str,
    *,
    job_id: str,
) -> None:
    detail = store.get_project(plan.project_id)
    current = _stage_states(detail, plan.experiment_id).get(plan.stage)
    if current == "running":
        if plan.action == "paper_preflight":
            store.complete_suite_journal_stage(
                plan.project_id,
                plan.experiment_id,
                suite_action=plan.action,
                stage=plan.stage,
                state=state,
                job_id=job_id,
                reason=reason,
            )
            return
        store.complete_suite_stage(
            plan.project_id,
            plan.experiment_id,
            suite_action=plan.action,
            stage=plan.stage,
            state=state,
            reason=reason,
        )


def _headline_state(data_dir: Path, plan: SuitePlan, run_ids: Sequence[str]) -> StageState:
    if not run_ids:
        return "pass"
    if plan.action not in {"three_null_families", "optimize_grid", "holdout_reveal"}:
        return "pass"
    from alpha_cli._artifacts import read_manifest
    from alpha_cli.run_store import find_run_dir

    run_dir = find_run_dir(data_dir, run_ids[0])
    if run_dir is None:
        raise DataError(f"suite result run {run_ids[0]!r} was not published")
    manifest = read_manifest(run_dir)
    if plan.action in {"optimize_grid", "holdout_reveal"}:
        return "pass" if manifest.get("passed") is True else "fail"
    outcomes = manifest.get("outcomes")
    if isinstance(outcomes, list):
        headline = next(
            (
                row
                for row in outcomes
                if isinstance(row, dict) and row.get("name") == "randomized_price_null"
            ),
            None,
        )
        if isinstance(headline, dict):
            return "pass" if headline.get("passed") is True else "fail"
    return "fail"


def _record_optimization_trial_attempts(
    store: ControlStore,
    plan: SuitePlan,
    *,
    data_dir: Path,
    job_id: str,
    run_ids: Sequence[str],
) -> None:
    """Project every declared grid row into the append-only project attempt ledger."""
    if plan.action != "optimize_grid":
        return
    if len(run_ids) != 1:
        raise DataError(
            "deterministic grid suite must publish exactly one canonical optimization run"
        )

    from alpha_cli import _optim
    from alpha_cli._artifacts import read_manifest
    from alpha_cli.artifact_contract import verify_manifest_artifacts
    from alpha_cli.run_store import find_run_dir

    run_id = run_ids[0]
    run_dir = find_run_dir(data_dir, run_id)
    if run_dir is None:
        raise DataError(f"optimization run {run_id!r} was not published")
    manifest = read_manifest(run_dir)
    verify_manifest_artifacts(run_dir, manifest)
    if manifest.get("command") != "optim_grid":
        raise DataError(f"suite optimization evidence {run_id!r} is not an optim_grid run")

    for outcome in _optim.read_trial_ledger(run_dir):
        details: dict[str, object] = {
            "action": plan.action,
            "job_id": job_id,
            "trial": outcome.trial_index,
            "config": [[name, value] for name, value in outcome.config],
            "source_artifact": "trial_ledger.parquet",
            "row_selector": {"trial": outcome.trial_index},
            "n_oos": len(outcome.oos_returns),
            "annualized_sharpe": outcome.annualized_sharpe,
        }
        if outcome.status in {"pruned", "rejected"}:
            details["reason"] = outcome.error
        store.record_attempt(
            plan.project_id,
            plan.experiment_id,
            stage=plan.stage,
            status=cast(AttemptStatus, outcome.status),
            config_fingerprint=outcome.config_fingerprint,
            run_id=run_id,
            error=outcome.error if outcome.status == "failed" else None,
            details=details,
        )


def reserve_suite_job(
    store: ControlStore,
    plan: SuitePlan,
    *,
    job_id: str | None = None,
) -> dict[str, object]:
    """Persist/reuse the exact queued suite journal before a detached worker is launched."""
    if not plan.ready:
        raise DataError("suite plan is not ready: " + "; ".join(plan.blockers))
    return store.create_suite_job(
        kind=f"suite:{plan.action}",
        request=plan.as_dict(),
        project_id=plan.project_id,
        experiment_id=plan.experiment_id,
        job_id=job_id,
    )


def execute_suite(
    store: ControlStore,
    plan: SuitePlan,
    *,
    data_dir: Path,
    job_id: str | None = None,
    owner_actor: str | None = None,
    owner_reason: str | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    step_runner: StepRunner = _default_step_runner,
) -> dict[str, object]:
    """Execute a ready plan and journal every state, attempt, log, and result."""
    if not plan.ready:
        raise DataError("suite plan is not ready: " + "; ".join(plan.blockers))
    resume_reveal = plan.governance.get("resume_same_job_after_interruption") is True
    if (
        plan.action == "holdout_reveal"
        and not resume_reveal
        and (not owner_actor or not owner_reason)
    ):
        raise DataError("holdout reveal requires an explicit owner actor and reason")
    request = plan.as_dict()
    job = reserve_suite_job(store, plan, job_id=job_id)
    jid = str(job["job_id"])
    audited_reveal_for_job = bool(
        plan.action == "holdout_reveal"
        and store.holdout_reveal_resume_authorized(plan.project_id, plan.experiment_id, jid)
    )

    def cancellation_requested() -> bool:
        return cancelled() or store.job_cancellation_requested(jid)

    if plan.action in _GOVERNED_STAGE_ACTIONS:
        _prepare_stage(store, plan)
    store.set_job_status(jid, "running")
    run_ids: list[str] = []
    current_index = 0
    try:
        for current_index, step in enumerate(plan.steps, start=1):
            fingerprint = _fingerprint(plan, step, current_index)
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="queued",
                config_fingerprint=fingerprint,
                details={
                    "action": plan.action,
                    "job_id": jid,
                    "step": current_index,
                    "label": step.label,
                    "evidence_role": step.evidence_role,
                },
            )
            store.append_job_event(
                jid,
                event_type="progress",
                payload={"step": current_index, "total": len(plan.steps), "label": step.label},
            )
            store.append_job_event(
                jid,
                event_type="heartbeat",
                payload={"step": current_index, "label": step.label},
            )
            if cancellation_requested():
                raise InterruptedError("suite action cancelled")
            if step.argv == ("__holdout__",):
                if not audited_reveal_for_job:
                    store.reveal_holdout(
                        plan.project_id,
                        plan.experiment_id,
                        actor=cast(str, owner_actor),
                        reason=cast(str, owner_reason),
                    )
                execution = StepExecution(returncode=0, run_ids=())
            else:
                execution = step_runner(step, jid, store, cancellation_requested)
            if cancellation_requested():
                raise InterruptedError("suite action cancelled")
            if execution.returncode != 0:
                raise DataError(
                    f"suite step {current_index} {step.label!r} failed with exit "
                    f"{execution.returncode}"
                )
            for run_id in execution.run_ids:
                if run_id not in run_ids:
                    run_ids.append(run_id)
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="passed",
                config_fingerprint=fingerprint,
                run_id=execution.run_ids[0] if execution.run_ids else None,
                details={
                    "action": plan.action,
                    "job_id": jid,
                    "step": current_index,
                    "label": step.label,
                    "evidence_role": step.evidence_role,
                    "run_ids": list(execution.run_ids),
                },
            )
        _record_optimization_trial_attempts(
            store,
            plan,
            data_dir=data_dir,
            job_id=jid,
            run_ids=run_ids,
        )
        stage_state = _headline_state(data_dir, plan, run_ids)
        linked_results: list[tuple[str, StageState]] = [(run_id, stage_state) for run_id in run_ids]
        if plan.action == "three_null_families" and run_ids:
            linked_results = [
                *((run_id, "warning") for run_id in run_ids[1:]),
                (run_ids[0], stage_state),
            ]
        for run_id, link_state in linked_results:
            store.link_suite_stage_run(
                plan.project_id,
                plan.experiment_id,
                suite_action=plan.action,
                stage=plan.stage,
                state=link_state,
                run_id=run_id,
            )
        if plan.action in _GOVERNED_STAGE_ACTIONS:
            _finish_stage(
                store,
                plan,
                stage_state,
                "suite completed; headline evidence governs stage state",
                job_id=jid,
            )
        reported_stage_state = (
            stage_state if plan.action in _GOVERNED_STAGE_ACTIONS else plan.current_stage_state
        )
        result = {
            "action": plan.action,
            "stage": plan.stage,
            "stage_state": reported_stage_state,
            "run_ids": run_ids,
            "headline_run_id": run_ids[0] if run_ids else None,
        }
        store.append_job_result(jid, result)
        completed = store.set_job_status(
            jid,
            "succeeded",
            result_run_id=run_ids[0] if run_ids else None,
        )
        return {**completed, "plan": request, "result": result}
    except InterruptedError:
        if current_index:
            step = plan.steps[current_index - 1]
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="cancelled",
                config_fingerprint=_fingerprint(plan, step, current_index),
                details={"action": plan.action, "job_id": jid, "step": current_index},
            )
        resumable_holdout = bool(
            plan.action == "holdout_reveal"
            and store.holdout_reveal_resume_authorized(plan.project_id, plan.experiment_id, jid)
        )
        if plan.action in _GOVERNED_STAGE_ACTIONS and not resumable_holdout:
            _finish_stage(store, plan, "fail", "suite action cancelled", job_id=jid)
        store.set_job_status(jid, "cancelled")
        raise
    except SuiteProcessCleanupError as exc:
        if current_index:
            step = plan.steps[current_index - 1]
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="failed",
                config_fingerprint=_fingerprint(plan, step, current_index),
                error=str(exc)[:8000],
                details={
                    "action": plan.action,
                    "job_id": jid,
                    "step": current_index,
                    "cleanup_unverified": True,
                },
            )
        store.append_job_event(
            jid,
            event_type="log",
            payload={
                "line": (
                    f"suite process-group cleanup failed: {exc}; "
                    "heavyweight capacity remains reserved"
                )
            },
        )
        # A terminal journal would release the shared heavyweight slot even though a descendant
        # may still be executing. Leave both the stage and job running until stale-lease
        # reconciliation can surface the abandoned execution for an owner.
        raise
    except Exception as exc:
        if current_index:
            step = plan.steps[current_index - 1]
            store.record_attempt(
                plan.project_id,
                plan.experiment_id,
                stage=plan.stage,
                status="failed",
                config_fingerprint=_fingerprint(plan, step, current_index),
                error=str(exc)[:8000],
                details={"action": plan.action, "job_id": jid, "step": current_index},
            )
        resumable_holdout = bool(
            plan.action == "holdout_reveal"
            and store.holdout_reveal_resume_authorized(plan.project_id, plan.experiment_id, jid)
        )
        if plan.action in _GOVERNED_STAGE_ACTIONS and not resumable_holdout:
            _finish_stage(store, plan, "fail", "suite action failed", job_id=jid)
        store.set_job_status(jid, "failed", terminal_error=str(exc)[:8000])
        raise


__all__ = [
    "SUITE_ACTIONS",
    "SuiteProcessCleanupError",
    "StepExecution",
    "SuiteAction",
    "SuitePlan",
    "SuiteStep",
    "build_suite_plan",
    "execute_suite",
    "reserve_suite_job",
]
