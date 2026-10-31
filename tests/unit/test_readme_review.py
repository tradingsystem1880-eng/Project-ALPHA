"""Native README review evidence: freshness and scope, never semantic proof."""

import json
from pathlib import Path

import gate
import git_guard
import pytest
import readme_review

from tests.unit._harness_support import git, pass_full_gate


@pytest.fixture
def readme_repo(repo: Path) -> Path:
    (repo / "README.md").write_text("# Fixture\n\nSee [source](tracked.py).\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "docs: seed README fixture")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def report(root: Path, disposition: str = "no_change") -> str:
    return json.dumps(
        {
            "reviewed_tree_hash": gate.compute_tree_hash(root),
            "disposition": disposition,
            "rationale": "Reviewed final code and links; this fixture change has no reader impact.",
        }
    )


def test_no_change_records_review_without_readme_churn(readme_repo: Path) -> None:
    root = readme_repo
    original = (root / "README.md").read_bytes()
    (root / "tracked.py").write_text("x = 2\n")
    assert gate.attest(root, "readme", report(root)) == 0
    assert readme_review.check(root) == (True, "")
    assert gate.attest(root, "readme", report(root)) == 0
    assert (root / "README.md").read_bytes() == original
    record = gate.read_json(root / gate.STATE_DIR / readme_review.STATE_FILE)
    assert record is not None and record["changed_paths"] == ["tracked.py"]


def test_updated_readme_and_stale_final_code(readme_repo: Path) -> None:
    root = readme_repo
    (root / "README.md").write_text("# Fixture\n\nUpdated explanation. [Source](tracked.py)\n")
    assert gate.attest(root, "readme", report(root, "updated")) == 0
    assert readme_review.check(root)[0]
    (root / "tracked.py").write_text("x = 7\n")
    assert not readme_review.check(root)[0]


def test_review_covers_earlier_commits_on_branch(
    readme_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = readme_repo
    (root / "tracked.py").write_text("x = 4\n")
    git(root, "add", "tracked.py")
    git(root, "commit", "-m", "feat: earlier branch change")
    assert gate.attest(root, "readme", report(root)) == 0
    record = gate.read_json(root / gate.STATE_DIR / readme_review.STATE_FILE)
    assert record is not None and record["changed_paths"] == ["tracked.py"]
    # ALPHA_GATE_BASE cannot narrow README review to just the current dirty diff.
    monkeypatch.setenv("ALPHA_GATE_BASE", "HEAD")
    assert readme_review.check(root)[0]


def test_base_movement_invalidates_record(readme_repo: Path) -> None:
    root = readme_repo
    assert gate.attest(root, "readme", report(root)) == 0
    moved = git(root, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "main advanced")
    git(root, "update-ref", "refs/remotes/origin/main", moved)
    assert not readme_review.check(root)[0]


def test_unknown_base_fails_closed(readme_repo: Path) -> None:
    git(readme_repo, "update-ref", "-d", "refs/remotes/origin/main")
    assert gate.attest(readme_repo, "readme", report(readme_repo)) != 0
    assert not readme_review.check(readme_repo)[0]


@pytest.mark.parametrize("change_readme", [False, True])
def test_disposition_must_match_actual_readme_diff(readme_repo: Path, change_readme: bool) -> None:
    root = readme_repo
    if change_readme:
        (root / "README.md").write_text("Changed explanation.\n")
    wrong = "no_change" if change_readme else "updated"
    assert gate.attest(root, "readme", report(root, wrong)) != 0


def test_broken_local_link_and_missing_readme_rejected(readme_repo: Path) -> None:
    root = readme_repo
    (root / "README.md").write_text("# Fixture\n\n[Missing](missing.md)\n")
    assert gate.attest(root, "readme", report(root, "updated")) != 0
    (root / "README.md").unlink()
    assert gate.attest(root, "readme", report(root, "updated")) != 0


@pytest.mark.parametrize("payload", ["{}", "not json", '{"rationale":"   "}'])
def test_malformed_report_rejected(readme_repo: Path, payload: str) -> None:
    assert gate.attest(readme_repo, "readme", payload) != 0


def test_final_tree_hash_is_not_automatically_certified(readme_repo: Path) -> None:
    payload = json.loads(report(readme_repo))
    payload["reviewed_tree_hash"] = "a" * 64
    assert gate.attest(readme_repo, "readme", json.dumps(payload)) != 0


def test_guard_blocks_missing_review_and_accepts_exact_evidence(
    readme_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = readme_repo
    (root / "tracked.py").write_text("x = 8\n")
    git(root, "add", "tracked.py")
    pass_full_gate(
        root, monkeypatch, with_readme=False
    )  # Simulated command outcomes, real bindings.
    code, reason = git_guard.check_commit(root)
    assert code != 0 and "README" in reason
    assert gate.attest(root, "readme", report(root)) == 0
    assert git_guard.check_commit(root) == (0, "")


def test_tampered_scope_cannot_reuse_review(readme_repo: Path) -> None:
    root = readme_repo
    (root / "tracked.py").write_text("x = 2\n")
    assert gate.attest(root, "readme", report(root)) == 0
    path = root / gate.STATE_DIR / readme_review.STATE_FILE
    record = gate.read_json(path)
    assert record is not None
    record["changed_paths"] = []
    gate.write_json_atomic(path, record)
    assert not readme_review.check(root)[0]


def test_real_installed_hook_requires_explicit_review(
    readme_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    from tests.unit.test_git_guard import _hooked_repo

    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    root = _hooked_repo(readme_repo)
    before = (root / "README.md").read_bytes()
    (root / "tracked.py").write_text("x = 99\n")
    git(root, "add", "tracked.py")
    pass_full_gate(root, monkeypatch, with_readme=False)
    command = ["git", "commit", "-m", "test: guarded delivery"]
    rejected = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    assert rejected.returncode != 0 and "README review" in rejected.stderr
    assert gate.attest(root, "readme", report(root)) == 0
    accepted = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    assert accepted.returncode == 0, accepted.stderr
    assert (root / "README.md").read_bytes() == before


def test_rename_scope_includes_removed_source_path(readme_repo: Path) -> None:
    root = readme_repo
    git(root, "mv", "tracked.py", "renamed.py")
    (root / "README.md").write_text("# Fixture\n\nSee [source](renamed.py).\n")
    assert gate.attest(root, "readme", report(root, "updated")) == 0
    record = gate.read_json(root / gate.STATE_DIR / readme_review.STATE_FILE)
    assert record is not None
    assert set(record["changed_paths"]) == {"README.md", "tracked.py", "renamed.py"}


def test_whitespace_rationale_is_not_a_review(readme_repo: Path) -> None:
    payload = json.loads(report(readme_repo))
    payload["rationale"] = " " * 40
    assert gate.attest(readme_repo, "readme", json.dumps(payload)) != 0


def test_readme_symlink_cannot_read_outside_repository(readme_repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "owner-notes.md"
    outside.write_text("Fixture content outside the repository must not be read as README.\n")
    (readme_repo / "README.md").unlink()
    (readme_repo / "README.md").symlink_to(outside)
    assert gate.attest(readme_repo, "readme", report(readme_repo, "updated")) != 0


def test_ignored_local_file_is_not_a_publishable_readme_link(readme_repo: Path) -> None:
    root = readme_repo
    local = root / gate.STATE_DIR / "notes.md"
    local.parent.mkdir(parents=True)
    local.write_text("Local-only fixture evidence.\n")
    (root / "README.md").write_text("# Fixture\n\n[Notes](.alpha/state/notes.md)\n")
    assert gate.attest(root, "readme", report(root, "updated")) != 0
