"""Bounded PDF text extraction into an immutable, untrusted artifact."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Final, cast

import pypdf
from pypdf import PdfReader

from literature_worker._errors import DataError

_SHA256: Final = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class ExtractionPolicy:
    max_input_bytes: int = 10 * 1024 * 1024
    max_pages: int = 200
    max_characters: int = 2_000_000

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in (self.max_input_bytes, self.max_pages, self.max_characters)
        ):
            raise DataError("literature extraction limits must be positive integers")


def _digest(value: str, field: str) -> str:
    if len(value) != 64 or any(character not in _SHA256 for character in value):
        raise DataError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _normalized_page_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip()


def _parser_config(policy: ExtractionPolicy) -> dict[str, object]:
    return {
        "parser": "pypdf",
        "parser_version": pypdf.__version__,
        "normalization": "NFC_LF_RSTRIP_V1",
        "limits": asdict(policy),
    }


def _artifact(
    *,
    source_sha256: str,
    policy: ExtractionPolicy,
    status: str,
    pages: list[dict[str, object]],
    warnings: list[str],
) -> dict[str, object]:
    config = _parser_config(policy)
    config_hash = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    core: dict[str, object] = {
        "schema": "ResearchDocumentTextV1",
        "source_sha256": source_sha256,
        "parser": config["parser"],
        "parser_version": config["parser_version"],
        "config_hash": config_hash,
        "normalization": config["normalization"],
        "status": status,
        "pages": pages,
        "page_count": len(pages),
        "character_count": sum(len(cast(str, page["text"])) for page in pages),
        "warnings": warnings,
        "trust_label": "UNTRUSTED_SOURCE",
    }
    artifact_id = (
        "rx_"
        + hashlib.sha256(
            json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
    )
    return {"extraction_id": artifact_id, **core}


def extract_pdf(
    raw: bytes,
    *,
    source_sha256: str,
    policy: ExtractionPolicy | None = None,
) -> dict[str, object]:
    """Extract normalized page text without treating any document text as instructions."""
    active = policy or ExtractionPolicy()
    expected = _digest(source_sha256, "literature source digest")
    if len(raw) > active.max_input_bytes:
        raise DataError("literature extraction input exceeds the byte limit")
    if hashlib.sha256(raw).hexdigest() != expected:
        raise DataError("literature source digest does not match acquired bytes")
    try:
        reader = PdfReader(BytesIO(raw), strict=True)
    except Exception as exc:  # pypdf exposes several parser-specific exception classes.
        return _artifact(
            source_sha256=expected,
            policy=active,
            status="parser_failed",
            pages=[],
            warnings=[f"PDF parser failed: {type(exc).__name__}"],
        )
    if reader.is_encrypted:
        return _artifact(
            source_sha256=expected,
            policy=active,
            status="encrypted",
            pages=[],
            warnings=["Encrypted PDF; password handling and bypass are out of scope."],
        )
    if len(reader.pages) > active.max_pages:
        return _artifact(
            source_sha256=expected,
            policy=active,
            status="truncated",
            pages=[],
            warnings=["PDF exceeds the configured page limit; no partial text was retained."],
        )
    pages: list[dict[str, object]] = []
    characters = 0
    try:
        for index, page in enumerate(reader.pages, start=1):
            text = _normalized_page_text(page.extract_text() or "")
            characters += len(text)
            if characters > active.max_characters:
                return _artifact(
                    source_sha256=expected,
                    policy=active,
                    status="truncated",
                    pages=[],
                    warnings=[
                        "PDF exceeds the configured character limit; no partial text was retained."
                    ],
                )
            pages.append(
                {
                    "page": index,
                    "text": text,
                    "character_count": len(text),
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
            )
    except Exception as exc:
        return _artifact(
            source_sha256=expected,
            policy=active,
            status="parser_failed",
            pages=[],
            warnings=[f"PDF page extraction failed: {type(exc).__name__}"],
        )
    status = "extracted" if any(page["text"] for page in pages) else "image_only"
    warnings = [] if status == "extracted" else ["No extractable text; OCR is out of scope."]
    return _artifact(
        source_sha256=expected,
        policy=active,
        status=status,
        pages=pages,
        warnings=warnings,
    )


def store_extraction(artifact: dict[str, object], directory: Path) -> dict[str, str]:
    """Persist an extraction exactly once under its content-derived identifier."""
    extraction_id = artifact.get("extraction_id")
    if not isinstance(extraction_id, str) or not extraction_id.startswith("rx_"):
        raise DataError("literature extraction artifact has no valid identifier")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{extraction_id}.json"
    encoded = (json.dumps(artifact, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    if target.exists():
        if target.read_bytes() != encoded:
            raise DataError("literature extraction identifier collision")
        return {"extraction_id": extraction_id, "extraction_path": str(target)}
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{extraction_id}.", dir=directory)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"extraction_id": extraction_id, "extraction_path": str(target)}


__all__ = ["ExtractionPolicy", "extract_pdf", "store_extraction"]
