"""Tests for the Claude Code hook entrypoints (scripts/claude_hooks.py).

Hooks are thin stdlib readers over the gate runner: every decision function
is pure enough to test with synthetic hook payloads against throwaway git
repos. Exit code 2 blocks; the message must always name the escape hatch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import claude_hooks
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


def _payload(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"session_id": "s1", "hook_event_name": "test"}
    base.update(kwargs)
    return base


class TestCommandParsing:
    def test_extracts_compound_commands(self) -> None:
        segments = claude_hooks.extract_commands("git add -A && git commit -m 'feat: x' | cat")
        assert len(segments) == 3

    @pytest.mark.parametrize(
        "command",
        [
            "git commit -m 'feat: x'",
            "git -C /tmp/repo commit -m 'fix: y'",
            "git add -A && git commit --amend",
            "cd x; git commit",
        ],
    )
    def test_detects_git_commit(self, command: str) -> None:
        assert claude_hooks.contains_git_commit(command)

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git log --grep commit",
            "echo git commit",
            "uv run pytest -q",
        ],
    )
    def test_ignores_non_commit(self, command: str) -> None:
        assert not claude_hooks.contains_git_commit(command)

    def test_extracts_dash_m_message(self) -> None:
        assert (
            claude_hooks.commit_message_of("git commit -m 'feat(x): add thing'")
            == "feat(x): add thing"
        )
        assert claude_hooks.commit_message_of("git commit --message='fix: y'") == "fix: y"
        assert claude_hooks.commit_message_of("git commit") is None


class TestCommitMessageConvention:
    @pytest.mark.parametrize(
        "message",
        [
            "feat(scope): add thing",
            "fix: repair thing",
            "test(hooks): cover thing",
            "build(gate): wire thing",
            "chore: tidy",
            "docs: explain",
            "refactor(cli): simplify",
            "data: refresh fixture",
        ],
    )
    def test_valid(self, message: str) -> None:
        assert claude_hooks.COMMIT_RE.match(message)

    @pytest.mark.parametrize(
        "message",
        [
            "Add thing",
            "feat add thing",
            "FEAT: shouting",
            "wip: stuff",
            "feat:",
            "feat: ",
        ],
    )
    def test_invalid(self, message: str) -> None:
        assert not claude_hooks.COMMIT_RE.match(message)


class TestDocsOnly:
    def test_docs_paths_waived(self) -> None:
        assert claude_hooks.docs_only(["README.md", "docs/x.md", ".claude/settings.json"])
        assert claude_hooks.docs_only([".agents/skills/x/SKILL.md"])

    def test_source_paths_not_waived(self) -> None:
        assert not claude_hooks.docs_only(["docs/x.md", "packages/alpha-core/src/a.py"])
        assert not claude_hooks.docs_only([])


class TestPreBashGuard:
    def _guard(self, repo: Path, command: str) -> tuple[int, str]:
        payload = _payload(tool_name="Bash", tool_input={"command": command})
        return claude_hooks.hook_pre_bash_guard(payload, repo)

    def test_non_commit_allowed(self, repo: Path) -> None:
        code, _ = self._guard(repo, "uv run pytest -q")
        assert code == 0

    def test_commit_without_stamp_blocked(self, repo: Path) -> None:
        (repo / "tracked.py").write_text("x = 2\n")
        _git(repo, "add", "-A")
        code, message = self._guard(repo, "git commit -m 'feat: x'")
        assert code == 2
        assert "gate.py full" in message

    def test_docs_only_commit_waived(self, repo: Path) -> None:
        (repo / "README.md").write_text("hi\n")
        _git(repo, "add", "-A")
        code, _ = self._guard(repo, "git commit -m 'docs: readme'")
        assert code == 0

    def test_bad_message_blocked(self, repo: Path) -> None:
        (repo / "README.md").write_text("hi\n")
        _git(repo, "add", "-A")
        code, message = self._guard(repo, "git commit -m 'update readme'")
        assert code == 2
        assert "conventional" in message.lower()

    def test_risk_tier_requires_review_verdict(self, repo: Path) -> None:
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)
        risky = repo / "packages" / "alpha-backtest" / "src" / "alpha_backtest"
        risky.mkdir(parents=True)
        (risky / "engine.py").write_text("e = 1\n")
        _git(repo, "add", "-A")
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)
        code, message = self._guard(repo, "git commit -m 'feat: risky'")
        assert code == 2
        assert "/review-gate" in message

    def test_risk_tier_with_approve_verdict_allowed(self, repo: Path) -> None:
        risky = repo / "packages" / "alpha-backtest" / "src" / "alpha_backtest"
        risky.mkdir(parents=True)
        (risky / "engine.py").write_text("e = 1\n")
        _git(repo, "add", "-A")
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)
        verdict = {
            "verdict": "APPROVE",
            "findings": [],
            "reviewed_tree_hash": gate.compute_tree_hash(repo),
        }
        assert gate.attest(repo, "review", json.dumps(verdict)) == 0
        code, _ = self._guard(repo, "git commit -m 'feat: risky'")
        assert code == 0

    def test_oversized_commit_blocked(self, repo: Path) -> None:
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)
        big = repo / "big.py"
        big.write_text("\n".join(f"line_{i} = {i}" for i in range(1200)) + "\n")
        _git(repo, "add", "-A")
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)
        code, message = self._guard(repo, "git commit -m 'feat: big'")
        assert code == 2
        assert "split" in message.lower()

    def test_override_consumed_once(self, repo: Path) -> None:
        (repo / "tracked.py").write_text("x = 2\n")
        _git(repo, "add", "-A")
        gate.write_override(repo, reason="emergency")
        code, _ = self._guard(repo, "git commit -m 'feat: x'")
        assert code == 0
        code, _ = self._guard(repo, "git commit -m 'feat: x'")
        assert code == 2


class TestPreEditGuard:
    def _guard(self, repo: Path, file_path: str, **tool_input: Any) -> tuple[int, str]:
        payload = _payload(
            tool_name="Edit",
            tool_input={"file_path": file_path, **tool_input},
        )
        return claude_hooks.hook_pre_edit_guard(payload, repo)

    def test_normal_file_allowed(self, repo: Path) -> None:
        code, _ = self._guard(repo, str(repo / "tracked.py"))
        assert code == 0

    def test_protected_file_blocked_naming_ack(self, repo: Path) -> None:
        code, message = self._guard(repo, str(repo / "scripts" / "gate.py"))
        assert code == 2
        assert "gate.py ack" in message

    def test_ack_consumed_once(self, repo: Path) -> None:
        gate.write_ack(repo, reason="governance change")
        code, _ = self._guard(repo, str(repo / "scripts" / "gate.py"))
        assert code == 0
        code, _ = self._guard(repo, str(repo / "scripts" / "gate.py"))
        assert code == 2

    def test_pyproject_guarded_content_blocked(self, repo: Path) -> None:
        code, _ = self._guard(
            repo,
            str(repo / "pyproject.toml"),
            old_string="fail_under = 93",
            new_string="fail_under = 50",
        )
        assert code == 2

    def test_pyproject_benign_content_allowed(self, repo: Path) -> None:
        code, _ = self._guard(
            repo,
            str(repo / "pyproject.toml"),
            old_string="line-length = 100",
            new_string="line-length = 100  # unchanged",
        )
        assert code == 0

    def test_file_outside_repo_allowed(self, repo: Path, tmp_path: Path) -> None:
        code, _ = self._guard(repo, str(tmp_path / "elsewhere" / "gate.py"))
        assert code == 0


class TestPostEdit:
    def _payload_for(self, repo: Path, rel: str) -> dict[str, Any]:
        return _payload(tool_name="Edit", tool_input={"file_path": str(repo / rel)})

    def test_non_python_ignored(self, repo: Path) -> None:
        code, _ = claude_hooks.hook_post_edit(
            self._payload_for(repo, "README.md"), repo, run_lint=lambda path: "never"
        )
        assert code == 0

    def test_python_outside_source_trees_ignored(self, repo: Path) -> None:
        code, _ = claude_hooks.hook_post_edit(
            self._payload_for(repo, "notebooks/x.py"), repo, run_lint=lambda path: "never"
        )
        assert code == 0

    def test_lint_failure_feeds_back(self, repo: Path) -> None:
        src = repo / "packages" / "alpha-core" / "src"
        src.mkdir(parents=True)
        (src / "bad.py").write_text("import os\n")
        code, message = claude_hooks.hook_post_edit(
            self._payload_for(repo, "packages/alpha-core/src/bad.py"),
            repo,
            run_lint=lambda path: "F401 unused import",
        )
        assert code == 2
        assert "F401" in message

    def test_lint_pass_records_session_edit(self, repo: Path) -> None:
        src = repo / "packages" / "alpha-core" / "src"
        src.mkdir(parents=True)
        (src / "ok.py").write_text("x = 1\n")
        code, _ = claude_hooks.hook_post_edit(
            self._payload_for(repo, "packages/alpha-core/src/ok.py"),
            repo,
            run_lint=lambda path: None,
        )
        assert code == 0
        state = claude_hooks.load_session(repo, "s1")
        assert "packages/alpha-core/src/ok.py" in state["edited_files"]


class TestStopGuard:
    def _stop(self, repo: Path, **kwargs: Any) -> tuple[int, str]:
        return claude_hooks.hook_stop_guard(_payload(**kwargs), repo)

    def _record_edit(self, repo: Path, rel: str) -> None:
        claude_hooks.record_edit(repo, "s1", rel)

    def test_no_edits_allowed(self, repo: Path) -> None:
        code, _ = self._stop(repo)
        assert code == 0

    def test_stop_hook_active_never_loops(self, repo: Path) -> None:
        self._record_edit(repo, "packages/alpha-core/src/a.py")
        code, _ = self._stop(repo, stop_hook_active=True)
        assert code == 0

    def test_source_edit_without_stamp_blocked(self, repo: Path) -> None:
        self._record_edit(repo, "packages/alpha-core/src/a.py")
        code, message = self._stop(repo)
        assert code == 2
        assert "gate.py fast" in message

    def test_source_edit_with_stamp_allowed(self, repo: Path) -> None:
        self._record_edit(repo, "packages/alpha-core/src/a.py")
        gate.write_stamp(repo, "fast", steps=[("all", 1.0, True)], duration=1.0)
        code, _ = self._stop(repo)
        assert code == 0

    def test_quant_edit_requires_attestation(self, repo: Path) -> None:
        self._record_edit(repo, "packages/alpha-validation/src/alpha_validation/dsr.py")
        gate.write_stamp(repo, "fast", steps=[("all", 1.0, True)], duration=1.0)
        code, message = self._stop(repo)
        assert code == 2
        assert "/verify-quant" in message

    def test_quant_edit_with_attestation_allowed(self, repo: Path) -> None:
        self._record_edit(repo, "packages/alpha-validation/src/alpha_validation/dsr.py")
        gate.write_stamp(repo, "fast", steps=[("all", 1.0, True)], duration=1.0)
        report = {
            "claims": [
                {
                    "claim": "c",
                    "source": "s",
                    "location": "l",
                    "verdict": "VERIFIED",
                }
            ],
            "docstring_citations": {"ok": True, "missing": []},
            "overall": "PASS",
        }
        assert gate.attest(repo, "quant", json.dumps(report)) == 0
        code, _ = self._stop(repo)
        assert code == 0

    def test_block_budget_yields_after_three(self, repo: Path) -> None:
        self._record_edit(repo, "packages/alpha-core/src/a.py")
        for _ in range(3):
            code, _ = self._stop(repo)
            assert code == 2
        code, message = self._stop(repo)
        assert code == 0
        assert "warning" in message.lower()


class TestContextHooks:
    def test_prompt_context_brief(self, repo: Path) -> None:
        code, text = claude_hooks.hook_prompt_context(_payload(), repo)
        assert code == 0
        branch = _git(repo, "branch", "--show-current")
        assert branch in text
        assert "stamp" in text.lower()

    def test_session_start_mentions_contract(self, repo: Path) -> None:
        code, text = claude_hooks.hook_session_start(_payload(), repo)
        assert code == 0
        lowered = text.lower()
        assert "gate" in lowered
        assert "smallest diff" in lowered
        assert "/plan-feature" in lowered

    def test_pre_compact_guidance(self, repo: Path) -> None:
        code, text = claude_hooks.hook_pre_compact(_payload(), repo)
        assert code == 0
        assert "failing tests" in text.lower()
