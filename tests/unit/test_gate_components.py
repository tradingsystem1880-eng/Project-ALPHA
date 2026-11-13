"""The CI component definitions and the comparison base the local check and mutation share."""

import json
from pathlib import Path

import gate
import gate_components
import pytest

from tests.unit._harness_support import git

ROOT = Path(__file__).resolve().parents[2]
STATIC = [
    "uv lock",
    "uv sync",
    "ruff check",
    "ruff format",
    "import contracts",
    "mypy",
    "harness lint",
    "harness doctor",
    "semgrep",
    "semgrep contracts",
    "openapi freshness",
    "openapi authority",
    "build wheels",
    "wheel smoke",
]
BACKEND = [*STATIC, "pytest + coverage"]


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
    harness = [rel for rel in gate.HARNESS_SCRIPTS if (ROOT / rel).is_file()]
    assert by_name["mypy"] == [*gate.FULL_GATE_MYPY_COMMAND, *harness]
    assert by_name["pytest + coverage"] == [
        *("uv", "run", "pytest", "-q", "-n", "auto", "--dist", "worksteal"),
        *("-m", "not network and not slow_oracle", "--cov", "--cov-report="),
    ]
    assert all(cwd == ROOT for _, cwd, _ in commands)
    assert sum(command[:3] == ["uv", "run", "mypy"] for command in by_name.values()) == 1
    quant_steps = gate_components.component_steps(ROOT, "backend-quant", context={"paths": paths})
    assert [n for n, _, _ in quant_steps] == ["uv sync", *(quant if quant_expected else [])]
    static = gate_components.component_steps(ROOT, "backend-static")
    assert [name for name, _, _ in static] == STATIC


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
    assert by_name["browser"] == [
        *("npm", "run", "test:e2e:built", "--", "--viewports", "reference")
    ]
    full = {name: c for name, _, c in gate_components.component_steps(ROOT, "frontend-full")}
    assert full["browser"][-2:] == ["--viewports", "all"]
    assert {k: v for k, v in full.items() if k != "browser"} == {
        k: v for k, v in by_name.items() if k != "browser"
    }
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

    def steps(
        root: Path, name: str, *, context: object = None, shard: object = None
    ) -> list[gate_components.Step]:
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


def test_shards_cover_every_test_file_exactly_once() -> None:
    files = gate_components.collected_test_files(ROOT)
    assert "tests/unit/test_gate_components.py" in files
    assert "tests/oracles/test_differential_runs_test.py" in files
    for total in (1, 3, 4):
        shards = [gate_components.shard_paths(ROOT, i, total) for i in range(1, total + 1)]
        flat = [path for shard in shards for path in shard]
        assert sorted(flat) == files and len(flat) == len(set(flat))
        assert all(shards)
    assert gate_components.shard_paths(ROOT, 2, 4) == gate_components.shard_paths(ROOT, 2, 4)


def test_shard_command_is_the_ci_pytest_run_over_one_shard() -> None:
    steps = gate_components.component_steps(ROOT, "backend-tests", shard=(2, 4))
    assert [name for name, _, _ in steps] == ["uv sync", "pytest shard 2/4"]
    command = steps[1][2]
    shard = gate_components.shard_paths(ROOT, 2, 4)
    assert command == [*gate_components.pytest_command(shard), "--junitxml=pytest-shard-2.xml"]
    assert "--cov" in command and "not network and not slow_oracle" in command


@pytest.mark.parametrize("bad", ["0/4", "5/4", "x/4", "4"])
def test_shard_spec_rejects_out_of_range(bad: str) -> None:
    with pytest.raises(SystemExit):
        gate.build_parser().parse_args(["component", "backend-tests", "--shard", bad])


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["docs/notes.md"], {"qlib": False, "literature": False, "eval": True}),
        (["apps/alpha-web/frontend/src/App.tsx"], {"qlib": False, "literature": False}),
        (["workers/literature/src/x.py"], {"qlib": False, "literature": True, "eval": False}),
        (["apps/alpha-cli/src/alpha_cli/x.py"], {"qlib": True, "literature": False}),
        (["scripts/gate_components.py"], {"qlib": True, "literature": True, "eval": True}),
        ([".github/workflows/ci.yml"], {"qlib": True, "literature": True, "eval": True}),
        (["workers/qlib/pyproject.toml"], {"qlib": True, "literature": False, "eval": False}),
        (["tools/alpha-eval/pyproject.toml"], {"qlib": False, "eval": True}),
        (None, {"qlib": True, "literature": True, "eval": True, "quant": True}),
        ([], {"qlib": False, "literature": False, "eval": False, "quant": False}),
    ],
)
def test_path_filters_select_conditional_jobs(
    paths: list[str] | None, expected: dict[str, bool]
) -> None:
    selected = gate_components.ci_changes(ROOT, {"paths": paths})
    assert set(selected) == {"qlib", "literature", "eval", "quant"}
    assert {name: selected[name] for name in expected} == expected


def test_push_runs_every_path_job_but_quant_keeps_its_own_rule() -> None:
    selected = gate_components.ci_changes(ROOT, {"paths": ["README.md"]}, run_all=True)
    assert selected == {"qlib": True, "literature": True, "eval": True, "quant": False}
    quant = gate_components.ci_changes(
        ROOT, {"paths": ["packages/alpha-validation/src/alpha_validation/dsr.py"]}
    )
    assert quant["quant"] is True


def test_changes_cli_prints_github_output_lines(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    monkeypatch.setenv("ALPHA_GATE_BASE", "missing-base")
    assert gate.main(["changes"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["eval=true", "literature=true", "qlib=true", "quant=false"]


def test_coverage_refuses_missing_shard_data(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / ".coverage.shard-1").write_text("")
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: pytest.fail("must not run"))
    assert gate_components.run_coverage(repo, shards=2, base="HEAD") == 1
    assert ".coverage.shard-2" in capsys.readouterr().out


def test_coverage_reports_global_figure_and_gates_changed_lines(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for index in (1, 2):
        (repo / f".coverage.shard-{index}").write_text("")
    calls: list[list[str]] = []

    def runner(command: list[str], **_: object) -> tuple[bool, float, str]:
        calls.append(command)
        if "diff-cover" in command:
            return False, 0.1, "Coverage: 50%"
        return True, 0.1, "92.50\nCombined 4 files\n" if "--format=total" in command else ""

    monkeypatch.setattr(gate, "_env_runner", runner)
    summary = tmp_path / "summary.md"
    assert gate_components.run_coverage(repo, shards=2, base="abc", summary=summary) == 1
    assert "92.50%" in summary.read_text()
    diff = next(command for command in calls if "diff-cover" in command)
    assert diff[diff.index("--compare-branch") + 1] == "abc"
    assert diff[diff.index("--config-file") + 1] == "pyproject.toml"
    assert gate_components.run_coverage(repo, shards=2, base=None) == 0


def test_changed_line_floor_lives_in_pyproject_and_is_guarded() -> None:
    import tomllib

    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert config["tool"]["diff_cover"]["fail_under"] == 85
    assert "fail_under" not in config["tool"]["coverage"]["report"]
    assert gate.harness_metrics(ROOT)["coverage_fail_under"] == 85
