"""Constant-only modules need actual mutations, never a fabricated empty measurement."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import harness_quant
import pytest
from mutation_legacy import export_stats


def cache(path: Path, rows: list[tuple[str, str, str]]) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "CREATE TABLE SourceFile(id INTEGER, filename TEXT);"
            "CREATE TABLE Line(id INTEGER, sourcefile INTEGER);"
            "CREATE TABLE Mutant(id INTEGER, line INTEGER, status TEXT, tested_against_hash TEXT);"
        )
        for index, (filename, status, tested) in enumerate(rows):
            connection.execute("INSERT INTO SourceFile VALUES (?, ?)", (index, filename))
            connection.execute("INSERT INTO Line VALUES (?, ?)", (index, index))
            connection.execute(
                "INSERT INTO Mutant VALUES (?, ?, ?, ?)", (index, index, status, tested)
            )


def test_constant_only_backend_keeps_function_modules_on_existing_tool(tmp_path: Path) -> None:
    module = tmp_path / "m.py"
    module.write_text("from typing import Final\nVERSION: Final = 4\n")
    assert harness_quant.mutation_backend(module) == "mutmut==2.5.1"
    module.write_text("VERSION = 4\ndef value(): return VERSION\n")
    assert harness_quant.mutation_backend(module) == "mutmut"


def test_export_counts_only_completed_real_mutations_conservatively(tmp_path: Path) -> None:
    source = tmp_path / ".mutmut-cache"
    cache(
        source,
        [
            ("src/m.py", status, "hash")
            for status in ("ok_killed", "bad_survived", "bad_timeout", "ok_suspicious")
        ],
    )
    stats = export_stats(source, "src/m.py")
    assert stats["total"] == 4 and stats["killed"] == 1
    assert stats["timeout"] == 1 and stats["no_tests"] == 0
    assert harness_quant.mutation_kill_rate(stats) == 0.25


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [("src/other.py", "ok_killed", "hash")],
        [("src/m.py", "untested", "hash")],
        [("src/m.py", "ok_killed", "")],
        [("src/m.py", "ok_killed", "NO TESTS FOUND")],
        [("src/m.py", "unknown", "hash")],
    ],
)
def test_export_rejects_empty_wrong_unfinished_and_unknown_counts(
    tmp_path: Path, rows: list[tuple[str, str, str]]
) -> None:
    source = tmp_path / ".mutmut-cache"
    cache(source, rows)
    with pytest.raises(ValueError):
        export_stats(source, "src/m.py")


def test_legacy_driver_preserves_selection_exclusions_and_score_floor(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    rel = "packages/alpha-validation/src/alpha_validation/version.py"
    module = tmp_path / rel
    module.parent.mkdir(parents=True)
    module.write_text("VERSION = 4\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\nmarkers=[]\n")
    commands: list[list[str]] = []

    def runner(command: list[str], **kwargs: Any) -> tuple[bool, float, str]:
        commands.append(command)
        if "pytest" in command:
            return False, 1.0, "FAILED tests/unit/test_layout.py::test_layout - FileNotFoundError\n"
        if "mutmut" in command:
            assert "mutmut==2.5.1" in command and "--CI" in command
            assert "--max-children" not in command
            test_command = command[command.index("--runner") + 1]
            assert "--deselect tests/unit/test_layout.py::test_layout" in test_command
            assert test_command.endswith(" tests") and "pytest" in test_command
            return True, 1.0, "four real mutations"
        assert any(Path(arg).name == "mutation_legacy.py" for arg in command)
        target = kwargs["cwd"] / "mutants/mutmut-cicd-stats.json"
        target.parent.mkdir()
        target.write_text(
            json.dumps({"killed": 1, "survived": 3, "total": 4, "no_tests": 0, "timeout": 0})
        )
        return True, 0.1, "exported counts"

    code, report = harness_quant.mutate(tmp_path, [rel], runner=runner, workers=2)
    entry = report["modules"][rel]
    assert code == 1 and entry["status"] == "fail"
    assert entry["kill_rate"] == 0.25 and entry["required"] == 0.9
    assert entry["tool"] == "mutmut==2.5.1"
    assert entry["excluded_tests"] == ["tests/unit/test_layout.py::test_layout"]
    assert len(commands) == 3
