from pathlib import Path

import pytest

from alpha_eval.sandbox import TrialPaths


def test_trial_collision_preserves_every_byte(tmp_path: Path) -> None:
    first = TrialPaths.create(tmp_path, "S", "codex:gpt-6-astra", 1)
    first.raw.write_text("historical evidence")
    with pytest.raises(FileExistsError):
        TrialPaths.create(tmp_path, "S", "codex:gpt-6-astra", 1)
    assert first.raw.read_text() == "historical evidence"


def test_retry_allocates_new_attempt(tmp_path: Path) -> None:
    first = TrialPaths.create(tmp_path, "S", "codex:gpt-6-astra", 1)
    first.raw.write_text("original")
    retry = TrialPaths.create(tmp_path, "S", "codex:gpt-6-astra", 1, retry=True)
    assert retry.root != first.root
    assert first.raw.read_text() == "original"


def test_workspace_exclusions_name_current_repository_paths() -> None:
    from alpha_eval.platform import repo_root
    from alpha_eval.sandbox import EXCLUDED_FROM_WORKSPACE

    # Benchmark-describing audits moved from docs/audit to docs/records/audits (2026-11).
    assert "docs/records/audits" in EXCLUDED_FROM_WORKSPACE
    assert "docs/audit" not in EXCLUDED_FROM_WORKSPACE
    root = repo_root()
    for doc_path in (p for p in EXCLUDED_FROM_WORKSPACE if p.startswith("docs/")):
        assert (root / doc_path).is_dir(), doc_path
