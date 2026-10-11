"""Grounded teammate questions over existing runs; no jobs, model calls or authority."""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import polars as pl

from alpha_cli.research_execution_digest import execution_digest
from alpha_cli.research_workflow_contract import InvestigationProposal
from alpha_core import DataError
from alpha_validation.metrics import drawdown_episodes


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _resolve(observations: dict[str, Any], pointer: str) -> None:
    value: Any = {"observations": observations}
    try:
        if not pointer.startswith("/observations/"):
            raise ValueError("outside observations")
        for part in pointer[1:].split("/"):
            if re.search(r"~(?![01])", part):
                raise ValueError("invalid escape")
            key = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                if re.fullmatch(r"0|[1-9][0-9]*", key) is None:
                    raise ValueError("invalid array index")
                value = value[int(key)]
            else:
                value = value[key]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise DataError(f"unresolved evidence pointer: {pointer}") from exc


def suggest_investigations(
    directory: Path,
    *,
    cutoff: str,
    proposals: tuple[InvestigationProposal, ...] = (),
    basis_sha256: str | None = None,
) -> dict[str, Any]:
    """Measure existing equity episodes and propose next tests, without running those tests.

    The whole declared run is already observed retrospective evidence. No pristine confirmation
    or agent-wide read boundary follows from this projection. External text is untrusted advice.
    """
    digest = execution_digest(directory, cutoff=cutoff)
    raw = (directory / "equity_curve.parquet").read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest["evidence"]["equity_curve"]["sha256"]:
        raise DataError("equity evidence changed during suggestion preparation")
    equity = pl.read_parquet(io.BytesIO(raw))
    dates = equity["ts"].to_list()
    episodes = [
        dict(
            peak=dates[e.peak_index].isoformat(),
            trough=dates[e.trough_index].isoformat(),
            recovery=dates[e.recovery_index].isoformat() if e.recovery_index is not None else None,
            depth=e.depth,
            peak_to_trough_intervals=e.length,
        )
        for e in drawdown_episodes(equity["equity"].to_list(), top=3)
    ]
    observations = dict(
        execution=digest,
        drawdown_episodes=episodes,
        regime_effect="not_tested",
        macro_cause="not_tested",
    )
    basis = _hash(
        dict(
            observations=observations,
            policy_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        )
    )
    if len(proposals) > 3 or (proposals and basis_sha256 != basis):
        raise DataError("external proposals require matching basis and at most three proposals")
    suggestions = _questions(observations)
    for index, proposal in enumerate(proposals):
        # Revalidate even programmatic callers that used model_copy/model_construct.
        proposal = InvestigationProposal.model_validate(proposal.model_dump())
        for pointer in proposal.evidence_pointers:
            _resolve(observations, pointer)
        suggestions.append(
            dict(
                id=f"external-{index + 1}",
                priority="proposed_extension",
                origin="external_proposal",
                claim_verification="binding_only",
                **proposal.model_dump(mode="json"),
            )
        )
    return dict(
        schema_version=1,
        advisory_only=True,
        admitted=False,
        execution_status="proposed",
        mode="retrospective_advice",
        strategy_disposition="not_assessed",
        basis_sha256=basis,
        observations=observations,
        suggestions=suggestions,
        executed_experiments=[],
        information_boundary="agent_read_isolation_not_established",
        confirmation_warning="This run has been inspected; a new context cannot make it untouched.",
        teammate_guidance=(
            "These questions are a minimum starting point, not an exhaustive research agenda. "
            "Suggest up to three more useful, falsifiable investigations when evidence justifies "
            "them. Explain why now, competing explanations, data needed and what would change "
            "the decision. Distinguish observations from hypotheses. A justified skip is useful. "
            "Proposals are not authorization, completed tests or proof of a cause."
        ),
    )


