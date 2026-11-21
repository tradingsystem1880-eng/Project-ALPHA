"""``_activity.snapshot_areas``: the newest mtime per governed data area, stat-only."""

from __future__ import annotations

import os
import time
from pathlib import Path

from alpha_web._activity import AREAS, snapshot_areas


def test_areas_are_the_seven_governed_roots() -> None:
    assert set(AREAS) == {"research", "control", "bars", "paper", "workspaces", "alerts", "ideas"}
    assert set(AREAS["ideas"]) == {
        "ideas",
        "diagnostics",
        "setups",
        "setup-studies",
        "ledger/trials.jsonl",
    }


def test_missing_roots_are_absent_not_zero(tmp_path: Path) -> None:
    assert snapshot_areas(tmp_path) == {}


def test_nested_bars_and_sqlite_sidecars_count(tmp_path: Path) -> None:
    deep = tmp_path / "store/bars/BTC/USDT.parquet"
    deep.parent.mkdir(parents=True)
    deep.write_text("b")
    (tmp_path / "control").mkdir()
    db = tmp_path / "control/workstation.sqlite3"
    db.write_text("db")
    wal = tmp_path / "control/workstation.sqlite3-wal"
    wal.write_text("w")
    later = time.time() + 50
    os.utime(wal, (later, later))
    snap = snapshot_areas(tmp_path)
    assert snap["bars"] >= deep.stat().st_mtime
    assert snap["control"] == wal.stat().st_mtime


def _touch(path: Path, when: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    os.utime(path, (when, when))
    os.utime(path.parent, (when, when))


def test_ideas_area_sees_a_card_a_ledger_row_and_a_new_tool_result(tmp_path: Path) -> None:
    base = time.time() - 1000
    _touch(tmp_path / "ideas/abc.toml", base)
    _touch(tmp_path / "ledger/trials.jsonl", base + 1)
    os.utime(tmp_path, (base, base))
    assert snapshot_areas(tmp_path)["ideas"] == base + 1
    _touch(tmp_path / "ledger/trials.jsonl", base + 5)
    assert snapshot_areas(tmp_path)["ideas"] == base + 5
    run = tmp_path / "diagnostics" / ("a" * 16)
    _touch(run / "first.json", base)
    os.utime(run, (base + 9, base + 9))
    _touch(run / "costs.json", base + 7)  # a new file moves the run folder's own clock
    assert snapshot_areas(tmp_path)["ideas"] >= base + 7


def test_ideas_walk_is_one_level_deep_so_its_cost_is_bounded(tmp_path: Path) -> None:
    """A tree of many run folders is answered from the folders, never from their files."""
    base = time.time() - 1000
    for n in range(300):
        folder = tmp_path / "diagnostics" / f"{n:016x}"
        _touch(folder / "deep" / "a.json", base)
        os.utime(folder / "deep" / "a.json", (base + 500, base + 500))
        os.utime(folder / "deep", (base, base))
        os.utime(folder, (base, base))
    os.utime(tmp_path / "diagnostics", (base, base))
    deep_only = snapshot_areas(tmp_path)["ideas"]
    assert deep_only == base
    started = time.perf_counter()
    for _ in range(5):
        snapshot_areas(tmp_path)
    assert (time.perf_counter() - started) / 5 < 0.5
