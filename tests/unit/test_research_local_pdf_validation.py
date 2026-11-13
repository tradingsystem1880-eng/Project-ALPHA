"""Fail-loud extraction validation, rebinding refusals and the CLI edge of the owner PDF import."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from alpha_cli import local_pdf_cmds
from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_core import DataError
from tests.unit.test_research_local_pdf import (
    PDF_BYTES,
    PROJECT_ID,
    _extraction_artifact,
    _fixture_worker,
    _store,
)

DIGEST = hashlib.sha256(PDF_BYTES).hexdigest()


def _reidentified(artifact: dict[str, object]) -> dict[str, object]:
    """Recompute the content identity so only the field under test is inconsistent."""
    core = {k: v for k, v in artifact.items() if k not in {"extraction_id", "artifact_sha256"}}
    raw = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return {"extraction_id": "rx_" + hashlib.sha256(raw).hexdigest(), **core}


def _with(**changes: object) -> dict[str, object]:
    return _reidentified({**_extraction_artifact(DIGEST), **changes})


def _page(text: str, number: int = 1) -> dict[str, object]:
    return {
        "page": number,
        "text": text,
        "character_count": len(text),
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def test_valid_fixture_extraction_is_returned_unchanged() -> None:
    artifact = _extraction_artifact(DIGEST)
    assert local_pdf_cmds._validated_extraction(artifact, source_sha256=DIGEST) is artifact


@pytest.mark.parametrize(
    ("artifact", "message"),
    [
        (_with(schema="ResearchDocumentTextV2"), "unsupported PDF extraction"),
        (_with(trust_label="TRUSTED"), "untrusted-source label"),
        (_with(warnings=["page 1 truncated"]), "metadata is incomplete or inconsistent"),
        (_with(page_count=True), "metadata is incomplete or inconsistent"),
        (_with(page_count=201), "metadata is incomplete or inconsistent"),
        (_with(config_hash="not-a-hash"), "metadata is incomplete or inconsistent"),
        (_with(parser_version=""), "metadata is incomplete or inconsistent"),
        (_with(character_count=-1), "metadata is incomplete or inconsistent"),
        (_with(pages=["page one"]), "contains an invalid page"),
        (_with(pages=[_page("text", number=2)]), "inconsistent page text"),
        (_with(pages=[_page("")], character_count=0), "complete readable text"),
        (_with(character_count=1), "complete readable text"),
    ],
)
def test_extraction_metadata_and_page_text_fail_loud(
    artifact: dict[str, object], message: str
) -> None:
    with pytest.raises(DataError, match=message):
        local_pdf_cmds._validated_extraction(artifact, source_sha256=DIGEST)


def test_extraction_identity_must_match_its_contents() -> None:
    artifact = {**_extraction_artifact(DIGEST), "extraction_id": "rx_" + "0" * 64}
    with pytest.raises(DataError, match="identity does not match its contents"):
        local_pdf_cmds._validated_extraction(artifact, source_sha256=DIGEST)
    malformed = {**_extraction_artifact(DIGEST), "extraction_id": "rx_short"}
    with pytest.raises(DataError, match="metadata is incomplete"):
        local_pdf_cmds._validated_extraction(malformed, source_sha256=DIGEST)


def test_extraction_identity_ignores_only_the_artifact_digest() -> None:
    artifact = {**_extraction_artifact(DIGEST), "artifact_sha256": "e" * 64}
    assert local_pdf_cmds._validated_extraction(artifact, source_sha256=DIGEST) is artifact


def test_tiny_file_is_not_a_pdf(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pdf"
    path.write_bytes(b"%PDF")
    with pytest.raises(DataError, match="is not a PDF"):
        local_pdf_cmds._read_owner_pdf(path)


def test_selected_path_removed_during_read_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "owner-paper.pdf"
    source.write_bytes(PDF_BYTES)
    original_reader = local_pdf_cmds._read_open_pdf

    def remove_then_read(fd: int, path: Path, before: os.stat_result) -> tuple[bytes, str]:
        path.unlink()
        return original_reader(fd, path, before)

    monkeypatch.setattr(local_pdf_cmds, "_read_open_pdf", remove_then_read)
    with pytest.raises(DataError, match="path changed during import"):
        local_pdf_cmds._read_owner_pdf(source)


@pytest.mark.parametrize("title", ["", "   ", "x" * 501, "bad\x00title"])
def test_title_must_be_bounded_text_before_any_read(tmp_path: Path, title: str) -> None:
    store = _store(tmp_path)
    with pytest.raises(DataError, match="title must contain bounded text"):
        local_pdf_cmds.import_owner_pdf_file(
            store,
            project_id=PROJECT_ID,
            file_path=tmp_path / "never-read.pdf",
            title=title,
            worker=_fixture_worker(),
        )


def _import(store: ControlStore, path: Path, title: str) -> dict[str, object]:
    return local_pdf_cmds.import_owner_pdf_file(
        store, project_id=PROJECT_ID, file_path=path, title=title, worker=_fixture_worker()
    )


def test_existing_extraction_is_not_rebound_to_a_different_title(tmp_path: Path) -> None:
    store = _store(tmp_path)
    source_file = tmp_path / "owner-paper.pdf"
    source_file.write_bytes(PDF_BYTES)
    first = _import(store, source_file, "Owner-provided paper")
    with pytest.raises(DataError, match="already bound to a different source record"):
        _import(store, source_file, "Renamed paper")
    sources = store.list_research_sources(PROJECT_ID)
    assert [s["source_id"] for s in sources] == [
        cast(dict[str, object], first["source"])["source_id"]
    ]


def test_reuse_reports_unavailable_original_bytes_without_replacing_them(tmp_path: Path) -> None:
    store = _store(tmp_path)
    source_file = tmp_path / "owner-paper.pdf"
    source_file.write_bytes(PDF_BYTES)
    first = _import(store, source_file, "Owner-provided paper")
    source_id = str(cast(dict[str, object], first["source"])["source_id"])
    artifact = store._data_dir / "research" / "literature" / "source-pdfs" / f"{source_id}.pdf"
    artifact.write_bytes(b"%PDF-corrupt")
    with pytest.raises(DataError, match="original bytes are corrupt; no replacement was made"):
        _import(store, source_file, "Owner-provided paper")
    assert artifact.read_bytes() == b"%PDF-corrupt"


def test_unexpected_extraction_lookup_errors_are_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    source_file = tmp_path / "owner-paper.pdf"
    source_file.write_bytes(PDF_BYTES)

    def broken_lookup(_extraction_id: str) -> dict[str, object]:
        raise DataError("research extraction index is unreadable")

    monkeypatch.setattr(store, "get_research_document_text", broken_lookup)
    with pytest.raises(DataError, match="index is unreadable"):
        _import(store, source_file, "Owner-provided paper")
    assert store.list_research_sources(PROJECT_ID) == []


def _cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, worker: Callable[[list[str]], object]
) -> CliRunner:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path / "control"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(local_pdf_cmds, "_run_literature_worker", worker)
    return CliRunner()


def test_cli_reports_refusals_as_bad_parameters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store(tmp_path)
    runner = _cli(tmp_path, monkeypatch, _fixture_worker())
    result = runner.invoke(
        app,
        ["research", "import-pdf", PROJECT_ID, "--file", str(tmp_path / "absent.pdf")]
        + ["--title", "Missing paper"],
    )
    assert result.exit_code == 2
    assert "existing non-symlink file" in result.output


def test_cli_imports_and_emits_json_or_a_summary_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    source_file = tmp_path / "owner-paper.pdf"
    source_file.write_bytes(PDF_BYTES)
    runner = _cli(tmp_path, monkeypatch, _fixture_worker())
    argv = ["research", "import-pdf", PROJECT_ID, "--file", str(source_file)]
    result = runner.invoke(app, [*argv, "--title", "Owner-provided paper", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["acquisition"]["sha256"] == DIGEST
    assert payload["document"]["status"] == "extracted"
    source_id = payload["source"]["source_id"]
    assert store.get_research_source(source_id)["content_hash"] == DIGEST

    again = runner.invoke(app, [*argv, "--title", "Owner-provided paper"])
    assert again.exit_code == 0, again.output
    assert again.output.strip() == f"imported owner-provided PDF source {source_id}"
