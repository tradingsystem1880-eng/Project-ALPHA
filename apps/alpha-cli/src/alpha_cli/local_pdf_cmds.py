"""Owner-invoked, local-only PDF import for literature sources."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

import typer

from alpha_cli.control_store import ControlStore
from alpha_cli.research_cmds import _emit, _run_literature_worker, _store
from alpha_core import DataError

_MAX_PDF_BYTES = 10 * 1024 * 1024
_MAX_PDF_PAGES = 200
_MAX_PDF_CHARACTERS = 2_000_000
_SHA256 = re.compile(r"[0-9a-f]{64}")
_EXTRACTION_ID = re.compile(r"rx_[0-9a-f]{64}")
_Worker = Callable[[list[str]], dict[str, object]]


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _read_open_pdf(fd: int, path: Path, before: os.stat_result) -> tuple[bytes, str]:
    if not stat.S_ISREG(before.st_mode):
        raise DataError("owner-provided PDF must be a regular file")
    if before.st_size < 5:
        raise DataError("owner-provided file is not a PDF")
    if before.st_size > _MAX_PDF_BYTES:
        raise DataError("owner-provided PDF exceeds the 10 MiB byte limit")

    contents = bytearray()
    while len(contents) <= _MAX_PDF_BYTES:
        count = min(64 * 1024, _MAX_PDF_BYTES + 1 - len(contents))
        chunk = os.read(fd, count)
        if not chunk:
            break
        contents.extend(chunk)
    if len(contents) > _MAX_PDF_BYTES:
        raise DataError("owner-provided PDF exceeds the 10 MiB byte limit")

    after = os.fstat(fd)
    try:
        path_after = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise DataError("owner-provided PDF path changed during import") from exc
    if (
        len(contents) != before.st_size
        or _stat_identity(after) != _stat_identity(before)
        or _stat_identity(path_after) != _stat_identity(before)
    ):
        raise DataError("owner-provided PDF changed during import")

    raw = bytes(contents)
    if not raw.startswith(b"%PDF-"):
        raise DataError("owner-provided file is not a PDF")
    return raw, hashlib.sha256(raw).hexdigest()


def _read_owner_pdf(path: Path) -> tuple[bytes, str]:
    """Read only the selected file, rejecting final symlinks and concurrent replacement."""
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise DataError("this platform cannot safely reject a symlinked owner PDF")
    selected = path.expanduser()
    # O_NONBLOCK: a FIFO or device must not block the open before the fstat regular-file check
    # rejects it; it has no effect on reading a regular file.
    flags = os.O_RDONLY | no_follow | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(selected, flags)
    except OSError as exc:
        raise DataError("owner-provided PDF must be an existing non-symlink file") from exc
    try:
        try:
            before = os.fstat(descriptor)
            return _read_open_pdf(descriptor, selected, before)
        except OSError as exc:
            raise DataError("owner-provided PDF could not be read safely") from exc
    finally:
        os.close(descriptor)


def _validated_extraction(artifact: dict[str, object], *, source_sha256: str) -> dict[str, object]:
    if artifact.get("schema") != "ResearchDocumentTextV1":
        raise DataError("literature worker returned an unsupported PDF extraction")
    if artifact.get("source_sha256") != source_sha256:
        raise DataError("literature worker extraction hash does not match the owner PDF")
    if artifact.get("status") != "extracted":
        status = artifact.get("status")
        raise DataError(f"owner PDF extraction is incomplete ({status}); source was not imported")
    if artifact.get("trust_label") != "UNTRUSTED_SOURCE":
        raise DataError("literature worker extraction is missing its untrusted-source label")

    extraction_id = artifact.get("extraction_id")
    config_hash = artifact.get("config_hash")
    parser_version = artifact.get("parser_version")
    pages = artifact.get("pages")
    warnings = artifact.get("warnings")
    page_count = artifact.get("page_count")
    character_count = artifact.get("character_count")
    if (
        not isinstance(extraction_id, str)
        or _EXTRACTION_ID.fullmatch(extraction_id) is None
        or not isinstance(config_hash, str)
        or _SHA256.fullmatch(config_hash) is None
        or not isinstance(parser_version, str)
        or not parser_version
        or not isinstance(pages, list)
        or isinstance(page_count, bool)
        or not isinstance(page_count, int)
        or not 1 <= page_count <= _MAX_PDF_PAGES
        or len(pages) != page_count
        or isinstance(character_count, bool)
        or not isinstance(character_count, int)
        or not 0 <= character_count <= _MAX_PDF_CHARACTERS
        or warnings != []
    ):
        raise DataError("literature worker extraction metadata is incomplete or inconsistent")

    observed_characters = 0
    has_text = False
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            raise DataError("literature worker extraction contains an invalid page")
        text = page.get("text")
        page_characters = page.get("character_count")
        page_sha256 = page.get("text_sha256")
        page_number = page.get("page")
        if (
            isinstance(page_number, bool)
            or not isinstance(page_number, int)
            or page_number != index
            or not isinstance(text, str)
            or isinstance(page_characters, bool)
            or not isinstance(page_characters, int)
            or page_characters != len(text)
            or not isinstance(page_sha256, str)
            or page_sha256 != hashlib.sha256(text.encode()).hexdigest()
        ):
            raise DataError("literature worker extraction contains inconsistent page text")
        observed_characters += len(text)
        has_text = has_text or bool(text)
    if observed_characters != character_count or not has_text:
        raise DataError("literature worker extraction does not contain complete readable text")
    artifact_core = {
        key: value
        for key, value in artifact.items()
        if key not in {"extraction_id", "artifact_sha256"}
    }
    expected_id = (
        "rx_"
        + hashlib.sha256(
            json.dumps(
                artifact_core,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
    )
    if extraction_id != expected_id:
        raise DataError("literature worker extraction identity does not match its contents")
    return artifact


def _document_summary(document: dict[str, object]) -> dict[str, object]:
    return {
        key: document.get(key)
        for key in (
            "extraction_id",
            "source_sha256",
            "status",
            "page_count",
            "character_count",
            "parser_version",
        )
    }


def _import_result(
    source: dict[str, object],
    document: dict[str, object],
    *,
    byte_count: int,
    source_sha256: str,
    idempotent_reuse: bool = False,
) -> dict[str, object]:
    acquisition: dict[str, object] = {
        "origin_kind": "owner_provided_local_pdf",
        "byte_count": byte_count,
        "sha256": source_sha256,
        "trust_label": "UNTRUSTED_SOURCE",
        "page_text_state": "extracted",
    }
    if idempotent_reuse:
        acquisition["idempotent_reuse"] = True
    return {
        "source": source,
        "document": _document_summary(document),
        "acquisition": acquisition,
    }


def import_owner_pdf_file(
    store: ControlStore,
    *,
    project_id: str,
    file_path: Path,
    title: str,
    worker: _Worker,
) -> dict[str, object]:
    """Import a selected PDF without network access or authority from document text."""
    clean_title = title.strip()
    if not clean_title or len(clean_title) > 500 or "\x00" in clean_title:
        raise DataError("owner-provided PDF title must contain bounded text")
    # This bounded read-only projection checks project ownership before opening the file.
    store.list_research_sources(project_id, limit=1)
    raw, source_sha256 = _read_owner_pdf(file_path)

    with tempfile.TemporaryDirectory(prefix="alpha-owner-pdf-") as temporary_root:
        temporary = Path(temporary_root)
        staged_pdf = temporary / "owner-source.pdf"
        staged_pdf.write_bytes(raw)
        extraction = worker(
            [
                "extract",
                "--object-path",
                str(staged_pdf),
                "--source-sha256",
                source_sha256,
                "--extractions-dir",
                str(temporary / "extractions"),
            ]
        )
        artifact = _validated_extraction(extraction, source_sha256=source_sha256)

    extraction_id = cast(str, artifact["extraction_id"])
    try:
        existing_document = store.get_research_document_text(extraction_id)
    except DataError as exc:
        if str(exc) != f"unknown research extraction {extraction_id!r}":
            raise
        existing_document = None
    if existing_document is not None:
        existing_source_id = existing_document.get("source_id")
        if not isinstance(existing_source_id, str):
            raise DataError("existing PDF extraction has no source binding")
        existing_source = store.get_research_source(existing_source_id)
        if existing_source.get("project_id") != project_id:
            raise DataError("owner PDF extraction is already bound to a different project")
        existing_metadata = existing_source.get("metadata")
        if (
            existing_source.get("content_hash") != source_sha256
            or existing_source.get("access_mode") != "owner_provided"
            or existing_source.get("title") != clean_title
            or existing_source.get("provider") != "owner"
            or existing_source.get("locator") != f"owner-provided:sha256:{source_sha256}"
            or not isinstance(existing_metadata, dict)
            or existing_metadata.get("origin_kind") != "owner_provided_local_pdf"
        ):
            raise DataError("owner PDF extraction is already bound to a different source record")
        return _import_result(
            existing_source,
            existing_document,
            byte_count=len(raw),
            source_sha256=source_sha256,
            idempotent_reuse=True,
        )

    source = store.create_research_source(
        project_id,
        title=clean_title,
        locator=f"owner-provided:sha256:{source_sha256}",
        provider="owner",
        access_mode="owner_provided",
        metadata={
            "origin_kind": "owner_provided_local_pdf",
            "trust_label": "UNTRUSTED_SOURCE",
        },
        content_hash=source_sha256,
    )
    try:
        document = store.record_research_document_text(str(source["source_id"]), artifact=artifact)
    except (DataError, OSError, sqlite3.Error) as exc:
        raise DataError(
            f"recoverable partial owner PDF import: source {source['source_id']} was recorded, "
            "but extracted text did not return a verified attachment. Check its extraction "
            "status before retrying with the same project, file, and title. "
            f"Cause: {exc}"
        ) from exc
    return _import_result(source, document, byte_count=len(raw), source_sha256=source_sha256)


def import_pdf_command(
    project_id: str,
    file_path: Path = typer.Option(..., "--file", help="one owner-selected local PDF"),  # noqa: B008
    title: str = typer.Option(..., "--title"),  # noqa: B008
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),  # noqa: B008
) -> None:
    """Import text from one owner-selected local PDF; no links are followed."""
    try:
        result = import_owner_pdf_file(
            _store(),
            project_id=project_id,
            file_path=file_path,
            title=title,
            worker=_run_literature_worker,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    source = cast(dict[str, object], result["source"])
    _emit(
        result,
        json_out=json_out,
        fallback=f"imported owner-provided PDF source {source['source_id']}",
    )


__all__ = ["import_pdf_command", "import_owner_pdf_file"]
