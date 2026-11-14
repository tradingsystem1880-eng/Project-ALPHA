"""Document search reads only tracked, allow-listed documentation; heading matches rank first."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import fs
import fs_search
import pytest
from fs_search import read_sources, search, search_sections


def _add(repo: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)


@pytest.fixture
def docs_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _add(
        tmp_path,
        {
            "CLAUDE.md": "# ALPHA\nResearch precedes strategy.\n",
            "docs/roadmap/backlog/features.md": "# Feature scope\n## H26 context filesystem\n"
            "Queryable intent and task context. NOT_TESTED; backup is separate.\n",
            "docs/work/2026-11-01-task/02-plan.md": "# Context task\n## Verification\n"
            "Context filesystem implementation remains pending.\n",
            "docs/adr/0001-context.md": "# ADR-0001: Context\n## Decision\n"
            "Context filesystem must preserve provenance.\n",
            "data/private.md": "SECRET context filesystem\n",
            "tests/holdout/private.md": "SECRET context filesystem\n",
            ".env.md": "SECRET context filesystem\n",
        },
    )
    return tmp_path


def test_search_keeps_line_ranges_headings_and_skips_private_paths(docs_repo: Path) -> None:
    found = search_sections(read_sources(docs_repo), "context filesystem")
    assert len(found) == 3
    assert {row.kind for row in found} == {"feature", "task", "decision"}
    feature = next(row for row in found if "H26" in row.heading)
    assert (feature.start, feature.end) == (2, 3)
    assert feature.heading == "Feature scope / H26 context filesystem"
    assert "NOT_TESTED; backup is separate" in feature.text
    assert all("SECRET" not in row.text for row in found)


def test_kind_filter_and_query_bounds(docs_repo: Path) -> None:
    sources = read_sources(docs_repo)
    assert {row.kind for row in search_sections(sources, "context", kind="task")} == {"task"}
    assert search_sections(sources, "no_such_feature") == []
    for bad in ("   ", "x" * 161, " ".join(f"w{i}" for i in range(13))):
        with pytest.raises(ValueError, match="query"):
            search_sections(sources, bad)
    with pytest.raises(ValueError, match="kind"):
        search_sections(sources, "context", kind="secrets")


@pytest.mark.parametrize(
    ("rel", "kind"),
    [
        ("docs/work/2026-11-01-live/02-plan.md", "task"),
        ("workflow/stages/02-plan/CONTEXT.md", "project"),
        ("docs/roadmap/backlog/options-research.md", "feature"),
        ("docs/roadmap/refactors/split-models.md", "feature"),
        (".claude/rules/docs.md", "reference"),
        ("CONTEXT.md", "project"),
        ("STATUS.md", "project"),
        ("packages/alpha-data/CONTEXT.md", "project"),
        ("apps/alpha-web/CONTEXT.md", "project"),
        ("tests/CONTEXT.md", "project"),
        ("docs/reference/commands.md", "reference"),
        ("docs/reference/invariants/data.md", "reference"),
        ("docs/archive/research-notes/2026-06/00-SYNTHESIS.md", "research"),
        ("docs/archive/research-notes/feature-readiness-checklist-2026-10-27.md", "research"),
    ],
)
def test_families(rel: str, kind: str) -> None:
    assert fs_search.family(rel) == kind


@pytest.mark.parametrize(
    "rel",
    [
        "docs/work/2026-11-01-x/deep/x.md",
        "docs/work/2026-11-01-x/data.json",
        "docs/roadmap/README.md",
        "docs/roadmap/backlog/image.png",
        "docs/archive/research-notes/mizerxbt-eth/mizerxbt_eth_short_1h.py",
        "docs/archive/other/x.md",
        "data/private.md",
        "tests/holdout/private.md",
        "tests/holdout/CONTEXT.md",
        "docs/reference/invariants/data.json",
        "packages/alpha-data/README.txt",
        ".env",
    ],
)
def test_paths_outside_the_allow_list_are_not_sources(rel: str) -> None:
    assert fs_search.family(rel) is None


def test_heading_matches_rank_ahead_of_text_matches(docs_repo: Path) -> None:
    _add(
        docs_repo,
        {
            "docs/adr/0002-ledger.md": "# Ledger rotation\nLedger rotation plan.\n",
            "docs/work/2026-11-01-new/02-plan.md": "# New plan\nThe ledger rotation plan.\n",
        },
    )
    found = search_sections(read_sources(docs_repo), "ledger rotation")
    assert [row.path for row in found] == [
        "docs/adr/0002-ledger.md",
        "docs/work/2026-11-01-new/02-plan.md",
    ]


def test_untracked_and_symlinked_documents_are_never_opened(docs_repo: Path) -> None:
    (docs_repo / "docs/roadmap/backlog/untracked.md").write_text("SECRET context")
    assert "docs/roadmap/backlog/untracked.md" not in read_sources(docs_repo)
    linked = docs_repo / "docs/roadmap/backlog/link.md"
    linked.symlink_to(docs_repo / "tests/holdout/private.md")
    subprocess.run(["git", "-C", str(docs_repo), "add", str(linked)], check=True)
    with pytest.raises(ValueError, match="symlink"):
        read_sources(docs_repo)


def test_parent_directory_symlink_is_rejected_before_read(docs_repo: Path) -> None:
    directory = docs_repo / "docs/roadmap/backlog"
    directory.rename(docs_repo / "saved-context")
    directory.symlink_to(docs_repo / "data", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        read_sources(docs_repo)


def test_missing_tracked_document_fails_loud(docs_repo: Path) -> None:
    (docs_repo / "docs/roadmap/backlog/features.md").unlink()
    with pytest.raises(FileNotFoundError):
        read_sources(docs_repo)


def test_limit_and_budget_name_every_omitted_match(docs_repo: Path) -> None:
    result = search(docs_repo, "context filesystem", limit=1)
    assert len(result["results"]) == 1
    assert result["matched"] == 3 == len(result["results"]) + len(result["omitted"])
    assert all("text" not in row for row in result["omitted"])
    tight = search(docs_repo, "context filesystem", budget_bytes=10)
    assert tight["results"] == [] and len(tight["omitted"]) == 3
    assert search(docs_repo, "absentneedle")["matched"] == 0
    # A large first match that does not fit is not skipped in favour of later, smaller ones.
    first = search(docs_repo, "context filesystem")["results"][0]
    tight = search(docs_repo, "context filesystem", budget_bytes=len(first["text"]) - 1)
    assert tight["results"] == [] and tight["omitted"][0]["path"] == first["path"]
    for limit in (0, 21, True):
        with pytest.raises(ValueError, match="limit"):
            search(docs_repo, "context", limit=limit)


def test_cli_text_and_json(docs_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = ["--root", str(docs_repo)]
    assert fs.main([*root, "search", "context filesystem", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["authority"] == "none" and payload["matched"] == 3
    assert {"path", "heading", "start", "end", "kind", "text"} <= set(payload["results"][0])
    assert fs.main([*root, "search", "context filesystem", "--limit", "2"]) == 0
    rendered = capsys.readouterr().out
    assert "2 of 3 matches" in rendered
    assert "[decision]" in rendered or "[feature]" in rendered
    assert "Not shown (1):" in rendered
    assert fs.main(["--root", str(docs_repo / "data"), "search", "context"]) == 2
    assert "no tracked documents" in capsys.readouterr().err
