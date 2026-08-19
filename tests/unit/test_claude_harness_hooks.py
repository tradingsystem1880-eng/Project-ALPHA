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
import harness_awareness
import pytest

from tests.unit._harness_support import git as _git
from tests.unit._harness_support import hook_payload as _payload


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

    def test_quoted_operators_stay_inside_message(self) -> None:
        cmd = "git commit -m 'feat: add x; also y && z | w'"
        assert len(claude_hooks.extract_commands(cmd)) == 1
        assert claude_hooks.commit_message_of(cmd) == "feat: add x; also y && z | w"

    def test_quoted_newline_stays_inside_message(self) -> None:
        cmd = 'git add -A && git commit -q -m "feat(scope): summary\n\nbody; with semicolon"'
        segments = claude_hooks.extract_commands(cmd)
        assert len(segments) == 2
        assert claude_hooks.commit_message_of(cmd) == "feat(scope): summary\n\nbody; with semicolon"

    def test_unquoted_newline_splits_commands(self) -> None:
        segments = claude_hooks.extract_commands("git add -A\ngit commit -m 'fix: y'")
        assert len(segments) == 2
        assert claude_hooks.contains_git_commit("git add -A\ngit commit -m 'fix: y'")

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
        assert claude_hooks.docs_only(["README.md", "docs/x.md", "docs/adr/0001.md"])
        assert claude_hooks.docs_only([".agents/skills/x/SKILL.md"])

    def test_control_plane_never_waived(self) -> None:
        assert not claude_hooks.docs_only([".claude/settings.json"])
        assert not claude_hooks.docs_only([".claude/agents/navigator.md"])
        assert not claude_hooks.docs_only([".codex/config.toml"])

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
            "reviewed_diff_hash": gate.scoped_diff_hash(repo, gate.matches_risk),
            "files_reviewed": ["packages/alpha-backtest/src/alpha_backtest/engine.py"],
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


class TestCommitMessageForms:
    def test_combined_short_flags(self) -> None:
        assert claude_hooks.commit_message_of("git commit -am 'feat: x'") == "feat: x"
        assert claude_hooks.commit_message_of("git commit -qm 'fix: y'") == "fix: y"

    def test_heredoc_body_unwrapped(self) -> None:
        cmd = "git commit -m \"$(cat <<'EOF'\nfeat(x): heredoc subject\n\nbody\nEOF\n)\""
        assert claude_hooks.commit_message_of(cmd) == "feat(x): heredoc subject\n\nbody"

    def test_file_message_undeterminable(self) -> None:
        assert claude_hooks.commit_message_of("git commit -F msg.txt") is None


class TestDestructiveVerbs:
    @pytest.mark.parametrize(
        "command",
        [
            "git commit --amend -m 'fix: x'",
            "git commit --no-verify -m 'fix: x'",
            "git commit -n -m 'fix: x'",
            "git reset --hard HEAD~1",
            "git checkout -- .",
            "git restore .",
            "git clean -fd",
            "git stash drop",
            "git push --force origin main",
            "rm -rf packages",
            "rm -r /Users/someone/project",
        ],
    )
    def test_blocked(self, repo: Path, command: str) -> None:
        code, message = claude_hooks.hook_pre_bash_guard(
            _payload(tool_input={"command": command}, cwd=str(repo)), repo
        )
        assert code == 2, message
        assert "BLOCKED" in message

    @pytest.mark.parametrize(
        "command",
        [
            "git commit -m 'feat: x'",
            "git checkout main",
            "git restore --staged a.py",
            "git stash list",
            "rm -rf /tmp/claude-501/scratch/thing",
            "rm file.txt",
            "git reset HEAD a.py",
        ],
    )
    def test_not_flagged(self, repo: Path, command: str) -> None:
        tokens = claude_hooks.extract_commands(command)[0]
        assert claude_hooks.destructive_reason(tokens, repo, repo) is None

    def test_chmod_on_control_plane_blocked(self, repo: Path) -> None:
        (repo / "scripts").mkdir()
        (repo / "scripts" / "gate.py").write_text("")
        tokens = ["chmod", "+x", "scripts/gate.py"]
        assert claude_hooks.destructive_reason(tokens, repo, repo)
        assert claude_hooks.destructive_reason(["chmod", "+x", "run.sh"], repo, repo) is None


