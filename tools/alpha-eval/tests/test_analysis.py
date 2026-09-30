"""Analysis metrics on synthetic score cards: telegraph gap, discrimination flags, agreement."""

from __future__ import annotations

from typing import Any

from alpha_eval.analysis import analyze
from alpha_eval.scenarios import load_all

S = {s.id: s for s in load_all()}
STRONG, WEAK = "claude:claude-sonnet-5", "claude:claude-haiku-4-5-20251001"


def _card(
    sid: str, sut: str, trial: int, statuses: dict[str, str], second: str | None = None
) -> dict[str, Any]:
    objs = {
        o.id: {
            "status": statuses.get(o.id, "missed"),
            "prompted": False,
            "core": o.core,
            "kind": o.kind,
            "required": o.required,
            "cites": [1],
            "second_status": second,
        }
        for o in S[sid].truth.objectives
    }
    return {
        "scenario_id": sid,
        "sut": sut,
        "trial": trial,
        "outcome": "pass" if all(v == "met" for v in statuses.values()) else "fail",
        "verdict": "reject",
        "criticals": [],
        "objectives": objs,
        "meta": {"cost_usd": 1.0, "required_objectives_missed": []},
    }


def test_telegraph_gap_and_flags() -> None:
    base, twin = "R17-high-win-rate", "R17-high-win-rate-h"
    ids = [o.id for o in S[base].truth.objectives]
    cards = [_card(base, STRONG, t, {ids[0]: "partial"}, second="met") for t in (1, 2, 3)]
    cards += [_card(twin, STRONG, t, {i: "met" for i in ids}) for t in (1, 2, 3)]
    cards += [_card(base, WEAK, 1, {ids[0]: "partial"})]
    result = analyze(cards, S, strong=STRONG, weak=WEAK)
    gap = result["telegraph_gap"][base]
    assert gap["recall_hinted"] == 1.0 and gap["gap"] > 0.8
    row = result["scenarios"][base]
    assert "all_fail" in row["flags"]
    assert row["judge_agreement"]["binary"] < 0.7 and "judges_disagree" in row["flags"]
