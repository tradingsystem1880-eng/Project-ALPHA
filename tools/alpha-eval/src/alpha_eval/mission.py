"""Decision-oriented capability summaries; scores are diagnostics, never trading authority."""

from __future__ import annotations

from collections import Counter
from typing import Any

CAPABILITIES = {
    "find_edge": {"R01", "R03", "R15", "R19", "R20", "A10", "M04", "ADV07"},
    "prove_edge": {
        "R04",
        "R05",
        "R07",
        "R08",
        "R14",
        "R17",
        "R21",
        "A09",
        "ADV03",
        "ADV04",
        "ADV06",
        "ADV07",
        "ADV08",
        "ADV10",
        "ADV14",
        "ADV15",
    },
    "build_systems": {"R06", "R08", "R12", "R20", "M02", "M03", "M07", "ADV02"},
    "trade_support": {"R04", "R09", "R11", "R16", "R20", "A01", "A07", "ADV13"},
    "trust_data": {"R01", "R07", "R10", "R13", "R16", "R18", "A02", "ADV05", "ADV09"},
    "research_continuity": {
        "R10",
        "R18",
        "A05",
        "L01",
        "L02",
        "L03",
        "L04",
        "L05",
        "ADV12",
        "ADV16",
    },
}


def summarize_capabilities(cards: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for capability, prefixes in CAPABILITIES.items():
        by_sut = {}
        for sut in sorted({c["sut"] for c in cards}):
            subset = [
                c
                for c in cards
                if c["sut"] == sut
                and c["scenario_id"].split("-")[0] in prefixes
                and not c["scenario_id"].endswith(("-h", "-v1"))
            ]
            if not subset:
                continue
            valid = [c for c in subset if c["outcome"] not in {"ungraded", "harness_invalid"}]
            by_sut[sut] = {
                "outcomes": dict(Counter(c["outcome"] for c in subset)),
                "graded_trials": len(valid),
                "criticals": dict(Counter(h["cls"] for c in valid for h in c["criticals"])),
                "required_missed": dict(
                    Counter(
                        o for c in valid for o in c["meta"].get("required_objectives_missed", [])
                    )
                ),
                "evidence": [
                    {
                        "scenario": c["scenario_id"],
                        "trial": c["trial"],
                        "outcome": c["outcome"],
                        "revision": c["meta"].get("scoring_revision"),
                    }
                    for c in subset
                ],
            }
        out[capability] = by_sut
    return out
