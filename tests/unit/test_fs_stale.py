"""`fs.py stale` lists living documents whose sources changed after their verified commit."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import fs
import fs_stale
import pytest


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for rel, text in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _doc(verified: str, *sources: str) -> str:
    listed = "".join(f"  - {source}\n" for source in sources)
    return f"---\nowner: data layer\nsources:\n{listed}verified: {verified}\n---\n\n# Doc\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    return tmp_path


def test_front_matter_parses_scalars_and_lists() -> None:
    meta = fs_stale.front_matter(_doc("abc1234", "src/**", "tests/test_*.py"))
    assert meta == {
        "owner": "data layer",
        "sources": ["src/**", "tests/test_*.py"],
        "verified": "abc1234",
    }
    assert fs_stale.front_matter("# No front matter\n") is None
    with pytest.raises(fs_stale.FrontMatterError, match="not closed"):
        fs_stale.front_matter("---\nowner: x\n")
    with pytest.raises(fs_stale.FrontMatterError, match="duplicate"):
        fs_stale.front_matter("---\nowner: x\nowner: y\n---\n")


def test_fresh_document_is_not_stale_and_own_edits_do_not_count(repo: Path) -> None:
    base = _commit(repo, {"src/a.py": "a = 1\n"}, "code")
    _commit(repo, {"docs/a.md": _doc(base, "src/**", "docs/a.md")}, "doc")
    _commit(repo, {"docs/a.md": _doc(base, "src/**", "docs/a.md") + "More.\n"}, "doc edit")
    [report] = fs_stale.stale(repo)
    assert report.path == "docs/a.md"
    assert report.changed_files == [] and report.problems == []


def test_source_change_after_verified_is_reported_with_count_and_newest_commit(repo: Path) -> None:
    base = _commit(repo, {"src/a.py": "a = 1\n", "src/b.py": "b = 1\n", "other.py": ""}, "code")
    _commit(repo, {"docs/a.md": _doc(base[:8], "src/**")}, "doc")
    _commit(repo, {"src/a.py": "a = 2\n"}, "change a")
    newest = _commit(repo, {"src/b.py": "b = 2\n", "other.py": "x = 1\n"}, "change b")
    [report] = fs_stale.stale(repo)
    assert report.changed_files == ["src/a.py", "src/b.py"]
    assert report.newest_commit == newest
    assert "STALE   docs/a.md: 2 source file(s)" in fs_stale.render_text([report])


def test_unmatched_glob_and_unknown_commit_are_problems(repo: Path) -> None:
    _commit(repo, {"src/a.py": "a = 1\n"}, "code")
    _commit(repo, {"docs/a.md": _doc("deadbeef", "src/**", "missing/**")}, "doc")
    [report] = fs_stale.stale(repo)
    assert "source glob matches no tracked file: missing/**" in report.problems
    assert any("not a known commit" in problem for problem in report.problems)


def test_generated_and_plain_documents_are_skipped(repo: Path) -> None:
    _commit(
        repo,
        {
            "src/a.py": "",
            "docs/gen.md": "---\ngenerated_by: make\nsources:\n  - src/**\n---\n# Gen\n",
            "docs/plain.md": "# Plain\n",
        },
        "docs",
    )
    assert fs_stale.stale(repo) == []


def test_cli_exit_codes_and_json(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = _commit(repo, {"src/a.py": "a = 1\n"}, "code")
    _commit(repo, {"docs/a.md": _doc(base, "src/**")}, "doc")
    assert fs.main(["--root", str(repo), "stale"]) == 0
    _commit(repo, {"src/a.py": "a = 2\n"}, "change")
    assert fs.main(["--root", str(repo), "stale"]) == 0
    assert fs.main(["--root", str(repo), "stale", "--strict"]) == 1
    capsys.readouterr()
    assert fs.main(["--root", str(repo), "stale", "--format", "json"]) == 0
    [row] = json.loads(capsys.readouterr().out)
    assert row["path"] == "docs/a.md" and row["changed_files"] == 1
    _commit(repo, {"docs/b.md": _doc(base, "nothing/**")}, "broken doc")
    assert fs.main(["--root", str(repo), "stale"]) == 1


def test_other_documents_and_foreign_front_matter_do_not_count(repo: Path) -> None:
    base = _commit(
        repo,
        {"workers/a/src/x.py": "", ".claude/agents/r.md": "---\nname: r\n  bad: [\n---\n# R\n"},
        "code",
    )
    _commit(repo, {"docs/w.md": _doc(base, "workers/**")}, "doc")
    _commit(repo, {"workers/a/CONTEXT.md": _doc(base, "workers/a/src/**")}, "routing file")
    reports = fs_stale.stale(repo)
    assert [r.path for r in reports] == ["docs/w.md", "workers/a/CONTEXT.md"]
    assert all(not r.changed_files and not r.problems for r in reports)


def test_workspace_instruction_files_do_not_make_a_document_stale(repo: Path) -> None:
    base = _commit(repo, {"workers/a/src/x.py": "", "workers/a/CONTEXT.md": "# A\n"}, "code")
    _commit(repo, {"docs/w.md": _doc(base, "workers/**")}, "doc")
    _commit(repo, {"workers/a/CLAUDE.md": "@CONTEXT.md\n", "CLAUDE.md": "# Id\n"}, "loaders")
    (report,) = fs_stale.stale(repo)
    assert report.changed_files == []
    _commit(repo, {"workers/a/src/x.py": "x = 1\n"}, "code change")
    (report,) = fs_stale.stale(repo)
    assert report.changed_files == ["workers/a/src/x.py"]
