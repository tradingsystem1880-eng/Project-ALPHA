"""Agent-neutral gate coverage and conservative impact selection."""

from pathlib import Path

import gate
import gate_components
import pytest

from tests.unit._harness_support import git


def test_unknown_base_requires_every_component() -> None:
    assert gate_components.required_components(None) == set(gate_components.COMPONENTS)


def test_shared_configuration_requires_every_component() -> None:
    assert gate_components.required_components(["pyproject.toml"]) == set(
        gate_components.COMPONENTS
    )


def test_worker_change_includes_worker_and_repository_checks() -> None:
    required = gate_components.required_components(["workers/literature/src/worker.py"])
    assert {"backend", "literature", "atlas"} <= required


def test_benchmark_change_requires_eval_component_only_with_repository_checks() -> None:
    required = gate_components.required_components(["tools/alpha-eval/src/alpha_eval/score.py"])
    assert required == {"backend", "atlas", "eval"}


def test_eval_component_runs_its_own_offline_suite() -> None:
    commands = gate_components.component_steps(Path.cwd(), "eval")
    assert all(cwd.name == "alpha-eval" for _, cwd, _ in commands)
    assert ["uv", "run", "pytest", "-q", "-m", "not network"] in [c for _, _, c in commands]


def test_component_cli_accepts_every_registered_component() -> None:
    parser = gate.build_parser()
    for name in gate_components.COMPONENTS:
        assert parser.parse_args(["component", name]).name == name


def test_frontend_commands_include_types_browser_and_freshness() -> None:
    commands = gate_components.component_steps(Path.cwd(), "frontend")
    flattened = "\n".join(" ".join(command) for _, _, command in commands)
    assert "tsc -b --pretty false" in flattened
    assert "test:coverage" in flattened
    assert "test:e2e" in flattened
    assert "generate:api" in flattened


def test_component_definitions_have_stable_digest() -> None:
    first = gate_components.definition_hash(Path.cwd(), "literature")
    assert len(first) == 64
    assert first == gate_components.definition_hash(Path.cwd(), "literature")


def test_component_failure_overwrites_old_success(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        gate_components, "component_steps", lambda root, name: [("test", root, ["test"])]
    )
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (True, 0.1, ""))
    assert gate_components.run_component(repo, "literature") == 0
    gate.write_stamp(repo, "full", steps=[], duration=0)
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (False, 0.1, "failure"))
    assert gate_components.run_component(repo, "literature") == 1
    assert not gate.stamp_is_valid(repo, "full")
    receipt = gate.read_json(repo / gate.STATE_DIR / "component-literature.json")
    assert receipt is not None and receipt["ok"] is False


def test_change_selection_includes_committed_and_untracked(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "committed.py").write_text("x = 1\n")
    git(repo, "add", "committed.py")
    git(repo, "commit", "-m", "test: committed change")
    (repo / "new.py").write_text("y = 1\n")
    assert {"committed.py", "new.py"} <= set(gate_components.changed_paths(repo, base) or [])


def test_component_failure_keeps_traceback_before_long_coverage_report(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    failure = "AssertionError: cancellation did not finish\n" + "coverage row\n" * 1000
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (False, 0.1, failure))
    assert gate_components.run_component(repo, "backend", steps=[("tests", repo, ["pytest"])]) == 1
    assert failure in capsys.readouterr().out


