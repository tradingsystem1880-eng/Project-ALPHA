"""docs/reference/checks.md names every CI job and every pytest marker."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKS = ROOT / "docs/reference/checks.md"
WORKFLOWS = ("ci.yml", "nightly.yml", "mutation-weekly.yml")


def workflow_jobs(text: str) -> list[str]:
    """Job ids: the two-space-indented keys under the top-level ``jobs:`` block."""
    body = text.split("\njobs:\n", 1)[1]
    return re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", body, re.MULTILINE)


def check_column() -> str:
    """The first column of the table, where each check is named in backticks."""
    rows = [line for line in CHECKS.read_text().splitlines() if line.startswith("| ")]
    return "\n".join(row.split("|")[1] for row in rows)


def test_job_parser_reads_job_ids_only() -> None:
    text = "on:\n  push:\njobs:\n  a-job:\n    steps:\n      - run: x\n  b:\n"
    assert workflow_jobs(text) == ["a-job", "b"]


def test_every_ci_job_is_in_the_checks_table() -> None:
    names = check_column()
    missing = [
        f"{workflow}: {job}"
        for workflow in WORKFLOWS
        for job in workflow_jobs((ROOT / ".github/workflows" / workflow).read_text())
        if f"`{job}`" not in names
    ]
    assert len(workflow_jobs((ROOT / ".github/workflows/ci.yml").read_text())) >= 8
    assert not missing, "Add a row to docs/reference/checks.md for: " + ", ".join(missing)


def test_every_pytest_marker_is_in_the_checks_table() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    markers = [m.split(":", 1)[0] for m in config["tool"]["pytest"]["ini_options"]["markers"]]
    names = check_column()
    missing = [marker for marker in markers if f"`{marker}`" not in names]
    assert markers and not missing, "Add a row to docs/reference/checks.md for: " + ", ".join(
        missing
    )
