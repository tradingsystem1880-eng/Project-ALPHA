"""Agent-neutral gate coverage and conservative impact selection."""

import json
import sys
from pathlib import Path

import gate
import gate_components
import pytest

from tests.unit._harness_support import git


@pytest.mark.parametrize(
    ("paths", "quant_expected"),
    [
        ([], False),
        (["packages/alpha-research/src/alpha_research/weekly_diagnostic.py"], True),
        (None, True),
    ],
)
def test_backend_checks_manual_before_expensive_steps(
    monkeypatch: pytest.MonkeyPatch,
    paths: list[str] | None,
    quant_expected: bool,
) -> None:
    monkeypatch.setattr(gate_components, "comparison_context", lambda _root, **_: {"paths": paths})
    root = Path.cwd()
    commands = gate_components.component_steps(root, "backend")
    preflight = (
        "manual preflight",
        root,
        [
            "uv",
            "run",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/unit/test_claude_md_relocation.py::TestCurrentManual::test_core_is_small",
        ],
    )
    assert commands[:3] == [
        ("uv lock", root, ["uv", "lock", "--check"]),
        ("uv sync", root, ["uv", "sync", "--locked"]),
        preflight,
    ]
    previous = [
        (name, root, [arg for arg in command if name != "semgrep" or arg != "--changed"])
        for name, command in gate.gate_steps("full", root)
        if name not in {"slow oracles", "mutation gate"}
    ]
    quant_steps = {"slow oracles", "mutation gate"}
    assert [
        step for step in commands if step[0] not in quant_steps | {"manual preflight"}
    ] == previous
    names = [name for name, _, _ in commands]
    if quant_expected:
        assert names[-2:] == ["slow oracles", "mutation gate"]
    else:
        assert not quant_steps.intersection(names)


@pytest.mark.parametrize("combined_bytes", [6_000, 6_001])
def test_manual_budget_decides_preflight_receipt(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    combined_bytes: int,
) -> None:
    from tests.unit import test_claude_md_relocation as manual_tests

    (repo / "CLAUDE.md").write_bytes(b"x" * 6_000)
    (repo / "AGENTS.md").write_bytes(b"x" * (combined_bytes - 6_000))
    monkeypatch.setattr(manual_tests, "ROOT", repo)
    commands = gate_components.component_steps(repo, "backend")
    seen: list[list[str]] = []

    def run(command: list[str], *, cwd: Path) -> tuple[bool, float, str]:
        seen.append(command)
        if any("test_core_is_small" in arg for arg in command):
            try:
                manual_tests.TestCurrentManual().test_core_is_small()
            except AssertionError:
                return False, 0.01, "manual exceeds the existing 6000-byte limit"
        return True, 0.01, ""

    monkeypatch.setattr(gate, "_env_runner", run)
    gate.write_stamp(repo, "full", steps=[], duration=0)
    valid = combined_bytes <= 6_000
    assert gate_components.run_component(repo, "backend", steps=commands) == (0 if valid else 1)
    assert len(seen) == (len(commands) if valid else 3)
    assert not gate.stamp_is_valid(repo, "full")
    receipt = gate.read_json(repo / gate.STATE_DIR / "component-backend.json")
    assert receipt and receipt["status"] == ("passed" if valid else "failed")
    assert receipt["ok"] is valid


def test_old_backend_receipt_without_preflight_cannot_match() -> None:
    root = Path.cwd()
    commands = gate_components.component_steps(root, "backend")
    previous = [step for step in commands if step[0] != "manual preflight"]
    receipt = {
        "schema_version": 1,
        "component": "backend",
        "tree_hash": "same-tree",
        "definition_hash": gate_components._steps_hash(root, previous),
        "status": "passed",
        "ok": True,
        "stable_tree": True,
        "steps": [
            {
                "name": name,
                "command": cmd,
                "cwd": str(cwd.relative_to(root)),
                "ok": True,
                "seconds": 0.1,
            }
            for name, cwd, cmd in previous
        ],
    }
    assert not gate_components._receipt_matches(root, "backend", commands, "same-tree", receipt)


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


