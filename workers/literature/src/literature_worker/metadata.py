"""Approved scholarly metadata services: request builders and fail-loud parsers.

OpenAlex, Crossref, Unpaywall, and arXiv only (ADR-0024); Google Scholar stays
manual-browser-only. Builders return the exact HTTPS URL for the worker's validated
fetch loop; parsers normalize responses into one record shape with a dedup key and
recorded retraction/version state. Every response is untrusted input.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ElementTree
from typing import Final
from urllib.parse import quote, urlsplit, urlunsplit

from literature_worker._errors import DataError

PROVIDER_HOSTS: Final = {
    "openalex": "api.openalex.org",
    "crossref": "api.crossref.org",
    "unpaywall": "api.unpaywall.org",
    "arxiv": "export.arxiv.org",
}

_ATOM_NS: Final = "{http://www.w3.org/2005/Atom}"
_DOI_PREFIX: Final = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)


def _arxiv_pdf_url(identifier: str) -> str | None:
    if not identifier:
        return None
    parsed = urlsplit(identifier)
    host = (parsed.hostname or "").lower()
    if host not in {"arxiv.org", "export.arxiv.org"} or not parsed.path.startswith("/abs/"):
        raise DataError("arxiv entry id is not a canonical arxiv abstract URL")
    path = "/pdf/" + parsed.path.removeprefix("/abs/")
    return urlunsplit(("https", host, path, "", ""))


def normalize_doi(value: str) -> str:
    cleaned = _DOI_PREFIX.sub("", value.strip()).lower()
    if not cleaned or "/" not in cleaned:
        raise DataError(f"invalid DOI {value!r}")
    return cleaned


def dedup_key(*, doi: str | None, title: str, year: int | None) -> str:
    """DOI when present; else a content key over normalized title+year."""
    if doi:
        return f"doi:{normalize_doi(doi)}"
    digest = hashlib.sha256(f"{title.casefold()}|{year}".encode()).hexdigest()
    return f"content:{digest[:32]}"


def lookup_url(provider: str, *, doi: str | None, query: str | None, email: str | None) -> str:
    """Build the exact approved-service URL for one metadata lookup."""
    if provider not in PROVIDER_HOSTS:
        raise DataError(f"unsupported literature provider {provider!r}")
    if doi is None and query is None:
        raise DataError("literature lookup requires --doi or --query")
    host = PROVIDER_HOSTS[provider]
    if provider == "openalex":
        if doi is not None:
            return f"https://{host}/works/doi:{quote(normalize_doi(doi), safe='/')}"
        return f"https://{host}/works?filter=title.search:{quote(query or '')}&per-page=5"
    if provider == "crossref":
        if doi is not None:
            return f"https://{host}/works/{quote(normalize_doi(doi), safe='/')}"
        return f"https://{host}/works?query.title={quote(query or '')}&rows=5"
    if provider == "unpaywall":
        if doi is None:
            raise DataError("unpaywall lookups require --doi")
        if not email:
            raise DataError("unpaywall lookups require --email (their required identifier)")
        return f"https://{host}/v2/{quote(normalize_doi(doi), safe='/')}?email={quote(email)}"
    # arxiv
    if query is None:
        raise DataError("arxiv lookups require --query")
    return f"https://{host}/api/query?search_query=all:{quote(query)}&max_results=5"


def _record(
    *,
    provider: str,
    title: str,
    doi: str | None,
    year: int | None,
    authors: list[str],
    retracted: bool | None,
    version: str | None,
    open_access_url: str | None,
) -> dict[str, object]:
    if not title:
        raise DataError(f"{provider} response is missing a title")
    return {
        "provider": provider,
        "title": title,
        "doi": None if doi is None else normalize_doi(doi),
        "year": year,
        "authors": authors,
        "retracted": retracted,
        "version": version,
        "open_access_url": open_access_url,
        "dedup_key": dedup_key(doi=doi, title=title, year=year),
        "trust_label": "UNTRUSTED_SOURCE",
    }


def _json_body(raw: bytes, provider: str) -> dict[str, object]:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"{provider} response is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise DataError(f"{provider} response is not a JSON object")
    return decoded


def _openalex_record(work: dict[str, object]) -> dict[str, object]:
    title = str(work.get("display_name") or work.get("title") or "")
    doi_raw = work.get("doi")
    year = work.get("publication_year")
    authors: list[str] = []
    authorships = work.get("authorships")
    if isinstance(authorships, list):
        for authorship in authorships:
            if isinstance(authorship, dict):
                author = authorship.get("author")
                if isinstance(author, dict) and isinstance(author.get("display_name"), str):
                    authors.append(str(author["display_name"]))
    oa_url: str | None = None
    best = work.get("best_oa_location")
    if isinstance(best, dict):
        for field in ("pdf_url", "landing_page_url"):
            value = best.get(field)
            if isinstance(value, str) and value:
                oa_url = value
                break
    retracted = work.get("is_retracted")
    return _record(
        provider="openalex",
        title=title,
        doi=doi_raw if isinstance(doi_raw, str) and doi_raw else None,
        year=year if isinstance(year, int) and not isinstance(year, bool) else None,
        authors=authors,
        retracted=retracted if isinstance(retracted, bool) else None,
        version=None,
        open_access_url=oa_url,
    )


def parse_openalex(raw: bytes) -> list[dict[str, object]]:
    body = _json_body(raw, "openalex")
    results = body.get("results")
    if isinstance(results, list):
        return [_openalex_record(work) for work in results if isinstance(work, dict)]
    return [_openalex_record(body)]


def _crossref_record(message: dict[str, object]) -> dict[str, object]:
    titles = message.get("title")
    title = str(titles[0]) if isinstance(titles, list) and titles else ""
    doi_raw = message.get("DOI")
    year: int | None = None
    published = message.get("published") or message.get("published-print")
    if isinstance(published, dict):
        parts = published.get("date-parts")
        if (
            isinstance(parts, list)
            and parts
            and isinstance(parts[0], list)
            and parts[0]
            and isinstance(parts[0][0], int)
        ):
            year = int(parts[0][0])
    authors: list[str] = []
    author_rows = message.get("author")
    if isinstance(author_rows, list):
        for row in author_rows:
            if isinstance(row, dict):
                name = " ".join(
                    str(row[part]) for part in ("given", "family") if isinstance(row.get(part), str)
                ).strip()
                if name:
                    authors.append(name)
    retracted: bool | None = None
    updates = message.get("update-to")
    if isinstance(updates, list):
        retracted = any(
            isinstance(update, dict) and update.get("type") == "retraction" for update in updates
        )
    return _record(
        provider="crossref",
        title=title,
        doi=doi_raw if isinstance(doi_raw, str) and doi_raw else None,
        year=year,
        authors=authors,
        retracted=retracted,
        version=None,
        open_access_url=None,
    )


def parse_crossref(raw: bytes) -> list[dict[str, object]]:
    body = _json_body(raw, "crossref")
    message = body.get("message")
    if not isinstance(message, dict):
        raise DataError("crossref response is missing its message envelope")
    items = message.get("items")
    if isinstance(items, list):
        return [_crossref_record(item) for item in items if isinstance(item, dict)]
    return [_crossref_record(message)]


def parse_unpaywall(raw: bytes) -> list[dict[str, object]]:
    body = _json_body(raw, "unpaywall")
    title = str(body.get("title") or "")
    doi_raw = body.get("doi")
    year = body.get("year")
    authors: list[str] = []
    z_authors = body.get("z_authors")
    if isinstance(z_authors, list):
        for row in z_authors:
            if isinstance(row, dict):
                name = " ".join(
                    str(row[part]) for part in ("given", "family") if isinstance(row.get(part), str)
                ).strip()
                if name:
                    authors.append(name)
    oa_url: str | None = None
    best = body.get("best_oa_location")
    if isinstance(best, dict):
        for field in ("url_for_pdf", "url"):
            value = best.get(field)
            if isinstance(value, str) and value:
                oa_url = value
                break
    return [
        _record(
            provider="unpaywall",
            title=title,
            doi=doi_raw if isinstance(doi_raw, str) and doi_raw else None,
            year=year if isinstance(year, int) and not isinstance(year, bool) else None,
            authors=authors,
            retracted=None,
            version=None,
            open_access_url=oa_url,
        )
    ]


def parse_arxiv(raw: bytes) -> list[dict[str, object]]:
    """Parse the arXiv Atom feed; DOCTYPE/ENTITY markup is refused outright."""
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise DataError("arxiv response contains prohibited XML entity markup")
    try:
        root = ElementTree.fromstring(raw.decode("utf-8"))
    except (UnicodeDecodeError, ElementTree.ParseError) as exc:
        raise DataError("arxiv response is not valid Atom XML") from exc
    records: list[dict[str, object]] = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        title = (entry.findtext(f"{_ATOM_NS}title") or "").strip()
        identifier = (entry.findtext(f"{_ATOM_NS}id") or "").strip()
        published = (entry.findtext(f"{_ATOM_NS}published") or "").strip()
        year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None
        authors = [
            (author.findtext(f"{_ATOM_NS}name") or "").strip()
            for author in entry.findall(f"{_ATOM_NS}author")
        ]
        version_match = re.search(r"v(\d+)$", identifier)
        records.append(
            _record(
                provider="arxiv",
                title=title,
                doi=None,
                year=year,
                authors=[name for name in authors if name],
                retracted=None,
                version=None if version_match is None else f"v{version_match.group(1)}",
                open_access_url=_arxiv_pdf_url(identifier),
            )
        )
    return records


_PARSERS: Final = {
    "openalex": parse_openalex,
    "crossref": parse_crossref,
    "unpaywall": parse_unpaywall,
    "arxiv": parse_arxiv,
}


def parse_lookup(provider: str, raw: bytes) -> list[dict[str, object]]:
    if provider not in _PARSERS:
        raise DataError(f"unsupported literature provider {provider!r}")
    return _PARSERS[provider](raw)


def deduplicate(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Keep first occurrence per dedup key; order is the providers' relevance order."""
    seen: set[str] = set()
    unique: list[dict[str, object]] = []
    for record in records:
        key = str(record.get("dedup_key", ""))
        if key and key not in seen:
            seen.add(key)
            unique.append(record)
    return unique


__all__ = [
    "PROVIDER_HOSTS",
    "dedup_key",
    "deduplicate",
    "lookup_url",
    "normalize_doi",
    "parse_arxiv",
    "parse_crossref",
    "parse_lookup",
    "parse_openalex",
    "parse_unpaywall",
]