def _questions(observations: dict[str, Any]) -> list[dict[str, Any]]:
    digest = observations["execution"]
    result: list[dict[str, Any]] = []

    def add(key: str, priority: str, pointer: str, **fields: Any) -> None:
        proposal = InvestigationProposal(evidence_pointers=(pointer,), **fields)
        _resolve(observations, pointer)
        result.append(
            dict(
                id=key,
                priority=priority,
                origin="deterministic_prompt",
                claim_verification="question_not_finding",
                **proposal.model_dump(mode="json"),
            )
        )

    if digest["sessions"]["expectation_source"] != "snapshot_schedule":
        add(
            "coverage",
            "integrity",
            "/observations/execution/sessions",
            question="Did the engine complete every intended session?",
            rationale="Artifact consistency alone does not establish the expected source schedule.",
            competing_explanation="A short result may reflect the requested window or incomplete "
            "execution.",
            test="Reconcile equity timestamps against the frozen snapshot and "
            "intended evaluation folds.",
            data_needed=("Verified snapshot schedule and evaluation window",),
            decision_value="Determines whether performance interpretation is valid.",
            stop_condition="Stop performance interpretation if execution coverage cannot be "
            "reconciled.",
        )
    if digest["denied_or_rejected_orders"]:
        add(
            "rejected_requests",
            "integrity",
            "/observations/execution/denied_or_rejected_orders",
            question="Did rejected requests change the intended strategy exposure?",
            rationale="The verified run contains denied or rejected requests, including "
            "pretrade checks.",
            competing_explanation="Cash, fees, quantity limits or another venue constraint may "
            "differ.",
            test="Inspect rejection evidence and align each request with positions "
            "and sizing assumptions.",
            data_needed=("Rejection details and position/exposure history",),
            decision_value="Separates strategy economics from implementation constraints.",
            stop_condition="Do not invent rejection causes where the sidecars lack them.",
        )
    if not digest["fill_events"] or not digest["closed_trades"]:
        add(
            "activity",
            "diagnostic",
            "/observations/execution/closed_trades",
            question="Did the strategy generate enough completed exposure to assess its thesis?",
            rationale="No fills or no closed trades were recorded; open exposure can "
            "still affect equity.",
            competing_explanation="Warmup, restrictive rules, open holdings or failed execution "
            "may explain this.",
            test="Inspect signal opportunities, fills and terminal positions "
            "before interpreting returns.",
            data_needed=("Signal timeline and terminal position evidence",),
            decision_value="Distinguishes missing evidence from evidence against the strategy.",
            stop_condition="Keep sample adequacy unresolved when position/opportunity "
            "evidence is absent.",
        )
    if observations["drawdown_episodes"]:
        add(
            "loss_episode",
            "diagnostic",
            "/observations/drawdown_episodes/0",
            question="What explains the deepest loss episode, and is there a testable "
            "conditional effect?",
            rationale="An observed drawdown merits decomposition; its size alone does "
            "not identify the cause.",
            competing_explanation="Market beta, sizing, costs, asset-specific events, data defects "
            "or noise.",
            test="Compare episode exposure and costs with aligned asset, benchmark "
            "and peer returns; then "
            "test a simple decision-time regime hypothesis only if the evidence warrants it.",
            data_needed=(
                "Aligned benchmark/peer returns",
                "Positions and costs",
                "Dated event/release sources",
            ),
            decision_value="Determines whether a new bounded regime or risk experiment is "
            "informative.",
            stop_condition="Preserve original losses; no causal attribution from coincident "
            "news or "
            "claim of a validated filter from this inspected window.",
        )
    if digest["fill_events"] and digest["closed_trades"]:
        add(
            "robustness",
            "diagnostic",
            "/observations/execution",
            question="Does the measured behaviour survive costs, time and comparable assets?",
            rationale="A completed run or validation verdict does not establish the "
            "mechanism or generality.",
            competing_explanation="Sample noise, common market exposure, selection or execution "
            "costs.",
            test="Propose a frozen sensitivity/transfer family with simple "
            "baselines and dependence-aware "
            "uncertainty; inspect all prior attempted variants before choosing it.",
            data_needed=(
                "Complete search ledger",
                "Comparable PIT asset data",
                "Execution cost assumptions",
            ),
            decision_value="Identifies whether further research is justified and what could "
            "falsify the claim.",
            stop_condition="Do not treat correlated coins as independent replication or "
            "reuse observed confirmation.",
        )
    return result
