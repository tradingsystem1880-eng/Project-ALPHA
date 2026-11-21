"""`alpha follow update`, `show` and `list` as the owner sees them, with an injected clock."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli import follow_cmds
from alpha_cli.main import app
from tests.fixtures.follow_fixtures import World

RUNNER = CliRunner()


def _cli(home: Path, *args: str) -> tuple[int, str]:
    result = RUNNER.invoke(app, ["follow", *args], env={"ALPHA_DATA_DIR": str(home)})
    return result.exit_code, result.output


def _five_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[World, str]:
    world = World(tmp_path, -0.2, [3.0, 3.0, 3.0, -8.0, -8.0, -8.0])
    follow = world.start()
    now: list[datetime] = [world.close_of(0)]
    monkeypatch.setattr(follow_cmds, "CLOCK", lambda: now[0])
    for k in range(5):
        world.grow()
        now[0] = world.close_of(k)
        code, out = _cli(tmp_path, "update", follow)
        assert code == 0, out
    return world, follow


def test_show_after_five_sessions_prints_entries_and_the_paper_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, follow = _five_sessions(tmp_path, monkeypatch)
    code, out = _cli(tmp_path, "show", follow)
    assert code == 0
    print(out)
    assert "Entries (newest last)" in out and "ould sell at the next open" in out
    assert (
        "buy" in out
        and "fast average price" in out
        and "fast_sma" not in out
        and "Paper account" in out
    )
    assert "Replay check at the last update: agrees; 4 session(s) compared." in out
    assert "profit" not in out.lower() and "paper follow" in out
    code, listed = _cli(tmp_path, "list")
    assert "new signal: would sell at the next open" in listed


def test_update_json_and_a_second_run_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world, follow = _five_sessions(tmp_path, monkeypatch)
    code, out = _cli(tmp_path, "update", "--all", "--json")
    row = json.loads(out)["follows"][0]
    assert code == 0 and row["status"] == "no-op" and "already in the journal" in row["message"]
    assert world.stored == 5 and row["follow_id"] == follow


def test_update_needs_one_target_and_refuses_a_stopped_follow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, follow = _five_sessions(tmp_path, monkeypatch)
    code, out = _cli(tmp_path, "update")
    assert code != 0 and "Name one follow" in out
    _cli(tmp_path, "stop", follow, "--reason", "test")
    code, out = _cli(tmp_path, "update", follow)
    assert code != 0 and "stopped" in out
    code, out = _cli(tmp_path, "update", "--all", "--json")
    assert code == 0 and json.loads(out)["follows"][0]["status"] == "skipped"