class TestBashWriteDetection:
    def test_targets_detected(self, repo: Path) -> None:
        py_open = "python3 -c \"open('scripts/gate.py','w').write('x')\""
        py_path = "python3 -c \"Path('a.md').write_text('x')\""
        cases = {
            "echo hi > out.txt": ["out.txt"],
            "cat a >> notes.log": ["notes.log"],
            "sed -i '' 's/a/b/' scripts/gate.py": ["scripts/gate.py"],
            "uv run ruff format scripts/gate.py": ["scripts/gate.py"],
            "uv run ruff format --check scripts/gate.py": [],
            "uv run ruff check --fix scripts/x.py": ["scripts/x.py"],
            py_open: ["scripts/gate.py"],
            "cp a.py b.py": ["b.py"],
            "echo x | tee -a t.txt": ["t.txt"],
            "echo hi > /dev/null": [],
            py_path: ["a.md"],
        }
        for command, expected in cases.items():
            assert claude_hooks.bash_write_targets(command, repo, repo) == expected, command

    def test_out_of_repo_targets_ignored(self, repo: Path, tmp_path: Path) -> None:
        other = tmp_path / "elsewhere.txt"
        assert claude_hooks.bash_write_targets(f"echo hi > {other}", repo, repo) == []

    def test_protected_shell_write_needs_ack(self, repo: Path) -> None:
        payload = _payload(tool_input={"command": "echo x > scripts/gate.py"}, cwd=str(repo))
        code, message = claude_hooks.hook_pre_bash_guard(payload, repo)
        assert code == 2 and "ack" in message
        gate.write_ack(repo, reason="r", path="scripts/gate.py")
        code, _ = claude_hooks.hook_pre_bash_guard(payload, repo)
        assert code == 0

    def test_post_bash_records_edit(self, repo: Path) -> None:
        payload = _payload(tool_input={"command": "echo x > tracked.py"}, cwd=str(repo))
        code, _ = claude_hooks.hook_post_bash(payload, repo)
        assert code == 0
        state = claude_hooks.load_session(repo, "s1")
        assert "tracked.py" in state["edited_files"]


