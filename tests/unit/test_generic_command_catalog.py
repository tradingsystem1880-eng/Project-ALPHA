"""Generic job classification: every served root is classified; nothing real is ``unknown``."""

from __future__ import annotations

import pytest
import typer
from typer.main import get_group

from alpha_cli.catalog import classify_generic_command
from alpha_cli.main import app


def test_empty_generic_command_is_unknown() -> None:
    assert classify_generic_command([]) == "unknown"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["crypto-data", "catalog"], "safe"),
        (["crypto-data", "storage-verify"], "safe"),
        (["crypto-data", "acquire"], "owner_only"),
        (["crypto-data", "asset-master-create"], "owner_only"),
        (["crypto-data"], "owner_only"),
        (["quantpad-data", "verify"], "safe"),
        (["quantpad-data", "archive"], "owner_only"),
        (["provider", "check", "tiingo"], "owner_only"),
        (["strategy-candidate", "paper-preflight"], "safe"),
        (["strategy-candidate", "run"], "empirical"),
        (["chart", "overlays"], "safe"),
        (["rules", "save"], "safe"),
        (["scan", "check"], "safe"),
        (["data", "audit"], "safe"),
        (["data", "repair"], "owner_only"),
        (["paper", "run"], "owner_only"),
    ],
)
def test_roots_classify_by_subcommand(argv: list[str], expected: str) -> None:
    assert classify_generic_command(argv) == expected


def _subcommands(root: str) -> list[str]:
    group = get_group(app)
    sub = group.commands[root]
    return sorted(sub.commands) if isinstance(sub, typer.core.TyperGroup) else []


@pytest.mark.parametrize(
    "root", ["crypto-data", "quantpad-data", "provider", "strategy-candidate", "data", "paper"]
)
def test_every_served_subcommand_of_a_classified_root_is_not_unknown(root: str) -> None:
    """An unlisted verb must fail this test rather than silently classify ``unknown``."""
    names = _subcommands(root)
    assert names, f"{root} serves no subcommands"
    for name in names:
        assert classify_generic_command([root, name]) != "unknown", f"{root} {name}"
