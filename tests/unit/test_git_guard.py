import shutil
import subprocess
from pathlib import Path

import gate
import git_guard
import pytest

from tests.unit._harness_support import git


def test_unstamped_commit_is_rejected(repo: Path) -> None:
    assert git_guard.check_commit(repo)[0] != 0


def test_partial_staging_does_not_inherit_worktree_stamp(repo: Path) -> None:
    (repo / "tracked.py").write_text("x = 2\n")
    git(repo, "add", "tracked.py")
    (repo / "tracked.py").write_text("x = 3\n")
    gate.write_stamp(repo, "full", steps=[], duration=0)
    code, reason = git_guard.check_commit(repo)
    assert code != 0 and "staged" in reason


def test_exact_staged_tree_accepts_full_stamp(repo: Path) -> None:
    (repo / "tracked.py").write_text("x = 2\n")
    git(repo, "add", "tracked.py")
    gate.write_stamp(repo, "full", steps=[], duration=0)
    assert git_guard.check_commit(repo) == (0, "")


def test_commit_cannot_accept_tree_swapped_after_stamp_check(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate.write_stamp(repo, "full", steps=[], duration=0)
    original = gate.stamp_is_valid

    def swap_after_check(root: Path, tier: str) -> bool:
        valid = original(root, tier)
        (root / "tracked.py").write_text("x = 42\n")
        git(root, "add", "tracked.py")
        return valid

    monkeypatch.setattr(gate, "stamp_is_valid", swap_after_check)
    assert git_guard.check_commit(repo)[0] != 0


def test_install_refuses_unrelated_existing_hooks(repo: Path) -> None:
    git(repo, "config", "core.hooksPath", "custom-hooks")
    with pytest.raises(ValueError, match="existing"):
        git_guard.install(repo)


def test_protected_configuration_requires_tree_bound_review(repo: Path) -> None:
    (repo / "CLAUDE.md").write_text("Changed engineering policy\n")
    git(repo, "add", "CLAUDE.md")
    gate.write_stamp(repo, "full", steps=[], duration=0)
    code, message = git_guard.check_commit(repo)
    assert code != 0 and "review" in message


def test_install_is_idempotent(repo: Path) -> None:
    git_guard.install(repo)
    git_guard.install(repo)
    assert git(repo, "config", "--get", "core.hooksPath") == ".githooks"


@pytest.mark.parametrize(
    "original", ["CLAUDE.md", "packages/alpha-research/src/alpha_research/estimate.py"]
)
def test_rename_out_of_review_scope_still_requires_review(repo: Path, original: str) -> None:
    source = repo / original
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("protected original contents\n")
    git(repo, "add", original)
    git(repo, "commit", "-m", "test: original protected path")
    git(repo, "mv", original, "ordinary.md")
    gate.write_stamp(repo, "full", steps=[], duration=0)
    code, message = git_guard.check_commit(repo)
    assert code != 0 and "review" in message


def test_reviewed_quant_rename_still_requires_quant_evidence(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = "packages/alpha-research/src/alpha_research/estimate.py"
    source = repo / original
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("quant original contents\n")
    git(repo, "add", original)
    git(repo, "commit", "-m", "test: original quant path")
    git(repo, "mv", original, "ordinary.md")
    gate.write_stamp(repo, "full", steps=[], duration=0)
    monkeypatch.setattr(gate, "review_verdict_valid", lambda root: True)
    gate.write_json_atomic(
        repo / gate.STATE_DIR / gate.REVIEW_VERDICT_FILE,
        {
            "verdict": {
                "reviewed_tree_hash": gate.compute_tree_hash(repo),
                "files_reviewed": [original],
            }
        },
    )
    code, message = git_guard.check_commit(repo)
    assert code != 0 and "Quant" in message


def test_real_git_commit_invokes_guard(repo: Path) -> None:
    source = Path(__file__).resolve().parents[2]
    shutil.copytree(source / ".githooks", repo / ".githooks")
    (repo / "scripts").mkdir()
    for name in ("gate.py", "git_guard.py"):
        shutil.copy2(source / "scripts" / name, repo / "scripts" / name)
    git_guard.install(repo)
    (repo / "tracked.py").write_text("x = 9\n")
    git(repo, "add", ".")
    result = subprocess.run(
        ["git", "commit", "-m", "test: guard smoke"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "No full gate result" in result.stderr
