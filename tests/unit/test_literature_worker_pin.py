"""The worker's vendored acquisition primitives must never drift from the originals."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).parents[2]


def test_vendored_acquisition_primitives_are_byte_identical_modulo_the_error_import() -> None:
    original = (_ROOT / "apps/alpha-cli/src/alpha_cli/research_acquisition.py").read_text(
        encoding="utf-8"
    )
    vendored = (_ROOT / "workers/literature/src/literature_worker/_acquisition.py").read_text(
        encoding="utf-8"
    )
    normalized = vendored.replace(
        "from literature_worker._errors import DataError",
        "from alpha_core import DataError",
    )
    assert normalized == original, (
        "workers/literature/src/literature_worker/_acquisition.py drifted from "
        "apps/alpha-cli/src/alpha_cli/research_acquisition.py; regenerate the vendored copy"
    )
