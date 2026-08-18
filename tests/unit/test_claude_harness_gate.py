"""Tests for the Claude Code harness gate runner (scripts/gate.py).

The gate runner is the single source of truth for tree-hash stamps, path
tiers, attestation artifacts, one-shot overrides/acks, the audit journal,
and the harness doctor. Everything here runs against throwaway git repos.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import gate
import pytest


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text(".claude/state/\n")
    (root / "tracked.py").write_text("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "chore: init")
    return root


class TestTreeHash:
    def test_deterministic(self, repo: Path) -> None:
        assert gate.compute_tree_hash(repo) == gate.compute_tree_hash(repo)

    def test_changes_on_tracked_edit(self, repo: Path) -> None:
        before = gate.compute_tree_hash(repo)
        (repo / "tracked.py").write_text("x = 2\n")
        assert gate.compute_tree_hash(repo) != before

    def test_changes_on_untracked_file(self, repo: Path) -> None:
        before = gate.compute_tree_hash(repo)
        (repo / "new.py").write_text("y = 1\n")
        assert gate.compute_tree_hash(repo) != before

    def test_changes_on_untracked_content_edit(self, repo: Path) -> None:
        (repo / "new.py").write_text("y = 1\n")
        before = gate.compute_tree_hash(repo)
        (repo / "new.py").write_text("y = 2\n")
        assert gate.compute_tree_hash(repo) != before

    def test_insensitive_to_gitignored_state(self, repo: Path) -> None:
        before = gate.compute_tree_hash(repo)
        state = repo / ".claude" / "state"
        state.mkdir(parents=True)
        (state / "gate-stamp.json").write_text("{}")
        assert gate.compute_tree_hash(repo) == before

    def test_changes_on_staged_change(self, repo: Path) -> None:
        before = gate.compute_tree_hash(repo)
        (repo / "tracked.py").write_text("x = 3\n")
        _git(repo, "add", "tracked.py")
        assert gate.compute_tree_hash(repo) != before


class TestScopedDiffHash:
    def test_stable_when_out_of_scope_changes(self, repo: Path) -> None:
        quant = repo / "packages" / "alpha-validation" / "src" / "alpha_validation"
        quant.mkdir(parents=True)
        (quant / "dsr.py").write_text("a = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "--quiet", "-m", "chore: quant")
        before = gate.scoped_diff_hash(repo, gate.matches_quant)
        (repo / "tracked.py").write_text("x = 99\n")
        assert gate.scoped_diff_hash(repo, gate.matches_quant) == before

    def test_changes_on_in_scope_edit(self, repo: Path) -> None:
        quant = repo / "packages" / "alpha-validation" / "src" / "alpha_validation"
        quant.mkdir(parents=True)
        (quant / "dsr.py").write_text("a = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "--quiet", "-m", "chore: quant")
        before = gate.scoped_diff_hash(repo, gate.matches_quant)
        (quant / "dsr.py").write_text("a = 2\n")
        assert gate.scoped_diff_hash(repo, gate.matches_quant) != before

    def test_changes_on_untracked_in_scope_file(self, repo: Path) -> None:
        before = gate.scoped_diff_hash(repo, gate.matches_quant)
        quant = repo / "packages" / "alpha-research" / "src" / "alpha_research"
        quant.mkdir(parents=True)
        (quant / "power.py").write_text("b = 1\n")
        assert gate.scoped_diff_hash(repo, gate.matches_quant) != before


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

    @pytest.mark.parametrize(
        "path",
        [
            "packages/alpha-validation/src/alpha_validation/metrics.py",
            "packages/alpha-backtest/src/alpha_backtest/engine.py",
            "apps/alpha-cli/src/alpha_cli/_gauntlet.py",
            "apps/alpha-cli/src/alpha_cli/_seeds.py",
            "apps/alpha-cli/src/alpha_cli/_runner.py",
        ],
    )
    def test_risk_matches(self, path: str) -> None:
        assert gate.matches_risk(path)

    @pytest.mark.parametrize(
        "path",
        [
            "apps/alpha-cli/src/alpha_cli/main.py",
            "apps/alpha-web/src/alpha_web/app.py",
            "docs/notes.md",
        ],
    )
    def test_risk_rejects(self, path: str) -> None:
        assert not gate.matches_risk(path)


class TestProtectedControlPlane:
    @pytest.mark.parametrize(
        "path",
        [
            "scripts/gate.py",
            "scripts/claude_hooks.py",
            "scripts/harness_models.py",
            ".claude/settings.json",
            ".claude/skills/karpathy-guidelines/SKILL.md",
            "tests/bias_guards/test_pit_poison.py",
            ".github/workflows/ci.yml",
            "CLAUDE.md",
        ],
    )
    def test_protected_paths(self, path: str) -> None:
        assert gate.protected_reason(path, "") is not None

    def test_pyproject_protected_only_for_guarded_content(self) -> None:
        assert gate.protected_reason("pyproject.toml", "[tool.importlinter]") is not None
        assert gate.protected_reason("pyproject.toml", "fail_under = 80") is not None
        assert gate.protected_reason("pyproject.toml", "strict = false") is not None
        assert gate.protected_reason("pyproject.toml", "line-length = 100") is None

    @pytest.mark.parametrize(
        "path",
        [
            "packages/alpha-validation/src/alpha_validation/metrics.py",
            "docs/notes.md",
            "tests/unit/test_bootstrap.py",
        ],
    )
    def test_unprotected_paths(self, path: str) -> None:
        assert gate.protected_reason(path, "") is None


class TestStamp:
    def test_write_and_check_tiers(self, repo: Path) -> None:
        gate.write_stamp(repo, "fast", steps=[("ruff", 1.0, True)], duration=1.0)
        assert gate.stamp_is_valid(repo, "fast")
        assert not gate.stamp_is_valid(repo, "full")
        gate.write_stamp(repo, "full", steps=[("all", 2.0, True)], duration=2.0)
        assert gate.stamp_is_valid(repo, "fast")
        assert gate.stamp_is_valid(repo, "full")

    def test_stamp_invalidated_by_edit(self, repo: Path) -> None:
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)
        (repo / "tracked.py").write_text("x = 4\n")
        assert not gate.stamp_is_valid(repo, "fast")

    def test_missing_stamp_invalid(self, repo: Path) -> None:
        assert not gate.stamp_is_valid(repo, "fast")

    def test_run_gate_failure_leaves_no_stamp(self, repo: Path) -> None:
        def runner(cmd: list[str]) -> tuple[bool, float, str]:
            return (False, 0.1, "boom")

        code = gate.run_gate(repo, "fast", runner=runner)
        assert code != 0
        assert not gate.stamp_is_valid(repo, "fast")

    def test_run_gate_success_writes_stamp(self, repo: Path) -> None:
        def runner(cmd: list[str]) -> tuple[bool, float, str]:
            return (True, 0.1, "")

        code = gate.run_gate(repo, "fast", runner=runner)
        assert code == 0
        assert gate.stamp_is_valid(repo, "fast")

    def test_run_gate_clears_prior_stamp_first(self, repo: Path) -> None:
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)

        def runner(cmd: list[str]) -> tuple[bool, float, str]:
            return (False, 0.1, "boom")

        gate.run_gate(repo, "fast", runner=runner)
        assert not gate.stamp_is_valid(repo, "fast")
        assert not gate.stamp_is_valid(repo, "full")


class TestAttest:
    def _quant_report(self, **overrides: Any) -> dict[str, Any]:
        report: dict[str, Any] = {
            "claims": [
                {
                    "claim": "DSR deflates by trial-Sharpe variance",
                    "source": "Bailey & Lopez de Prado (2014)",
                    "location": "packages/alpha-validation/src/alpha_validation/dsr.py:10",
                    "verdict": "VERIFIED",
                }
            ],
            "docstring_citations": {"ok": True, "missing": []},
            "overall": "PASS",
        }
        report.update(overrides)
        return report

    def test_quant_attest_pass_writes_bound_artifact(self, repo: Path) -> None:
        code = gate.attest(repo, "quant", json.dumps(self._quant_report()))
        assert code == 0
        assert gate.quant_attestation_valid(repo)

    def test_quant_attest_invalidated_by_quant_edit(self, repo: Path) -> None:
        gate.attest(repo, "quant", json.dumps(self._quant_report()))
        quant = repo / "packages" / "alpha-validation" / "src" / "alpha_validation"
        quant.mkdir(parents=True)
        (quant / "dsr.py").write_text("a = 1\n")
        assert not gate.quant_attestation_valid(repo)

    def test_quant_attest_survives_out_of_scope_edit(self, repo: Path) -> None:
        gate.attest(repo, "quant", json.dumps(self._quant_report()))
        (repo / "tracked.py").write_text("x = 5\n")
        assert gate.quant_attestation_valid(repo)

    def test_quant_attest_rejects_fail_overall(self, repo: Path) -> None:
        report = self._quant_report(overall="FAIL")
        assert gate.attest(repo, "quant", json.dumps(report)) != 0
        assert not gate.quant_attestation_valid(repo)

    def test_quant_attest_rejects_pass_with_discrepancy(self, repo: Path) -> None:
        report = self._quant_report()
        report["claims"][0]["verdict"] = "DISCREPANCY"
        assert gate.attest(repo, "quant", json.dumps(report)) != 0

    def test_quant_attest_rejects_pass_with_missing_citation(self, repo: Path) -> None:
        report = self._quant_report(docstring_citations={"ok": False, "missing": ["dsr.py:f"]})
        assert gate.attest(repo, "quant", json.dumps(report)) != 0

    def test_attest_rejects_malformed_json(self, repo: Path) -> None:
        assert gate.attest(repo, "quant", "{not json") != 0
        assert gate.attest(repo, "quant", json.dumps({"unexpected": 1})) != 0

    def _review(self, repo: Path, **overrides: Any) -> dict[str, Any]:
        verdict: dict[str, Any] = {
            "verdict": "APPROVE",
            "findings": [],
            "reviewed_tree_hash": gate.compute_tree_hash(repo),
        }
        verdict.update(overrides)
        return verdict

    def test_review_attest_approve_binds_tree(self, repo: Path) -> None:
        assert gate.attest(repo, "review", json.dumps(self._review(repo))) == 0
        assert gate.review_verdict_valid(repo)
        (repo / "tracked.py").write_text("x = 6\n")
        assert not gate.review_verdict_valid(repo)

    def test_review_attest_rejects_block(self, repo: Path) -> None:
        verdict = self._review(
            repo,
            verdict="BLOCK",
            findings=[
                {
                    "severity": "high",
                    "file": "a.py",
                    "line": 1,
                    "summary": "bug",
                }
            ],
        )
        assert gate.attest(repo, "review", json.dumps(verdict)) != 0
        assert not gate.review_verdict_valid(repo)

    def test_review_attest_rejects_stale_tree_hash(self, repo: Path) -> None:
        verdict = self._review(repo, reviewed_tree_hash="0" * 64)
        assert gate.attest(repo, "review", json.dumps(verdict)) != 0


class TestOnceTokens:
    def test_override_consumed_once(self, repo: Path) -> None:
        gate.write_override(repo, reason="emergency")
        assert gate.consume_override(repo) is not None
        assert gate.consume_override(repo) is None

    def test_ack_consumed_once(self, repo: Path) -> None:
        gate.write_ack(repo, reason="editing gate itself")
        assert gate.consume_ack(repo) is not None
        assert gate.consume_ack(repo) is None


class TestAudit:
    def test_events_appended(self, repo: Path) -> None:
        gate.write_stamp(repo, "fast", steps=[("ruff", 1.0, True)], duration=1.0)
        gate.write_override(repo, reason="r1")
        gate.consume_override(repo)
        journal = repo / ".claude" / "state" / "harness-audit.jsonl"
        lines = [json.loads(line) for line in journal.read_text().splitlines()]
        events = [line["event"] for line in lines]
        assert "stamp_written" in events
        assert "override_written" in events
        assert "override_consumed" in events
        for line in lines:
            assert set(line) >= {"ts", "session_id", "event", "detail", "tree_hash"}


class TestDoctor:
    def test_doctor_fails_on_missing_settings(self, repo: Path) -> None:
        code, report = gate.doctor(repo)
        assert code != 0
        assert any(not check["ok"] for check in report["checks"])

    def test_doctor_passes_on_wired_repo(self, repo: Path) -> None:
        claude = repo / ".claude"
        claude.mkdir(exist_ok=True)
        hook_cmd = 'python3 "$CLAUDE_PROJECT_DIR"/scripts/claude_hooks.py'
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": f"{hook_cmd} {name}"}
                            for name in ("pre-edit-guard", "pre-bash-guard")
                        ]
                    }
                ],
                "PostToolUse": [
                    {"hooks": [{"type": "command", "command": f"{hook_cmd} post-edit"}]}
                ],
                "Stop": [{"hooks": [{"type": "command", "command": f"{hook_cmd} stop-guard"}]}],
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": f"{hook_cmd} session-start"}]}
                ],
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": f"{hook_cmd} prompt-context"}]}
                ],
                "PreCompact": [
                    {"hooks": [{"type": "command", "command": f"{hook_cmd} pre-compact"}]}
                ],
            }
        }
        (claude / "settings.json").write_text(json.dumps(settings))
        (claude / "statusline.py").write_text("print('ok')\n")
        scripts = repo / "scripts"
        scripts.mkdir()
        for name in ("gate.py", "claude_hooks.py", "harness_models.py"):
            (scripts / name).write_text("# stub\n")
        code, report = gate.doctor(repo)
        failing = [check for check in report["checks"] if not check["ok"]]
        assert code == 0, failing
