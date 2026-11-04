"""JSON-only synthetic checkpoint roundtrip; neither process imports the other's package."""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("crash", [False, True])
def test_checkpoint_roundtrip_to_existing_cli_journal(crash: bool) -> None:
    root = Path(__file__).resolve().parents[3]
    script = f"""
from pathlib import Path

import pytest
from tempfile import TemporaryDirectory
from tests.unit.test_w09_durable_observations import storage, _exercise_worker_json_checkpoints
with TemporaryDirectory(prefix="alpha-w09-engineering-") as directory:
    fixture = storage.__wrapped__(Path(directory))
    _exercise_worker_json_checkpoints(fixture, crash={crash!r})
"""
    result = subprocess.run(
        [str(root / ".venv" / "bin" / "python"), "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
