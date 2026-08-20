"""Owner-invoked CLI for the isolated literature worker: lookup and fetch, JSON out."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from literature_worker._acquisition import AcquisitionPolicy
from literature_worker._errors import DataError
from literature_worker.discovery import DiscoveryBudget, discover
from literature_worker.extract import extract_pdf, store_extraction
from literature_worker.fetch import (
    default_resolver,
    fetch_validated,
    store_object,
    urllib_transport,
)
from literature_worker.metadata import (
    PROVIDER_HOSTS,
    deduplicate,
    lookup_url,
    parse_lookup,
)

_METADATA_MEDIA_TYPES = frozenset(
    {"application/json", "application/atom+xml", "text/xml", "application/xml"}
)
_DOCUMENT_HOSTS = frozenset({"arxiv.org", "export.arxiv.org"})


def _lookup(args: argparse.Namespace) -> dict[str, object]:
    url = lookup_url(args.provider, doi=args.doi, query=args.query, email=args.email)
    policy = AcquisitionPolicy(
        allowed_hosts=frozenset({PROVIDER_HOSTS[args.provider]}),
        allowed_media_types=_METADATA_MEDIA_TYPES,
        max_response_bytes=2 * 1024 * 1024,
    )
    raw, receipt = fetch_validated(
        url, policy=policy, resolver=default_resolver, transport=urllib_transport
    )
    records = deduplicate(parse_lookup(args.provider, raw))
    return {
        "provider": args.provider,
        "request_url": url,
        "response_sha256": receipt.sha256,
        "records": records,
    }


def _fetch(args: argparse.Namespace) -> dict[str, object]:
    hosts = frozenset(host.strip().lower() for host in args.allow_host if host.strip())
    if not hosts:
        hosts = _DOCUMENT_HOSTS
    policy = AcquisitionPolicy(allowed_hosts=hosts)
    raw, receipt = fetch_validated(
        args.url, policy=policy, resolver=default_resolver, transport=urllib_transport
    )
    stored = store_object(raw, receipt, Path(args.objects_dir))
    return {
        "final_url": receipt.final_url,
        "media_type": receipt.media_type,
        "byte_count": receipt.byte_count,
        "sha256": receipt.sha256,
        "trust_label": receipt.trust_label,
        **stored,
    }


def _provider_lookup(
    provider: str,
    *,
    query: str | None,
    doi: str | None,
    email: str,
) -> tuple[list[dict[str, object]], str]:
    url = lookup_url(provider, doi=doi, query=query, email=email)
    policy = AcquisitionPolicy(
        allowed_hosts=frozenset({PROVIDER_HOSTS[provider]}),
        allowed_media_types=_METADATA_MEDIA_TYPES,
        max_response_bytes=2 * 1024 * 1024,
    )
    raw, receipt = fetch_validated(
        url, policy=policy, resolver=default_resolver, transport=urllib_transport
    )
    return parse_lookup(provider, raw), receipt.sha256


def _discover(args: argparse.Namespace) -> dict[str, object]:
    return discover(
        args.query,
        budget=DiscoveryBudget(
            max_candidates=args.max_candidates,
            max_full_texts=args.max_full_texts,
        ),
        lookup=lambda provider, query, doi: _provider_lookup(
            provider, query=query, doi=doi, email=args.email
        ),
    )


def _extract(args: argparse.Namespace) -> dict[str, object]:
    object_path = Path(args.object_path)
    raw = object_path.read_bytes()
    artifact = extract_pdf(raw, source_sha256=args.source_sha256)
    stored = store_extraction(artifact, Path(args.extractions_dir))
    return {
        **artifact,
        "artifact_sha256": hashlib.sha256(Path(stored["extraction_path"]).read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="literature-worker")
    commands = parser.add_subparsers(dest="command", required=True)

    lookup = commands.add_parser("lookup", help="metadata lookup on an approved service")
    lookup.add_argument("--provider", required=True, choices=sorted(PROVIDER_HOSTS))
    lookup.add_argument("--doi")
    lookup.add_argument("--query")
    lookup.add_argument("--email", help="required by Unpaywall's usage policy")

    fetch = commands.add_parser("fetch", help="validated open-access document fetch")
    fetch.add_argument("--url", required=True)
    fetch.add_argument("--objects-dir", required=True)
    fetch.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="explicit host allowlist entries (repeatable); defaults to arXiv hosts",
    )

    discovery = commands.add_parser("discover", help="bounded approved-provider discovery")
    discovery.add_argument("--query", required=True)
    discovery.add_argument("--email", required=True, help="Unpaywall contact identifier")
    discovery.add_argument("--max-candidates", type=int, default=20)
    discovery.add_argument("--max-full-texts", type=int, default=5)

    extract = commands.add_parser("extract", help="bounded immutable PDF text extraction")
    extract.add_argument("--object-path", required=True)
    extract.add_argument("--source-sha256", required=True)
    extract.add_argument("--extractions-dir", required=True)

    args = parser.parse_args()
    try:
        if args.command == "lookup":
            result = _lookup(args)
        elif args.command == "fetch":
            result = _fetch(args)
        elif args.command == "discover":
            result = _discover(args)
        else:
            result = _extract(args)
    except (DataError, OSError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
