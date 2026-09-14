"""The SPA's overlay vocabulary must be exactly the CLI's (neurotrader888 port, stream E).

``chartOverlaysModel.ts`` mirrors ``alpha_cli.chart_cmds`` so a typo fails in the dialog rather
than as a 400 and so every pattern the CLI can draw is offered; a head added on one side only
would either dead-end a preset or hide an indicator. The tables are pinned here the way
``test_web_owner_actions_drift.py`` pins the owner-action union.
"""

from __future__ import annotations

import re
from pathlib import Path

from alpha_cli.chart_cmds import INDICATORS, PATTERNS, parse_indicator
from alpha_strategies.rules import INDICATOR_ARITY, INDICATOR_FIELDS, parse_operand

_FRONTEND = Path(__file__).resolve().parents[2] / "apps" / "alpha-web" / "frontend" / "src"
_MODEL = (_FRONTEND / "panels" / "chartOverlaysModel.ts").read_text(encoding="utf-8")
_BUILDER = (_FRONTEND / "panels" / "ruleBuilderModel.ts").read_text(encoding="utf-8")


def _ts_block(source: str, name: str) -> str:
    start = source.index(name)
    return source[start : source.index("\n})", start)]


def _ts_arity(source: str) -> dict[str, int]:
    return {
        head: int(n)
        for head, n in re.findall(
            r"^\s+([a-z_0-9]+): (\d+),$", _ts_block(source, "export const ARITY"), re.M
        )
    }


def _ts_fields(source: str) -> dict[str, tuple[str, ...]]:
    return {
        head: tuple(re.findall(r"'([a-z]+)'", members))
        for head, members in re.findall(
            r"^\s+([a-z_0-9]+): \[(.*)\],$", _ts_block(source, "export const FIELDS"), re.M
        )
    }


def _ts_operand_examples() -> list[str]:
    start = _BUILDER.index("export const OPERAND_EXAMPLES")
    return re.findall(r"'([^']+)'", _BUILDER[start : _BUILDER.index("\n])", start)])


def _ts_patterns() -> list[str]:
    start = _MODEL.index("export const PATTERNS = [")
    return re.findall(r"'([a-z_]+)'", _MODEL[start : _MODEL.index("] as const", start)])


def _ts_presets() -> list[str]:
    start = _MODEL.index("export const INDICATOR_PRESETS")
    return re.findall(r"id: '([^']+)'", _MODEL[start : _MODEL.index("\n])", start)])


def test_spa_indicator_arity_matches_the_cli_table() -> None:
    spa = _ts_arity(_MODEL)
    assert spa, "no ARITY rows parsed from chartOverlaysModel.ts"
    assert spa == {name: arity for name, (arity, _label) in INDICATORS.items()}


def test_spa_pattern_list_matches_the_cli_list_in_order() -> None:
    assert _ts_patterns() == list(PATTERNS)


def test_every_spa_preset_is_a_spec_the_cli_accepts_and_covers_every_head() -> None:
    presets = _ts_presets()
    assert presets, "no INDICATOR_PRESETS parsed from chartOverlaysModel.ts"
    for preset in presets:
        assert parse_indicator(preset).id == preset
    assert {preset.split(":")[0] for preset in presets} == set(INDICATORS)


def test_rule_builder_tables_match_the_rules_parser() -> None:
    assert _ts_arity(_BUILDER) == dict(INDICATOR_ARITY)
    assert _ts_fields(_BUILDER) == dict(INDICATOR_FIELDS)
    # a rule operand reads exactly the series the chart draws, so the rule table is the chart
    # table minus the one indicator the strategy layer cannot compute
    assert set(INDICATORS) - set(INDICATOR_ARITY) == {"rsi_pc1"}


def test_every_rule_builder_example_is_an_operand_the_parser_accepts() -> None:
    examples = _ts_operand_examples()
    assert examples, "no OPERAND_EXAMPLES parsed from ruleBuilderModel.ts"
    heads: set[str] = set()
    for text in examples:
        if text in {"high", "low", "close"}:
            payload: dict[str, object] = {"source": text}
        elif re.fullmatch(r"-?\d+(\.\d+)?", text):
            payload = {"value": float(text)}
        else:
            head, *rest = text.split(":")
            params = [float(v) for v in rest[: INDICATOR_ARITY[head]]]
            payload = {"indicator": head, "params": params}
            if head in INDICATOR_FIELDS:
                payload["field"] = rest[-1]
            heads.add(head)
        assert parse_operand(payload, "example").label == text
    assert heads == set(INDICATOR_ARITY)
