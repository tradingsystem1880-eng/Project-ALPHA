"""Command-line entry point for the isolated worker process."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from alpha_qlib_worker.fake import run_fake
from alpha_qlib_worker.real import run_real
from alpha_qlib_worker.tabular import backend_capabilities


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alpha-qlib-worker")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    fake = commands.add_parser("fake")
    fake.add_argument("exchange", type=Path)
    fake.add_argument(
        "--worker-lock",
        type=Path,
        required=True,
        help="uv.lock for the executing isolated worker",
    )
    real = commands.add_parser("real")
    real.add_argument("exchange", type=Path)
    real.add_argument(
        "--worker-lock",
        type=Path,
        required=True,
        help="uv.lock for the executing isolated worker",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "capabilities":
            print(json.dumps(backend_capabilities(), sort_keys=True, allow_nan=False))
        elif args.command == "fake":
            run_fake(args.exchange, worker_lock_path=args.worker_lock)
        else:
            run_real(args.exchange, worker_lock_path=args.worker_lock)
    except Exception as exc:
        print(f"alpha-qlib-worker: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
