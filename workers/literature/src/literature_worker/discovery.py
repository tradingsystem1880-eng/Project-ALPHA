"""Bounded, deterministic discovery across the approved scholarly providers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Protocol, cast
from urllib.parse import urlsplit

from literature_worker._errors import DataError
from literature_worker.metadata import _has_reported_ssrn_version_relation, lookup_url

_QUERY_TOKEN = re.compile(r"[a-z0-9]+")
_DOCUMENT_HOSTS = frozenset({"arxiv.org", "export.arxiv.org"})


@dataclass(frozen=True, slots=True)
class DiscoveryBudget:
    max_candidates: int = 20
    max_full_texts: int = 5

    def __post_init__(self) -> None:
        if not 1 <= self.max_candidates <= 20:
            raise DataError("literature discovery candidate budget must be in 1..20")
        if not 0 <= self.max_full_texts <= 5:
            raise DataError("literature full-text budget must be in 0..5")


class Lookup(Protocol):
    def __call__(
        self,
        provider: str,
        *,
        query: str | None,
        doi: str | None,
    ) -> tuple[list[dict[str, object]], str]: ...


def _access_state(url: object) -> str:
    if not isinstance(url, str) or not url:
        return "metadata_only"
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        return "unavailable"
    if parsed.hostname not in _DOCUMENT_HOSTS:
        return "unavailable"
    if parsed.path.casefold().endswith(".pdf") or parsed.path.startswith("/pdf/"):
        return "direct_pdf"
    return "landing_page"


def _relevance(query_tokens: set[str], title: str) -> tuple[list[str], str]:
    title_tokens = set(_QUERY_TOKEN.findall(title.casefold()))
    matched = sorted(query_tokens & title_tokens)
    if matched:
        return matched, f"matched title concepts: {', '.join(matched)}."
    return [], "No exact query concept appears in the title; review metadata before acquisition."


def _candidate_evidence(
    provider: str, response_sha256: str, record: dict[str, object]
) -> dict[str, str]:
    evidence = {"provider": provider, "response_sha256": response_sha256}
    doi = record.get("doi")
    if provider in {"openalex", "crossref"} and isinstance(doi, str) and doi:
        evidence["record_url"] = lookup_url(provider, doi=doi, query=None, email=None)
        evidence["record_doi"] = doi
    return evidence


def _merge_provider_evidence(*records: dict[str, object]) -> list[dict[str, str]]:
    evidence_by_key: dict[str, dict[str, str]] = {}
    for record in records:
        entries = record.get("provider_evidence")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and all(
                isinstance(key, str) and isinstance(value, str) for key, value in entry.items()
            ):
                evidence_by_key[json.dumps(entry, sort_keys=True, separators=(",", ":"))] = entry
    return [evidence_by_key[key] for key in sorted(evidence_by_key)]


def _string_relation_rows(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        cast(dict[str, str], relation)
        for relation in value
        if isinstance(relation, dict)
        and all(isinstance(key, str) and isinstance(item, str) for key, item in relation.items())
    ]


def _merge_candidate(current: dict[str, object], incoming: dict[str, object]) -> dict[str, object]:
    merged = dict(current)
    merged["provider_evidence"] = _merge_provider_evidence(current, incoming)
    relations = _string_relation_rows(current.get("provider_relations")) + _string_relation_rows(
        incoming.get("provider_relations")
    )
    relation_by_key = {
        json.dumps(relation, sort_keys=True, separators=(",", ":")): relation
        for relation in relations
    }
    if relation_by_key:
        merged["provider_relations"] = [relation_by_key[key] for key in sorted(relation_by_key)]

    current_ssrn = current.get("ssrn")
    incoming_ssrn = incoming.get("ssrn")
    if isinstance(current_ssrn, dict) and isinstance(incoming_ssrn, dict):
        if current_ssrn.get("id") != incoming_ssrn.get("id"):
            raise DataError("duplicate literature records disagree on their SSRN identifier")
        ssrn = dict(current_ssrn)
        if incoming_ssrn.get("record_type") == "ssrn_preprint_record":
            ssrn["record_type"] = incoming_ssrn["record_type"]
            ssrn["identity_source"] = incoming_ssrn.get("identity_source")
        ssrn_relations = _string_relation_rows(
            current_ssrn.get("provider_relations")
        ) + _string_relation_rows(incoming_ssrn.get("provider_relations"))
        ssrn_relation_by_key = {
            json.dumps(relation, sort_keys=True, separators=(",", ":")): relation
            for relation in ssrn_relations
        }
        ssrn["provider_relations"] = [
            ssrn_relation_by_key[key] for key in sorted(ssrn_relation_by_key)
        ]
        reported_relation = _has_reported_ssrn_version_relation(
            ssrn["provider_relations"],
            ssrn_id=str(ssrn.get("id")),
            direct_ssrn_record=ssrn.get("record_type") == "ssrn_preprint_record",
        )
        ssrn["published_version_relation"] = (
            "provider_reported" if reported_relation else "unverified"
        )
        merged["ssrn"] = ssrn
    elif isinstance(incoming_ssrn, dict):
        merged["ssrn"] = incoming_ssrn
    return merged


def discover(
    query: str,
    *,
    budget: DiscoveryBudget | None = None,
    lookup: Lookup,
) -> dict[str, object]:
    """Discover candidates; ranking is provider order plus title-token overlap, not quality."""
    clean_query = " ".join(query.split())
    tokens = set(_QUERY_TOKEN.findall(clean_query.casefold()))
    if not clean_query or not tokens or len(clean_query) > 500:
        raise DataError("literature discovery query must contain bounded searchable text")
    active = budget or DiscoveryBudget()
    provider_receipts: list[dict[str, str]] = []
    records: list[dict[str, object]] = []
    for provider in ("openalex", "crossref", "arxiv"):
        found, response_sha256 = lookup(provider, query=clean_query, doi=None)
        provider_receipts.append({"provider": provider, "response_sha256": response_sha256})
        records.extend(
            {
                **record,
                "provider_evidence": [_candidate_evidence(provider, response_sha256, record)],
            }
            for record in found
        )
    # Unpaywall is DOI-specific. It enriches at most the still-bounded unique DOI set.
    dois = sorted(
        {doi for record in records if isinstance((doi := record.get("doi")), str) and doi}
    )[: active.max_candidates]
    for doi in dois:
        found, response_sha256 = lookup("unpaywall", query=None, doi=doi)
        provider_receipts.append(
            {"provider": "unpaywall", "doi": doi, "response_sha256": response_sha256}
        )
        records.extend(
            {
                **record,
                "provider_evidence": [_candidate_evidence("unpaywall", response_sha256, record)],
            }
            for record in found
        )

    by_key: dict[str, dict[str, object]] = {}
    for record in records:
        key = record.get("dedup_key")
        if not isinstance(key, str) or not key:
            continue
        current = by_key.get(key)
        if current is None:
            by_key[key] = dict(record)
            continue
        merged = _merge_candidate(current, record)
        if (
            _access_state(record.get("open_access_url")) == "direct_pdf"
            and _access_state(current.get("open_access_url")) != "direct_pdf"
        ):
            merged["open_access_url"] = record.get("open_access_url")
            merged["provider"] = f"{current.get('provider')}+{record.get('provider')}"
        by_key[key] = merged

    candidates: list[dict[str, object]] = []
    for key in sorted(by_key):
        record = by_key[key]
        title = str(record.get("title") or "")
        matched, explanation = _relevance(tokens, title)
        candidate = {
            **record,
            "candidate_id": "lc_" + hashlib.sha256(key.encode()).hexdigest(),
            "access_state": _access_state(record.get("open_access_url")),
            "matched_concepts": matched,
            "relevance_explanation": explanation,
        }
        candidates.append(candidate)
    candidates.sort(
        key=lambda candidate: (
            -len(candidate["matched_concepts"]),  # type: ignore[arg-type]
            str(candidate.get("dedup_key")),
        )
    )
    candidates = candidates[: active.max_candidates]
    contract = {
        "schema": "LiteratureDiscoveryContractV1",
        "query": clean_query,
        "providers": ["openalex", "crossref", "arxiv", "unpaywall"],
        "budget": asdict(active),
    }
    receipt_core = {
        "schema": "LiteratureDiscoveryReceiptV1",
        "contract": contract,
        "budget": asdict(active),
        "provider_responses": provider_receipts,
        "candidate_count": len(candidates),
        "candidate_digest": hashlib.sha256(
            json.dumps(candidates, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "trust_label": "UNTRUSTED_SOURCE",
    }
    receipt_id = (
        "ld_"
        + hashlib.sha256(
            json.dumps(receipt_core, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    return {
        "schema": "LiteratureDiscoveryV1",
        "discovery_id": receipt_id,
        "query": clean_query,
        "candidates": candidates,
        "receipt": {"receipt_id": receipt_id, **receipt_core},
    }


__all__ = ["DiscoveryBudget", "Lookup", "discover"]
