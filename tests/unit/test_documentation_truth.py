"""Current owner documentation must not reintroduce retired product claims."""

from __future__ import annotations

import re
from pathlib import Path

from scripts import check_openapi_operations

ROOT = Path(__file__).parents[2]


def test_current_entry_docs_retire_cost_layout_and_ai_marketing_claims() -> None:
    documents = [ROOT / "README.md", ROOT / "docs/ARCHITECTURE.md"]
    text = "\n".join(path.read_text(encoding="utf-8") for path in documents).lower()
    for retired in ("$0", "dockview", "ai research desk", "screened source pack"):
        assert retired not in text

    manual_head = (
        (ROOT / "CLAUDE.md")
        .read_text(encoding="utf-8")
        .split("## Architecture DAG", maxsplit=1)[0]
        .lower()
    )
    assert "$0" not in manual_head
    assert "capability-authority-matrix.md" in manual_head


def test_generated_capability_matrix_and_openapi_classification_are_current() -> None:
    assert (
        check_openapi_operations.CLASSIFICATION.read_text(encoding="utf-8")
        == check_openapi_operations.rendered_classification()
    )
    assert (
        check_openapi_operations.MATRIX.read_text(encoding="utf-8")
        == check_openapi_operations.rendered_matrix()
    )


def test_handwritten_docs_do_not_copy_generated_mcp_counts() -> None:
    documents = [
        ROOT / "README.md",
        ROOT / "CLAUDE.md",
        ROOT / "docs/ARCHITECTURE.md",
        ROOT / "docs/governance/2026-07-19-post-v2-risk-register.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
    assert re.search(r"\b(?:48|54|59|62) (?:current )?(?:bounded )?MCP tools", text) is None
    assert re.search(r"pin (?:stays|consciously) \d+", text, flags=re.IGNORECASE) is None
