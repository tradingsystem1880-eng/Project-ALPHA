"""Specialist reviews cannot substitute prose for empirical evidence or enlarge a search."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from alpha_cli.research_workflow_contract import ResearchWorkflowPlan, SpecialistReview


def test_plan_requires_baseline_before_variants_and_bounded_search() -> None:
    with pytest.raises(ValidationError):
        ResearchWorkflowPlan(question="test", target="next week", candidate_limit=0)
    with pytest.raises(ValidationError, match="baseline"):
        ResearchWorkflowPlan(
            question="test", target="next week", candidate_limit=3, candidates=("a", "b")
        )


def test_completed_review_requires_content_bound_evidence() -> None:
    with pytest.raises(ValidationError, match="evidence"):
        SpecialistReview(
            role="data", case_id="case", status="completed_evidence", conclusion="Looks good"
        )
    with pytest.raises(ValidationError, match="blocker"):
        SpecialistReview(
            role="overfitting", case_id="case", status="honest_block", conclusion="Unavailable"
        )
    review = SpecialistReview(
        role="economics_market_structure",
        case_id="case",
        status="honest_block",
        conclusion="Execution cannot be assessed",
        blocker="No quotes or fills supplied",
    )
    assert review.advisory_only


def test_cli_rejects_wrong_evidence_hash(tmp_path: Path) -> None:
    import json

    import typer

    from alpha_cli.research_diagnostic_cmds import check_review

    artifact = tmp_path / "data.json"
    artifact.write_text('{"score": 1}')
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            dict(
                role="data",
                case_id="case",
                status="completed_evidence",
                conclusion="Measured",
                evidence=[dict(artifact=str(artifact), sha256="0" * 64, pointer="/score")],
            )
        )
    )
    with pytest.raises(typer.BadParameter, match="hash mismatch"):
        check_review(str(review))


@pytest.mark.parametrize("pointer", ["/-1", "/01", "/+1", "/~2"])
def test_cli_rejects_noncanonical_pointers(tmp_path: Path, pointer: str) -> None:
    import hashlib
    import json

    import typer

    from alpha_cli.research_diagnostic_cmds import check_review

    artifact = tmp_path / "array.json"
    raw = b"[1,2]"
    artifact.write_bytes(raw)
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            dict(
                role="data",
                case_id="case",
                status="completed_evidence",
                conclusion="Measured",
                evidence=[
                    dict(
                        artifact=str(artifact),
                        sha256=hashlib.sha256(raw).hexdigest(),
                        pointer=pointer,
                    )
                ],
            )
        )
    )
    with pytest.raises(typer.BadParameter):
        check_review(str(review))
