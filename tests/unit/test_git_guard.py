"""The installed Git hooks refuse only a malformed commit message; nothing else blocks a commit."""

import shutil
import subprocess
from pathlib import Path

import git_guard
import pytest

from tests.unit._harness_support import git

SOURCE = Path(__file__).resolve().parents[2]


def test_install_refuses_unrelated_existing_hooks(repo: Path) -> None:
    git(repo, "config", "core.hooksPath", "custom-hooks")
    with pytest.raises(ValueError, match="existing"):
        git_guard.install(repo)


def test_install_is_idempotent(repo: Path) -> None:
    git_guard.install(repo)
    git_guard.install(repo)
    assert git(repo, "config", "--get", "core.hooksPath") == ".githooks"


@pytest.mark.parametrize(
    ("subject", "code"),
    [
        ("feat(cli): add a flag", 0),
        ("fix!: break loudly", 0),
        ("chore(docs): regenerate", 0),
        ("wip", 1),
        ("Feat: capitalised type", 1),
        ("feat(cli) missing colon", 1),
        ("", 1),
    ],
)
def test_commit_message_format(tmp_path: Path, subject: str, code: int) -> None:
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text(f"{subject}\n\nbody\n")
    assert git_guard.check_message(message)[0] == code


def _hooked_repo(repo: Path) -> Path:
    shutil.copytree(SOURCE / ".githooks", repo / ".githooks")
    (repo / "scripts").mkdir()
    for name in ("gate.py", "git_guard.py"):
        shutil.copy2(SOURCE / "scripts" / name, repo / "scripts" / name)
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "-m", "chore: hook fixture")
    git_guard.install(repo)
    return repo


def _commit(repo: Path, subject: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "commit", "-m", subject],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_installed_hooks_commit_partial_staging_without_any_gate_evidence(repo: Path) -> None:
    _hooked_repo(repo)
    (repo / "tracked.py").write_text("x = 2\n")
    (repo / "unstaged.py").write_text("y = 1\n")
    git(repo, "add", "tracked.py")
    result = _commit(repo, "test: commit only what is staged")
    assert result.returncode == 0, result.stderr
    assert git(repo, "status", "--porcelain") == "?? unstaged.py"
    assert not (repo / ".alpha").exists()


def test_installed_hooks_refuse_a_malformed_message(repo: Path) -> None:
    _hooked_repo(repo)
    (repo / "tracked.py").write_text("x = 3\n")
    git(repo, "add", "tracked.py")
    result = _commit(repo, "updated stuff")
    assert result.returncode != 0
    assert "conventional commit subject" in result.stderr
    assert git(repo, "log", "-1", "--format=%s") == "chore: hook fixture"
