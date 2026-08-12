"""Offline fixture tests for the approved metadata services."""

from __future__ import annotations

import json

import pytest

from literature_worker._errors import DataError
from literature_worker.metadata import (
    deduplicate,
    lookup_url,
    normalize_doi,
    parse_arxiv,
    parse_crossref,
    parse_openalex,
    parse_unpaywall,
)


def test_lookup_urls_pin_the_approved_hosts() -> None:
    assert lookup_url("openalex", doi="10.1/x", query=None, email=None).startswith(
        "https://api.openalex.org/works/doi:10.1/x"
    )
    assert "api.crossref.org/works?query.title=double%20bottom" in lookup_url(
        "crossref", doi=None, query="double bottom", email=None
    )
    assert lookup_url("unpaywall", doi="10.1/x", query=None, email="o@example.com").startswith(
        "https://api.unpaywall.org/v2/10.1/x?email="
    )
    assert lookup_url("arxiv", doi=None, query="momentum", email=None).startswith(
        "https://export.arxiv.org/api/query?search_query=all:momentum"
    )
    with pytest.raises(DataError, match="unsupported literature provider"):
        lookup_url("scholar", doi="10.1/x", query=None, email=None)
    with pytest.raises(DataError, match="require --email"):
        lookup_url("unpaywall", doi="10.1/x", query=None, email=None)


def test_doi_normalization_strips_resolver_prefixes() -> None:
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("10.1234/abc") == "10.1234/abc"
    with pytest.raises(DataError, match="invalid DOI"):
        normalize_doi("not-a-doi")


def test_openalex_parser_normalizes_retraction_and_open_access() -> None:
    payload = {
        "results": [
            {
                "display_name": "Double bottoms revisited",
                "doi": "https://doi.org/10.5/db",
                "publication_year": 2019,
                "is_retracted": True,
                "authorships": [{"author": {"display_name": "A. Author"}}],
                "best_oa_location": {"pdf_url": "https://example.org/x.pdf"},
            }
        ]
    }
    records = parse_openalex(json.dumps(payload).encode())
    assert records[0]["doi"] == "10.5/db"
    assert records[0]["retracted"] is True
    assert records[0]["authors"] == ["A. Author"]
    assert records[0]["dedup_key"] == "doi:10.5/db"
    assert records[0]["trust_label"] == "UNTRUSTED_SOURCE"


def test_crossref_parser_reads_retraction_updates_and_years() -> None:
    payload = {
        "message": {
            "title": ["Calendar effects"],
            "DOI": "10.9/cal",
            "published": {"date-parts": [[2015, 3]]},
            "author": [{"given": "A.", "family": "Author"}],
            "update-to": [{"type": "retraction"}],
        }
    }
    records = parse_crossref(json.dumps(payload).encode())
    assert records[0]["year"] == 2015
    assert records[0]["retracted"] is True
    assert records[0]["authors"] == ["A. Author"]
    with pytest.raises(DataError, match="message envelope"):
        parse_crossref(b"{}")


def test_unpaywall_parser_extracts_best_open_access_location() -> None:
    payload = {
        "title": "Calendar effects",
        "doi": "10.9/cal",
        "year": 2015,
        "z_authors": [{"given": "A.", "family": "Author"}],
        "best_oa_location": {"url_for_pdf": "https://example.org/x.pdf"},
    }
    records = parse_unpaywall(json.dumps(payload).encode())
    assert records[0]["open_access_url"] == "https://example.org/x.pdf"


def test_arxiv_parser_reads_versions_and_refuses_entity_markup() -> None:
    atom = (
        b'<?xml version="1.0"?>'
        b'<feed xmlns="http://www.w3.org/2005/Atom">'
        b"<entry><title>Momentum</title>"
        b"<id>http://arxiv.org/abs/1234.5678v2</id>"
        b"<published>2019-01-01T00:00:00Z</published>"
        b"<author><name>A. Author</name></author></entry></feed>"
    )
    records = parse_arxiv(atom)
    assert records[0]["version"] == "v2"
    assert records[0]["year"] == 2019
    assert records[0]["open_access_url"] == "https://arxiv.org/pdf/1234.5678v2"
    hostile = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><feed/>'
    with pytest.raises(DataError, match="entity markup"):
        parse_arxiv(hostile)


def test_deduplicate_prefers_first_occurrence_by_doi_and_content_key() -> None:
    records = parse_openalex(
        json.dumps(
            {
                "results": [
                    {"display_name": "Paper", "doi": "https://doi.org/10.5/db"},
                    {"display_name": "Paper duplicate", "doi": "10.5/DB"},
                    {"display_name": "Untitled sibling", "publication_year": 2020},
                    {"display_name": "Untitled sibling", "publication_year": 2020},
                ]
            }
        ).encode()
    )
    unique = deduplicate(records)
    assert [record["title"] for record in unique] == ["Paper", "Untitled sibling"]
