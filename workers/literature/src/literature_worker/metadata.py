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
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit

from literature_worker._errors import DataError

PROVIDER_HOSTS: Final = {
    "openalex": "api.openalex.org",
    "crossref": "api.crossref.org",
    "unpaywall": "api.unpaywall.org",
    "arxiv": "export.arxiv.org",
}

_ATOM_NS: Final = "{http://www.w3.org/2005/Atom}"
_DOI_PREFIX: Final = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)
_SSRN_DOI_PREFIX: Final = "10.2139/ssrn."
_SSRN_DOI_ID: Final = re.compile(r"^10\.2139/ssrn\.([1-9][0-9]*)$")
_SSRN_ID: Final = re.compile(r"^[1-9][0-9]*$")
_SSRN_HOSTS: Final = frozenset({"papers.ssrn.com", "ssrn.com", "www.ssrn.com"})


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


def _ssrn_id_from_doi(doi: str | None) -> str | None:
    if doi is None:
        return None
    normalized = normalize_doi(doi)
    if not normalized.startswith(_SSRN_DOI_PREFIX):
        return None
    match = _SSRN_DOI_ID.fullmatch(normalized)
    if match is None:
        raise DataError("invalid SSRN DOI identifier")
    return match.group(1)


def _ssrn_id_from_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise DataError("invalid SSRN abstract URL") from exc
    host = (parsed.hostname or "").casefold()
    if host not in _SSRN_HOSTS:
        return None
    if (
        parsed.scheme.casefold() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
    ):
        raise DataError("invalid SSRN abstract URL")
    identifier: str | None = None
    if host == "papers.ssrn.com" and parsed.path == "/sol3/papers.cfm":
        query = parse_qs(parsed.query, keep_blank_values=True)
        values = query.get("abstract_id", [])
        if set(query) != {"abstract_id"} or len(values) != 1:
            raise DataError("invalid SSRN abstract URL")
        identifier = values[0]
    elif host in {"ssrn.com", "www.ssrn.com"}:
        match = re.fullmatch(r"/abstract=([^/]+)", parsed.path)
        if match is not None and not parsed.query:
            identifier = match.group(1)
    if identifier is None:
        return None
    if _SSRN_ID.fullmatch(identifier) is None:
        raise DataError("invalid SSRN abstract identifier")
    return identifier


def _crossref_relations(value: object) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return []
    relations: list[dict[str, str]] = []
    for relation_type, entries in sorted(value.items(), key=lambda item: str(item[0]))[:20]:
        if not isinstance(relation_type, str) or not relation_type or len(relation_type) > 100:
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries[:20]:
            if not isinstance(entry, dict):
                continue
            id_type = entry.get("id-type")
            identifier = entry.get("id")
            if (
                isinstance(id_type, str)
                and id_type
                and len(id_type) <= 64
                and isinstance(identifier, str)
                and identifier
                and len(identifier) <= 300
            ):
                relations.append(
                    {"type": relation_type, "id_type": id_type, "identifier": identifier}
                )
    return relations


def _has_reported_ssrn_version_relation(
    relations: list[dict[str, str]], *, ssrn_id: str, direct_ssrn_record: bool
) -> bool:
    for relation in relations:
        relation_type = relation.get("type", "").casefold()
        if relation.get("id_type", "").casefold() != "doi":
            continue
        identifier = relation.get("identifier")
        if not identifier:
            continue
        related_ssrn_id = _ssrn_id_from_doi(identifier)
        if (
            relation_type == "has-preprint"
            and not direct_ssrn_record
            and related_ssrn_id == ssrn_id
        ):
            return True
        if relation_type == "is-preprint-of" and direct_ssrn_record and related_ssrn_id is None:
            return True
    return False


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
    ssrn_url: str | None = None,
    provider_relations: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    if not title:
        raise DataError(f"{provider} response is missing a title")
    normalized_doi = None if doi is None else normalize_doi(doi)
    direct_ssrn_doi_id = _ssrn_id_from_doi(normalized_doi)
    ssrn_url_id = _ssrn_id_from_url(ssrn_url)
    if (
        direct_ssrn_doi_id is not None
        and ssrn_url_id is not None
        and direct_ssrn_doi_id != ssrn_url_id
    ):
        raise DataError("SSRN DOI and abstract URL identifiers conflict")
    related_ssrn_dois: dict[str, str] = {}
    for relation in provider_relations or []:
        if relation.get("id_type", "").casefold() != "doi":
            continue
        relation_doi = relation.get("identifier")
        if isinstance(relation_doi, str):
            relation_ssrn_id = _ssrn_id_from_doi(relation_doi)
            if relation_ssrn_id is not None:
                related_ssrn_dois[relation_ssrn_id] = normalize_doi(relation_doi)
    ssrn_id = direct_ssrn_doi_id or ssrn_url_id
    identity_source = "doi" if direct_ssrn_doi_id is not None else "abstract_url"
    direct_ssrn_record = direct_ssrn_doi_id is not None or (
        ssrn_url_id is not None and normalized_doi is None
    )
    if ssrn_id is None and len(related_ssrn_dois) == 1:
        ssrn_id = next(iter(related_ssrn_dois))
        identity_source = "provider_relation"
    has_reported_version_relation = ssrn_id is not None and _has_reported_ssrn_version_relation(
        provider_relations or [],
        ssrn_id=ssrn_id,
        direct_ssrn_record=direct_ssrn_record,
    )
    record: dict[str, object] = {
        "provider": provider,
        "title": title,
        "doi": normalized_doi,
        "year": year,
        "authors": authors,
        "retracted": retracted,
        "version": version,
        "open_access_url": open_access_url,
        "dedup_key": dedup_key(doi=doi, title=title, year=year),
        "trust_label": "UNTRUSTED_SOURCE",
    }
    if provider_relations:
        record["provider_relations"] = provider_relations
    if ssrn_id is not None:
        ssrn_doi = (
            normalized_doi if direct_ssrn_doi_id == ssrn_id else related_ssrn_dois.get(ssrn_id)
        )
        record["ssrn"] = {
            "id": ssrn_id,
            "doi": ssrn_doi,
            "abstract_url": ("https://papers.ssrn.com/sol3/papers.cfm?abstract_id=" + ssrn_id),
            "record_type": (
                "provider_related_ssrn_record" if not direct_ssrn_record else "ssrn_preprint_record"
            ),
            "identity_source": identity_source,
            "related_ssrn_ids": sorted(set(related_ssrn_dois) - {ssrn_id}),
            "published_version_relation": (
                "provider_reported" if has_reported_version_relation else "unverified"
            ),
            "provider_relations": provider_relations or [],
            "full_text_state": "metadata_only",
            "access_verification": "unverified",
            "content_version_sha256": None,
        }
    return record


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
    ssrn_url: str | None = None
    best = work.get("best_oa_location")
    if isinstance(best, dict):
        landing_page = best.get("landing_page_url")
        if isinstance(landing_page, str) and landing_page:
            ssrn_url = landing_page
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
        ssrn_url=ssrn_url,
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
        provider_relations=_crossref_relations(message.get("relation")),
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
