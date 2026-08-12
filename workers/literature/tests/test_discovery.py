"""Deterministic multi-provider discovery contracts."""

from __future__ import annotations

from literature_worker.discovery import DiscoveryBudget, discover


def test_discovery_deduplicates_across_providers_and_explains_relevance() -> None:
    records = {
        "openalex": [
            {
                "provider": "openalex",
                "title": "Double bottom price patterns",
                "doi": "10.1/shared",
                "year": 2020,
                "authors": ["A"],
                "retracted": False,
                "version": None,
                "open_access_url": "https://arxiv.org/pdf/paper",
                "dedup_key": "doi:10.1/shared",
                "trust_label": "UNTRUSTED_SOURCE",
            }
        ],
        "crossref": [
            {
                "provider": "crossref",
                "title": "Duplicate record",
                "doi": "10.1/shared",
                "year": 2020,
                "authors": [],
                "retracted": None,
                "version": None,
                "open_access_url": None,
                "dedup_key": "doi:10.1/shared",
                "trust_label": "UNTRUSTED_SOURCE",
            }
        ],
        "arxiv": [],
        "unpaywall": [],
    }

    result = discover(
        "double bottom",
        lookup=lambda provider, **_: (records[provider], f"{provider}-sha"),
    )

    assert result["schema"] == "LiteratureDiscoveryV1"
    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["access_state"] == "direct_pdf"
    assert candidate["matched_concepts"] == ["bottom", "double"]
    assert "matched title concepts" in candidate["relevance_explanation"]
    assert result["receipt"]["candidate_count"] == 1
    assert result["receipt"]["trust_label"] == "UNTRUSTED_SOURCE"


def test_discovery_budget_caps_candidates_and_never_calls_unpaywall_without_doi() -> None:
    called: list[tuple[str, str | None]] = []

    def lookup(provider: str, **kwargs: object) -> tuple[list[dict[str, object]], str]:
        called.append((provider, kwargs.get("doi") if isinstance(kwargs.get("doi"), str) else None))
        if provider == "openalex":
            return (
                [
                    {
                        "provider": provider,
                        "title": f"Result {index}",
                        "doi": None,
                        "year": 2020,
                        "authors": [],
                        "retracted": None,
                        "version": None,
                        "open_access_url": None,
                        "dedup_key": f"content:{index:032x}",
                        "trust_label": "UNTRUSTED_SOURCE",
                    }
                    for index in range(10)
                ],
                "openalex-sha",
            )
        return ([], f"{provider}-sha")

    result = discover("market pattern", budget=DiscoveryBudget(max_candidates=3), lookup=lookup)
    assert len(result["candidates"]) == 3
    assert all(provider != "unpaywall" for provider, _ in called)
    assert result["receipt"]["budget"]["max_candidates"] == 3
