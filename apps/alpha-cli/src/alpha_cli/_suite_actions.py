"""Ordered action-specific suite step builders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from alpha_cli._schemas import specs_for
from alpha_cli._suite_types import (
    _CANDIDATE_SIMPLE_ACTIONS,
    _CANDIDATE_SIMPLE_GOVERNANCE,
    _SAFE_MODEL,
    _SAFE_REVISION,
    _STANDARD_DEFINITION_OPTIONS,
    SuiteStep,
    _common,
    _cutoff_preview,
    _definition_options,
    _float_text,
    _latest_run,
    _latest_run_for_command,
    _managed_qlib_id,
    _number,
    _PlanContext,
    _ResearchWindow,
    _seed,
    _split_options,
    _stage_float,
    _stage_int,
    _strategy_options,
    _workload,
)
from alpha_core import DataError


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
            ["--max-workers", str(_stage_int(config, "max_workers", 1, minimum=1, maximum=64))]
        )
    step = SuiteStep(
        label="Deterministic grid optimization",
        argv=tuple(args),
        preview=_cutoff_preview(args, cutoff=research_cutoff, marker=cutoff_marker),
        evidence_role="selection_with_pbo_dsr_reality_check_spa",
        redactions=((research_cutoff, cutoff_marker),),
    )
    return step, combinations


def _candidate_step(
    *,
    snapshot: str,
    research_contract_id: str,
    analysis: str,
    label: str,
    evidence_role: str,
    cutoff: str,
    public_cutoff: str,
) -> SuiteStep:
    argv = (
        "strategy-candidate",
        "run",
        snapshot,
        "--research-contract-id",
        research_contract_id,
        "--analysis",
        analysis,
        "--as-of",
        cutoff,
    )
    return SuiteStep(
        label,
        argv,
        _cutoff_preview(argv, cutoff=cutoff, marker=public_cutoff),
        evidence_role,
        ((cutoff, public_cutoff),),
    )


def _null_family_steps(
    research_common: Sequence[str],
    split: Mapping[str, object],
    seeds: Mapping[str, object],
    config: Mapping[str, object],
    window: _ResearchWindow,
) -> list[SuiteStep]:
    """Build headline and sensitivity commands in the established validation order."""
    steps: list[SuiteStep] = []
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
        "--tier3-paths",
        str(_stage_int(config, "tier3_paths", 64, minimum=1, maximum=10_000)),
        "--n-resamples",
        str(_stage_int(config, "n_resamples", 2000, minimum=100, maximum=100_000)),
        "--mean-block",
        _float_text(_stage_float(config, "mean_block", 5.0, minimum=1.0, maximum=10_000.0)),
        "--threshold",
        _float_text(_stage_float(config, "null_threshold", 0.95, minimum=0.0, maximum=1.0)),
        "--tier1-divergence-tol",
        _float_text(_stage_float(config, "tier1_divergence_tol", 0.25, minimum=0.0, maximum=100.0)),
    ]
    if "max_workers" in config:
        validation.extend(
            ["--max-workers", str(_stage_int(config, "max_workers", 1, minimum=1, maximum=64))]
        )
    for family, label, role in (
        ("bootstrap", "Stationary bootstrap headline", "headline_tier1_plus_tier2"),
        ("student_t", "Student-t sensitivity", "tier1_sensitivity_tier2_repeated_non_governing"),
        ("garch", "GARCH sensitivity", "tier1_sensitivity_tier2_repeated_non_governing"),
    ):
        args = (*validation, "--null-model", family)
        steps.append(window.step(label, args, role))
    return steps


def _candidate_simple_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    specifications = _CANDIDATE_SIMPLE_ACTIONS[ctx.action]
    steps.extend(
        _candidate_step(
            snapshot=ctx.snapshot,
            research_contract_id=str(ctx.research_contract_id),
            analysis=analysis,
            label=label,
            evidence_role=evidence_role,
            cutoff=ctx.window.cutoff,
            public_cutoff=ctx.window.public_cutoff,
        )
        for analysis, label, evidence_role in specifications
    )
    ctx.governance.update(_CANDIDATE_SIMPLE_GOVERNANCE.get(ctx.action, {}))
    workload = _workload(
        ctx.action,
        commands=len(specifications),
        canonical_runs=len(specifications),
        **({"grid_configurations": 3} if ctx.action == "optimize_grid" else {}),
    )

    return steps, workload


def _candidate_monte_carlo_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    source = _latest_run_for_command(
        ctx.project,
        ctx.experiment_id,
        ("robustness",),
        data_dir=ctx.data_dir,
        commands=frozenset({"candidate_null_bootstrap"}),
    )
    source_run = None if source is None else source[0]
    if source_run is None:
        ctx.blockers.append("candidate Monte Carlo requires the completed headline null run")
        source_run = "<required-validation-run>"
    for analysis, label, role in (
        (
            "monte_carlo_classical",
            "Classical event-return Monte Carlo",
            "iid_regime_student_t_no_majority_vote",
        ),
        (
            "monte_carlo_kronos_fixture",
            "Disclosed fake model-family fixture",
            "fake_ar1_fixture_not_observed_evidence",
        ),
    ):
        args = (
            "strategy-candidate",
            "run",
            ctx.snapshot,
            "--research-contract-id",
            str(ctx.research_contract_id),
            "--analysis",
            analysis,
            "--source-run-id",
            source_run,
            "--as-of",
            ctx.window.cutoff,
        )
        steps.append(ctx.window.step(label, args, role))
    ctx.governance.update(
        {
            "aggregation": "no_majority_vote",
            "kronos_role": "disclosed_fake_fixture_not_market_oracle",
        }
    )
    workload = _workload(ctx.action, commands=2, canonical_runs=2)

    return steps, workload


def _candidate_holdout_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    if ctx.holdout is None:
        ctx.blockers.append("final holdout must be sealed before owner reveal")
    elif ctx.holdout.get("revealed_at") is not None and not ctx.resume_reveal:
        ctx.blockers.append("final holdout was already revealed")
    elif ctx.holdout.get("contaminated_at") is not None:
        ctx.blockers.append("final holdout is contaminated for this lineage")
    sealed_spec = ctx.store.get_holdout_spec(ctx.project_id, ctx.experiment_id)
    if sealed_spec is None:
        ctx.blockers.append("final holdout must include a sealed evaluation window")
    steps.append(
        SuiteStep(
            "One-shot final holdout reveal",
            ("__holdout__",),
            (
                "project",
                "reveal-holdout",
                ctx.project_id,
                ctx.experiment_id,
                "--actor",
                "<owner>",
                "--reason",
                "<owner-confirmed>",
            ),
            "owner_only_irreversible_audit",
        )
    )
    if sealed_spec is not None:
        spec_hash = str(sealed_spec["spec_hash"])
        args = (
            "strategy-candidate",
            "run",
            ctx.snapshot,
            "--research-contract-id",
            str(ctx.research_contract_id),
            "--analysis",
            "holdout",
            "--holdout-start",
            str(sealed_spec["start_date"]),
            "--holdout-end",
            str(sealed_spec["end_date"]),
            "--holdout-spec-hash",
            spec_hash,
        )
        preview = (
            "strategy-candidate",
            "run",
            ctx.snapshot,
            "--research-contract-id",
            str(ctx.research_contract_id),
            "--analysis",
            "holdout",
            "--holdout-window",
            f"<sealed:{spec_hash}>",
        )
        steps.append(
            SuiteStep(
                "Locked candidate holdout evaluation",
                args,
                preview,
                "one_shot_fixed_candidate_holdout",
            )
        )
    ctx.governance.update(
        {
            "owner_only": True,
            "available_to_mcp": False,
            "one_shot": True,
            "resume_same_job_after_interruption": ctx.resume_reveal,
            "sealed_window_redacted_until_reveal": True,
            "deployment_scope": "sandbox_only",
            "places_orders": False,
        }
    )
    workload = _workload(ctx.action, commands=2, canonical_runs=1)

    return steps, workload


def _candidate_paper_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    args = ("strategy-candidate", "paper-preflight", "--json")
    steps.append(
        SuiteStep(
            "Unsupported multi-venue paper boundary",
            args,
            args,
            "blocked_as_designed_no_paper_credit",
        )
    )
    ctx.governance.update(
        {
            "sandbox": True,
            "places_orders": False,
            "owner_only_launch": False,
            "preflight_outcome": "UNSUPPORTED_MULTI_VENUE_PAPER",
            "paper_readiness_credit": False,
        }
    )
    workload = _workload(ctx.action, commands=1, canonical_runs=0)

    return steps, workload


def _unsupported_candidate_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    ctx.blockers.append(f"hedged basis candidate analysis {ctx.action!r} is not implemented")
    workload = _workload(ctx.action, commands=0, canonical_runs=0)

    return steps, workload


def _baseline_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    args = ("backtest", "run", *ctx.research_common)
    steps.append(ctx.window.step("Baseline discovery", args, "discovery_only"))
    workload = _workload(ctx.action, commands=1, canonical_runs=1)

    return steps, workload


def _inner_oos_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    args = ("backtest", "oos", *ctx.research_common, *_split_options(ctx.split))
    steps.append(ctx.window.step("Inner walk-forward OOS", args, "fixed_rule_no_refit"))
    ctx.governance["oos_semantics"] = "fixed_rule_evaluation_no_refit"
    workload = _workload(ctx.action, commands=1, canonical_runs=1)

    return steps, workload


def _three_null_families_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    steps.extend(
        _null_family_steps(ctx.research_common, ctx.split, ctx.seeds, ctx.config, ctx.window)
    )
    ctx.governance.update(
        {
            "aggregation": "no_majority_vote",
            "headline": (
                "bootstrap Tier-1 paired with full-engine Tier-2 and bar-permutation Tier-3"
            ),
            "sensitivities": ["student_t Tier-1", "garch Tier-1"],
            "sensitivity_tier2_execution": (
                "the canonical validate command currently repeats full-engine Tier-2 for "
                "Student-t and GARCH; those repeated checks are recorded but are non-governing"
            ),
        }
    )
    workload = _workload(ctx.action, commands=3, canonical_runs=3)

    return steps, workload


def _monte_carlo_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    source = _latest_run_for_command(
        ctx.project,
        ctx.experiment_id,
        ("robustness",),
        data_dir=ctx.data_dir,
        commands=frozenset({"validate"}),
        states=frozenset({"pass", "warning", "fail"}),
        null_model="bootstrap",
    )
    evaluation_source = _latest_run_for_command(
        ctx.project,
        ctx.experiment_id,
        ("kronos",),
        data_dir=ctx.data_dir,
        commands=frozenset({"forecast_eval"}),
    )
    if source is None:
        ctx.blockers.append("Monte Carlo requires the completed bootstrap validation run")
        source_run = "<bootstrap-validation-required>"
        source_manifest: dict[str, object] = {}
    else:
        source_run, source_manifest = source
        metadata = source_manifest.get("metadata")
        null_model = metadata.get("null_model") if isinstance(metadata, Mapping) else None
        if null_model != "bootstrap":
            ctx.blockers.append("Monte Carlo source must be the stationary-bootstrap headline run")
    if evaluation_source is None:
        ctx.blockers.append("Monte Carlo requires a matching Kronos rolling-origin evaluation")
        evaluation_run = "<forecast-evaluation-required>"
        evaluation_manifest: dict[str, object] = {}
    else:
        evaluation_run, evaluation_manifest = evaluation_source

    classical_args = (
        "monte-carlo",
        "classical",
        "--from-run",
        source_run,
        "--paths",
        str(_stage_int(ctx.config, "monte_carlo_paths", 10_000, minimum=1, maximum=1_000_000)),
        "--regime-window",
        str(_stage_int(ctx.config, "monte_carlo_regime_window", 63, minimum=2, maximum=2_000)),
        "--min-state-observations",
        str(
            _stage_int(
                ctx.config, "monte_carlo_min_state_observations", 20, minimum=1, maximum=100_000
            )
        ),
        "--min-state-transitions",
        str(
            _stage_int(
                ctx.config, "monte_carlo_min_state_transitions", 10, minimum=1, maximum=100_000
            )
        ),
        "--seed",
        str(_seed(ctx.seeds)),
    )
    steps.append(
        SuiteStep(
            "Classical Monte Carlo families",
            classical_args,
            classical_args,
            "iid_regime_student_t_no_majority_vote",
        )
    )

    eval_model = evaluation_manifest.get("model")
    eval_params = evaluation_manifest.get("params")
    model_block = eval_model if isinstance(eval_model, Mapping) else {}
    params_block = eval_params if isinstance(eval_params, Mapping) else {}
    model_id = str(model_block.get("model_id", "fake"))
    context_bars = int(params_block.get("context", 512))
    kronos_args: list[str] = [
        "monte-carlo",
        "kronos",
        "--from-run",
        source_run,
        "--forecast-eval-run",
        evaluation_run,
        "--paths",
        str(_stage_int(ctx.config, "kronos_monte_carlo_paths", 128, minimum=1, maximum=10_000)),
        "--context",
        str(context_bars),
        "--model",
        model_id,
        "--seed",
        str(_seed(ctx.seeds)),
    ]
    for field, flag in (
        ("model_revision", "--model-revision"),
        ("tokenizer_id", "--tokenizer"),
        ("tokenizer_revision", "--tokenizer-revision"),
        ("device", "--device"),
    ):
        value = model_block.get(field)
        if isinstance(value, str) and value:
            kronos_args.extend((flag, value))
    steps.append(
        SuiteStep(
            "Kronos synthetic-OHLCV full-engine replay",
            tuple(kronos_args),
            tuple(kronos_args),
            "standalone_model_path_no_observed_signal_replay",
        )
    )
    ctx.governance.update(
        {
            "aggregation": "no_majority_vote",
            "warning_authority": "trusted_local_owner_cli_only",
            "warning_decisions": ["continue", "revise", "reject"],
            "kronos_role": "calibrated_stochastic_generator_not_market_oracle",
        }
    )
    workload = _workload(ctx.action, commands=2, canonical_runs=2)

    return steps, workload


def _optimize_grid_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    step, combinations = _grid_steps(
        primary=ctx.primary,
        strategy=ctx.strategy,
        snapshot=ctx.snapshot,
        costs=ctx.costs,
        definition=ctx.definition,
        parameter_space=ctx.parameter_space,
        split=ctx.split,
        seeds=ctx.seeds,
        config=ctx.config,
        research_cutoff=ctx.window.cutoff,
        cutoff_marker=ctx.window.public_cutoff,
        gate_overridden=ctx.gate_overridden,
    )
    steps.append(step)
    workload = _workload(ctx.action, commands=1, canonical_runs=1, grid_configurations=combinations)

    return steps, workload


def _fixed_stress_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    fixed_source_run = _latest_run(ctx.project, ctx.experiment_id, ("oos", "baseline"))
    if fixed_source_run is None:
        ctx.blockers.append("fixed stress requires a cited baseline or OOS run")
        fixed_source_run = "<required-run>"
    args = ("risk", "scenario", "--from-run", fixed_source_run, "--json")
    steps.append(SuiteStep("Fixed stress scenarios", args, args, "scenario_sensitivity"))
    ctx.governance["separate_from_nulls"] = True
    workload = _workload(ctx.action, commands=1, canonical_runs=0)

    return steps, workload


def _portfolio_cross_asset_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    if len(ctx.universe) < 2:
        ctx.blockers.append("portfolio/cross-asset analysis requires at least two frozen symbols")
    base = [
        *ctx.universe,
        "--strategy",
        ctx.strategy,
        "--snapshot",
        ctx.snapshot,
        "--fee-bps",
        _float_text(_number(ctx.costs.get("fee_bps", 1.0), "fee_bps", minimum=0.0)),
        "--slippage-bps",
        _float_text(_number(ctx.costs.get("slippage_bps", 2.0), "slippage_bps", minimum=0.0)),
        *_definition_options(ctx.definition),
        *_strategy_options(ctx.strategy, ctx.definition),
        *_split_options(ctx.split),
        "--seed",
        str(_seed(ctx.seeds)),
        "--as-of",
        ctx.window.cutoff,
        *(["--research-gate-override"] if ctx.gate_overridden else []),
    ]
    weighting = ctx.config.get("portfolio_weighting", "equal")
    if weighting not in {"equal", "inverse_vol"}:
        raise DataError("portfolio_weighting must be equal or inverse_vol")
    portfolio_args = ("backtest", "portfolio", *base, "--weighting", str(weighting))
    cross_args = ("backtest", "cross-sectional", *base)
    steps.extend(
        [
            ctx.window.step("Portfolio OOS analysis", portfolio_args, "portfolio_allocation"),
            ctx.window.step("Cross-asset OOS analysis", cross_args, "cross_asset_association"),
        ]
    )
    workload = _workload(ctx.action, commands=2, canonical_runs=2)

    return steps, workload


def _qlib_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    if len(ctx.universe) < 20:
        ctx.blockers.append("Qlib starter requires at least 20 frozen symbols")
    managed_id = _managed_qlib_id(ctx.experiment_id)
    ml_root = ctx.data_dir / "control" / "ml"
    input_bundle = ml_root / "inputs" / managed_id
    exchange = ml_root / "exchanges" / managed_id
    worker_lock = Path(__file__).resolve().parents[4] / "workers" / "qlib" / "uv.lock"
    if input_bundle.exists() or exchange.exists():
        ctx.blockers.append(
            "managed Qlib resources already exist for this immutable experiment; "
            "inspect the existing ML experiment or create a new ExperimentSpec"
        )
    if worker_lock.is_symlink() or not worker_lock.is_file():
        ctx.blockers.append("isolated Qlib worker lock is unavailable")
    input_marker = f"<managed-input:{managed_id}>"
    exchange_marker = f"<managed-exchange:{managed_id}>"
    lock_marker = "<isolated-worker-lock>"
    redactions = (
        (str(input_bundle), input_marker),
        (str(exchange), exchange_marker),
        (str(worker_lock), lock_marker),
        (ctx.window.cutoff, ctx.window.public_cutoff),
    )
    export = (
        "ml",
        "export-input",
        ctx.project_id,
        ctx.experiment_id,
        str(input_bundle),
        "--as-of",
        ctx.window.cutoff,
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
    replay = ("ml", "replay", str(exchange), "--as-of", ctx.window.cutoff, "--json")
    steps.extend(
        [
            SuiteStep(
                "Generate immutable Qlib input",
                export,
                (
                    "ml",
                    "export-input",
                    ctx.project_id,
                    ctx.experiment_id,
                    input_marker,
                    "--as-of",
                    ctx.window.public_cutoff,
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
                ("ml", "replay", exchange_marker, "--as-of", ctx.window.public_cutoff, "--json"),
                "oos_replay_model_not_recomputed_under_counterfactual",
                redactions,
            ),
        ]
    )
    ctx.governance.update(
        {
            "isolated_worker": True,
            "counterfactual_refit": False,
            "promotion_eligible": False,
            "managed_resource_id": managed_id,
            "minimum_aligned_sessions": 756,
            "minimum_aligned_sessions_enforced_by": "immutable input export",
        }
    )
    workload = _workload(ctx.action, commands=4, canonical_runs=1)

    return steps, workload


def _kronos_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    model = ctx.config.get("kronos_model")
    model_args: list[str] = []
    if model is None:
        ctx.blockers.append("Kronos requires a pinned model id in the immutable experiment")
    elif not isinstance(model, str) or _SAFE_MODEL.fullmatch(model) is None:
        raise DataError("kronos_model must be 'fake' or a managed repository id")
    else:
        model_args = ["--model", model]
    if isinstance(model, str) and model != "fake" and "kronos_model_revision" not in ctx.config:
        ctx.blockers.append("Kronos repository models require a pinned model revision")
    for key, flag in (
        ("kronos_model_revision", "--model-revision"),
        ("kronos_tokenizer_revision", "--tokenizer-revision"),
    ):
        value = ctx.config.get(key)
        if value is not None:
            if not isinstance(value, str) or _SAFE_REVISION.fullmatch(value) is None:
                raise DataError(f"{key} must be a safe immutable revision id")
            model_args.extend([flag, value])
    tokenizer = ctx.config.get("kronos_tokenizer")
    if tokenizer is not None:
        if not isinstance(tokenizer, str) or _SAFE_MODEL.fullmatch(tokenizer) is None:
            raise DataError("kronos_tokenizer must be a managed repository id")
        model_args.extend(["--tokenizer", tokenizer])
    device = ctx.config.get("kronos_device", "cpu")
    if device not in {"cpu", "mps", "cuda"}:
        raise DataError("kronos_device must be cpu, mps, or cuda")
    model_args.extend(["--device", str(device)])
    horizon = _stage_int(ctx.config, "kronos_horizon", 21, minimum=1, maximum=512)
    samples = _stage_int(ctx.config, "kronos_samples", 100, minimum=1, maximum=1000)
    eval_samples = _stage_int(ctx.config, "kronos_eval_samples", 30, minimum=1, maximum=200)
    context = _stage_int(ctx.config, "kronos_context", 400, minimum=2, maximum=100_000)
    stride = _stage_int(ctx.config, "kronos_stride", 21, minimum=1, maximum=10_000)
    temperature = _stage_float(ctx.config, "kronos_temperature", 1.0, minimum=0.0, maximum=10.0)
    top_p = _stage_float(ctx.config, "kronos_top_p", 0.9, minimum=0.0, maximum=1.0)
    top_k = _stage_int(ctx.config, "kronos_top_k", 0, minimum=0, maximum=1_000_000)
    forecast = (
        "forecast",
        "run",
        ctx.primary,
        "--snapshot",
        ctx.snapshot,
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
        str(_seed(ctx.seeds)),
        "--as-of",
        ctx.window.cutoff,
        *model_args,
    )
    evaluate = (
        "forecast",
        "eval",
        ctx.primary,
        "--snapshot",
        ctx.snapshot,
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
        str(_seed(ctx.seeds)),
        "--as-of",
        ctx.window.cutoff,
        *model_args,
    )
    steps.extend(
        [
            ctx.window.step("Kronos forecast cone", forecast, "forecast_samples"),
            ctx.window.step("Kronos rolling evaluation", evaluate, "rolling_evaluation"),
        ]
    )
    ctx.governance["pretraining_overlap_warning_permanent"] = True
    workload = _workload(ctx.action, commands=2, canonical_runs=2)

    return steps, workload


def _holdout_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    if ctx.holdout is None:
        ctx.blockers.append("final holdout must be sealed before owner reveal")
    elif ctx.holdout.get("revealed_at") is not None and not ctx.resume_reveal:
        ctx.blockers.append("final holdout was already revealed")
    elif ctx.holdout.get("contaminated_at") is not None:
        ctx.blockers.append("final holdout is contaminated for this lineage")
    sealed_spec = ctx.store.get_holdout_spec(ctx.project_id, ctx.experiment_id)
    if sealed_spec is None:
        ctx.blockers.append("final holdout must include a sealed evaluation window")
    preview = (
        "project",
        "reveal-holdout",
        ctx.project_id,
        ctx.experiment_id,
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
            ctx.config, "holdout_min_sharpe", 0.0, minimum=-100.0, maximum=100.0
        )
        evaluation = (
            "backtest",
            "holdout",
            *ctx.common,
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
            *ctx.common,
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
    ctx.governance.update(
        {
            "owner_only": True,
            "available_to_mcp": False,
            "one_shot": True,
            "resume_same_job_after_interruption": ctx.resume_reveal,
            "sealed_window_redacted_until_reveal": True,
        }
    )
    workload = _workload(ctx.action, commands=2, canonical_runs=1)

    return steps, workload


def _paper_preflight_steps(ctx: _PlanContext) -> tuple[list[SuiteStep], dict[str, object]]:
    steps: list[SuiteStep] = []
    paper_symbol_raw = ctx.config.get("paper_symbol")
    paper_symbol = (
        str(paper_symbol_raw)
        if paper_symbol_raw is not None
        else next((symbol for symbol in ctx.universe if "/" in symbol), "")
    )
    if paper_symbol not in ctx.universe or "/" not in paper_symbol:
        ctx.blockers.append("paper preflight requires a frozen BASE/QUOTE symbol")
        paper_symbol = "<required-base/quote>"
    paper_args = ["paper", "preflight", paper_symbol, "--strategy", ctx.strategy]
    if "starting_cash" in ctx.definition:
        paper_args.extend(
            [
                "--starting-cash",
                _float_text(_number(ctx.definition["starting_cash"], "starting_cash", minimum=1.0)),
            ]
        )
    paper_args.extend(_strategy_options(ctx.strategy, ctx.definition))
    steps.append(
        SuiteStep(
            "Sandbox paper preflight",
            tuple(paper_args),
            tuple(paper_args),
            "sandbox_preflight_only",
        )
    )
    ctx.governance.update({"sandbox": True, "places_orders": False, "owner_only_launch": True})
    workload = _workload(ctx.action, commands=1, canonical_runs=0)

    return steps, workload
