"""``_activity.snapshot_areas``: the newest mtime per governed data area, stat-only."""

from __future__ import annotations

import os
import time
from pathlib import Path

from alpha_web._activity import AREAS, snapshot_areas


def test_areas_are_the_six_governed_roots() -> None:
    assert set(AREAS) == {"research", "control", "bars", "paper", "workspaces", "alerts"}


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
