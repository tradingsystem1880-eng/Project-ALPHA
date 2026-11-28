"""The root README states only what is true about page checks and the RD-Agent commands.

It must not claim that reference pages carry a fingerprint of the code they describe, nor that
RD-Agent has no `alpha` command; it says instead that front matter `sources:` names a page's code
(linking the document lifecycle) and that `alpha rdagent run` and `alpha rdagent status` exist.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
README = ROOT / "README.md"


def _text() -> str:
    """The README with all whitespace runs folded to one space, so wrapped lines still match."""
    return " ".join(README.read_text(encoding="utf-8").split())


def test_readme_says_what_ties_pages_to_code() -> None:
    text = _text()
    lowered = text.lower()
    assert "carry a fingerprint" not in lowered, "README still says pages carry a fingerprint"
    assert "fingerprint of the code" not in lowered, (
        "README still says pages carry a fingerprint of the code they describe"
    )
    assert "sources:" in text, "README should say front matter `sources:` names a page's code"
    assert "documentation.md#document-lifecycle" in text, (
        "README should link docs/reference/invariants/documentation.md#document-lifecycle"
    )


def test_readme_names_the_rdagent_alpha_commands() -> None:
    text = _text()
    assert "not yet by an `alpha` command" not in text, (
        "README still says RD-Agent has no alpha command"
    )
    assert "alpha rdagent run" in text, "README should name `alpha rdagent run`"
    assert "alpha rdagent status" in text, "README should name `alpha rdagent status`"
