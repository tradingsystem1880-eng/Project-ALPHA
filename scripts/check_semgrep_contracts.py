"""Discriminating regression for exact protocol identity versus computed estimates."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fixture = root / ".semgrep/fixtures/float_contract.py.txt"
    expected = {
        index + 2
        for index, line in enumerate(fixture.read_text().splitlines())
        if line.strip() == "# finding"
    }
    with tempfile.TemporaryDirectory(prefix="alpha-semgrep-contract-") as temporary:
        target = Path(temporary) / "packages/alpha-research/probe.py"
        target.parent.mkdir(parents=True)
        shutil.copyfile(fixture, target)
        result = subprocess.run(
            [
                "uvx",
                "semgrep",
                "--config",
                str(root / ".semgrep/alpha.yml"),
                "--metrics=off",
                "--disable-version-check",
                "--no-git-ignore",
                "--json",
                "--quiet",
                "packages/alpha-research/probe.py",
            ],
            cwd=temporary,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        if payload.get("errors"):
            raise RuntimeError(f"Semgrep failed: {payload['errors']}")
        actual = {
            entry["start"]["line"]
            for entry in payload["results"]
            if entry["check_id"].endswith("alpha-float-literal-equality")
        }
        if actual != expected:
            raise RuntimeError(f"Semgrep contract: expected findings {expected}, got {actual}")
    print("Semgrep contract: exact generation checks exempt; all four leaky comparisons detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
