"""The CI component definitions and the comparison base the local check and mutation share."""

import json
from pathlib import Path

import gate
import gate_components
import pytest

from tests.unit._harness_support import git

ROOT = Path(__file__).resolve().parents[2]
BACKEND = [
    "uv lock",
    "uv sync",
    "ruff check",
    "ruff format",
    "import contracts",
    "mypy",
    "mypy harness",
    "harness lint",
    "semgrep",
    "semgrep contracts",
    "pytest + coverage",
    "openapi freshness",
    "openapi authority",
    "build wheels",
    "wheel smoke",
]


@pytest.mark.parametrize(
    ("paths", "quant_expected"),
    [
        ([], False),
        (["packages/alpha-research/src/alpha_research/weekly_diagnostic.py"], True),
        (None, True),
    ],
)
def test_backend_runs_the_ci_steps_and_quant_checks_only_when_quant_source_changed(
    monkeypatch: pytest.MonkeyPatch, paths: list[str] | None, quant_expected: bool
) -> None:
    monkeypatch.setattr(gate_components, "comparison_context", lambda _root, **_: {"paths": paths})
    commands = gate_components.component_steps(ROOT, "backend")
    names = [name for name, _, _ in commands]
    quant = ["slow oracles", "mutation gate"]
    assert names == BACKEND + (quant if quant_expected else [])
    by_name = {name: command for name, _, command in commands}
    assert by_name["mypy"] == list(gate.FULL_GATE_MYPY_COMMAND)
    assert by_name["pytest + coverage"] == [
        *("uv", "run", "pytest", "-q", "-n", "auto"),
        *("-m", "not network and not slow_oracle", "--cov"),
    ]
    assert all(cwd == ROOT for _, cwd, _ in commands)


def test_an_empty_component_refuses_to_pass(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gate,
        "_env_runner",
        lambda *a, **kw: pytest.fail("an empty component must not run a command"),
    )
    assert gate_components.run_component(repo, "literature", steps=[]) == 1


def test_components_write_no_state(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (True, 0.1, ""))
    assert gate_components.run_component(repo, "qlib", steps=[("t", repo, ["t"])]) == 0
    assert not (repo / ".alpha").exists()


def test_eval_component_runs_its_own_offline_suite() -> None:
    commands = gate_components.component_steps(ROOT, "eval")
    assert all(cwd.name == "alpha-eval" for _, cwd, _ in commands)
    assert ["uv", "run", "pytest", "-q", "-m", "not network"] in [c for _, _, c in commands]


def test_component_cli_accepts_every_registered_component() -> None:
    parser = gate.build_parser()
    for name in gate_components.COMPONENTS:
        assert parser.parse_args(["component", name]).name == name


def test_frontend_build_checks_types_once_before_browser_and_freshness() -> None:
    commands = gate_components.component_steps(ROOT, "frontend")
    names = [name for name, _, _ in commands]
    by_name = {name: command for name, _, command in commands}
    scripts = json.loads((ROOT / "apps/alpha-web/frontend/package.json").read_text())["scripts"]
    assert by_name["build + types"] == ["npm", "run", "build"]
    assert scripts["build"].startswith("tsc -b && ")
    assert scripts["test:e2e:built"] == (
        "uv run --offline --no-python-downloads --no-sync python "
        "../../../scripts/run_frontend_browser_lanes.py"
    )
    assert scripts["test:e2e"] == "npm run build && npm run test:e2e:built"
    assert by_name["browser"] == ["npm", "run", "test:e2e:built"]
    assert names.index("build + types") < names.index("browser") < names.index("SPA freshness")
    assert sum("tsc" in arg for _, _, command in commands for arg in command) == 0
    assert by_name["coverage"] == ["npm", "run", "test:coverage"]
    assert by_name["API generation"] == ["npm", "run", "generate:api"]
    assert "API freshness" in names


