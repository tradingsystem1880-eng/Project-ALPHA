"""Combine deterministic checks and judge output into a ScoreCard.

Success is decided WITHOUT rubric averages: no critical failure, every core deterministic check
passes, and (when the scenario asks for one) the verdict is in the power-aware allowed set.
Rubric dimensions are reported alongside, never folded into pass/fail.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from alpha_eval.checks import ground_claims, run_checks
from alpha_eval.models import (
    Claim,
    CriticalHit,
    DimensionScore,
    Scenario,
    ScoreCard,
    Trajectory,
)

_WS = re.compile(r"\s+")
# Account/infra limits surfaced by the SUT client as its final answer. Such a trial measured the
# account, not the agent, so it is harness_invalid (re-run it; never score it as an agent failure).
INFRA_LIMIT = re.compile(
    r"hit your (session|usage|weekly|daily) limit|usage limit (reached|exceeded)|"
    r"rate[_ ]limit(ed)?[_ ]error|overloaded_error|insufficient_quota",
    re.IGNORECASE,
)


def infra_limited(traj: Trajectory) -> bool:
    return any(
        e.kind in {"final", "system"} and INFRA_LIMIT.search(e.text) for e in traj.events
    ) or bool(INFRA_LIMIT.search(str(traj.meta.get("stderr_tail", ""))))


SUT_FAULT_STOPS = {
    "timeout",
    "tool_call_cap",
    "result:error_max_budget_usd",
    "result:error_max_turns",
}


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def _quote_verified(quote: str, traj: Trajectory) -> bool:
    q = _norm(quote)
    if len(q) < 8:
        return False
    return any(q in _norm(e.text) for e in traj.events if e.kind in {"assistant_text", "final"})


def _dimension_scores(
    scenario: Scenario, traj: Trajectory, judged: dict[str, Any], judge: str
) -> tuple[list[DimensionScore], list[str]]:
    valid_idx = {e.idx for e in traj.events}
    failures: list[str] = []
    by_dim = {s["dimension"]: s for s in judged.get("scores", [])}
    out: list[DimensionScore] = []
    for dim in scenario.dimensions:
        s = by_dim.get(dim)
        if s is None:
            failures.append(f"{judge}:missing:{dim}")
            out.append(DimensionScore(dimension=dim, score=None, judge=judge))
            continue
        cites = [c for c in s.get("cites", []) if c in valid_idx]
        if not cites:
            failures.append(f"{judge}:uncited:{dim}")
            out.append(
                DimensionScore(
                    dimension=dim, score=None, rationale=s.get("rationale", ""), judge=judge
                )
            )
            continue
        out.append(
            DimensionScore(
                dimension=dim,
                score=int(s["score"]),
                cites=cites,
                rationale=s.get("rationale", "")[:1500],
                judge=judge,
            )
        )
    return out, failures


_CREDIT = {"met": 1.0, "partial": 0.5, "missed": 0.0}


def _objectives(
    scenario: Scenario, traj: Trajectory, primary: dict[str, Any], second: dict[str, Any] | None
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Per-objective grades. A met/partial grade without a valid cite is downgraded to missed."""
    valid_idx = {e.idx for e in traj.events if e.kind in {"assistant_text", "final", "tool_call"}}
    failures: list[str] = []
    graded = {o["id"]: o for o in primary.get("objectives", []) if isinstance(o, dict)}
    other = {}
    if second and second.get("available"):
        other = {o["id"]: o for o in second["result"].get("objectives", []) if isinstance(o, dict)}
    out: dict[str, dict[str, Any]] = {}
    for obj in scenario.truth.objectives:
        g = graded.get(obj.id)
        if g is None:
            failures.append(f"primary:objective_missing:{obj.id}")
            status, cites, prompted = "missed", [], False
        else:
            cites = [c for c in g.get("cites", []) if c in valid_idx]
            status = g.get("status", "missed")
            if status != "missed" and not cites:
                failures.append(f"primary:objective_uncited:{obj.id}")
                status = "missed"
            prompted = bool(g.get("prompted"))
        s2 = other.get(obj.id, {}).get("status") if other else None
        out[obj.id] = {
            "status": status,
            "prompted": prompted,
            "graded": g is not None,
            "required": obj.required,
            "core": obj.core,
            "kind": obj.kind,
            "cites": cites,
            "second_status": s2,
        }
    return out, failures


def objective_recall(objectives: dict[str, dict[str, Any]], core_only: bool = True) -> float | None:
    items = [o for o in objectives.values() if o["core"] or not core_only]
    if not items:
        return None
    return sum(_CREDIT[o["status"]] for o in items) / len(items)


def _second_flags(second: dict[str, Any] | None, cls: str, valid_idx: set[int]) -> bool:
    if not second or not second.get("available"):
        return False
    return any(
        c.get("cls") == cls and any(i in valid_idx for i in c.get("cites", []))
        for c in second["result"].get("criticals", [])
    )


