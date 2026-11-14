"""Tests for the Claude Code harness gate runner (scripts/gate.py).

Covers quant-tier path selection, the harness doctor and weakening scanner, the
ADR awareness, plan checks and the quant-rigor sweeps. Everything here runs
against throwaway git repos.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import check_semgrep_contracts
import gate
import harness_awareness
import harness_quant
import pytest
import semgrep_runner

from tests.unit._harness_support import git as _git


class TestPathTiers:
    @pytest.mark.parametrize(
        "path",
        [
            "packages/alpha-validation/src/alpha_validation/metrics.py",
            "packages/alpha-research/src/alpha_research/power.py",
            "packages/alpha-cli-x/src/x/montecarlo_helpers.py",
            "packages/alpha-data/src/alpha_data/bootstrap_windows.py",
            "packages/alpha-backtest/src/x/cpcv_glue.py",
        ],
    )
    def test_quant_matches(self, path: str) -> None:
        assert gate.matches_quant(path)

    @pytest.mark.parametrize(
        "path",
        [
            "packages/alpha-backtest/src/alpha_backtest/engine.py",
            "apps/alpha-cli/src/alpha_cli/main.py",
            "tests/unit/test_bootstrap.py",
            "docs/notes.md",
            "apps/alpha-web/src/alpha_web/app.py",
        ],
    )
    def test_quant_rejects(self, path: str) -> None:
        assert not gate.matches_quant(path)


class TestDoctor:
    @pytest.fixture(autouse=True)
    def _no_machine_items(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """These tests cover the harness wiring; the machine section has its own tests."""
        monkeypatch.setattr(gate, "machine_readiness", lambda root: [])

    def test_doctor_fails_on_missing_settings(self, repo: Path) -> None:
        code, report = gate.doctor(repo)
        assert code != 0
        assert any(not check["ok"] for check in report["checks"])

    def test_doctor_passes_on_wired_repo(self, repo: Path) -> None:
        claude = repo / ".claude"
        claude.mkdir(exist_ok=True)
        _wire_minimal_harness(repo)
        code, report = gate.doctor(repo)
        failing = [check for check in report["checks"] if not check["ok"]]
        assert code == 0, failing

    def test_doctor_fails_when_a_hook_is_unwired(self, repo: Path) -> None:
        _wire_minimal_harness(repo)
        settings = json.loads((repo / ".claude" / "settings.json").read_text())
        settings["hooks"]["PreToolUse"][0]["hooks"] = [
            h
            for h in settings["hooks"]["PreToolUse"][0]["hooks"]
            if not h["command"].endswith("pre-mcp-guard")
        ]
        (repo / ".claude" / "settings.json").write_text(json.dumps(settings))
        code, report = gate.doctor(repo)
        assert code != 0
        assert any(
            c["name"] == "hook wired: pre-mcp-guard" and not c["ok"] for c in report["checks"]
        )

    def test_doctor_reports_weakening(self, repo: Path) -> None:
        _wire_minimal_harness(repo)
        settings = json.loads((repo / ".claude" / "settings.json").read_text())
        settings["permissions"]["deny"] = []
        (repo / ".claude" / "settings.json").write_text(json.dumps(settings))
        code, report = gate.doctor(repo)
        assert code != 0
        weak = [c for c in report["checks"] if c["name"] == "harness not weakened"]
        assert weak and not weak[0]["ok"] and "deny rule removed" in weak[0]["detail"]


def _wire_minimal_harness(repo: Path) -> None:
    claude = repo / ".claude"
    claude.mkdir(exist_ok=True)
    hook_cmd = 'python3 "$CLAUDE_PROJECT_DIR"/scripts/claude_hooks.py'
    settings = {
        "permissions": {"deny": ["Read(.env)", "Bash(git push --force*)"]},
        "hooks": {
            "PreToolUse": [
                {
                    "hooks": [
                        {"type": "command", "command": f"{hook_cmd} {name}"}
                        for name in gate.HOOK_NAMES
                    ]
                }
            ]
        },
    }
    (claude / "settings.json").write_text(json.dumps(settings))
    for rel in gate.HARNESS_SCRIPTS:
        script = repo / rel
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# stub\n")
    gate.write_baseline(repo)


class TestLintHarness:
    def test_missing_baseline_reported(self, repo: Path) -> None:
        problems = gate.lint_harness(repo)
        assert problems and "missing" in problems[0]

    def test_regressions_detected(self, repo: Path) -> None:
        _wire_minimal_harness(repo)
        assert gate.lint_harness(repo) == []
        (repo / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\naddopts = '-q'\n[tool.coverage.report]\nfail_under = 93\n"
        )
        gate.write_baseline(repo)
        (repo / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\naddopts = '-q'\n[tool.coverage.report]\nfail_under = 80\n"
        )
        problems = gate.lint_harness(repo)
        assert any("fail_under lowered" in p for p in problems)
        settings = json.loads((repo / ".claude" / "settings.json").read_text())
        settings["hooks"] = {}
        (repo / ".claude" / "settings.json").write_text(json.dumps(settings))
        problems = gate.lint_harness(repo)
        assert any("hook event unwired" in p for p in problems)

    def test_quant_suppression_growth_detected(self, repo: Path) -> None:
        _wire_minimal_harness(repo)
        quant = repo / "packages" / "alpha-validation" / "src" / "alpha_validation"
        quant.mkdir(parents=True)
        (quant / "dsr.py").write_text("x = 1  # noqa: E501\n")
        problems = gate.lint_harness(repo)
        assert any("suppressions grew" in p for p in problems)


class TestScopedPaths:
    def test_status_preserves_spaces_and_both_rename_paths(self, repo: Path) -> None:
        _git(repo, "mv", "tracked.py", "renamed file.py")
        assert set(gate._status_entries(repo)) == {
            ("tracked.py", False),
            ("renamed file.py", False),
        }

    def test_scoped_changed_paths_tracked_and_untracked(self, repo: Path) -> None:
        quant = repo / "packages" / "alpha-validation" / "src" / "alpha_validation"
        quant.mkdir(parents=True)
        (quant / "dsr.py").write_text("a = 1\n")
        (repo / "tracked.py").write_text("x = 9\n")
        assert gate.scoped_changed_paths(repo, gate.matches_quant) == [
            "packages/alpha-validation/src/alpha_validation/dsr.py"
        ]
        assert gate.scoped_changed_paths(repo, lambda p: p == "tracked.py") == ["tracked.py"]


class TestAdrAwareness:
    def test_adr_drift_names_unreferenced_adrs(self, tmp_path: Path) -> None:
        (tmp_path / "docs" / "adr").mkdir(parents=True)
        (tmp_path / "docs" / "adr" / "0001-first.md").write_text("# ADR-0001 first\n")
        (tmp_path / "docs" / "adr" / "0002-second.md").write_text("# ADR-0002 second\n")
        index = tmp_path / "docs" / "adr" / "README.md"
        index.write_text("| [0001](0001-first.md) | First |\nADR-0002 named but not linked\n")
        (tmp_path / "CLAUDE.md").write_text("ADR-0002 elsewhere does not count\n")
        assert harness_awareness.adr_files(tmp_path) == ["0001-first.md", "0002-second.md"]
        assert harness_awareness.adr_drift(tmp_path) == ["ADR-0002"]
        index.write_text("| [0001](0001-first.md) |\n| [0002](./0002-second.md) |\n")
        assert harness_awareness.adr_drift(tmp_path) == []


_VALID_PLAN: dict[str, Any] = {
    "title": "Add X",
    "context": "why",
    "assumptions": [{"statement": "Y holds", "verified_by": "grep Y"}],
    "alternatives_considered": ["do nothing (rejected: Z)"],
    "pre_mortem": ["fails if A", "fails if B"],
    "slices": [
        {
            "title": "s1",
            "verify": "uv run pytest tests/unit/test_x.py",
            "expected": "1 passed",
            "rollback": "git checkout -- packages/alpha-core/src/alpha_core/x.py",
            "files": ["packages/alpha-core/src/alpha_core/x.py"],
        },
        {"title": "s2", "verify": "gate.py fast", "expected": "stamp", "rollback": "revert"},
    ],
    "tier_impact": ["none"],
    "docs_to_update": ["CLAUDE.md"],
    "out_of_scope": ["the SPA"],
    "files": ["tests/unit/test_x.py"],
}


def _plan_doc(block: dict[str, Any] | str) -> str:
    body = block if isinstance(block, str) else json.dumps(block, indent=2)
    return f"# Plan\n\n```json\n{body}\n```\n\n## Slices\n"


class TestPlanCheck:
    def test_valid_plan_passes_and_summarizes(self, tmp_path: Path) -> None:
        plan = tmp_path / "2026-03-01-x.md"
        plan.write_text(_plan_doc(_VALID_PLAN))
        ok, message = harness_awareness.plan_check(plan)
        assert ok, message
        assert "2 slice(s), 0 done" in message

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("pre_mortem", ["only one"]),
            ("alternatives_considered", []),
            ("slices", [_VALID_PLAN["slices"][0]]),
            ("assumptions", [{"statement": "unverified"}]),
            ("tier_impact", ["cosmic"]),
        ],
    )
    def test_missing_reasoning_fields_fail(self, tmp_path: Path, field: str, value: Any) -> None:
        plan = tmp_path / "p.md"
        plan.write_text(_plan_doc({**_VALID_PLAN, field: value}))
        ok, message = harness_awareness.plan_check(plan)
        assert not ok
        assert "FeaturePlan invalid" in message

    def test_no_front_block_fails(self, tmp_path: Path) -> None:
        plan = tmp_path / "p.md"
        plan.write_text("# Plan without a block\n\n```json\nnot json\n```\n")
        ok, message = harness_awareness.plan_check(plan)
        assert not ok and "no fenced" in message
        assert harness_awareness.plan_front_block("no fences at all") is None


class TestQuantRigorTooling:
    """W5: mutation gate, semgrep, determinism double-run, raise-site coverage, on-touch steps."""

    def _quant_module(self, repo: Path, name: str = "dsr", body: str = "X = 1\n") -> str:
        rel = f"packages/alpha-validation/src/alpha_validation/{name}.py"
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
        return rel

    def test_quant_source_modules_default_to_changed_tree(self, repo: Path) -> None:
        rel = self._quant_module(repo)
        (repo / "tests" / "oracles").mkdir(parents=True)
        (repo / "tests" / "oracles" / "test_x.py").write_text("def test_x() -> None: ...\n")
        assert gate.quant_source_modules(repo) == [rel]
        assert gate.quant_source_modules(repo, ["packages/alpha-core/src/alpha_core/x.py"]) == []

    def test_mutation_staging_layout_and_config(self, repo: Path) -> None:
        rel = self._quant_module(repo)
        (repo / "packages/alpha-validation/src/alpha_validation/__init__.py").write_text("")
        tests_dir = repo / "tests"
        (tests_dir / "unit").mkdir(parents=True)
        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "unit" / "test_dsr.py").write_text(
            "import alpha_validation.dsr\nfrom tests.unit.helpers_dsr import fixture\n"
        )
        (tests_dir / "unit" / "helpers_dsr.py").write_text("fixture = 1\n")
        (tests_dir / "unit" / "test_other.py").write_text("import gate\n")
        (repo / "pyproject.toml").write_text('[tool.pytest.ini_options]\nmarkers = ["oracle: o"]\n')
        staging = repo / ".claude" / "state" / "mutation"
        only = harness_quant.stage_mutation_tree(repo, [rel], staging)
        assert only == ["src/alpha_validation/dsr.py"]
        assert (staging / "src" / "alpha_validation" / "dsr.py").is_file()
        assert (staging / rel).is_file()  # workspace layout mirrored for source-inspecting tests
        assert (staging / "tests" / "unit" / "test_dsr.py").is_file()
        assert (staging / "tests" / "unit" / "helpers_dsr.py").is_file()  # intra-tests import kept
        assert not (staging / "tests" / "unit" / "test_other.py").exists()  # unrelated test dropped
        cfg = (staging / "pyproject.toml").read_text()
        assert 'only_mutate = ["src/alpha_validation/dsr.py"]' in cfg
        assert 'also_copy = ["packages", "scripts"]' in cfg
        # tests/conftest.py imports the test-process owner; staged runs must find it
        assert (staging / "scripts" / "run_owned_test.py").is_file()
        assert 'pythonpath = [".", "src", "scripts"]' in cfg
        assert 'markers = ["oracle: o"]' in cfg
        assert "use_git_change_detection = false" in cfg

    def test_frontmatter_reads_yaml_block_lists(self) -> None:
        text = '---\npaths:\n  - "packages/x/**"\n  - "apps/y/**"\nname: z\n---\nbody\n'
        assert gate._frontmatter(text) == {
            "paths": '["packages/x/**", "apps/y/**"]',
            "name": "z",
        }
        assert gate._frontmatter("---\npaths: [a, b]\n---\n") == {"paths": "[a, b]"}

    def test_staging_only_failures_become_deselect_and_ignore_args(self) -> None:
        output = (
            "FAILED tests/unit/test_theme_drift.py::test_css[bg] - FileNotFoundError: x.css\n"
            "ERROR tests/unit/test_broken.py - ImportError\n"
            "1 failed, 1 error in 0.1s\n"
        )
        assert harness_quant.staging_only_failures(output) == [
            "--deselect",
            "tests/unit/test_theme_drift.py::test_css[bg]",
            "--ignore",
            "tests/unit/test_broken.py",
        ]
        assert harness_quant.staging_only_failures("3 passed\n") == []

    def test_mutation_verdict_thresholds(self, tmp_path: Path) -> None:
        stats = {"killed": 155, "survived": 37, "total": 192, "skipped": 0}
        assert harness_quant.mutation_kill_rate(stats) == pytest.approx(155 / 192)
        # no baseline: the 0.90 floor applies
        assert harness_quant.mutation_required("m.py", {}) == pytest.approx(
            harness_quant.MUTATION_MIN_KILL
        )
        # a module already below the floor must not regress below its recorded baseline
        assert harness_quant.mutation_required("m.py", {"m.py": 0.80}) == pytest.approx(0.80)
        # a module above the floor is held to the floor, not to its own high-water mark
        assert harness_quant.mutation_required("m.py", {"m.py": 0.97}) == pytest.approx(0.90)

    def test_mutate_reports_unavailable_when_runner_cannot_start(self, repo: Path) -> None:
        rel = self._quant_module(repo)
        (repo / "packages/alpha-validation/src/alpha_validation/__init__.py").write_text("")
        (repo / "tests").mkdir()
        (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\nmarkers = []\n")

        def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
            return (False, 0.0, "mutmut: command not found")

        code, report = harness_quant.mutate(repo, [rel], runner=runner)
        assert code == 0  # tooling absence never blocks; it is reported loudly
        assert report["modules"][rel]["status"].startswith("unavailable:")

    def test_mutate_report_surfaces_unattributed_mutants_and_forwards_timeout(
        self, repo: Path
    ) -> None:
        rel = self._quant_module(repo, body="def value(): return 1\n")
        (repo / "packages/alpha-validation/src/alpha_validation/__init__.py").write_text("")
        (repo / "tests").mkdir()
        (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\nmarkers = []\n")
        seen_timeouts: list[float] = []

        def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
            seen_timeouts.append(kwargs["timeout"])
            if cmd[-1] == "run":  # mutmut run: pretend it wrote its stats
                stats = Path(kwargs["cwd"]) / "mutants" / "mutmut-cicd-stats.json"
                stats.parent.mkdir(exist_ok=True)
                cicd = {"killed": 1, "survived": 3, "total": 47, "no_tests": 42, "timeout": 1}
                stats.write_text(json.dumps(cicd))
            return (True, 1.0, "")

        code, report = harness_quant.mutate(repo, [rel], runner=runner, timeout=5400.0)
        entry = report["modules"][rel]
        assert code == 1 and entry["status"] == "fail"
        # module-scope mutants mutmut cannot attribute are visible, and NOT credited as kills
        assert entry["no_tests"] == 42 and entry["timeout"] == 1
        assert entry["kill_rate"] == round(1 / 47, 4)
        assert 5400.0 in seen_timeouts

    def test_mutate_runs_mutmut_with_single_threaded_accelerate(self, repo: Path) -> None:
        # mutmut isolates each mutant with os.fork(); Apple's Accelerate BLAS is not fork-safe
        # once its thread pool exists, so every mutant reaching numpy/scipy linear algebra is
        # recorded as "segfault" (never credited as a kill) unless the pool is pinned to one thread.
        rel = self._quant_module(repo, body="def value(): return 1\n")
        (repo / "packages/alpha-validation/src/alpha_validation/__init__.py").write_text("")
        (repo / "tests").mkdir()
        (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\nmarkers = []\n")
        envs: dict[str, dict[str, str] | None] = {}

        def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
            envs[cmd[-1]] = kwargs.get("env")
            return (False, 0.0, "")

        harness_quant.mutate(repo, [rel], runner=runner)
        assert envs["run"] is not None
        assert envs["run"]["VECLIB_MAXIMUM_THREADS"] == "1"
        assert envs["run"]["PATH"] == os.environ["PATH"]  # the rest of the environment is kept

    def test_semgrep_command_and_scope(self, repo: Path) -> None:
        for rel in ("packages/x.py", "docs/a.md", "tests/t.py"):
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text("")
        cmd = harness_quant.semgrep_command(
            repo, ["packages/x.py", "docs/a.md", "tests/t.py", "gone.py"]
        )
        assert cmd[:4] == ["uvx", "--from", "semgrep==1.181.0", "semgrep"]
        assert cmd[4:10] == [
            "--config",
            str(gate.SEMGREP_RULES),
            "--metrics=off",
            "--quiet",
            "--error",
            "packages/x.py",
        ]
        assert cmd[-2:] == ["packages/x.py", "tests/t.py"]  # only python targets
        assert harness_quant.semgrep_command(repo, []) == []

    def test_semgrep_runner_checks_version_and_preserves_arguments(self) -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []
        scan_args = ["--config", ".semgrep/alpha.yml", "--metrics=off", "packages/x.py"]

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            if command[-1] == "--version":
                return subprocess.CompletedProcess(
                    command, 0, "1.181.0\n", "uvx: installing pinned Semgrep\n"
                )
            return subprocess.CompletedProcess(command, 7, "scan output", "scan failure")

        result = semgrep_runner.run_semgrep(
            scan_args, runner=run, capture_output=True, text=True, check=False
        )

        assert result.returncode == 7
        assert result.stderr == "uvx: installing pinned Semgrep\nscan failure"
        assert calls == [
            (
                ["uvx", "--from", "semgrep==1.181.0", "semgrep", "--version"],
                {"capture_output": True, "text": True, "check": False},
            ),
            (
                ["uvx", "--from", "semgrep==1.181.0", "semgrep", *scan_args],
                {"capture_output": True, "text": True, "check": False},
            ),
        ]

    def test_semgrep_runner_rejects_version_mismatch_without_scanning(self) -> None:
        calls: list[list[str]] = []

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "1.182.1\n", "")

        result = semgrep_runner.run_semgrep(["--config", ".semgrep/alpha.yml"], runner=run)

        assert result.returncode != 0
        assert "expected 1.181.0, found 1.182.1" in result.stderr
        assert calls == [["uvx", "--from", "semgrep==1.181.0", "semgrep", "--version"]]

    def test_semgrep_runner_does_not_match_version_text_in_diagnostics(self) -> None:
        calls: list[list[str]] = []

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(
                command,
                0,
                "1.182.1\n",
                "diagnostic: expected 1.181.0 from repository policy\n",
            )

        result = semgrep_runner.run_semgrep(["--config", ".semgrep/alpha.yml"], runner=run)

        assert result.returncode == 2
        assert "found 1.182.1" in result.stderr
        assert "expected 1.181.0 from repository policy" in result.stderr
        assert calls == [["uvx", "--from", "semgrep==1.181.0", "semgrep", "--version"]]

    @pytest.mark.parametrize("stdout", ["", "1.181.0\nextra output\n"])
    def test_semgrep_runner_rejects_empty_or_extra_version_stdout(self, stdout: str) -> None:
        calls: list[list[str]] = []

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout, "bootstrap diagnostic\n")

        result = semgrep_runner.run_semgrep(["--config", ".semgrep/alpha.yml"], runner=run)

        assert result.returncode == 2
        assert calls == [["uvx", "--from", "semgrep==1.181.0", "semgrep", "--version"]]

    def test_semgrep_runner_propagates_version_tool_failure(self) -> None:
        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 19, "partial stdout", "uvx failed")

        result = semgrep_runner.run_semgrep(["--config", ".semgrep/alpha.yml"], runner=run)
        assert result.returncode == 19
        assert result.stdout == "partial stdout"
        assert result.stderr == "uvx failed"

    def test_semgrep_gate_rejects_a_version_mismatch(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            if command[-1] == "--version":
                return subprocess.CompletedProcess(
                    command,
                    0,
                    "1.182.1\n",
                    "diagnostic mentions expected 1.181.0\n",
                )
            raise AssertionError("mismatched Semgrep version must not scan")

        monkeypatch.setattr(subprocess, "run", run)
        assert harness_quant.semgrep(repo, changed_only=False) == 1
        assert len(calls) == 1 and calls[0][0][-1] == "--version"
        captured = capsys.readouterr()
        assert "expected 1.181.0, found 1.182.1" in captured.err
        assert "diagnostic mentions expected 1.181.0" in captured.err

    def test_semgrep_gate_accepts_cold_cache_bootstrap_stderr(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            if command[-1] == "--version":
                return subprocess.CompletedProcess(
                    command, 0, "1.181.0\n", "Downloading and installing pinned Semgrep\n"
                )
            return subprocess.CompletedProcess(command, 0, "scan output", "scan stderr")

        monkeypatch.setattr(subprocess, "run", run)
        assert harness_quant.semgrep(repo, changed_only=False) == 0
        assert len(calls) == 2
        assert calls[0][0][-1] == "--version"
        assert calls[1][0] == [
            "uvx",
            "--from",
            "semgrep==1.181.0",
            "semgrep",
            *harness_quant._SEMGREP_OPTIONS,
            "packages",
            "apps",
            "scripts",
            "tests",
        ]
        captured = capsys.readouterr()
        assert "[semgrep] ok" in captured.out
        assert "Downloading and installing pinned Semgrep" in captured.err

    def test_semgrep_contract_caller_preserves_scan_arguments_offline(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []
        target_exists: list[bool] = []

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            if command[-1] == "--version":
                return subprocess.CompletedProcess(
                    command, 0, "1.181.0\n", "Installing pinned Semgrep in uvx cache\n"
                )
            target = command[-1]
            target_path = Path(kwargs["cwd"]) / target
            target_exists.append(target_path.is_file())
            fixture = target_path.read_text()
            lines = [
                index + 2
                for index, line in enumerate(fixture.splitlines())
                if line.strip() == "# finding"
            ]
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "errors": [],
                        "results": [
                            {
                                "check_id": "alpha.alpha-float-literal-equality",
                                "start": {"line": line},
                            }
                            for line in lines
                        ],
                    }
                ),
                "",
            )

        monkeypatch.setattr(subprocess, "run", run)
        assert check_semgrep_contracts.main() == 0
        scan_command, scan_kwargs = calls[1]
        assert scan_command == [
            "uvx",
            "--from",
            "semgrep==1.181.0",
            "semgrep",
            "--config",
            str(Path(check_semgrep_contracts.__file__).resolve().parents[1] / ".semgrep/alpha.yml"),
            "--metrics=off",
            "--disable-version-check",
            "--no-git-ignore",
            "--json",
            "--quiet",
            "packages/alpha-research/probe.py",
        ]
        assert target_exists == [True]
        assert scan_kwargs["capture_output"] is True and scan_kwargs["text"] is True
        assert "Installing pinned Semgrep in uvx cache" in capsys.readouterr().err

    def test_semgrep_contract_caller_fails_on_tool_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, "1.181.0\n", "")
            return subprocess.CompletedProcess(
                command, 9, "partial scan stdout", "semgrep scan failed"
            )

        monkeypatch.setattr(subprocess, "run", run)
        with pytest.raises(
            RuntimeError, match="exit code 9: partial scan stdout\\nsemgrep scan failed"
        ):
            check_semgrep_contracts.main()
        assert len(calls) == 2 and calls[1][-1] == "packages/alpha-research/probe.py"

    def test_semgrep_contract_caller_propagates_version_probe_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 23, "", "uvx bootstrap failed")

        monkeypatch.setattr(subprocess, "run", run)
        with pytest.raises(RuntimeError, match="exit code 23: uvx bootstrap failed"):
            check_semgrep_contracts.main()
        assert len(calls) == 1 and calls[0][-1] == "--version"

    @pytest.mark.parametrize(
        ("output", "expected"),
        [
            # Real findings whose matched source mentions OSError / a missing file must FAIL.
            ("3 Code Findings\n  340┆ except OSError:\n  341┆     pass\n", 1),
            ("finding: raise DataError('No such file')\n", 1),
            # Missing scanner and launch failures are blocking; they fail the step.
            ("FileNotFoundError: [Errno 2] No such file or directory: 'uvx'", 1),
            ("zsh: command not found: uvx", 1),
        ],
    )
    def test_semgrep_unavailable_is_decided_by_the_launch_not_the_findings(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, output: str, expected: int
    ) -> None:
        (repo / ".semgrep").mkdir()
        (repo / ".semgrep" / "alpha.yml").write_text("rules: []\n")

        real_run = subprocess.run

        def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if command and command[0] == "git":
                return real_run(command, **kwargs)
            return subprocess.CompletedProcess(command, 127, "", output)

        monkeypatch.setattr(
            subprocess,
            "run",
            run,
        )
        assert harness_quant.semgrep(repo, changed_only=False) == expected

    def test_raise_sites_are_found_by_ast(self, tmp_path: Path) -> None:
        mod = tmp_path / "m.py"
        mod.write_text(
            "def f(x):\n    if x:\n        raise ValueError('a')\n    return 1\n\nraise SystemExit"
        )
        assert harness_quant.raise_sites(mod) == [3, 6]

    def test_uncovered_raise_sites_from_coverage_json(self, repo: Path) -> None:
        body = "def f(x):\n    if x:\n        raise ValueError\n    return 1\n"
        rel = self._quant_module(repo, body=body)
        cov = {"files": {rel: {"missing_lines": [3]}}}
        (repo / "cov.json").write_text(json.dumps(cov))
        assert harness_quant.uncovered_raise_sites(repo, repo / "cov.json", [rel]) == [f"{rel}:3"]
        cov = {"files": {rel: {"missing_lines": []}}}
        (repo / "cov.json").write_text(json.dumps(cov))
        assert harness_quant.uncovered_raise_sites(repo, repo / "cov.json", [rel]) == []

    def test_determinism_runs_twice_under_perturbed_env(self, repo: Path) -> None:
        (repo / "tests" / "integration").mkdir(parents=True)
        (repo / "tests" / "integration" / "test_figure_determinism.py").write_text("")
        seen: list[dict[str, str]] = []

        def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
            env = kwargs.get("env") or {}
            seen.append({k: env[k] for k in ("PYTHONHASHSEED", "TZ", "OMP_NUM_THREADS")})
            assert cmd[-1].endswith("test_figure_determinism.py")
            return (True, 0.1, "")

        ok, detail = harness_quant.determinism(repo, runner=runner)
        assert ok and "2 passes" in detail
        assert len(seen) == 2 and seen[0]["PYTHONHASHSEED"] != seen[1]["PYTHONHASHSEED"]
        assert seen[0]["TZ"] != seen[1]["TZ"]
        assert {s["OMP_NUM_THREADS"] for s in seen} == {"1"}

    def test_determinism_reports_which_pass_failed(self, repo: Path) -> None:
        (repo / "tests" / "unit").mkdir(parents=True)
        (repo / "tests" / "unit" / "test_content_identity_goldens.py").write_text("")
        calls = {"n": 0}

        def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
            calls["n"] += 1
            return (calls["n"] == 1, 0.1, "hash mismatch")

        ok, detail = harness_quant.determinism(repo, runner=runner)
        assert not ok and "pass 2" in detail


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('prefix {"a": 1} suffix', '{"a": 1}'),
        ('```json\n{"a": {"b": 2}}\n```', '{"a": {"b": 2}}'),
        ("no braces here", None),
        ("} {", None),
    ],
)
def test_first_json_object_slices_outermost_braces(text: str, expected: str | None) -> None:
    assert gate.first_json_object(text) == expected


def test_every_gate_subcommand_has_working_help() -> None:
    import argparse

    parser = gate.build_parser()
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert "selftest" not in subparsers.choices
    for name, sub in subparsers.choices.items():
        assert sub.format_help(), name