def test_change_selection_includes_committed_and_untracked(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "committed.py").write_text("x = 1\n")
    git(repo, "add", "committed.py")
    git(repo, "commit", "-m", "test: committed change")
    (repo / "new.py").write_text("y = 1\n")
    context = gate_components.comparison_context(repo, base)
    assert {"committed.py", "new.py"} <= set(context["paths"] or [])


def test_component_failure_keeps_traceback_before_long_coverage_report(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failure = "AssertionError: cancellation did not finish\n" + "coverage row\n" * 1000
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (False, 0.1, failure))
    assert gate_components.run_component(repo, "backend", steps=[("tests", repo, ["pytest"])]) == 1
    assert failure in capsys.readouterr().out


def test_unknown_change_base_does_not_report_empty(repo: Path) -> None:
    assert gate_components.comparison_context(repo, "missing-base")["paths"] is None


def test_backend_semgrep_does_not_depend_on_dirty_checkout() -> None:
    commands = gate_components.component_steps(ROOT, "backend")
    semgrep = next(command for name, _, command in commands if name == "semgrep")
    assert "--changed" not in semgrep


def test_component_freezes_definition_before_execution(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def steps(root: Path, name: str, *, context: object = None) -> list[gate_components.Step]:
        calls.append(name)
        return [("test", root, [f"test-{len(calls)}"])]

    commands: list[list[str]] = []

    def execute(command: list[str], *, cwd: Path) -> tuple[bool, float, str]:
        commands.append(command)
        return True, 0.1, ""

    monkeypatch.setattr(gate_components, "component_steps", steps)
    monkeypatch.setattr(gate, "_env_runner", execute)
    assert gate_components.run_component(repo, "literature") == 0
    assert calls == ["literature"]
    assert commands == [["test-1"]]


def _moved_base(repo: Path) -> str:
    """Two commits with origin/main at the second."""
    (repo / "tracked.py").write_text("x = 2\n")
    git(repo, "commit", "--quiet", "-am", "chore: second")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return git(repo, "rev-parse", "HEAD")


def test_comparison_context_binds_reference_commit_and_merge_base(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALPHA_GATE_BASE", raising=False)
    head = _moved_base(repo)
    (repo / "new.py").write_text("y = 1\n")
    context = gate_components.comparison_context(repo)
    assert context == {
        "reference": "origin/main",
        "reference_source": "default",
        "resolved_base": head,
        "merge_base": head,
        "selection_mode": "exact_diff",
        "paths": ["new.py"],
    }
    monkeypatch.setenv("ALPHA_GATE_BASE", "origin/main")
    explicit = gate_components.comparison_context(repo)
    assert explicit["reference_source"] == "environment"
    assert explicit["merge_base"] == context["merge_base"]


@pytest.mark.parametrize("reference", ["", "does-not-exist", "-h"])
def test_unresolvable_reference_selects_conservatively(
    repo: Path, monkeypatch: pytest.MonkeyPatch, reference: str
) -> None:
    _moved_base(repo)
    monkeypatch.setenv("ALPHA_GATE_BASE", reference)
    context = gate_components.comparison_context(repo)
    assert context["reference"] == reference
    assert context["resolved_base"] is None and context["merge_base"] is None
    assert context["selection_mode"] == "conservative_fallback" and context["paths"] is None


def test_detached_head_is_exact_and_unborn_head_is_conservative(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALPHA_GATE_BASE", raising=False)
    head = _moved_base(repo)
    git(repo, "checkout", "--quiet", "--detach")
    detached = gate_components.comparison_context(repo)
    assert detached["merge_base"] == head and detached["selection_mode"] == "exact_diff"
    git(repo, "checkout", "--quiet", "--orphan", "unborn")
    unborn = gate_components.comparison_context(repo)
    assert unborn["resolved_base"] == head and unborn["merge_base"] is None
    assert unborn["selection_mode"] == "conservative_fallback"
