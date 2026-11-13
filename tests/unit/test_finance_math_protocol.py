"""Finance-math guidance extends the existing source-grounded literature protocol."""

from __future__ import annotations

import doctest
import hashlib
from pathlib import Path

import numpy as np
import pytest

from alpha_cli.research_protocols import load_research_protocols, read_research_protocol
from alpha_core import DataError
from alpha_research.rolling_pca import pca_components, pca_scores, rolling_pca_scores

_ROOT = Path(__file__).resolve().parents[2]
_GUIDE = _ROOT / "docs" / "operations" / "finance-math-evidence.md"


def test_literature_protocol_discovers_finance_math_without_new_schema() -> None:
    protocol = read_research_protocol("literature-review")
    content = str(protocol["content"])
    assert "## Finance-math evidence and numerical reuse" in content
    assert "../../../docs/operations/finance-math-evidence.md" in content
    assert _GUIDE.is_file()
    assert protocol["sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert len(load_research_protocols()) == 13


def test_finance_math_protocol_keeps_evidence_and_authority_separate() -> None:
    content = " ".join(
        str(read_research_protocol("literature-review")["content"]).casefold().split()
    )
    for required in (
        "book cover is metadata, not book-text evidence",
        "sourceanchorv1",
        "knowledge evidence",
        "numerical verification",
        "research/promotion authority",
        "unknown edition",
        "not a registered analysis family",
        "no automatic promotion",
        "scale, units, conditioning",
    ):
        assert required in content


def test_finance_math_guide_preserves_carousel_limits_and_reuse_api() -> None:
    content = _GUIDE.read_text(encoding="utf-8")
    rows = [line for line in content.splitlines() if line.startswith("| ") and "/15 |" in line]
    assert len(rows) == 13
    for slide in range(2, 15):
        assert f"| {slide}/15 |" in content
    assert content.count("| Unknown |") == 4
    for required in (
        "Slide 15/15 was not supplied",
        "Statistics / Introduction to Probability",
        "No book pages were supplied or read",
        "unverified book coverage",
        "pca_components",
        "pca_scores",
        "rolling_pca_scores",
        "synthetic",
        "not a forecast",
        "No new numerical implementation",
    ):
        assert required in content


def test_documented_synthetic_pca_example_executes() -> None:
    result = doctest.testfile(str(_GUIDE), module_relative=False)
    assert result.attempted == 19
    assert result.failed == 0


def test_verified_source_leads_do_not_imply_governed_book_evidence() -> None:
    content = _GUIDE.read_text(encoding="utf-8")
    for required in (
        "## Verified source leads, not admitted book evidence",
        "https://measure.axler.net/MIRA.pdf",
        "https://linear.axler.net/LADR4e.pdf",
        "https://stat110.hsites.harvard.edu/",
        "https://creativecommons.org/licenses/by-nc/4.0/",
        "30 October 2026",
        "4 November 2026",
        "different from the photographed third edition",
        "Download was denied by the owner",
        "No SourceAnchorV1 records were created",
        "## Original PCA derivation and reference checks",
        "uncorrelated does not imply independent",
        "owner-selected bounded excerpt",
        "alpha research import-pdf PROJECT_ID --file EXCERPT.pdf --title TITLE",
    ):
        assert required in content
    assert "No book pages were supplied or read from the carousel" in content


def test_existing_pca_matches_fixed_svd_reference() -> None:
    # Fixed float64 inputs with distinct eigenvalues; no sampling or market claim.
    rows = 0.01 * np.array(
        [
            [-2.0, 1.0, 0.0],
            [-1.0, -1.0, 2.0],
            [0.0, 0.0, -1.0],
            [1.0, 2.0, -1.0],
            [2.0, -2.0, 0.0],
            [0.0, 1.0, 1.0],
        ]
    )
    fitted = pca_components(rows, n_components=2)
    centered = rows - rows.mean(axis=0)
    _, singular_values, right_vectors = np.linalg.svd(centered, full_matrices=False)
    tolerance = 64 * np.finfo(np.float64).eps
    np.testing.assert_allclose(
        fitted.components.T @ fitted.components,
        right_vectors[:2].T @ right_vectors[:2],
        rtol=tolerance,
        atol=tolerance,
    )
    np.testing.assert_allclose(
        fitted.explained_variance,
        singular_values[:2] ** 2 / (len(rows) - 1),
        rtol=tolerance,
    )
    np.testing.assert_allclose(
        fitted.components @ fitted.components.T,
        np.eye(2),
        rtol=tolerance,
        atol=tolerance,
    )
    reconstructed = pca_scores(rows, fitted) @ fitted.components
    np.testing.assert_allclose(
        np.sum((centered - reconstructed) ** 2),
        np.sum(singular_values[2:] ** 2),
        rtol=tolerance,
        atol=tolerance * float(np.sum(centered**2)),
    )


def test_existing_pca_preserves_prior_bytes_and_rejects_zero_variance() -> None:
    x = np.arange(-2.0, 3.0)
    rows = np.column_stack((0.01 * x, 0.02 * x))
    before = rolling_pca_scores(rows, window=3, n_components=1)
    rows[-1] = [10.0, -10.0]
    after = rolling_pca_scores(rows, window=3, n_components=1)
    # Identity check on unchanged deterministic computation, not a float golden.
    assert before[:4].tobytes() == after[:4].tobytes()
    with pytest.raises(DataError, match="zero total variance"):
        pca_components(np.zeros((3, 2)), n_components=1)
