"""Tiered research-readiness semantics are conservative and evidence-referenced."""

from alpha_cli.research_readiness import derive_research_readiness


def _d1_evidence() -> dict[str, object]:
    return {
        "primary_result": {
            "status": "TESTED",
            "practical_magnitude": {"status": "CLEARS_HURDLE"},
        },
        "multiplicity": {"status": "PASSED"},
        "power": {"status": "PASSED"},
        "negative_controls": {"status": "PASSED"},
    }


def test_confirmation_readiness_blocks_every_required_control_failure() -> None:
    evidence = _d1_evidence()
    evidence["negative_controls"] = {"status": "INCONCLUSIVE"}
    readiness = derive_research_readiness(
        evidence,
        required_falsifiers=("shuffled_event_null", "leadlag_leakage"),
        skipped_required_families=("leadlag_leakage",),
    )

    assert readiness["confirmation_readiness"]["state"] == "blocked"
    blockers = readiness["confirmation_readiness"]["blockers"]
    assert {blocker["code"] for blocker in blockers} == {
        "required_falsifier_not_passed",
        "required_family_skipped",
    }
    assert all(blocker["evidence_refs"] for blocker in blockers)


def test_ready_confirmation_does_not_imply_promotion_readiness() -> None:
    readiness = derive_research_readiness(
        _d1_evidence(),
        required_falsifiers=("shuffled_event_null", "leadlag_leakage"),
    )

    assert readiness["confirmation_readiness"]["state"] == "ready"
    assert readiness["confirmation_readiness"]["blockers"] == []
    assert readiness["promotion_readiness"]["state"] == "blocked"
    assert readiness["promotion_readiness"]["blockers"][0]["code"] == ("confirmation_not_supported")


def test_promotion_requires_supported_classification_and_reliable_d2() -> None:
    evidence = {
        "confirmation_classification": "SUPPORTED",
        "multiplicity": {"status": "PASSED"},
        "power": {"status": "PASSED"},
    }

    readiness = derive_research_readiness(evidence)

    assert readiness["promotion_readiness"]["state"] == "ready"
    assert readiness["promotion_readiness"]["blockers"] == []
