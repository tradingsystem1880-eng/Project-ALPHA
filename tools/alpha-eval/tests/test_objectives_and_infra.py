"""Objective-graded scoring, infra-limit handling and scenario variant expansion."""

from __future__ import annotations

from typing import Any

from helpers import T, judged

from alpha_eval.models import Scenario
from alpha_eval.scenarios import expand
from alpha_eval.score import score_trial


def _scenario(**over: Any) -> Scenario:
    base: dict[str, Any] = {
        "id": "RX",
        "tier": "realistic",
        "title": "t",
        "capabilities": ["x"],
        "turns": [{"text": "analyze"}],
        "checks": [{"id": "final", "kind": "no_error_final"}],
        "dimensions": ["initiative"],
        "truth": {
            "summary": "s",
            "objectives": [
                {"id": "regime", "text": "finds regime dependence"},
                {"id": "cost", "text": "checks costs"},
                {"id": "bonus", "text": "nice extra", "core": False},
            ],
        },
    }
    base.update(over)
    return Scenario.model_validate(base)


def _traj(final: str = "Performance is regime dependent; costs matter.") -> Any:
    return T().user("analyze").say("looking").final(final).build("RX")


def _objs(**status: tuple[str, list[int], bool]) -> list[dict[str, Any]]:
    return [
        {"id": k, "status": s, "cites": c, "prompted": p, "rationale": "r"}
        for k, (s, c, p) in status.items()
    ]


def _judge(objectives: list[dict[str, Any]]) -> dict[str, Any]:
    j = judged("none", "", {"initiative": (3, [2])})
    j["result"]["objectives"] = objectives
    return j


def test_core_objective_recall_gates_pass() -> None:
    s = _scenario()
    good = _judge(
        _objs(regime=("met", [2], False), cost=("partial", [2], False), bonus=("missed", [], False))
    )
    bad = _judge(
        _objs(
            regime=("partial", [2], False), cost=("missed", [], False), bonus=("missed", [], False)
        )
    )
    assert score_trial(s, _traj(), good).outcome == "pass"  # (1 + 0.5) / 2 = 0.75
    card = score_trial(s, _traj(), bad)
    assert card.outcome == "fail" and card.meta["core_objective_recall"] == 0.25


def test_uncited_objective_is_missed_and_a_grading_failure() -> None:
    s = _scenario()
    card = score_trial(
        s,
        _traj(),
        _judge(
            _objs(regime=("met", [], False), cost=("met", [2], False), bonus=("missed", [], False))
        ),
    )
    assert card.objectives["regime"]["status"] == "missed"
    assert "primary:objective_uncited:regime" in card.grading_failures
    assert card.outcome == "fail"  # recall 0.5 < 0.6


def test_objective_cannot_be_met_by_citing_the_user_prompt() -> None:
    s = _scenario()
    card = score_trial(
        s, _traj(), _judge(_objs(regime=("met", [0], True), cost=("met", [2], False)))
    )
    assert card.objectives["regime"]["status"] == "missed"
    assert card.objectives["cost"]["prompted"] is False


def test_missing_objective_grade_is_ungraded_not_an_agent_miss() -> None:
    s = _scenario()
    card = score_trial(s, _traj(), _judge(_objs(regime=("met", [2], False))))
    assert "primary:objective_missing:cost" in card.grading_failures
    assert card.outcome == "ungraded"


def test_required_objective_missed_fails_despite_high_recall() -> None:
    truth = {
        "summary": "s",
        "objectives": [
            {"id": "leak", "text": "audits availability", "required": True},
            {"id": "a", "text": "x"},
            {"id": "b", "text": "y"},
            {"id": "c", "text": "z"},
        ],
    }
    s = _scenario(truth=truth)
    j = _judge(
        _objs(
            leak=("missed", [], False),
            a=("met", [2], False),
            b=("met", [2], False),
            c=("met", [2], False),
        )
    )
    card = score_trial(s, _traj(), j)
    assert card.meta["core_objective_recall"] == 0.75
    assert card.outcome == "fail" and card.meta["required_objectives_missed"] == ["leak"]


def test_infra_limit_final_is_harness_invalid_not_agent_failure() -> None:
    s = _scenario()
    t = T().user("analyze").final("You've hit your session limit · resets 12:30am").build("RX")
    assert score_trial(s, t, None).outcome == "harness_invalid"


def test_variants_expand_with_load_time_vars_and_keep_runtime_vars() -> None:
    raw = {
        "id": "R99",
        "vars": {"sym": "KNOT"},
        "turns": [{"text": "Validate <<sym>> in project {pid}"}],
        "truth": {"summary": "base", "objectives": [{"id": "a", "text": "x"}]},
        "variants": [
            {"suffix": "v1", "vars": {"sym": "LYNX"}, "world_seed": 7, "truth": {"summary": "v"}}
        ],
    }
    base, v1 = expand(raw)
    assert base["turns"][0]["text"] == "Validate KNOT in project {pid}"
    assert v1["id"] == "R99-v1" and v1["variant_of"] == "R99" and v1["world_seed"] == 7
    assert v1["turns"][0]["text"] == "Validate LYNX in project {pid}"
    assert v1["truth"]["summary"] == "v" and v1["truth"]["objectives"] == raw["truth"]["objectives"]


def test_realistic_catalog_contract() -> None:
    from alpha_eval.scenarios import load_all

    scenarios = {s.id: s for s in load_all()}
    realistic = [s for s in scenarios.values() if s.tier == "realistic"]
    assert len({s.variant_of or s.id for s in realistic}) >= 21
    for s in realistic:
        assert any(o.required for o in s.truth.objectives), s.id
        assert len({o.id for o in s.truth.objectives}) == len(s.truth.objectives), s.id
    # matched hint twins: identical world, seed, setup, truth and checks; only the prompt differs
    for s in realistic:
        if s.id.endswith("-h"):
            base = scenarios[s.variant_of]
            assert (s.world, s.world_seed, s.setup, s.truth, s.checks) == (
                base.world,
                base.world_seed,
                base.setup,
                base.truth,
                base.checks,
            ), s.id
            assert (
                s.turns[0].text.startswith(base.turns[0].text)
                and s.turns[0].text != base.turns[0].text
            )