def test_frontend_build_checks_types_once_before_browser_and_freshness() -> None:
    commands = gate_components.component_steps(Path.cwd(), "frontend")
    names = [name for name, _, _ in commands]
    by_name = {name: command for name, _, command in commands}
    scripts = json.loads((Path.cwd() / "apps/alpha-web/frontend/package.json").read_text())[
        "scripts"
    ]
    assert by_name["build + types"] == ["npm", "run", "build"]
    assert scripts["build"].startswith("tsc -b && ")
    assert scripts["test:e2e:built"] == "playwright test"
    assert scripts["test:e2e"] == "npm run build && playwright test"
    assert by_name["browser"] == ["npm", "run", "test:e2e:built"]
    assert names.index("build + types") < names.index("browser") < names.index("SPA freshness")
    assert sum("tsc" in arg for _, _, command in commands for arg in command) == 0
    assert by_name["coverage"] == ["npm", "run", "test:coverage"]
    assert by_name["API generation"] == ["npm", "run", "generate:api"]
    assert "API freshness" in names


def test_component_definitions_have_stable_digest() -> None:
    first = gate_components.definition_hash(Path.cwd(), "literature")
    assert len(first) == 64
    assert first == gate_components.definition_hash(Path.cwd(), "literature")


def test_component_failure_overwrites_old_success(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        gate_components, "component_steps", lambda root, name, **_: [("test", root, ["test"])]
    )
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (True, 0.1, ""))
    assert gate_components.run_component(repo, "literature") == 0
    gate.write_stamp(repo, "full", steps=[], duration=0)
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (False, 0.1, "failure"))
    assert gate_components.run_component(repo, "literature") == 1
    assert not gate.stamp_is_valid(repo, "full")
    receipt = gate.read_json(repo / gate.STATE_DIR / "component-literature.json")
    assert receipt is not None and receipt["ok"] is False


def test_empty_component_definition_cannot_be_passed_or_stamped_full(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate_components, "component_steps", lambda root, name, **_: [])
    monkeypatch.setattr(
        gate,
        "_env_runner",
        lambda *a, **kw: pytest.fail("an empty component must not run a command"),
    )
    gate.write_stamp(repo, "full", steps=[], duration=0)

    assert gate_components.run_full(repo) == 1
    assert not gate.stamp_is_valid(repo, "full")
    receipt = gate.read_json(repo / gate.STATE_DIR / "component-backend.json")
    assert receipt is not None
    assert receipt["status"] == "failed"
    assert receipt["ok"] is False
    assert receipt["stable_tree"] is True
    assert receipt["steps"] == []


def test_empty_component_receipt_cannot_match() -> None:
    root = Path.cwd()
    receipt = {
        "schema_version": 1,
        "component": "literature",
        "tree_hash": "same-tree",
        "definition_hash": gate_components._steps_hash(root, []),
        "status": "passed",
        "ok": True,
        "stable_tree": True,
        "steps": [],
    }

    assert not gate_components._receipt_matches(root, "literature", [], "same-tree", receipt)


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
    assert gate_components.comparison_context(repo, "missing-base")["paths"] is None


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
        gate_components, "component_steps", lambda root, name, **_: [("test", root, ["test"])]
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
        gate_components, "component_steps", lambda root, name, **_: [("test", root, ["test"])]
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

    def steps(root: Path, name: str, *, context: object = None) -> list[gate_components.Step]:
        calls.append(name)
        return [("test", root, [name])]

    monkeypatch.setattr(gate_components, "component_steps", steps)
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (True, 0.1, ""))
    original = gate_components._run_component

    def run(
        root: Path,
        name: str,
        *,
        steps: list[gate_components.Step] | None = None,
        context: dict[str, object] | None = None,
    ) -> int:
        result = original(root, name, steps=steps, context=context)
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

    monkeypatch.setattr(gate_components, "_run_component", run)
    assert gate_components.run_full(repo) == (0 if corruption is None else 1)
    assert gate.stamp_is_valid(repo, "full") is (corruption is None)
    assert calls == list(gate_components.COMPONENTS)


def _stamped_base(repo: Path) -> str:
    """Two commits with origin/main at the second, so the base can move without HEAD."""
    (repo / "tracked.py").write_text("x = 2\n")
    git(repo, "commit", "--quiet", "-am", "chore: second")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return git(repo, "rev-parse", "HEAD")


def _simple_gate(monkeypatch: pytest.MonkeyPatch, command: list[str] | None = None) -> None:
    monkeypatch.delenv("ALPHA_GATE_BASE", raising=False)
    monkeypatch.setattr(
        gate_components,
        "component_steps",
        lambda root, name, **_: [("test", root, command or ["test"])],
    )
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (True, 0.1, ""))


