"""Tests for the Claude Code harness gate runner (scripts/gate.py).

The gate runner is the single source of truth for tree-hash stamps, path
tiers, attestation artifacts, one-shot overrides/acks, the audit journal,
and the harness doctor. Everything here runs against throwaway git repos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gate
import pytest

from tests.unit._harness_support import git as _git


@pytest.fixture()
def repo(harness_repo: Path) -> Path:
    return harness_repo


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

    def test_invariant_across_pure_commit(self, repo: Path) -> None:
        """A commit changes no file content, so it must not invalidate the hash.

        Without this, every commit in an atomic sequence forces a full gate
        re-run even though the certified content is byte-identical.
        """
        (repo / "tracked.py").write_text("x = 2\n")
        _git(repo, "add", "-A")
        before = gate.compute_tree_hash(repo)
        _git(repo, "commit", "--quiet", "-m", "feat: change")
        assert gate.compute_tree_hash(repo) == before

    def test_stamp_survives_pure_commit(self, repo: Path) -> None:
        (repo / "tracked.py").write_text("x = 2\n")
        _git(repo, "add", "-A")
        gate.write_stamp(repo, "full", steps=[("all", 1.0, True)], duration=1.0)
        assert gate.stamp_is_valid(repo, "full")
        _git(repo, "commit", "--quiet", "-m", "feat: change")
        assert gate.stamp_is_valid(repo, "full")


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
            "reviewed_diff_hash": gate.scoped_diff_hash(repo, gate.matches_risk),
            "files_reviewed": gate.scoped_changed_paths(repo, gate.matches_risk),
        }
        verdict.update(overrides)
        return verdict

    def test_review_attest_approve_binds_risk_diff(self, repo: Path) -> None:
        assert gate.attest(repo, "review", json.dumps(self._review(repo))) == 0
        assert gate.review_verdict_valid(repo)
        (repo / "tracked.py").write_text("x = 6\n")
        assert gate.review_verdict_valid(repo), "out-of-scope edit must not invalidate"
        risky = repo / "packages" / "alpha-backtest" / "src" / "alpha_backtest"
        risky.mkdir(parents=True)
        (risky / "engine.py").write_text("e = 1\n")
        assert not gate.review_verdict_valid(repo), "risk-tier edit after review invalidates"

    def test_review_attest_rejects_unlisted_risk_file(self, repo: Path) -> None:
        risky = repo / "packages" / "alpha-backtest" / "src" / "alpha_backtest"
        risky.mkdir(parents=True)
        (risky / "engine.py").write_text("e = 1\n")
        verdict = self._review(repo, files_reviewed=[])
        assert gate.attest(repo, "review", json.dumps(verdict)) != 0
        verdict = self._review(repo)
        assert "packages/alpha-backtest/src/alpha_backtest/engine.py" in verdict["files_reviewed"]
        assert gate.attest(repo, "review", json.dumps(verdict)) == 0

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

    def test_review_attest_rejects_stale_diff_hash(self, repo: Path) -> None:
        verdict = self._review(repo, reviewed_diff_hash="0" * 64)
        assert gate.attest(repo, "review", json.dumps(verdict)) != 0

    def test_quant_attest_rejects_unlisted_quant_file(self, repo: Path) -> None:
        quant = repo / "packages" / "alpha-validation" / "src" / "alpha_validation"
        quant.mkdir(parents=True)
        (quant / "dsr.py").write_text("a = 1\n")
        assert gate.attest(repo, "quant", json.dumps(self._quant_report())) != 0
        listed = self._quant_report(
            files_reviewed=["packages/alpha-validation/src/alpha_validation/dsr.py"]
        )
        assert gate.attest(repo, "quant", json.dumps(listed)) == 0

    def test_quant_attest_rejects_pass_with_failed_spot_check(self, repo: Path) -> None:
        report = self._quant_report(
            numeric_spot_checks=[
                {
                    "description": "PSR(0)",
                    "expected": 0.5,
                    "observed": 0.7,
                    "tolerance": 1e-9,
                    "ok": False,
                }
            ]
        )
        assert gate.attest(repo, "quant", json.dumps(report)) != 0
        assert (
            gate.attest(repo, "quant", json.dumps(self._quant_report(oracles_present=False))) != 0
        )


class TestOnceTokens:
    def test_override_consumed_once(self, repo: Path) -> None:
        gate.write_override(repo, reason="emergency")
        assert gate.consume_override(repo) is not None
        assert gate.consume_override(repo) is None

    def test_ack_consumed_once(self, repo: Path) -> None:
        gate.write_ack(repo, reason="editing gate itself")
        assert gate.consume_ack(repo) is not None
        assert gate.consume_ack(repo) is None

    def test_disarming_records_a_drop_not_a_use(self, repo: Path) -> None:
        """The digest stays honest only if a dropped token differs from a spent one."""
        gate.write_ack(repo, reason="never needed after all")
        assert gate.disarm_token(repo, "ack") is not None
        assert gate.consume_ack(repo) is None  # gone, so it cannot fire later

        kinds = [e["event"] for e in gate.read_audit(repo)]
        assert "ack_disarmed" in kinds
        assert "ack_consumed" not in kinds

    def test_disarming_nothing_is_not_an_error(self, repo: Path) -> None:
        assert gate.disarm_token(repo, "ack") is None
        assert gate.disarm_token(repo, "override") is None

    def test_a_disarmed_token_is_no_longer_live(self, repo: Path) -> None:
        gate.write_override(repo, reason="armed then abandoned")
        assert "LIVE" in gate.audit_digest(repo)
        gate.disarm_token(repo, "override")
        assert "LIVE" not in gate.audit_digest(repo)


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
    (claude / "statusline.py").write_text("print('ok')\n")
    scripts = repo / "scripts"
    scripts.mkdir(exist_ok=True)
    for name in ("gate.py", "claude_hooks.py", "harness_models.py", "codex_bridge.py"):
        (scripts / name).write_text("# stub\n")
    gate.write_baseline(repo, reason="test", authorized_by="test")


class TestOwnerToken:
    def test_unconfigured_is_self_serve_but_labelled(self, repo: Path) -> None:
        allowed, who = gate.authorize_escape(repo, kind="override")
        assert allowed and "not configured" in who

    def test_configured_requires_matching_env_token(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gate.owner_init(repo, "correct-horse-battery")
        monkeypatch.delenv(gate.OWNER_TOKEN_ENV, raising=False)
        allowed, who = gate.authorize_escape(repo, kind="override")
        assert not allowed and "owner" in who
        monkeypatch.setenv(gate.OWNER_TOKEN_ENV, "wrong-token-value")
        assert not gate.owner_present(repo)
        monkeypatch.setenv(gate.OWNER_TOKEN_ENV, "correct-horse-battery")
        assert gate.owner_present(repo)
        allowed, who = gate.authorize_escape(repo, kind="override")
        assert allowed and who == "owner"

    def test_owner_file_stores_hash_not_token(self, repo: Path) -> None:
        gate.owner_init(repo, "correct-horse-battery")
        raw = (repo / gate.OWNER_FILE).read_text()
        assert "correct-horse-battery" not in raw
        assert "ownerTokenHash" in raw

    def test_short_token_refused(self, repo: Path) -> None:
        with pytest.raises(ValueError):
            gate.owner_init(repo, "short")

    def test_agent_low_risk_ack_budget(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        gate.owner_init(repo, "correct-horse-battery")
        monkeypatch.delenv(gate.OWNER_TOKEN_ENV, raising=False)
        monkeypatch.setenv("CLAUDE_SESSION_ID", "s1")
        for _ in range(gate.AGENT_ACK_LIMIT):
            allowed, _who = gate.authorize_escape(
                repo, kind="ack", path=".claude/agents/navigator.md"
            )
            assert allowed
        allowed, who = gate.authorize_escape(repo, kind="ack", path=".claude/agents/navigator.md")
        assert not allowed and "budget" in who
        allowed, _ = gate.authorize_escape(repo, kind="ack", path="scripts/gate.py")
        assert not allowed, "gate.py is never agent-ackable once the owner token exists"


class TestAckPathBinding:
    def test_path_bound_ack_only_clears_that_path(self, repo: Path) -> None:
        gate.write_ack(repo, reason="r", path="scripts/gate.py")
        assert gate.consume_ack(repo, path="scripts/claude_hooks.py") is None
        assert gate.consume_ack(repo, path="scripts/gate.py") is not None
        assert gate.consume_ack(repo, path="scripts/gate.py") is None

    def test_unbound_ack_clears_any_path(self, repo: Path) -> None:
        gate.write_ack(repo, reason="r")
        assert gate.consume_ack(repo, path="scripts/gate.py") is not None


class TestAuditChain:
    def test_chain_links_and_detects_tampering(self, repo: Path) -> None:
        gate.append_audit(repo, "a", "1")
        gate.append_audit(repo, "b", "2")
        gate.append_audit(repo, "c", "3")
        ok, detail = gate.verify_audit_chain(repo)
        assert ok, detail
        events = gate.read_audit(repo)
        assert [e["event"] for e in events] == ["a", "b", "c"]
        assert events[0]["prev_hash"] == "" and events[1]["prev_hash"] and events[2]["prev_hash"]
        journal = repo / gate.STATE_DIR / gate.AUDIT_FILE
        lines = journal.read_text().splitlines()
        del lines[1]
        journal.write_text("\n".join(lines) + "\n")
        ok, detail = gate.verify_audit_chain(repo)
        assert not ok and "mismatch" in detail

    def test_read_audit_filters(self, repo: Path) -> None:
        gate.append_audit(repo, "x", "1")
        gate.append_audit(repo, "y", "2")
        assert [e["event"] for e in gate.read_audit(repo, kind="y")] == ["y"]
        assert gate.read_audit(repo, since="9999-01-01") == []

    def test_concurrent_append_fork_is_reported_not_failed(self, repo: Path) -> None:
        gate.append_audit(repo, "a", "1")
        gate.append_audit(repo, "b", "2")
        journal = repo / gate.STATE_DIR / gate.AUDIT_FILE
        lines = journal.read_text().splitlines()
        # Simulate the pre-lock race: a sibling of line 2 bound to the same parent.
        sibling = json.loads(lines[1])
        sibling["event"] = "b_sibling"
        lines.append(json.dumps(sibling, sort_keys=True))
        journal.write_text("\n".join(lines) + "\n")
        ok, detail = gate.verify_audit_chain(repo)
        assert ok, detail
        assert "1 concurrent-append fork" in detail
        # A sibling far apart in time is not a fork — it is a rewrite.
        sibling["ts"] = "2000-01-01T00:00:00+00:00"
        lines[-1] = json.dumps(sibling, sort_keys=True)
        journal.write_text("\n".join(lines) + "\n")
        ok, detail = gate.verify_audit_chain(repo)
        assert not ok and "mismatch" in detail

    def test_parallel_appends_keep_one_chain(self, repo: Path) -> None:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: gate.append_audit(repo, "par", str(i)), range(24)))
        ok, detail = gate.verify_audit_chain(repo)
        assert ok, detail
        assert "fork" not in detail, detail
        assert len(gate.read_audit(repo, kind="par")) == 24


class TestProtectedPathsV2:
    @pytest.mark.parametrize(
        "path",
        [
            ".claude/agents/navigator.md",
            ".claude/commands/gate.md",
            ".claude/rules/quant.md",
            ".claude/statusline.py",
            ".mcp.json",
            ".codex/config.toml",
            "scripts/codex_bridge.py",
            "tests/unit/test_claude_harness_gate.py",
            "tests/oracles/test_metamorphic_dsr.py",
            "tests/holdout/test_gauntlet.py",
            ".github/workflows/nightly.yml",
            "AGENTS.md",
        ],
    )
    def test_control_plane_extended(self, path: str) -> None:
        assert gate.protected_reason(path) is not None

    def test_hidden_holdout_predicate(self) -> None:
        assert gate.is_hidden_holdout("tests/holdout/test_x.py")
        assert not gate.is_hidden_holdout("tests/unit/test_x.py")

    def test_agent_ackable_only_low_risk_text(self) -> None:
        assert gate.agent_ackable(".claude/agents/x.md")
        assert gate.agent_ackable(".claude/rules/x.md")
        assert not gate.agent_ackable("scripts/gate.py")
        assert not gate.agent_ackable(".claude/settings.json")


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
        gate.write_baseline(repo, reason="t", authorized_by="t")
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
    def test_scoped_changed_paths_tracked_and_untracked(self, repo: Path) -> None:
        quant = repo / "packages" / "alpha-validation" / "src" / "alpha_validation"
        quant.mkdir(parents=True)
        (quant / "dsr.py").write_text("a = 1\n")
        (repo / "tracked.py").write_text("x = 9\n")
        assert gate.scoped_changed_paths(repo, gate.matches_quant) == [
            "packages/alpha-validation/src/alpha_validation/dsr.py"
        ]
        assert gate.scoped_changed_paths(repo, lambda p: p == "tracked.py") == ["tracked.py"]


def _brief_repo(repo: Path) -> None:
    """Populate a throwaway repo with the awareness inputs `gate.py brief` reads."""
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "docs" / "adr" / "0001-first.md").write_text("# ADR-0001 first\n")
    (repo / "docs" / "adr" / "0002-second.md").write_text("# ADR-0002 second\n")
    (repo / "docs" / "adr" / "README.md").write_text("index\n")
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-01-01-old.md").write_text("# Old plan\n\n**Delivery state:** Completed.\n")
    (plans / "2026-02-01-open.md").write_text("# Open plan\n\nGoal: ship it.\n")
    retro = repo / "docs" / "operations" / "retrospectives"
    retro.mkdir(parents=True)
    (retro / "2026-01-05-a.md").write_text("# A\n\n## Watch-outs\n- old one\n")
    (retro / "2026-01-09-b.md").write_text(
        "# B\n\n## What the harness caught\n- x\n\n"
        "## Watch-outs\n- newest watch\n- second\n\n## Next\n"
    )
    (repo / "CLAUDE.md").write_text("see ADR-0001 only\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "docs: awareness fixtures")


class TestBrief:
    def test_brief_reports_tree_facts(self, repo: Path) -> None:
        _brief_repo(repo)
        text = gate.build_brief(repo)
        assert "REPO BRIEF" in text
        assert "docs: awareness fixtures" in text  # recent commits
        assert "2026-02-01-open.md" in text  # newest plan not marked completed
        assert "2026-01-01-old.md" not in text
        assert "newest watch" in text and "second" in text and "old one" not in text
        assert "ADRs: 2 (latest 0002-second.md)" in text
        assert "ADR-0002" in text and "not referenced" in text  # drift alert

    def test_brief_cached_by_tree_hash(self, repo: Path) -> None:
        _brief_repo(repo)
        first = gate.repo_brief(repo)
        cache = repo / ".claude" / "state" / gate.BRIEF_FILE
        assert cache.exists()
        (repo / "CLAUDE.md").write_text("see ADR-0001 and ADR-0002\n")
        second = gate.repo_brief(repo)
        assert first != second
        assert "not referenced" not in second
        assert gate.repo_brief(repo) == second  # cache hit is byte-identical

    def test_brief_cache_is_invalidated_by_a_commit(self, repo: Path) -> None:
        """A commit changes no byte on disk, so a content-only cache key would go stale.

        The brief reports HEAD and the dirty count. Both change on commit while the tree
        hash — which covers file bytes only, so that committing cannot invalidate a gate
        stamp — stays put. Keyed on content alone the brief would keep claiming
        uncommitted files and omitting the commit just made.
        """
        _brief_repo(repo)
        (repo / "note.md").write_text("scratch\n")
        before = gate.repo_brief(repo)
        assert "1 dirty file(s)" in before
        assert "chore: commit the note" not in before

        tree_before = gate.compute_tree_hash(repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "--quiet", "-m", "chore: commit the note")

        assert gate.compute_tree_hash(repo) == tree_before  # the byte content is unchanged
        after = gate.repo_brief(repo)
        assert "0 dirty file(s)" in after
        assert "chore: commit the note" in after

    def test_brief_cache_key_tracks_the_branch(self, repo: Path) -> None:
        _brief_repo(repo)
        key = gate._brief_cache_key(repo)
        _git(repo, "checkout", "--quiet", "-b", "some-other-branch")
        assert gate._brief_cache_key(repo) != key
        assert "some-other-branch" in gate.repo_brief(repo)

    def test_adr_mentions_understand_ranges(self) -> None:
        text = "ADR-0013 and ADRs 0019-0020 plus ADR-0021..0026 (ADRs 0013-0016)"
        assert gate.referenced_adr_ids(text) == {13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 26}

    def test_only_newest_plan_is_considered(self, repo: Path) -> None:
        _brief_repo(repo)
        plans = repo / "docs" / "superpowers" / "plans"
        (plans / "2026-03-01-done.md").write_text("# Done\n\n**Delivery state:** Completed.\n")
        assert gate.open_plan(repo) is None

    def test_brief_survives_missing_inputs(self, repo: Path) -> None:
        text = gate.build_brief(repo)
        assert "REPO BRIEF" in text
        assert "ADRs: 0" in text


class TestIndex:
    def test_index_lists_public_symbols_contracts_and_adrs(self, repo: Path) -> None:
        _brief_repo(repo)
        pkg = repo / "packages" / "alpha-core" / "src" / "alpha_core"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text('__all__ = ["Bar"]\n')
        (pkg / "types.py").write_text(
            "class Bar:\n    pass\n\ndef _private() -> None:\n    pass\n\ndef public_fn() -> int:\n"
            "    return 1\n"
        )
        (repo / "pyproject.toml").write_text(
            "[tool.importlinter]\nroot_packages = ['alpha_core']\n"
            "[[tool.importlinter.contracts]]\nname = 'alpha_core imports nothing internal'\n"
            "type = 'forbidden'\n"
        )
        index = gate.build_index(repo, cli=False)
        assert index["packages"]["alpha_core"]["types.py"] == ["Bar", "public_fn"]
        assert index["packages"]["alpha_core"]["__init__.py"] == ["Bar"]
        assert index["import_linter_contracts"] == ["alpha_core imports nothing internal"]
        assert index["adrs"] == ["0001-first.md", "0002-second.md"]
        assert index["cli_commands"] == {"unavailable": "cli=False"}
        path = gate.write_index(repo, cli=False)
        assert path == repo / ".claude" / "state" / gate.INDEX_FILE
        assert json.loads(path.read_text())["tree_hash"] == gate.compute_tree_hash(repo)


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
        ok, message = gate.plan_check(plan)
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
        ok, message = gate.plan_check(plan)
        assert not ok
        assert "FeaturePlan invalid" in message

    def test_no_front_block_fails(self, tmp_path: Path) -> None:
        plan = tmp_path / "p.md"
        plan.write_text("# Plan without a block\n\n```json\nnot json\n```\n")
        ok, message = gate.plan_check(plan)
        assert not ok and "no fenced" in message
        assert gate.plan_front_block("no fences at all") is None

    def test_active_plan_scope_reads_without_pydantic(self, repo: Path) -> None:
        plans = repo / "docs" / "superpowers" / "plans"
        plans.mkdir(parents=True)
        (plans / "2026-01-01-old.md").write_text("# Old\n\n**Delivery state:** Completed.\n")
        (plans / "2026-02-01-open.md").write_text(_plan_doc(_VALID_PLAN))
        name, scope = gate.active_plan_scope(repo)
        assert name == "2026-02-01-open.md"
        assert scope == ["tests/unit/test_x.py", "packages/alpha-core/src/alpha_core/x.py"]
        assert gate.in_plan_scope("tests/unit/test_x.py", scope)
        assert gate.in_plan_scope("packages/alpha-core/src/alpha_core/x.py", scope)
        assert not gate.in_plan_scope("packages/alpha-core/src/alpha_core/y.py", scope)
        assert gate.in_plan_scope("apps/a/b.py", ["apps/a/", "z"])
        assert gate.in_plan_scope("apps/a/b.py", ["apps/*/b.py"])
        (plans / "2026-02-01-open.md").write_text("# Open plan without a block\n")
        assert gate.active_plan_scope(repo) == ("2026-02-01-open.md", [])


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
        only = gate.stage_mutation_tree(repo, [rel], staging)
        assert only == ["src/alpha_validation/dsr.py"]
        assert (staging / "src" / "alpha_validation" / "dsr.py").is_file()
        assert (staging / rel).is_file()  # workspace layout mirrored for source-inspecting tests
        assert (staging / "tests" / "unit" / "test_dsr.py").is_file()
        assert (staging / "tests" / "unit" / "helpers_dsr.py").is_file()  # intra-tests import kept
        assert not (staging / "tests" / "unit" / "test_other.py").exists()  # unrelated test dropped
        cfg = (staging / "pyproject.toml").read_text()
        assert 'only_mutate = ["src/alpha_validation/dsr.py"]' in cfg
        assert 'also_copy = ["packages"]' in cfg
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
        assert gate.staging_only_failures(output) == [
            "--deselect",
            "tests/unit/test_theme_drift.py::test_css[bg]",
            "--ignore",
            "tests/unit/test_broken.py",
        ]
        assert gate.staging_only_failures("3 passed\n") == []

    def test_mutation_verdict_thresholds(self, tmp_path: Path) -> None:
        stats = {"killed": 155, "survived": 37, "total": 192, "skipped": 0}
        assert gate.mutation_kill_rate(stats) == pytest.approx(155 / 192)
        # no baseline: the 0.90 floor applies
        assert gate.mutation_required("m.py", {}) == pytest.approx(gate.MUTATION_MIN_KILL)
        # a module already below the floor must not regress below its recorded baseline
        assert gate.mutation_required("m.py", {"m.py": 0.80}) == pytest.approx(0.80)
        # a module above the floor is held to the floor, not to its own high-water mark
        assert gate.mutation_required("m.py", {"m.py": 0.97}) == pytest.approx(0.90)

    def test_mutate_reports_unavailable_when_runner_cannot_start(self, repo: Path) -> None:
        rel = self._quant_module(repo)
        (repo / "packages/alpha-validation/src/alpha_validation/__init__.py").write_text("")
        (repo / "tests").mkdir()
        (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\nmarkers = []\n")

        def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
            return (False, 0.0, "mutmut: command not found")

        code, report = gate.mutate(repo, [rel], runner=runner)
        assert code == 0  # tooling absence never blocks; it is reported loudly
        assert report["modules"][rel]["status"].startswith("unavailable:")

    def test_mutate_report_surfaces_unattributed_mutants_and_forwards_timeout(
        self, repo: Path
    ) -> None:
        rel = self._quant_module(repo)
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

        code, report = gate.mutate(repo, [rel], runner=runner, timeout=5400.0)
        entry = report["modules"][rel]
        assert code == 1 and entry["status"] == "fail"
        # module-scope mutants mutmut cannot attribute are visible, and NOT credited as kills
        assert entry["no_tests"] == 42 and entry["timeout"] == 1
        assert entry["kill_rate"] == round(1 / 47, 4)
        assert 5400.0 in seen_timeouts

    def test_semgrep_command_and_scope(self, repo: Path) -> None:
        for rel in ("packages/x.py", "docs/a.md", "tests/t.py"):
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text("")
        cmd = gate.semgrep_command(repo, ["packages/x.py", "docs/a.md", "tests/t.py", "gone.py"])
        assert cmd[:2] == ["uvx", "semgrep"] and "--config" in cmd and ".semgrep/alpha.yml" in cmd
        assert cmd[-2:] == ["packages/x.py", "tests/t.py"]  # only python targets
        assert gate.semgrep_command(repo, []) == []

    def test_raise_sites_are_found_by_ast(self, tmp_path: Path) -> None:
        mod = tmp_path / "m.py"
        mod.write_text(
            "def f(x):\n    if x:\n        raise ValueError('a')\n    return 1\n\nraise SystemExit"
        )
        assert gate.raise_sites(mod) == [3, 6]

    def test_uncovered_raise_sites_from_coverage_json(self, repo: Path) -> None:
        body = "def f(x):\n    if x:\n        raise ValueError\n    return 1\n"
        rel = self._quant_module(repo, body=body)
        cov = {"files": {rel: {"missing_lines": [3]}}}
        (repo / "cov.json").write_text(json.dumps(cov))
        assert gate.uncovered_raise_sites(repo, repo / "cov.json", [rel]) == [f"{rel}:3"]
        cov = {"files": {rel: {"missing_lines": []}}}
        (repo / "cov.json").write_text(json.dumps(cov))
        assert gate.uncovered_raise_sites(repo, repo / "cov.json", [rel]) == []

    def test_determinism_runs_twice_under_perturbed_env(self, repo: Path) -> None:
        (repo / "tests" / "integration").mkdir(parents=True)
        (repo / "tests" / "integration" / "test_figure_determinism.py").write_text("")
        seen: list[dict[str, str]] = []

        def runner(cmd: list[str], **kwargs: Any) -> tuple[bool, float, str]:
            env = kwargs.get("env") or {}
            seen.append({k: env[k] for k in ("PYTHONHASHSEED", "TZ", "OMP_NUM_THREADS")})
            assert cmd[-1].endswith("test_figure_determinism.py")
            return (True, 0.1, "")

        ok, detail = gate.determinism(repo, runner=runner)
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

        ok, detail = gate.determinism(repo, runner=runner)
        assert not ok and "pass 2" in detail

    def test_full_gate_adds_on_touch_steps_only_when_quant_source_changed(self, repo: Path) -> None:
        names = [name for name, _ in gate.gate_steps("full", repo)]
        assert "slow oracles" not in names and "mutation gate" not in names
        self._quant_module(repo)
        names = [name for name, _ in gate.gate_steps("full", repo)]
        assert "slow oracles" in names and "mutation gate" in names
        assert "semgrep" not in [name for name, _ in gate.gate_steps("fast", repo)]
        (repo / ".semgrep").mkdir()
        (repo / ".semgrep" / "alpha.yml").write_text("rules: []\n")
        assert "semgrep" in [name for name, _ in gate.gate_steps("fast", repo)]


class TestAuditDigest:
    """`gate.py audit --digest` is the escape logbook: counts and paths, never contents."""

    def test_rolls_acks_up_by_path(self, repo: Path) -> None:
        gate.write_ack(repo, reason="one", authorized_by="agent", path="CLAUDE.md")
        gate.consume_ack(repo, path="CLAUDE.md")
        gate.write_ack(repo, reason="two", authorized_by="agent", path="CLAUDE.md")
        gate.consume_ack(repo, path="CLAUDE.md")
        gate.write_ack(repo, reason="three", authorized_by="agent", path=".claude/settings.json")
        digest = gate.audit_digest(repo)
        assert "self-authorized escapes     3" in digest.replace("  ", " ").replace("   ", " ") or (
            "ack_written" in digest
        )
        # one line per path, carrying its own count — not one line per ack
        assert "CLAUDE.md" in digest and ".claude/settings.json" in digest
        assert digest.count("CLAUDE.md") == 1

    def test_counts_overrides_blocks_and_chain(self, repo: Path) -> None:
        gate.write_override(repo, reason="merge commit", authorized_by="agent")
        gate.append_audit(repo, "blocked_pre-bash-guard", "nope")
        gate.append_audit(repo, "blocked_post-edit", "nope")
        gate.append_audit(repo, "codex_call", "probe")
        digest = gate.audit_digest(repo)
        assert "override_written" in digest
        assert "blocks the harness enforced" in digest
        assert "blocked_pre-bash-guard" in digest
        assert "chain: ok" in digest

    def test_reports_owner_token_state(self, repo: Path) -> None:
        gate.write_ack(repo, reason="x", authorized_by="agent", path="CLAUDE.md")
        assert "owner token: NOT configured" in gate.audit_digest(repo)

    def test_window_excludes_older_events(self, repo: Path) -> None:
        gate.write_ack(repo, reason="x", authorized_by="agent", path="CLAUDE.md")
        assert "(none)" in gate.audit_digest(repo, since="9999-01-01")

    def test_empty_journal_is_honest_not_a_crash(self, repo: Path) -> None:
        digest = gate.audit_digest(repo)
        assert "(none)" in digest

    def test_ack_path_is_recorded_on_the_journal_line(self, repo: Path) -> None:
        gate.write_ack(repo, reason="x", authorized_by="agent", path="CLAUDE.md")
        written = [e for e in gate.read_audit(repo) if e["event"] == "ack_written"]
        assert written and written[-1]["path"] == "CLAUDE.md"
        gate.consume_ack(repo, path="CLAUDE.md")
        consumed = [e for e in gate.read_audit(repo) if e["event"] == "ack_consumed"]
        assert consumed and consumed[-1]["path"] == "CLAUDE.md"
        ok, _ = gate.verify_audit_chain(repo)
        assert ok, "adding a field must not break the hash chain"

    def test_reports_a_token_that_is_still_armed(self, repo: Path) -> None:
        gate.write_override(repo, reason="merge commit", authorized_by="agent")
        digest = gate.audit_digest(repo)
        assert "LIVE — armed, not yet used" in digest
        assert "commit override" in digest and "merge commit" in digest

    def test_a_consumed_token_is_no_longer_live(self, repo: Path) -> None:
        gate.write_override(repo, reason="merge commit", authorized_by="agent")
        gate.consume_override(repo)
        assert "LIVE — armed, not yet used" not in gate.audit_digest(repo)

    def test_a_live_ack_names_the_file_it_unlocks(self, repo: Path) -> None:
        gate.write_ack(repo, reason="why", authorized_by="agent", path="scripts/gate.py")
        digest = gate.audit_digest(repo)
        assert "governance ack" in digest
        assert digest.count("scripts/gate.py") == 2, "once in the rollup, once as still-armed"


def test_stamp_tier_reports_highest_fresh_tier(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert gate.stamp_tier(repo) == "none"
    gate.write_stamp(repo, "fast", steps=[], duration=0.1)
    assert gate.stamp_tier(repo) == "fast"
    gate.write_stamp(repo, "full", steps=[], duration=0.1)
    assert gate.stamp_tier(repo) == "full"
    (repo / "poke.txt").write_text("x")  # tree changed → stale
    assert gate.stamp_tier(repo) == "none"


def test_stamp_is_valid_hashes_the_tree_once(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gate.write_stamp(repo, "full", steps=[], duration=0.1)
    calls = 0
    real = gate.compute_tree_hash

    def counted(root: Path) -> str:
        nonlocal calls
        calls += 1
        return real(root)

    monkeypatch.setattr(gate, "compute_tree_hash", counted)
    assert gate.stamp_is_valid(repo, "fast") is True
    assert calls == 1


def test_every_gate_subcommand_has_working_help() -> None:
    import argparse

    parser = gate.build_parser()
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert "selftest" not in subparsers.choices
    for name, sub in subparsers.choices.items():
        assert sub.format_help(), name
