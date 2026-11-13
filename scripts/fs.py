"""The file system's command line: orientation and document search. Read-only; writes stdout.

    uv run python scripts/fs.py orient [--component NAME] [--json]
    uv run python scripts/fs.py search "QUERY" [--kind KIND] [--limit N] [--format text|json]

``orient`` lists components, module counts and the routing documents to read first. ``search``
returns ranked excerpts of tracked documentation (path, heading, line range, kind, and whether
the document is live or archived history), live documents first.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fs_orient
import fs_search


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fs", description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", type=Path, help="ALPHA checkout (default: this script's)")
    sub = parser.add_subparsers(dest="command", required=True)
    orient = sub.add_parser("orient", help="components, module counts and routing documents")
    orient.add_argument("--component", help="list one component's modules")
    orient.add_argument("--json", action="store_true")
    search = sub.add_parser("search", help="ranked excerpts of tracked documentation")
    search.add_argument("query")
    search.add_argument("--kind", choices=fs_search.KINDS, default="all")
    search.add_argument("--limit", type=int, default=8, help="excerpts to show (1-20)")
    search.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root if args.root is not None else Path(__file__).resolve().parents[1]
    try:
        if args.command == "orient":
            payload = fs_orient.orientation(root, component=args.component)
            print(
                json.dumps(payload, sort_keys=True)
                if args.json
                else fs_orient.render_orientation(payload)
            )
        else:
            result = fs_search.search(root, args.query, kind=args.kind, limit=args.limit)
            print(
                json.dumps(result, sort_keys=True, indent=2)
                if args.format == "json"
                else fs_search.render_text(result)
            )
    except (ValueError, OSError) as exc:
        print(f"fs {args.command}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