def test_parallel_coverage_shards_do_not_change_repo_tree_hash(repo: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    (repo / ".gitignore").write_text((project_root / ".gitignore").read_text())
    before = gate.compute_tree_hash(repo)
    shard = repo / ".coverage.machine.pid123.random"
    shard.write_bytes(b"temporary parallel coverage data")
    assert gate.compute_tree_hash(repo) == before
    shard.unlink()
    assert gate.compute_tree_hash(repo) == before


def test_unknown_change_base_does_not_report_empty(repo: Path) -> None:
    assert gate_components.changed_paths(repo, "missing-base") is None


def test_backend_semgrep_does_not_depend_on_dirty_checkout() -> None:
    commands = gate_components.component_steps(Path.cwd(), "backend")
    semgrep = next(command for name, _, command in commands if name == "semgrep")
    assert "--changed" not in semgrep


def test_legacy_audit_remains_readable_without_copying_tokens(repo: Path) -> None:
    legacy = repo / gate.LEGACY_STATE_DIR
    legacy.mkdir(parents=True)
    (legacy / gate.AUDIT_FILE).write_text('{"event": "historic", "detail": "retained"}\n')
    before = (legacy / gate.AUDIT_FILE).read_bytes()
    assert gate.read_audit(repo, legacy=True)[0]["event"] == "historic"
    assert gate.verify_audit_chain(repo, legacy=True)[0]
    assert gate.read_audit(repo) == []
    assert (legacy / gate.AUDIT_FILE).read_bytes() == before


def test_component_freezes_definition_before_execution(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def steps(root: Path, name: str) -> list[gate_components.Step]:
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


@pytest.mark.parametrize("during_definition", [False, True])
def test_interruption_replaces_prior_component_success(
    repo: Path, monkeypatch: pytest.MonkeyPatch, during_definition: bool
) -> None:
    receipt_path = repo / gate.STATE_DIR / "component-literature.json"
    gate.write_stamp(repo, "full", steps=[], duration=0)
    gate.write_json_atomic(receipt_path, {"ok": True, "status": "passed"})

    def interrupted(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(
        gate_components, "component_steps", lambda root, name: [("test", root, ["test"])]
    )
    if during_definition:
        monkeypatch.setattr(gate_components, "component_steps", interrupted)
    else:
        monkeypatch.setattr(gate, "_env_runner", interrupted)
    with pytest.raises(KeyboardInterrupt):
        gate_components.run_component(repo, "literature")
    receipt = gate.read_json(receipt_path)
    assert receipt is not None and receipt["ok"] is False
    assert receipt["status"] == "started"
    assert not gate.stamp_is_valid(repo, "full")


def test_component_tree_change_cannot_pass(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gate_components, "component_steps", lambda root, name: [("test", root, ["test"])]
    )

    def mutate_tree(*args: object, **kwargs: object) -> tuple[bool, float, str]:
        (repo / "tracked.py").write_text("changed during gate\n")
        return True, 0.1, ""

    monkeypatch.setattr(gate, "_env_runner", mutate_tree)
    assert gate_components.run_component(repo, "literature") == 1
    receipt = gate.read_json(repo / gate.STATE_DIR / "component-literature.json")
    assert receipt is not None
    assert receipt["status"] == "failed" and receipt["stable_tree"] is False


@pytest.mark.parametrize(
    "corruption",
    [None, "definition_hash", "status", "stable_tree", "steps", "command", "step_ok"],
)
def test_full_validates_complete_frozen_receipts(
    repo: Path, monkeypatch: pytest.MonkeyPatch, corruption: str | None
) -> None:
    calls = []

    def steps(root: Path, name: str) -> list[gate_components.Step]:
        calls.append(name)
        return [("test", root, [name])]

    monkeypatch.setattr(gate_components, "component_steps", steps)
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (True, 0.1, ""))
    original = gate_components.run_component

    def run(root: Path, name: str, *, steps: list[gate_components.Step] | None = None) -> int:
        result = original(root, name, steps=steps)
        path = root / gate.STATE_DIR / f"component-{name}.json"
        receipt = gate.read_json(path)
        assert receipt is not None
        if corruption == "command":
            receipt["steps"][0]["command"] = ["different"]
        elif corruption == "step_ok":
            receipt["steps"][0]["ok"] = False
        elif corruption:
            receipt[corruption] = {
                "definition_hash": "wrong",
                "status": "started",
                "stable_tree": False,
                "steps": [],
            }[corruption]
        gate.write_json_atomic(path, receipt)
        return result

    monkeypatch.setattr(gate_components, "run_component", run)
    assert gate_components.run_full(repo) == (0 if corruption is None else 1)
    assert gate.stamp_is_valid(repo, "full") is (corruption is None)
    assert calls == list(gate_components.COMPONENTS)
