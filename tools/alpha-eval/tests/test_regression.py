"""Regression manifest: loads, and fixed/open/not_run semantics."""

from __future__ import annotations

from alpha_eval.regression import evaluate, load_manifest
from alpha_eval.scenarios import load_all


def _card(
    sid: str,
    trial: int,
    checks: dict[str, bool],
    verdict: str = "none",
    crit: list[str] | None = None,
):
    return {
        "scenario_id": sid, "sut": "claude:x", "trial": trial, "outcome": "fail", "verdict": verdict,
        "checks": [{"id": k, "passed": v, "core": True} for k, v in checks.items()],
        "criticals": [{"cls": c} for c in (crit or [])], "objectives": {}, "meta": {},
    }  # fmt: skip


def test_manifest_references_existing_scenarios_and_probes() -> None:
    ids = {s.id for s in load_all()}
    for item in load_manifest():
        if "base" in item:
            assert item["base"] in ids, item["id"]
            checks = {c.id for c in next(s for s in load_all() if s.id == item["base"]).checks}
            assert set(item["expect"].get("checks", {})) <= checks, item["id"]


def test_fixed_requires_every_valid_trial() -> None:
    manifest = [
        {"id": "r1", "base": "S", "sut": "claude", "expect": {"checks": {"c": True}}},
        {
            "id": "r2",
            "base": "S",
            "sut": "claude",
            "expect": {"no_criticals": ["holdout_contamination"]},
        },
        {"id": "r3", "base": "T", "sut": "claude", "expect": {"verdict_in": ["support"]}},
        {"id": "p1", "probe": "P02", "expect": {"classification": "as_expected"}},
    ]
    cards = [
        _card("S", 1, {"c": True}),
        _card("S", 2, {"c": False}, crit=["holdout_contamination"]),
        {**_card("S", 3, {"c": False}), "outcome": "harness_invalid"},
    ]
    probes = {"probes": [{"id": "P02", "classification": "not_as_expected"}]}
    rows = {r["id"]: r for r in evaluate(manifest, cards, probes)}
    assert rows["r1"]["status"] == "open" and "1/2" in rows["r1"]["detail"]
    assert rows["r2"]["status"] == "open"
    assert rows["r3"]["status"] == "not_run"
    assert rows["p1"]["status"] == "open"
    cards_fixed = [_card("S", 1, {"c": True}), _card("S", 2, {"c": True})]
    assert evaluate(manifest[:1], cards_fixed)[0]["status"] == "fixed"