def test_comparison_context_binds_reference_commit_and_merge_base(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALPHA_GATE_BASE", raising=False)
    head = _stamped_base(repo)
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
    assert gate_components.binding(explicit) == gate_components.binding(context)


@pytest.mark.parametrize("reference", ["", "does-not-exist", "-h"])
def test_unresolvable_reference_selects_conservatively(
    repo: Path, monkeypatch: pytest.MonkeyPatch, reference: str
) -> None:
    _stamped_base(repo)
    monkeypatch.setenv("ALPHA_GATE_BASE", reference)
    context = gate_components.comparison_context(repo)
    assert context["reference"] == reference
    assert context["resolved_base"] is None and context["merge_base"] is None
    assert context["selection_mode"] == "conservative_fallback" and context["paths"] is None


def test_detached_head_is_exact_and_unborn_head_is_conservative(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALPHA_GATE_BASE", raising=False)
    head = _stamped_base(repo)
    git(repo, "checkout", "--quiet", "--detach")
    detached = gate_components.comparison_context(repo)
    assert detached["merge_base"] == head and detached["selection_mode"] == "exact_diff"
    git(repo, "checkout", "--quiet", "--orphan", "unborn")
    unborn = gate_components.comparison_context(repo)
    assert unborn["resolved_base"] == head and unborn["merge_base"] is None
    assert unborn["selection_mode"] == "conservative_fallback"


def test_run_full_records_one_comparison_in_stamp_and_receipts(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _simple_gate(monkeypatch)
    _stamped_base(repo)
    expected = gate_components.binding(gate_components.comparison_context(repo))
    assert gate_components.run_full(repo) == 0
    stamp = gate.read_json(repo / gate.STATE_DIR / gate.STAMP_FILE)
    assert stamp is not None and stamp["comparison"] == expected
    for name in gate_components.COMPONENTS:
        receipt = gate.read_json(repo / gate.STATE_DIR / f"component-{name}.json")
        assert receipt is not None
        assert receipt["comparison"] == expected
        assert receipt["interpreter"] == sys.executable
    assert gate_components.full_stamp_usable(repo, stamp) == (True, "")


def test_comparison_change_during_full_writes_no_stamp(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _simple_gate(monkeypatch)
    _stamped_base(repo)
    moved = git(repo, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "moved base")

    def fetch_during_gate(*args: object, **kwargs: object) -> tuple[bool, float, str]:
        git(repo, "update-ref", "refs/remotes/origin/main", moved)
        return True, 0.1, ""

    monkeypatch.setattr(gate, "_env_runner", fetch_during_gate)
    assert gate_components.run_full(repo) == 1
    assert gate.read_json(repo / gate.STATE_DIR / gate.STAMP_FILE) is None


@pytest.mark.parametrize(
    ("change", "usable"),
    [
        ("none", True),
        ("unrelated_refs", True),
        ("explicit_same_reference", True),
        ("moved_base_same_merge_base", False),
        ("older_merge_base", False),
        ("other_reference_same_commit", False),
        ("missing_receipt", False),
        ("receipt_comparison_tampered", False),
        ("forged_null_comparison", False),
        ("receipt_without_interpreter", False),
        ("changed_command", False),
    ],
)
def test_full_stamp_usable_binds_base_and_definitions(
    repo: Path, monkeypatch: pytest.MonkeyPatch, change: str, usable: bool
) -> None:
    _simple_gate(monkeypatch)
    _stamped_base(repo)
    first = git(repo, "rev-parse", "HEAD~1")
    assert gate_components.run_full(repo) == 0
    state = repo / gate.STATE_DIR
    receipt_path = state / "component-eval.json"
    receipt = gate.read_json(receipt_path)
    stamp = gate.read_json(state / gate.STAMP_FILE)
    assert receipt is not None and stamp is not None
    if change == "unrelated_refs":
        git(repo, "update-ref", "refs/remotes/origin/feature", first)
        git(repo, "branch", "other", first)
        git(repo, "tag", "v-test", first)
    elif change == "explicit_same_reference":
        monkeypatch.setenv("ALPHA_GATE_BASE", "origin/main")
    elif change == "moved_base_same_merge_base":
        moved = git(repo, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "ahead")
        git(repo, "update-ref", "refs/remotes/origin/main", moved)
        assert (
            gate_components.comparison_context(repo)["merge_base"]
            == stamp["comparison"]["merge_base"]
        )
    elif change == "older_merge_base":
        git(repo, "update-ref", "refs/remotes/origin/main", first)
    elif change == "other_reference_same_commit":
        monkeypatch.setenv("ALPHA_GATE_BASE", "refs/remotes/origin/main")
    elif change == "missing_receipt":
        receipt_path.unlink()
    elif change == "receipt_comparison_tampered":
        receipt["comparison"] = {**receipt["comparison"], "merge_base": first}
        gate.write_json_atomic(receipt_path, receipt)
    elif change == "forged_null_comparison":
        stamp["comparison"] = None
        for name in gate_components.COMPONENTS:
            path = state / f"component-{name}.json"
            forged = gate.read_json(path)
            assert forged is not None
            forged.pop("comparison")
            gate.write_json_atomic(path, forged)
    elif change == "receipt_without_interpreter":
        receipt.pop("interpreter")
        gate.write_json_atomic(receipt_path, receipt)
    elif change == "changed_command":
        _simple_gate(monkeypatch, ["other"])
    ok, reason = gate_components.full_stamp_usable(repo, stamp)
    assert ok is usable
    assert bool(reason) is not usable


def test_interpreter_path_is_portable_but_other_arguments_still_bind(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stamped_base(repo)
    monkeypatch.delenv("ALPHA_GATE_BASE", raising=False)
    extra: list[str] = []
    monkeypatch.setattr(
        gate_components,
        "component_steps",
        lambda root, name, **_: [("lint", root, [sys.executable, "lint.py", *extra])],
    )
    monkeypatch.setattr(gate, "_env_runner", lambda *a, **kw: (True, 0.1, ""))
    monkeypatch.setattr(sys, "executable", "/gate/venv/bin/python")
    assert gate_components.run_full(repo) == 0
    stamp = gate.read_json(repo / gate.STATE_DIR / gate.STAMP_FILE)
    assert stamp is not None
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    assert gate_components.full_stamp_usable(repo, stamp) == (True, "")
    extra.append("--fix")
    assert gate_components.full_stamp_usable(repo, stamp)[0] is False


def test_check_full_command_applies_the_commit_time_stamp_check(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _simple_gate(monkeypatch)
    _stamped_base(repo)
    monkeypatch.chdir(repo)
    assert gate_components.run_full(repo) == 0
    assert gate.main(["check", "--tier", "full"]) == 0
    moved = git(repo, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "fetched")
    git(repo, "update-ref", "refs/remotes/origin/main", moved)
    capsys.readouterr()
    assert gate.main(["check", "--tier", "full"]) == 1
    assert "comparison base" in capsys.readouterr().out
    gate.write_stamp(repo, "full", steps=[], duration=0)
    assert gate.main(["check", "--tier", "full"]) == 1, "legacy stamp without a binding"
    assert gate.main(["check", "--tier", "fast"]) == 0, "tree-only fast check unchanged"


PRIOR_STAMP = b'{"tier": "full"}'


def _prior_evidence(repo: Path) -> dict[str, bytes]:
    state = repo / gate.STATE_DIR
    state.mkdir(parents=True, exist_ok=True)
    evidence = {
        gate.STATE_DIR / gate.STAMP_FILE: PRIOR_STAMP,
        gate.STATE_DIR / "component-eval.json": b'{"component": "eval"}',
        gate.STATE_DIR / gate.REVIEW_VERDICT_FILE: b'{"verdict": "BLOCK"}',
        Path(".coverage"): b"coverage-data",
    }
    for path, data in evidence.items():
        (repo / path).write_bytes(data)
    (state / "owner-token.txt").write_bytes(b"private")
    return {path.as_posix(): data for path, data in evidence.items()}


def _checkpoints(repo: Path) -> list[Path]:
    directory = repo / gate_components.CHECKPOINT_DIR
    return sorted(directory.glob("pre-run-*")) if directory.exists() else []


def _run_route(route: str, repo: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, list[str]]:
    """Run one supported gate entry route; each step first proves the prior stamp was kept."""
    _simple_gate(monkeypatch)
    calls: list[str] = []

    def runner(*_args: object, **_kwargs: object) -> tuple[bool, float, str]:
        calls.append(route)
        assert len(_checkpoints(repo)) == 1, "evidence is preserved before any step runs"
        return True, 0.1, ""

    monkeypatch.setattr(gate, "_env_runner", runner)
    if route == "full":
        return gate_components.run_full(repo), calls
    if route == "component":
        return gate_components.run_component(repo, "eval"), calls
    return gate.run_gate(repo, "fast", runner=runner), calls


ROUTES = ["full", "component", "fast"]


@pytest.mark.parametrize("route", ROUTES)
def test_every_gate_route_preserves_prior_evidence_once_before_replacing_it(
    repo: Path, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    _stamped_base(repo)
    prior = _prior_evidence(repo)
    code, calls = _run_route(route, repo, monkeypatch)
    assert code == 0 and calls
    if route == "full":
        assert len(calls) == len(gate_components.COMPONENTS)
    [checkpoint] = _checkpoints(repo)  # one snapshot, even for six-component dispatch
    rows = (checkpoint / "MANIFEST.tsv").read_text().splitlines()
    assert {row.split("\t")[0] for row in rows} == set(prior)
    assert not (checkpoint / ".alpha/state/owner-token.txt").exists()
    for name, data in prior.items():
        assert (checkpoint / name).read_bytes() == data
        assert not (checkpoint / name).stat().st_mode & 0o222


def test_identical_evidence_reuses_the_verified_checkpoint(repo: Path) -> None:
    _prior_evidence(repo)
    assert gate_components.preserve_prior_evidence(repo)
    first = _checkpoints(repo)
    assert gate_components.preserve_prior_evidence(repo)
    assert len(first) == 1 and _checkpoints(repo) == first


@pytest.mark.parametrize("route", ROUTES)
def test_gate_route_without_prior_evidence_creates_no_checkpoint(
    repo: Path, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    _stamped_base(repo)
    monkeypatch.setattr(gate_components, "PRESERVED_EVIDENCE", ())
    _simple_gate(monkeypatch)
    calls: list[str] = []

    def runner(*_args: object, **_kwargs: object) -> tuple[bool, float, str]:
        calls.append(route)
        return True, 0.1, ""

    monkeypatch.setattr(gate, "_env_runner", runner)
    runs = {
        "full": lambda: gate_components.run_full(repo),
        "component": lambda: gate_components.run_component(repo, "eval"),
        "fast": lambda: gate.run_gate(repo, "fast", runner=gate._env_runner),
    }
    assert runs[route]() == 0 and calls and _checkpoints(repo) == []


@pytest.mark.parametrize("fault", ["corrupt_copy", "source_changes", "tampered_checkpoint"])
@pytest.mark.parametrize("route", ROUTES)
def test_preservation_failure_stops_every_route_before_any_overwrite(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    route: str,
    fault: str,
) -> None:
    _stamped_base(repo)
    _prior_evidence(repo)
    stamp = repo / gate.STATE_DIR / gate.STAMP_FILE
    if fault == "tampered_checkpoint":
        assert gate_components.preserve_prior_evidence(repo)
        [checkpoint] = _checkpoints(repo)
        copy = checkpoint / ".coverage"
        copy.chmod(0o644)
        copy.write_bytes(b"tampered")
    else:
        original = Path.write_bytes

        def faulty(path: Path, data: bytes) -> int:
            written = original(path, data)
            if path.name == gate.STAMP_FILE and ".incomplete-" in str(path):
                original(path if fault == "corrupt_copy" else stamp, b"changed")
            return written

        monkeypatch.setattr(Path, "write_bytes", faulty)
    before = _checkpoints(repo)
    receipt = (repo / gate.STATE_DIR / "component-eval.json").read_bytes()
    code, calls = _run_route(route, repo, monkeypatch)
    assert code == 1 and calls == []
    assert _checkpoints(repo) == before
    incomplete = list((repo / gate_components.CHECKPOINT_DIR).glob(".incomplete-*"))
    output = capsys.readouterr().out
    if fault == "tampered_checkpoint":
        assert incomplete == [] and "exists with different contents" in output
    else:  # the failed attempt's staging copy is retained and named, never cleaned up
        [kept] = incomplete
        assert f"incomplete copy kept at {kept.relative_to(repo)}" in output
    assert (repo / gate.STATE_DIR / "component-eval.json").read_bytes() == receipt
    if fault != "source_changes":
        assert stamp.read_bytes() == PRIOR_STAMP
