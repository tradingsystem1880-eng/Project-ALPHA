"""Generated governance documents stay in step with the code that generates them."""

from __future__ import annotations

from scripts import check_openapi_operations


def test_generated_capability_matrix_and_openapi_classification_are_current() -> None:
    assert (
        check_openapi_operations.CLASSIFICATION.read_text(encoding="utf-8")
        == check_openapi_operations.rendered_classification()
    )
    assert (
        check_openapi_operations.MATRIX.read_text(encoding="utf-8")
        == check_openapi_operations.rendered_matrix()
    )
