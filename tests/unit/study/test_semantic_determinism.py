"""Cross-process determinism for the blind semantic projection identity."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]


def _bytes(*, seed: str, timezone: str) -> bytes:
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = seed
    environment["TZ"] = timezone
    code = (
        "import json; "
        "from tests.unit.study.test_semantic import _projection; "
        "print(json.dumps(_projection().to_dict(), sort_keys=True, "
        "separators=(',', ':'), allow_nan=False))"
    )
    return subprocess.check_output([sys.executable, "-c", code], cwd=ROOT, env=environment).strip()


def test_semantic_projection_bytes_are_environment_independent() -> None:
    utc = _bytes(seed="1", timezone="UTC")
    brisbane = _bytes(seed="999", timezone="Australia/Brisbane")
    assert utc == brisbane
    assert json.loads(utc)["content_sha256"]