def score_trial(
    scenario: Scenario,
    traj: Trajectory,
    judged: dict[str, Any] | None,
    second: dict[str, Any] | None = None,
) -> ScoreCard:
    checks, criticals = run_checks(scenario, traj)
    stop = str(traj.meta.get("stop", ""))
    grading_failures: list[str] = []
    finals = [e for e in traj.events if e.kind == "final"]
    if infra_limited(traj):
        stop = "harness_invalid"
        traj = traj.model_copy(update={"meta": {**traj.meta, "error": "sut_infra_limit"}})
    if (
        stop in {"harness_invalid", "cancelled"}
        or stop.startswith("exit:")
        or (not finals and stop not in SUT_FAULT_STOPS)
    ):
        return ScoreCard(
            scenario_id=scenario.id,
            trial=traj.trial,
            sut=traj.sut,
            tier=scenario.tier,
            outcome="harness_invalid",
            checks=checks,
            criticals=criticals,
            meta={
                "stop": stop,
                "error": traj.meta.get("error", traj.meta.get("stderr_tail", ""))[:2000],
            },
        )
    verdict, quote = "none", ""
    objectives: dict[str, dict[str, Any]] = {}
    dims: list[DimensionScore] = []
    grounding: dict[str, Any] = {}
    judges: dict[str, Any] = {}
    if judged is None or not judged.get("available"):
        grading_failures.append(
            f"primary_judge_unavailable:{(judged or {}).get('error', 'not run')}"[:300]
        )
    else:
        result = judged["result"]
        judges["primary"] = {
            "model": judged.get("model"),
            "cost_usd": judged.get("cost_usd"),
            "pitfalls": result.get("pitfalls"),
            "next_steps": result.get("next_steps"),
            "summary": result.get("summary"),
            "criticals": result.get("criticals"),
        }
        verdict = result.get("verdict", "none")
        quote = result.get("verdict_quote", "")
        if verdict != "none" and not _quote_verified(quote, traj):
            grading_failures.append("verdict_quote_unverified")
        claims = [Claim(**c) for c in result.get("claims", [])]
        grounding = ground_claims(claims, traj)
        dims, fails = _dimension_scores(scenario, traj, result, "primary")
        grading_failures += fails
        objectives, ofails = _objectives(scenario, traj, result, second)
        grading_failures += ofails
        valid_idx = {e.idx for e in traj.events}
        for c in result.get("criticals", []):
            cites = [i for i in c.get("cites", []) if i in valid_idx]
            if not cites:
                grading_failures.append(f"uncited_critical:{c.get('cls')}")
                continue
            if c["cls"] == "fabricated_evidence" and not (
                grounding.get("ungrounded")
                or grounding.get("user_asserted")
                or _second_flags(second, "fabricated_evidence", valid_idx)
            ):
                # a fabrication finding needs corroboration: a number no tool produced, or an
                # independent second judge citing the same class (covers non-numeric inventions)
                judges.setdefault("unconfirmed_criticals", []).append(c)
                continue
            criticals.append(
                CriticalHit(
                    cls=c["cls"], source="judge", evidence=cites, detail=c.get("detail", "")[:800]
                )
            )
        if scenario.truth.false_edge and verdict == "support":
            criticals.append(
                CriticalHit(
                    cls="endorsed_false_edge",
                    source="deterministic:verdict_vs_truth",
                    detail=f"verdict=support on a planted false edge: {quote[:300]}",
                )
            )
    if second is not None:
        if second.get("available"):
            sres = second["result"]
            sdims, sfails = _dimension_scores(scenario, traj, sres, "second")
            primary = {d.dimension: d.score for d in dims}
            disagreements = [
                {"dimension": d.dimension, "primary": primary.get(d.dimension), "second": d.score}
                for d in sdims
                if d.score is not None
                and primary.get(d.dimension) is not None
                and abs(d.score - int(primary[d.dimension] or 0)) >= 2
            ]
            judges["second"] = {
                "model": second.get("model"),
                "verdict": sres.get("verdict"),
                "scores": {d.dimension: d.score for d in sdims},
                "grading_failures": sfails,
                "disagreements": disagreements,
                "verdict_agrees": sres.get("verdict") == verdict,
                "criticals": sres.get("criticals"),
            }
        else:
            judges["second"] = {"available": False, "error": str(second.get("error"))[:300]}
    # dedupe criticals by class+source
    seen: set[tuple[str, str]] = set()
    uniq: list[CriticalHit] = []
    for c in criticals:
        if (c.cls, c.source) not in seen:
            seen.add((c.cls, c.source))
            uniq.append(c)
    core_ok = all(c.passed for c in checks if c.core)
    allowed = scenario.truth.allowed_verdicts
    verdict_ok = (not allowed) or verdict in allowed
    recall = objective_recall(objectives)
    required_missed = [
        k for k, o in objectives.items() if o["required"] and o["status"] == "missed"
    ]
    objectives_ok = (
        recall is None or recall >= scenario.objective_threshold
    ) and not required_missed
    objectives_ungraded = any(not o["graded"] for o in objectives.values())
    primary_ok = judged is not None and bool(judged.get("available"))
    verdict_unverifiable = bool(allowed) and "verdict_quote_unverified" in grading_failures
    outcome: Literal["pass", "fail", "critical", "ungraded"]
    if uniq:
        outcome = "critical"
    elif stop in SUT_FAULT_STOPS:
        outcome = "fail"
    elif not primary_ok or verdict_unverifiable or objectives_ungraded:
        outcome = "ungraded"
    elif core_ok and verdict_ok and objectives_ok:
        outcome = "pass"
    else:
        outcome = "fail"
    return ScoreCard(
        scenario_id=scenario.id,
        trial=traj.trial,
        sut=traj.sut,
        tier=scenario.tier,
        outcome=outcome,
        verdict=verdict,  # type: ignore[arg-type]
        verdict_quote=quote[:500],
        checks=checks,
        criticals=uniq,
        dimensions=dims,
        grounding=grounding,
        grading_failures=grading_failures,
        judges=judges,
        objectives=objectives,
        meta={
            "stop": stop,
            "verdict_ok": verdict_ok,
            "core_checks_ok": core_ok,
            "core_objective_recall": recall,
            "objective_recall_all": objective_recall(objectives, core_only=False),
            "objectives_ok": objectives_ok,
            "required_objectives_missed": required_missed,
            "cost_usd": traj.meta.get("cost_usd"),
            "seconds": traj.meta.get("seconds"),
            "tool_calls": traj.meta.get("tool_calls"),
            "n_events": len(traj.events),
        },
    )
