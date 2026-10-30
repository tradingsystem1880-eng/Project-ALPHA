"""Source-only retrieval must preserve provenance and reject stale handoffs."""

import subprocess
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_atlas.context_sources import read_sources, search_sections

NOW = datetime(2026, 10, 30, tzinfo=UTC)


@pytest.fixture
def context_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    files = {
        "CLAUDE.md": "# ALPHA\nResearch precedes strategy.\n",
        "docs/context/features.md": "# Feature scope\n## H26 context filesystem\n"
        "Queryable intent and task context. NOT_TESTED; backup is separate.\n",
        "docs/superpowers/plans/task.md": "# Context task\n## Verification\n"
        "Context filesystem implementation remains pending.\n",
        "docs/adr/0001-context.md": "# ADR-0001: Context\n## Decision\n"
        "Context filesystem must preserve provenance.\n",
        "data/private.md": "SECRET context filesystem\n",
        "tests/holdout/private.md": "SECRET context filesystem\n",
    }
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    return tmp_path


def test_query_preserves_limits_decisions_and_line_provenance(context_repo: Path) -> None:
    sources = read_sources(context_repo)
    found = search_sections(sources, "context filesystem", kind="all")
    assert len(found) == 3
    assert {row.kind for row in found} == {"project", "task", "decision"}
    feature = next(row for row in found if "H26" in row.heading)
    assert feature.start == 2 and feature.end == 3
    assert "NOT_TESTED; backup is separate" in feature.text
    assert feature.source_sha256 == sources[feature.path].sha256
    assert all("SECRET" not in row.text for row in found)


def test_query_filters_tasks_and_rejects_empty_query(context_repo: Path) -> None:
    sources = read_sources(context_repo)
    assert {row.kind for row in search_sections(sources, "context", kind="task")} == {"task"}
    assert search_sections(sources, "no_such_feature", kind="all") == []
    with pytest.raises(ValueError, match="query"):
        search_sections(sources, "   ", kind="all")


def test_untracked_and_symlink_sources_are_never_opened(context_repo: Path) -> None:
    (context_repo / "docs/context/untracked.md").write_text("SECRET context")
    assert "docs/context/untracked.md" not in read_sources(context_repo)
    linked = context_repo / "docs/context/link.md"
    linked.symlink_to(context_repo / "tests/holdout/private.md")
    subprocess.run(["git", "-C", str(context_repo), "add", str(linked)], check=True)
    with pytest.raises(ValueError, match="symlink"):
        read_sources(context_repo)


def test_parent_directory_symlink_is_rejected_before_read(context_repo: Path) -> None:
    directory = context_repo / "docs/context"
    directory.rename(context_repo / "saved-context")
    directory.symlink_to(context_repo / "data", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        read_sources(context_repo)


def test_changed_and_missing_tracked_sources_fail_loud(context_repo: Path) -> None:
    old = read_sources(context_repo)
    target = context_repo / "docs/context/features.md"
    target.write_text("# Updated\n")
    assert (
        read_sources(context_repo)["docs/context/features.md"].sha256
        != old["docs/context/features.md"].sha256
    )
    target.unlink()
    with pytest.raises(FileNotFoundError):
        read_sources(context_repo)


def test_receipt_round_trip_and_exact_exclusions(context_repo: Path) -> None:
    from alpha_atlas.context import build_receipt, validate_receipt

    receipt = build_receipt(context_repo, "context filesystem", limit=1, now=NOW)
    assert len(receipt["selected"]) == 1
    assert len(receipt["excluded"]) == 2
    assert {row["reason"] for row in receipt["excluded"]} == {"result_limit"}
    assert receipt["authority"] == "none"
    validate_receipt(context_repo, receipt, now=NOW + timedelta(minutes=30))


@pytest.mark.parametrize("change", ["edit", "add", "delete", "tamper", "expire", "future"])
def test_receipt_rejects_stale_or_corrupt_handoffs(context_repo: Path, change: str) -> None:
    from alpha_atlas.context import build_receipt, validate_receipt

    receipt = build_receipt(context_repo, "context filesystem", now=NOW)
    if change == "edit":
        (context_repo / "CLAUDE.md").write_text("# ALPHA\nChanged constraints.\n")
    elif change == "add":
        extra = context_repo / "docs/adr/0002-new.md"
        extra.write_text("# Context filesystem decision\nNew contrary decision.\n")
        subprocess.run(["git", "-C", str(context_repo), "add", str(extra)], check=True)
    elif change == "delete":
        (context_repo / "CLAUDE.md").unlink()
    elif change == "tamper":
        receipt = deepcopy(receipt)
        receipt["selected"][0]["text"] = "Invented approval"
    check_time = NOW + timedelta(hours=2) if change == "expire" else NOW
    if change == "future":
        check_time = NOW - timedelta(seconds=1)
    with pytest.raises(ValueError):
        validate_receipt(context_repo, receipt, now=check_time)


def test_budget_omissions_and_empty_results_are_explicit(context_repo: Path) -> None:
    from alpha_atlas.context import build_receipt

    receipt = build_receipt(context_repo, "context filesystem", budget_bytes=256, now=NOW)
    assert receipt["selected_bytes"] <= 256
    assert receipt["matched_count"] == len(receipt["selected"]) + len(receipt["excluded"])
    empty = build_receipt(context_repo, "absentneedle", now=NOW)
    assert empty["status"] == "no_matches"
    assert empty["selected"] == empty["excluded"] == []


def test_invalid_receipt_parameters_are_rejected(context_repo: Path) -> None:
    from alpha_atlas.context import build_receipt, validate_receipt

    for params in ({"limit": True}, {"limit": 0}, {"ttl_seconds": 0}, {"budget_bytes": 0}):
        with pytest.raises(ValueError):
            build_receipt(context_repo, "context", now=NOW, **params)
    with pytest.raises(ValueError):
        validate_receipt(context_repo, {"schema_version": 100}, now=NOW)


def test_rehashed_tampering_and_policy_change_are_rejected(
    context_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_atlas.context import _digest, build_receipt, validate_receipt

    receipt = build_receipt(context_repo, "context filesystem", now=NOW)
    tampered = deepcopy(receipt)
    tampered["selected"][0]["text"] = "Invented approval"
    tampered["receipt_sha256"] = _digest(
        {key: value for key, value in tampered.items() if key != "receipt_sha256"}
    )
    with pytest.raises(ValueError, match="payload changed"):
        validate_receipt(context_repo, tampered, now=NOW)
    monkeypatch.setattr("alpha_atlas.context.context_sources.__file__", __file__)
    with pytest.raises(ValueError, match="policy"):
        validate_receipt(context_repo, receipt, now=NOW)


def test_cli_json_markdown_text_and_check(
    context_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from alpha_atlas.context import main

    root_args = ["--root", str(context_repo)]
    assert main([*root_args, "query", "context filesystem"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    receipt_path = context_repo / "handoff.json"
    receipt_path.write_text(json.dumps(receipt))
    assert main([*root_args, "check", str(receipt_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "fresh"
    for output_format in ("markdown", "text"):
        assert main([*root_args, "query", "context filesystem", "--format", output_format]) == 0
        rendered = capsys.readouterr().out
        assert "NOT_TESTED; backup is separate" in rendered
        assert "docs/adr/0001-context.md:2-3" in rendered
    receipt_path.write_text("not json")
    assert main([*root_args, "check", str(receipt_path)]) == 2
    assert "context:" in capsys.readouterr().err
    assert main(["--root", str(context_repo / "data"), "query", "context"]) == 2
    assert "no tracked context sources" in capsys.readouterr().err
