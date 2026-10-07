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
