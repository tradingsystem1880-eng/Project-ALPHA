"""Disposable harness templates must stay stable while tests copy them."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.unit._harness_support import build_harness_repo, git


def _maintenance_commands(trace: Path) -> list[list[str]]:
    return [
        event["argv"]
        for line in trace.read_text().splitlines()
        if (event := json.loads(line)).get("event") == "child_start"
        and "maintenance" in event.get("argv", [])
    ]


def test_template_suppresses_automatic_maintenance_before_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "gitconfig"
    config.write_text(
        "[maintenance]\n"
        "auto = true\nautoDetach = false\nstrategy = incremental\n"
        '[maintenance "gc"]\nenabled = false\n'
        '[maintenance "loose-objects"]\nenabled = true\nauto = -1\n'
    )
    trace = tmp_path / "trace.jsonl"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TRACE2_EVENT", str(trace))

    template = build_harness_repo(tmp_path / "template")
    assert not _maintenance_commands(trace)
    copy = tmp_path / "copy"
    shutil.copytree(template, copy, symlinks=True)
    assert git(copy, "config", "--local", "--bool", "maintenance.auto") == "false"
    assert git(copy, "show", "HEAD:tracked.py") == "x = 1"

    # Prove this configuration really triggers maintenance when suppression is absent.
    git(copy, "config", "--local", "--unset", "maintenance.auto")
    git(copy, "commit", "--quiet", "--allow-empty", "-m", "maintenance control")
    assert _maintenance_commands(trace)
    assert list((copy / ".git" / "objects" / "pack").glob("*.pack"))
