"""Read-only context queries and expiring, replay-verifiable engineering handoffs.

Receipts are derived views, not signed authority, test receipts or scientific context.
The CLI writes only stdout; callers may retain it with existing local task evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from alpha_atlas import context_sources
from alpha_atlas.context_sources import KINDS, Source, read_sources, search_sections
from alpha_atlas.core.paths import find_repo_root


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _clock(now: datetime | None) -> datetime:
    value = datetime.now(UTC) if now is None else now
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("context clock must be timezone-aware")
    return value.astimezone(UTC)


def _bounded_integer(value: int, name: str, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")


def _build(
    sources: dict[str, Source],
    query: str,
    *,
    kind: str,
    limit: int,
    budget_bytes: int,
    ttl_seconds: int,
    created: datetime,
) -> dict[str, Any]:
    _bounded_integer(limit, "limit", 1, 20)
    _bounded_integer(budget_bytes, "budget_bytes", 256, 40_000)
    _bounded_integer(ttl_seconds, "ttl_seconds", 1, 86_400)
    matches = search_sections(sources, query, kind=kind)
    if len(matches) > 500:
        raise ValueError("more than 500 context matches; narrow the query or kind")
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    used = 0
    for row in matches:
        size = len(row.text.encode("utf-8"))
        reason = "result_limit" if len(selected) >= limit else "byte_budget"
        if len(selected) < limit and used + size <= budget_bytes:
            selected.append(asdict(row))
            used += size
        else:
            metadata = asdict(row)
            del metadata["text"]
            excluded.append({**metadata, "reason": reason})
    policy = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in (
            ("context", Path(__file__)),
            ("context_sources", Path(context_sources.__file__)),
        )
    }
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "authority": "none",
        "scope": "tracked engineering documents; source claims require review",
        "query": query,
        "kind": kind,
        "limit": limit,
        "budget_bytes": budget_bytes,
        "ttl_seconds": ttl_seconds,
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(seconds=ttl_seconds)).isoformat(),
        "policy_sha256": _digest(policy),
        "sources": {path: source.sha256 for path, source in sorted(sources.items())},
        "matched_count": len(matches),
        "selected_bytes": used,
        "status": "no_matches"
        if not matches
        else "matches_omitted"
        if excluded
        else "matches_selected",
        "selected": selected,
        "excluded": excluded,
    }
    return {**receipt, "receipt_sha256": _digest(receipt)}


def build_receipt(
    root: Path,
    query: str,
    *,
    kind: str = "all",
    limit: int = 8,
    budget_bytes: int = 12_000,
    ttl_seconds: int = 3_600,
    now: datetime | None = None,
) -> dict[str, Any]:
    return _build(
        read_sources(root),
        query,
        kind=kind,
        limit=limit,
        budget_bytes=budget_bytes,
        ttl_seconds=ttl_seconds,
        created=_clock(now),
    )


def validate_receipt(root: Path, receipt: object, *, now: datetime | None = None) -> None:
    """Reject changed corpus/policy, omission edits, corrupt excerpts and expired handoffs."""
    if (
        not isinstance(receipt, dict)
        or type(receipt.get("schema_version")) is not int
        or receipt.get("schema_version") != 1
    ):
        raise ValueError("invalid context receipt schema")
    try:
        payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if receipt.get("receipt_sha256") != _digest(payload):
            raise ValueError("context receipt digest mismatch")
        created = datetime.fromisoformat(receipt["created_at"])
        expires = datetime.fromisoformat(receipt["expires_at"])
        current = _clock(now)
        if current < _clock(created) or current >= _clock(expires):
            raise ValueError("context receipt expired or clock precedes creation")
        sources = read_sources(root)
        hashes = {path: source.sha256 for path, source in sources.items()}
        if hashes != receipt["sources"]:
            raise ValueError("context sources changed; rerun query before consumption")
        expected = _build(
            sources,
            receipt["query"],
            kind=receipt["kind"],
            limit=receipt["limit"],
            budget_bytes=receipt["budget_bytes"],
            ttl_seconds=receipt["ttl_seconds"],
            created=created,
        )
        if expected != receipt:
            raise ValueError("context policy or query payload changed; rerun query")
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError("context receipt or required source is unavailable/invalid") from exc


def render_markdown(receipt: dict[str, Any]) -> str:
    """Readable output preserves source text verbatim and names every omitted match."""
    lines = [
        f"# Context: {receipt['query']}",
        "",
        f"Authority: none. Status: {receipt['status']}. Expires: {receipt['expires_at']}.",
        f"Receipt: {receipt['receipt_sha256']}",
        "Source claims and contradictions require review; matches do not prove implementation.",
    ]
    for row in receipt["selected"]:
        lines.extend(
            [
                "",
                f"## {row['path']}:{row['start']}-{row['end']} ({row['kind']})",
                f"Heading: {row['heading']}",
                f"Source SHA-256: {row['source_sha256']}",
                "",
                row["text"],
            ]
        )
    if receipt["excluded"]:
        lines.extend(["", "## Omitted matches (review before relying on selected context)", ""])
        lines.extend(
            f"- {row['path']}:{row['start']}-{row['end']}: {row['reason']} ({row['heading']})"
            for row in receipt["excluded"]
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="ALPHA checkout (default: tool's checkout)")
    commands = parser.add_subparsers(dest="command", required=True)
    query = commands.add_parser("query", help="query current tracked source documents")
    query.add_argument("text")
    query.add_argument("--kind", choices=KINDS, default="all")
    query.add_argument("--limit", type=int, default=8)
    query.add_argument("--budget-bytes", type=int, default=12_000)
    query.add_argument("--ttl-seconds", type=int, default=3_600)
    query.add_argument("--format", choices=("json", "markdown", "text"), default="json")
    check = commands.add_parser("check", help="validate a saved JSON receipt without modifying it")
    check.add_argument("receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.root if args.root is not None else find_repo_root(Path(__file__).resolve())
        if args.command == "check":
            if args.receipt.stat().st_size > 2_000_000:
                raise ValueError("context receipt exceeds 2 MB")
            validate_receipt(root, json.loads(args.receipt.read_text(encoding="utf-8")))
            print(json.dumps({"status": "fresh", "authority": "none"}, sort_keys=True))
        else:
            receipt = build_receipt(
                root,
                args.text,
                kind=args.kind,
                limit=args.limit,
                budget_bytes=args.budget_bytes,
                ttl_seconds=args.ttl_seconds,
            )
            print(
                json.dumps(receipt, sort_keys=True, indent=2)
                if args.format == "json"
                else render_markdown(receipt),
                end="\n",
            )
        return 0
    except (ValueError, OSError) as exc:
        print(f"context: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
