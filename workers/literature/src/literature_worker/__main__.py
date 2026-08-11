"""Owner-invoked CLI for the isolated literature worker: lookup and fetch, JSON out."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from literature_worker._acquisition import AcquisitionPolicy
from literature_worker._errors import DataError
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

    args = parser.parse_args()
    try:
        result = _lookup(args) if args.command == "lookup" else _fetch(args)
    except DataError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
