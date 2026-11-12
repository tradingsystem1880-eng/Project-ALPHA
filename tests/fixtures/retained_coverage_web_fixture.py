"""Disposable browser/API fixture: actual retained bytes and CLI; no provider or real store.

Synthetic identity/capacity exist only in this explicitly selected test process/CLI child.
They do not weaken or qualify production storage admission.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import tempfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from alpha_data.crypto.contracts import CryptoDatasetIdentityV1
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.storage import Capacity, CryptoBulkStore


def synthetic_store(root: Path) -> CryptoBulkStore:
    return CryptoBulkStore(
        bulk_root=root / "bulk",
        manifest_root=root / "crypto" / "manifests",
        expected_volume_uuid="SYNTHETIC",
        volume_uuid=lambda _: "SYNTHETIC",
        capacity=lambda _: Capacity(total_bytes=2_000_000_000_000, free_bytes=1_500_000_000_000),
    )


def seed(root: Path) -> dict[str, str]:
    import polars as pl

    store = synthetic_store(root)
    store.bulk_root.mkdir(parents=True)
    base_dataset = CryptoDatasetIdentityV1(
        provider="binance",
        venue="binance",
        market_type="spot",
        family="market_bars",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="1d",
        units="provider_native_ohlcv",
        timestamp_convention="interval_start_utc",
    )
    identities = {}
    first = datetime(2024, 1, 1, tzinfo=UTC)
    for name, days in (("gaps", [1, 2]), ("full", [0, 1, 2, 3]), ("conflict", [0, 1, 1, 2, 3])):
        base = {"gaps": "BTC", "full": "ETH", "conflict": "SOL"}[name]
        dataset = replace(base_dataset, instrument=base + "USDT", base_asset=base)
        frame = pl.DataFrame(
            {
                "open_time": [first + timedelta(days=day) for day in days],
                "open": [100.0] * len(days),
                "high": [105.0] * len(days),
                "low": [95.0] * len(days),
                "close": [101.0] * len(days),
                "base_volume": [20.0] * len(days),
                "close_time": [first + timedelta(days=day + 1, milliseconds=-1) for day in days],
                "quote_volume": [2020.0] * len(days),
                "trade_count": list(range(len(days))),
                "taker_buy_base_volume": [10.0] * len(days),
                "taker_buy_quote_volume": [1010.0] * len(days),
            }
        )

        def parse(_: bytes, selected: pl.DataFrame = frame) -> pl.DataFrame:
            return selected

        result = ingest_provider_payload(
            store,
            dataset=dataset,
            payload=("synthetic-" + name).encode(),
            request=(("symbol", dataset.instrument), ("interval", "1d")),
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            provider_schema="synthetic.binance.klines",
            parser_version="synthetic.v1",
            logical_name=name + ".json",
            parser=parse,
            observed_column="open_time",
            key_columns=("open_time",),
            expected_cadence=timedelta(days=1),
            period_start_timestamps=True,
        )
        identities[name] = str(result.normalized_manifest["manifest_id"])
    return identities


def fingerprint(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def install_cli(root: Path) -> None:
    from alpha_cli import crypto_data_cmds

    crypto_data_cmds._bulk_store = lambda: synthetic_store(root)

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("fixture quality must not fetch, acquire or initialize ControlStore")

    for name in (
        "_control_store",
        "_acquire_result",
        "_backfill_acquire",
        "fetch_binance_archive",
        "fetch_binance_checksum",
        "fetch_binance_public_api",
        "fetch_bybit_public",
    ):
        setattr(crypto_data_cmds, name, denied)


# All are existing read-only CLI operations. No provider check/acquire or mutator is allowed.
READ_ONLY_COMMANDS = frozenset(
    {
        ("crypto-data", "quality"),
        ("crypto-data", "coverage"),
        ("crypto-data", "catalog"),
        ("crypto-data", "capabilities"),
        ("crypto-data", "asset-masters"),
        ("crypto-data", "storage"),
        ("crypto-data", "features"),
        ("crypto-data", "profiles"),
        ("crypto-data", "profile-batches"),
        ("info", "strategies"),
        ("info", "commands"),
        ("info", "symbols"),
        ("info", "providers"),
        ("info", "system"),
        ("data", "symbols"),
        ("data", "snapshots"),
        ("project", "list"),
        ("project", "show"),
        ("research", "list"),
        ("research", "status"),
        ("research", "proposal-options"),
    }
)


def cli(root: Path, args: list[str]) -> None:
    if tuple(args[:2]) not in READ_ONLY_COMMANDS and tuple(args[:3]) != (
        "research",
        "data",
        "list",
    ):
        raise ValueError("fixture child permits only closed read-only commands")
    os.environ["ALPHA_DATA_DIR"] = str(root)
    os.chdir(root)
    install_cli(root)
    from alpha_cli.main import app

    app(args=args, prog_name="alpha")


def seed_projects(root: Path) -> dict[str, str]:
    """Create draft-only synthetic cases through the supported store contract, no runs."""
    from alpha_cli.control_store import ControlStore
    from alpha_cli.research_intake import draft_exploration_contract

    store = ControlStore(root)
    result: dict[str, str] = {}
    for key in ("A", "B"):
        idea = (
            f"Synthetic retained BTC data-quality browser fixture {key}; "
            "no scientific or execution claim."
        )
        captured = store.capture_research_case(
            name=f"Synthetic coverage {key}",
            hypothesis=idea,
            falsification_criterion="This disposable UI fixture is never research evidence.",
            draft_payload=draft_exploration_contract(idea),
            created_by="synthetic_fixture",
            next_action="Inspect synthetic retained evidence only; do not launch a study.",
            responsibility="codex",
            at=datetime(2026, 11, 8, tzinfo=UTC),
        )
        project = captured["project"]
        assert isinstance(project, dict)
        result[key] = str(project["project_id"])
    return result


def serve(*, with_projects: bool = False) -> None:
    import uvicorn

    from alpha_web import _catalog
    from alpha_web.app import create_app

    with tempfile.TemporaryDirectory(prefix="alpha-retained-coverage-web-") as directory:
        root = Path(directory)
        ids = seed(root)
        projects = seed_projects(root) if with_projects else {}
        os.environ["ALPHA_DATA_DIR"] = directory
        os.environ["ALPHA_PAPER_ENABLED"] = "false"
        os.environ["ALPHA_IBKR_PAPER_ENABLED"] = "false"
        fixture_script = Path(__file__).resolve()
        commands: list[list[str]] = []
        faults = {"project_inventory_unavailable": False}

        def command(args: list[str]) -> list[str]:
            commands.append(args)
            if faults["project_inventory_unavailable"] and tuple(args[:2]) in {
                ("project", "list"),
                ("research", "list"),
            }:
                raise RuntimeError("SYNTHETIC_PROJECT_INVENTORY_UNAVAILABLE")
            return [sys.executable, str(fixture_script), "cli", directory, *args]

        _catalog._command = command
        original_cwd = Path.cwd()
        os.chdir(root)
        try:
            app = create_app()

            @app.get("/__fixture/retained-coverage", include_in_schema=False)
            def metadata() -> dict[str, object]:
                return {
                    "ids": ids,
                    "fingerprint": fingerprint(root),
                    "synthetic": True,
                    "commands": commands,
                    "projects": projects,
                    "faults": faults,
                    "retained_fingerprint": {
                        key: value
                        for key, value in fingerprint(root).items()
                        if key.startswith(("crypto/", "bulk/"))
                    },
                }

            if with_projects:

                @app.post("/__fixture/project-inventory", include_in_schema=False)
                def project_inventory_fault(unavailable: bool) -> dict[str, bool]:
                    # Test-only in-memory fault; no store records or production routes change.
                    faults["project_inventory_unavailable"] = unavailable
                    return faults

            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(128)
                print(
                    json.dumps(
                        {"port": listener.getsockname()[1], "ids": ids, "projects": projects}
                    ),
                    flush=True,
                )
                uvicorn.Server(uvicorn.Config(app, log_level="error")).run(sockets=[listener])
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    if sys.argv[1] == "cli":
        cli(Path(sys.argv[2]), sys.argv[3:])
    elif sys.argv[1] == "serve":
        serve()
    elif sys.argv[1] == "serve-projects":
        serve(with_projects=True)
    else:
        raise ValueError("unknown fixture mode")
