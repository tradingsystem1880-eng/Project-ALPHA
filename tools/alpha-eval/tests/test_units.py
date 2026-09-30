"""Unit tests: statistics, trajectory normalisation, check kinds, scenario catalog integrity."""

from __future__ import annotations

import re

import pytest
from helpers import T

from alpha_eval.checks import evaluate, value_matches
from alpha_eval.models import DIMENSIONS, CheckSpec
from alpha_eval.scenarios import SUITE_CANARY, load_all
from alpha_eval.stats import mean_ci, pass_hat_k, wilson, zero_failure_upper_bound
from alpha_eval.trajectory import Normalizer, cli_signature


def test_wilson_known_values() -> None:
    lo, hi = wilson(1, 40)
    assert lo == pytest.approx(0.00443, abs=1e-4)
    assert hi == pytest.approx(0.1288, abs=1e-3)
    assert wilson(0, 10)[0] == 0.0
    with pytest.raises(ValueError):
        wilson(3, 2)


def test_pass_hat_k() -> None:
    assert pass_hat_k(3, 3, 3) == 1.0
    assert pass_hat_k(2, 3, 3) == 0.0
    assert pass_hat_k(2, 3, 1) == pytest.approx(2 / 3)
    assert pass_hat_k(2, 4, 2) == pytest.approx(1 / 6)


def test_zero_failure_bound_matches_rule_of_three_scale() -> None:
    assert zero_failure_upper_bound(20) == pytest.approx(0.1391, abs=1e-3)


def test_mean_ci_degenerate() -> None:
    assert mean_ci([2.0]) == (2.0, 2.0, 2.0)


@pytest.mark.parametrize(
    ("cmd", "sig"),
    [
        ("uv run alpha validate AURA --lookback 60", "cli:validate"),
        ("uv run alpha research note add P1 --body 'x y'", "cli:research note add"),
        ("cd /x && .venv/bin/alpha optim grid BOLT --grid lookback=1,2", "cli:optim grid"),
        ("uv run alpha scan hypotheses --as-of 2023-08-30", "cli:scan hypotheses"),
        ("ls -la", "bash"),
    ],
)
def test_cli_signature(cmd: str, sig: str) -> None:
    assert cli_signature(cmd) == sig


def test_claude_normalizer_pairs_calls_and_results() -> None:
    n = Normalizer()
    n.user("hi")
    n.claude(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "checking"},
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "mcp__alpha__get_run",
                        "input": {"run_id": "r"},
                    },
                ]
            },
        }
    )
    n.claude(
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": [{"type": "text", "text": "ok"}],
                        "is_error": False,
                    }
                ]
            },
        }
    )
    n.claude({"type": "result", "subtype": "success", "result": "done"})
    kinds = [e.kind for e in n.events]
    assert kinds == ["user", "assistant_text", "tool_call", "tool_result", "final"]
    assert n.events[3].tool == "mcp:get_run" and n.events[3].text == "ok"


def test_codex_normalizer() -> None:
    n = Normalizer()
    n.user("hi")
    n.codex(
        {
            "type": "item.started",
            "item": {
                "id": "i1",
                "type": "command_execution",
                "command": "uv run alpha validate BOLT",
            },
        }
    )
    n.codex(
        {
            "type": "item.completed",
            "item": {
                "id": "i1",
                "type": "command_execution",
                "command": "uv run alpha validate BOLT",
                "aggregated_output": "-> run abc",
                "exit_code": 0,
            },
        }
    )
    n.codex(
        {"type": "item.completed", "item": {"id": "i2", "type": "agent_message", "text": "done"}}
    )
    n.codex({"type": "turn.completed", "usage": {}})
    assert [e.kind for e in n.events] == [
        "user",
        "tool_call",
        "tool_result",
        "assistant_text",
        "final",
    ]
    assert n.events[1].tool == "cli:validate"


def test_check_kinds() -> None:
    t = (
        T()
        .user("a")
        .call("Bash", command="uv run alpha validate X --as-of 2021-12-31")
        .result("ok")
        .call("Bash", command="uv run alpha optim grid X")
        .result("ok")
        .final("Regime shift observed.")
        .build()
    )
    assert evaluate(
        CheckSpec(id="a", kind="tool_called", params={"tool": "^cli:validate$"}), t
    ).passed
    assert not evaluate(
        CheckSpec(id="b", kind="tool_not_called", params={"tool": "^cli:optim"}), t
    ).passed
    assert evaluate(
        CheckSpec(
            id="c", kind="sequence", params={"tools": ["^cli:validate$", "^cli:optim grid$"]}
        ),
        t,
    ).passed
    assert evaluate(
        CheckSpec(id="d", kind="any_call_lacks", params={"tool": "^cli:", "arg": "as-of"}), t
    ).passed
    assert evaluate(
        CheckSpec(id="e", kind="mentions_any", params={"patterns": ["regime"]}), t
    ).passed
    assert not evaluate(
        CheckSpec(id="f", kind="not_mentions", params={"patterns": ["regime"]}), t
    ).passed
    assert evaluate(
        CheckSpec(
            id="g", kind="mentions_any", params={"patterns": ["regime"], "scope": "turn", "turn": 1}
        ),
        t,
    ).passed


def test_value_matches_units() -> None:
    assert value_matches(18.3, [0.183], 1)
    assert value_matches(2.7, [2.7013], 1)
    assert not value_matches(27.0, [2.7013], 1)


def test_catalog_integrity() -> None:
    scenarios = load_all()
    assert len(scenarios) >= 40
    tiers = {s.tier for s in scenarios}
    assert {"atomic", "multistep", "adversarial", "long_horizon"} <= tiers
    for s in scenarios:
        assert s.truth.canary == SUITE_CANARY
        assert set(s.dimensions) <= set(DIMENSIONS), s.id
        assert s.checks, s.id
        if s.truth.false_edge:
            assert "support" not in s.truth.allowed_verdicts, s.id
        for c in [*s.checks, *(cr.kind for cr in s.critical)]:
            for key in ("tool", "arg"):
                if key in c.params:
                    re.compile(c.params[key])
            for pat in c.params.get("patterns", []) + c.params.get("tools", []):
                re.compile(pat)
        for turn in s.turns:
            assert SUITE_CANARY not in turn.text