class TestHiddenHoldout:
    def _holdout_file(self, repo: Path) -> Path:
        holdout = repo / "tests" / "holdout"
        holdout.mkdir(parents=True)
        target = holdout / "test_secret.py"
        target.write_text("def test_x(): pass\n")
        return target

    def test_read_edit_bash_denied_without_owner(self, repo: Path) -> None:
        target = self._holdout_file(repo)
        tool = {"file_path": str(target)}
        code, msg = claude_hooks.hook_pre_read_guard(_payload(tool_input=tool), repo)
        assert code == 2 and "HIDDEN HOLDOUT" in msg
        code, _ = claude_hooks.hook_pre_edit_guard(_payload(tool_input=tool), repo)
        assert code == 2
        code, _ = claude_hooks.hook_pre_bash_guard(
            _payload(tool_input={"command": "cat tests/holdout/test_secret.py"}, cwd=str(repo)),
            repo,
        )
        assert code == 2
        code, _ = claude_hooks.hook_pre_bash_guard(
            _payload(
                tool_input={"command": "uv run pytest tests/holdout/test_secret.py"},
                cwd=str(repo),
            ),
            repo,
        )
        assert code == 0, "running the holdout suite is allowed; reading it is not"

    def test_git_may_move_but_never_render_holdout_content(self, repo: Path) -> None:
        self._holdout_file(repo)
        for cmd in (
            "git show HEAD:tests/holdout/test_secret.py",
            "git diff HEAD -- tests/holdout",
            "git log -p -- tests/holdout/test_secret.py",
            "git grep -n threshold tests/holdout/",
        ):
            code, msg = claude_hooks.hook_pre_bash_guard(
                _payload(tool_input={"command": cmd}, cwd=str(repo)), repo
            )
            assert code == 2 and "HIDDEN HOLDOUT" in msg, cmd
        for cmd in ("git mv tests/holdout_seed tests/holdout", "git add tests/holdout"):
            code, _ = claude_hooks.hook_pre_bash_guard(
                _payload(tool_input={"command": cmd}, cwd=str(repo)), repo
            )
            assert code == 0, cmd

    def test_reviewer_agent_may_read(self, repo: Path) -> None:
        target = self._holdout_file(repo)
        payload = _payload(tool_input={"file_path": str(target)}, agent_type="independent-reviewer")
        assert claude_hooks.hook_pre_read_guard(payload, repo)[0] == 0

    def test_owner_may_edit(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gate.owner_init(repo, "correct-horse-battery")
        monkeypatch.setenv(gate.OWNER_TOKEN_ENV, "correct-horse-battery")
        target = self._holdout_file(repo)
        code, _ = claude_hooks.hook_pre_edit_guard(
            _payload(tool_input={"file_path": str(target)}), repo
        )
        assert code == 0


class TestMcpGuard:
    def test_owner_verbs_denied(self, repo: Path) -> None:
        for tool in ("mcp__alpha__research_approve", "mcp__alpha__reveal_holdout"):
            code, msg = claude_hooks.hook_pre_mcp_guard(_payload(tool_name=tool), repo)
            assert code == 2 and "owner-authority" in msg

    def test_ordinary_tools_allowed_and_codex_logged(self, repo: Path) -> None:
        code, _ = claude_hooks.hook_pre_mcp_guard(_payload(tool_name="mcp__alpha__get_run"), repo)
        assert code == 0
        code, _ = claude_hooks.hook_pre_mcp_guard(_payload(tool_name="mcp__codex__codex"), repo)
        assert code == 0
        assert [e["event"] for e in gate.read_audit(repo, kind="codex_call")] == ["codex_call"]


class TestSubagentStop:
    def test_non_json_agent_ignored(self, repo: Path) -> None:
        payload = _payload(agent_type="navigator", last_assistant_message="prose")
        assert claude_hooks.hook_subagent_stop(payload, repo) == (0, "")

    def test_json_agent_validated(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def fake(root: Path, schema: str, text: str) -> str | None:
            calls.append(schema)
            return None if text.strip().startswith("{") else "not json"

        monkeypatch.setattr(claude_hooks, "validate_against_schema", fake)
        payload = _payload(
            agent_type="independent-reviewer", agent_id="a1", last_assistant_message="prose"
        )
        code, msg = claude_hooks.hook_subagent_stop(payload, repo)
        assert code == 2 and "ReviewVerdict" in msg
        code, _ = claude_hooks.hook_subagent_stop(payload, repo)
        assert code == 2
        code, _ = claude_hooks.hook_subagent_stop(payload, repo)
        assert code == 0, "block budget per agent exhausted -> allow"
        payload["last_assistant_message"] = '{"verdict": "APPROVE"}'
        payload["agent_id"] = "a2"
        assert claude_hooks.hook_subagent_stop(payload, repo) == (0, "")
        assert calls and set(calls) == {"ReviewVerdict"}

    def test_codex_liaison_accepts_review_or_research(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []

        def fake(root: Path, schema: str, text: str) -> str | None:
            seen.append(schema)
            return None if schema in text else f"not a {schema}"

        monkeypatch.setattr(claude_hooks, "validate_against_schema", fake)
        for kind in ("CodexReview", "CodexResearch"):
            payload = _payload(
                agent_type="codex-liaison", agent_id=kind, last_assistant_message=kind
            )
            assert claude_hooks.hook_subagent_stop(payload, repo) == (0, "")
        payload = _payload(agent_type="codex-liaison", agent_id="x", last_assistant_message="prose")
        code, msg = claude_hooks.hook_subagent_stop(payload, repo)
        assert code == 2 and "CodexReview|CodexResearch" in msg
        assert set(seen) == {"CodexReview", "CodexResearch"}

    def test_real_validation_against_models(self, repo: Path) -> None:
        root = Path(__file__).resolve().parents[2]
        if not (root / ".venv" / "bin" / "python").is_file():
            pytest.skip("project venv unavailable")
        good = json.dumps(
            {
                "verdict": "APPROVE",
                "findings": [],
                "reviewed_diff_hash": "0" * 64,
                "files_reviewed": [],
            }
        )
        assert claude_hooks.validate_against_schema(root, "ReviewVerdict", good) is None
        fenced = "```json\n" + good + "\n```"
        assert claude_hooks.validate_against_schema(root, "ReviewVerdict", fenced) is None
        assert claude_hooks.validate_against_schema(root, "ReviewVerdict", '{"verdict": "MAYBE"}')


class TestTaskCompleted:
    def test_no_test_reference_allows(self, repo: Path) -> None:
        assert claude_hooks.hook_task_completed(_payload(task_title="do thing"), repo) == (0, "")

    def test_failing_named_test_blocks(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        tests = repo / "tests" / "unit"
        tests.mkdir(parents=True)
        (tests / "test_thing.py").write_text("def test_x():\n    assert False\n")

        class Result:
            returncode = 1
            stdout = "FAILED tests/unit/test_thing.py::test_x"
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: Result())
        code, msg = claude_hooks.hook_task_completed(
            _payload(task_title="Fix tests/unit/test_thing.py"), repo
        )
        assert code == 2 and "FAIL" in msg


class TestConfigChange:
    def test_recent_ack_allows(self, repo: Path) -> None:
        gate.write_ack(repo, reason="r")
        gate.consume_ack(repo)
        payload = _payload(config_source="project_settings", config_path=".claude/settings.json")
        assert claude_hooks.hook_config_change(payload, repo)[0] == 0

    def test_unacked_change_blocked(self, repo: Path) -> None:
        payload = _payload(config_source="skills", config_path=".claude/skills/x/SKILL.md")
        code, msg = claude_hooks.hook_config_change(payload, repo)
        assert code == 2 and "ack" in msg
        assert gate.read_audit(repo, kind="config_change_unacked")

    def test_policy_settings_never_blocked(self, repo: Path) -> None:
        payload = _payload(config_source="policy_settings", config_path="x")
        assert claude_hooks.hook_config_change(payload, repo)[0] == 0


class TestTelemetryHooks:
    def test_failure_recorded(self, repo: Path) -> None:
        claude_hooks.hook_post_tool_failure(
            _payload(tool_name="Bash", tool_input={}, error="boom"), repo
        )
        state = claude_hooks.load_session(repo, "s1")
        assert state["failures"][0]["tool"] == "Bash"

    def test_tool_log_audits_dispatch(self, repo: Path) -> None:
        claude_hooks.hook_tool_log(
            _payload(tool_name="Agent", tool_input={"subagent_type": "navigator"}), repo
        )
        events = gate.read_audit(repo, kind="dispatch")
        assert events and "navigator" in events[0]["detail"]


class TestStopBudgetAudit:
    def test_exhaustion_is_audited_and_flagged(self, repo: Path) -> None:
        claude_hooks.record_edit(repo, "s1", "packages/alpha-core/src/a.py")
        for _ in range(claude_hooks.STOP_BLOCK_BUDGET):
            claude_hooks.hook_stop_guard(_payload(), repo)
        code, msg = claude_hooks.hook_stop_guard(_payload(), repo)
        assert code == 0 and "UNVERIFIED" in msg
        assert claude_hooks.load_session(repo, "s1")["stop_budget_exhausted"] is True
        assert len(gate.read_audit(repo, kind="stop_budget_exhausted")) == 1
        claude_hooks.hook_stop_guard(_payload(), repo)
        assert len(gate.read_audit(repo, kind="stop_budget_exhausted")) == 1, "audited once"
        _, brief = claude_hooks.hook_prompt_context(_payload(), repo)
        assert "stop-budget:EXHAUSTED" in brief

    def test_non_lintable_source_edit_counts(self, repo: Path) -> None:
        # A13: any tracked non-docs edit counts as a source edit at Stop.
        claude_hooks.hook_post_edit(
            _payload(tool_input={"file_path": str(repo / "pyproject.toml")}),
            repo,
            run_lint=lambda p: None,
        )
        code, _ = claude_hooks.hook_stop_guard(_payload(), repo)
        assert code == 2


class TestKarpathyAlwaysOn:
    def test_session_start_and_post_compact_inject_block(self, repo: Path) -> None:
        _, start = claude_hooks.hook_session_start(_payload(), repo)
        _, post = claude_hooks.hook_post_compact(_payload(), repo)
        for text in (start, post):
            assert "KARPATHY GUIDELINES" in text
            for heading in (
                "Think Before Coding",
                "Simplicity First",
                "Surgical Changes",
                "Goal-Driven Execution",
            ):
                assert heading in text
        assert "OWNER TOKEN NOT CONFIGURED" in start

    def test_session_start_and_post_compact_carry_repo_brief(self, repo: Path) -> None:
        _, start = claude_hooks.hook_session_start(_payload(), repo)
        _, post = claude_hooks.hook_post_compact(_payload(), repo)
        for text in (start, post):
            assert "REPO BRIEF" in text
            assert "recent commits:" in text
        assert (repo / ".claude" / "state" / harness_awareness.BRIEF_FILE).exists()

    def test_prompt_brief_reminder(self, repo: Path) -> None:
        _, brief = claude_hooks.hook_prompt_context(_payload(), repo)
        assert "karpathy: think→simplify→surgical→goal-verify" in brief
        assert "owner-token:UNSET" in brief

    def test_post_compact_lists_obligations(self, repo: Path) -> None:
        claude_hooks.record_edit(
            repo, "s1", "packages/alpha-validation/src/alpha_validation/dsr.py"
        )
        _, post = claude_hooks.hook_post_compact(_payload(), repo)
        assert "OWED: /verify-quant" in post
        assert "dsr.py" in post

    def test_over_eager_edit_is_warned_and_audited_never_blocked(self, repo: Path) -> None:
        plans = repo / "docs" / "superpowers" / "plans"
        plans.mkdir(parents=True)
        block = json.dumps({"files": ["packages/alpha-core/src/alpha_core/x.py"], "slices": []})
        (plans / "2026-02-01-open.md").write_text(f"# Open\n\n```json\n{block}\n```\n")
        in_scope = "packages/alpha-core/src/alpha_core/x.py"
        out_of_scope = "packages/alpha-core/src/alpha_core/y.py"
        claude_hooks.record_edit(repo, "s1", in_scope)
        claude_hooks.record_edit(repo, "s1", out_of_scope)
        claude_hooks.record_edit(repo, "s1", "docs/notes.md")  # docs are never over-eager
        state = claude_hooks.load_session(repo, "s1")
        assert state["over_eager"] == [out_of_scope]
        events = [e["detail"] for e in gate.read_audit(repo, kind="over_eager_edit")]
        assert events == [out_of_scope]
        code, post = claude_hooks.hook_post_compact(_payload(), repo)
        assert code == 0
        assert "SCOPE WARNING: 1 edit(s)" in post and out_of_scope in post
        # No declared scope (plan without a block) => the warn is disarmed.
        (plans / "2026-02-01-open.md").write_text("# Open plan, no front block\n")
        claude_hooks.record_edit(repo, "s2", out_of_scope)
        assert claude_hooks.load_session(repo, "s2")["over_eager"] == []


class TestAgentBashSandbox:
    """W6: sandboxed subagents may only run allow-listed command prefixes (payload agent_type)."""

    def _run(self, repo: Path, agent: str, cmd: str) -> tuple[int, str]:
        return claude_hooks.hook_pre_bash_guard(
            _payload(tool_input={"command": cmd}, cwd=str(repo), agent_type=agent), repo
        )

    def test_main_session_and_unlisted_agents_are_unaffected(self, repo: Path) -> None:
        for agent, cmd in (("", "rm -rf build"), ("navigator", "uv sync")):
            segments = claude_hooks.extract_commands(cmd)
            assert claude_hooks.agent_bash_violation(agent, cmd, segments) is None

    @pytest.mark.parametrize(
        ("agent", "cmd"),
        [
            ("quant-verifier", "uv run pytest tests/oracles/test_metamorphic_dsr.py -q"),
            ("quant-verifier", "uv run python -c 'import math; print(math.erf(1.0))'"),
            ("quant-verifier", "python3 scripts/codex_bridge.py research --question 'DSR?'"),
            ("codex-liaison", "python3 scripts/codex_bridge.py review --uncommitted"),
            ("independent-reviewer", "git diff HEAD -- packages && uv run pytest tests/holdout -q"),
            ("red-team-code", "rg -n 'shift\\(-' packages | head"),
        ],
    )
    def test_allowed_prefixes_pass(self, repo: Path, agent: str, cmd: str) -> None:
        assert self._run(repo, agent, cmd)[0] == 0, cmd

    @pytest.mark.parametrize(
        ("agent", "cmd"),
        [
            ("quant-verifier", "uv run pytest tests/unit -q"),  # only the oracle suites
            ("quant-verifier", "python3 scripts/codex_bridge.py review --uncommitted"),
            ("codex-liaison", "uv run pytest tests/oracles -q"),
            ("codex-liaison", "codex exec 'hi'"),  # only through the bridge
            ("independent-reviewer", "git commit -m 'feat: x'"),
            ("independent-reviewer", "uv run python scripts/gate.py override --reason x"),
            ("red-team-code", "echo $(cat tracked.py)"),
            ("red-team-code", "lsof -i"),  # tokens match exactly; only paths use startswith
        ],
    )
    def test_out_of_sandbox_commands_are_blocked(self, repo: Path, agent: str, cmd: str) -> None:
        code, msg = self._run(repo, agent, cmd)
        assert code == 2 and "BLOCKED" in msg and "sandbox" in msg, cmd


def test_prompt_context_hashes_the_tree_once(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gate.write_stamp(repo, "fast", steps=[], duration=0.1)  # no stamp ⇒ nothing hashes at all
    calls = 0
    real = gate.compute_tree_hash

    def counted(root: Path) -> str:
        nonlocal calls
        calls += 1
        return real(root)

    monkeypatch.setattr(gate, "compute_tree_hash", counted)
    code, _ = claude_hooks.hook_prompt_context({"session_id": "s1"}, repo)
    assert code == 0
    assert calls == 1
