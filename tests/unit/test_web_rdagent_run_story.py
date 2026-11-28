"""The web run story reads recorded idea identity and shortlist state as the writer stored them."""

from __future__ import annotations

import pytest

from alpha_web import _rdagent_run_story as story

DIGEST = "a" * 64


def test_story_key_reads_identity_and_refuses_a_bad_hash() -> None:
    row = {"iteration": 2, "name": "Funding", "code_sha256": DIGEST}
    assert story._story_key(row) == (2, "Funding", DIGEST)
    assert story._story_key({"iteration": 2, "name": "Funding"}) is None
    with pytest.raises(ValueError, match="code hash"):
        story._story_key({**row, "code_sha256": "not-a-hash"})
    with pytest.raises(ValueError, match="identity"):
        story._story_key({**row, "iteration": "2"})
    assert "STORY_FIELDS" not in story._story_raw({})


def test_shortlisted_reads_the_status_and_leaves_unknown_ones_open() -> None:
    assert story._shortlisted({"shortlist": True}) is True
    assert story._shortlisted({"shortlist": False}) is False
    for status in story.BEFORE_SHORTLIST:
        assert story._shortlisted({"status": status}) is False
    assert story._shortlisted({"status": "some-status-never-recorded"}) is None
    assert story._story_trials([], [], {"run"}) == []
