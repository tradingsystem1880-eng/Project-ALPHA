"""`gate.py check` maps changed files to the tests worth running locally."""

import json
from pathlib import Path

import gate
import gate_select
import pytest

from tests.unit._harness_support import git


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("packages/alpha-data/src/alpha_data/pit.py", "alpha_data.pit"),
        ("packages/alpha-data/src/alpha_data/crypto/quality.py", "alpha_data.crypto.quality"),
        ("apps/alpha-cli/src/alpha_cli/__init__.py", "alpha_cli"),
        ("scripts/gate.py", "gate"),
        ("tests/unit/_harness_support.py", "tests.unit._harness_support"),
        ("tests/unit/test_x.py", None),
        ("tests/conftest.py", None),
        ("docs/README.md", None),
        ("workers/qlib/src/alpha_qlib_worker/x.py", None),
    ],
)
def test_module_name(path: str, expected: str | None) -> None:
    assert gate_select.module_name(path) == expected


@pytest.mark.parametrize(
    ("text", "module", "expected"),
    [
        ("import alpha_data.pit\n", "alpha_data.pit", True),
        ("from alpha_data.pit import PointInTimeReader\n", "alpha_data.pit", True),
        ("from alpha_data import pit, other\n", "alpha_data.pit", True),
        ("from alpha_data import (\n    other,\n    pit,\n)\n", "alpha_data.pit", True),
        ("from alpha_data.pit_extra import x\n", "alpha_data.pit", False),
        ("from alpha_data import pitfall\n", "alpha_data.pit", False),
        ("# from alpha_data import pit\n", "alpha_data.pit", False),
        ("import gate\n", "gate", True),
        ("from gate import doctor\n", "gate", True),
        ("from scripts import check_openapi_operations\n", "check_openapi_operations", True),
        ("import gate_components\n", "gate", False),
    ],
)
def test_imports_module(text: str, module: str, expected: bool) -> None:
    assert gate_select.imports_module(text, module) is expected


def test_changes_map_to_their_own_and_importing_tests(tmp_path: Path) -> None:
    _write(tmp_path, "tests/unit/test_pit.py", "from alpha_data.pit import read\n")
    _write(tmp_path, "tests/unit/test_other.py", "import alpha_core\n")
    _write(tmp_path, "tests/unit/test_edited.py", "def test_a():\n    pass\n")
    _write(tmp_path, "tests/unit/test_gate_x.py", "import gate\n")
    _write(tmp_path, "tests/bias_guards/test_guard.py", "from alpha_data.pit import read\n")
    selection = gate_select.select(
        tmp_path,
        [
            "packages/alpha-data/src/alpha_data/pit.py",
            "tests/unit/test_edited.py",
            "tests/unit/test_deleted.py",
            "scripts/gate.py",
            "docs/notes.md",
        ],
    )
    assert selection.always == gate_select.ALWAYS
    # The bias guard already runs as part of ALWAYS; deleted files are not passed to pytest.
    assert selection.mapped == (
        "tests/unit/test_edited.py",
        "tests/unit/test_gate_x.py",
        "tests/unit/test_pit.py",
    )
    assert selection.notes == ()


def test_unknown_base_runs_only_the_guards_and_last_failures(tmp_path: Path) -> None:
    _write(tmp_path, "tests/unit/test_a.py", "def test_a():\n    pass\n")
    _write(
        tmp_path,
        str(gate_select.LAST_FAILED),
        json.dumps(
            {
                "tests/unit/test_a.py::test_a": True,
                "tests/unit/test_gone.py::test_b": True,
                "tests/oracles/test_o.py::test_c": True,
            }
        ),
    )
    _write(tmp_path, "tests/oracles/test_o.py", "def test_c():\n    pass\n")
    selection = gate_select.select(tmp_path, None)
    assert selection.mapped == ()
    assert selection.last_failed == ("tests/unit/test_a.py::test_a",)
    assert selection.changed is None
    assert "comparison base unavailable" in selection.notes[0]
    assert selection.pytest_paths() == [*gate_select.ALWAYS, "tests/unit/test_a.py::test_a"]


def test_a_broad_change_keeps_only_tests_named_after_it(tmp_path: Path) -> None:
    many = "\n".join(f"def test_{i}():\n    pass" for i in range(gate_select.MAX_MAPPED_TESTS + 1))
    _write(tmp_path, "tests/unit/test_wide_user.py", f"import alpha_core.types\n{many}\n")
    _write(tmp_path, "tests/unit/test_types.py", "from alpha_core import types\n")
    selection = gate_select.select(tmp_path, ["packages/alpha-core/src/alpha_core/types.py"])
    assert selection.mapped == ("tests/unit/test_types.py",)
    assert "left the rest to CI" in selection.notes[0]


def test_conftest_changes_are_reported_not_guessed(tmp_path: Path) -> None:
    selection = gate_select.select(tmp_path, ["tests/unit/conftest.py"])
    assert selection.mapped == ()
    assert "tests/unit/conftest.py changed" in selection.notes[0]


def test_check_runs_lint_types_and_selected_tests_and_writes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ALPHA_GATE_BASE", raising=False)
    _write(repo, "tests/unit/test_new.py", "def test_new():\n    pass\n")
    calls: list[list[str]] = []

    def runner(command: list[str], **_: object) -> tuple[bool, float, str]:
        calls.append(command)
        return (command[2] != "lint-imports", 0.1, "contract broken")

    assert gate.run_check(repo, runner=runner) == 1
    names = [line.split(":")[0] for line in capsys.readouterr().out.splitlines()]
    assert names[:5] == [
        "[check] ruff check",
        "[check] ruff format",
        "[check] import contracts",
    ] + [
        "[check] mypy",
        "[check] pytest",
    ]
    pytest_command = calls[-1]
    assert pytest_command[-4:] == [*gate_select.ALWAYS, "tests/unit/test_new.py"]
    assert "no:cacheprovider" not in pytest_command
    assert calls[3][:6] == list(gate.FULL_GATE_MYPY_COMMAND)
    assert git(repo, "status", "--porcelain") == "?? tests/"


def test_check_all_runs_the_fast_tier(repo: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **_: object) -> tuple[bool, float, str]:
        calls.append(command)
        return (True, 0.1, "")

    assert gate.run_check(repo, run_all=True, runner=runner) == 0
    assert calls[-1][-2:] == ["-m", gate.FAST_TIER_MARKERS]


def test_check_cli_flags() -> None:
    args = gate.build_parser().parse_args(["check", "--all", "--base", "main"])
    assert args.all is True and args.base == "main"


def test_last_failures_survive_renamed_cases_and_drop_removed_tests(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_a.py",
        "class TestA:\n    def test_a(self, case):\n        pass\n",
    )
    _write(
        tmp_path,
        str(gate_select.LAST_FAILED),
        json.dumps(
            {
                "tests/unit/test_a.py::TestA::test_a[old case name]": True,
                "tests/unit/test_a.py::TestA::test_a[other]": True,
                "tests/unit/test_a.py::test_removed": True,
                "tests/unit/test_a.py": True,
            }
        ),
    )
    selection = gate_select.select(tmp_path, None)
    assert selection.last_failed == ("tests/unit/test_a.py::TestA::test_a",)
