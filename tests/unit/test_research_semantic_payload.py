"""Canonical semantic payload text and frozen cutoff invariants."""

from __future__ import annotations

import pytest

import alpha_cli.control_store as control_store_module
from alpha_core import DataError
from tests.fixtures.research_semantic_payload_fixtures import (
    PROJECT_ID,
    _semantic_definition_payload,
    _semantic_review_payload,
    _semantic_source,
)


def test_semantic_payload_accepts_the_frozen_study_second_precision_cutoff() -> None:
    source = {**_semantic_source(), "cutoff_confirmed_at": "2026-08-13T00:00:00Z"}
    payload = _semantic_definition_payload(
        source, control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    )

    assert control_store_module._semantic_source_map(source)["cutoff_confirmed_at"] == (
        "2026-08-13T00:00:00Z"
    )
    assert control_store_module._semantic_payload(payload)["cutoff_confirmed_at"] == (
        "2026-08-13T00:00:00Z"
    )


@pytest.mark.parametrize(
    ("event_type", "field", "maximum"),
    [
        pytest.param("definition", "definition_label", 256, id="definition-label"),
        pytest.param("definition", "definition_text", 8192, id="definition-text"),
        pytest.param("review", "review_text", 8192, id="review-text"),
    ],
)
def test_semantic_payload_requires_canonical_text(
    event_type: str, field: str, maximum: int
) -> None:
    source = _semantic_source()
    head = control_store_module._semantic_empty_head_sha256(PROJECT_ID)
    definition_id = "sd_" + "d" * 64
    payload = (
        _semantic_definition_payload(source, head)
        if event_type == "definition"
        else _semantic_review_payload(source, head, definition_id, "approve")
    )
    exact = "x" * maximum
    payload[field] = exact
    assert control_store_module._semantic_payload(payload)[field] == exact
    payload[field] = f" {exact} "
    with pytest.raises(DataError, match="canonical"):
        control_store_module._semantic_payload(payload)
