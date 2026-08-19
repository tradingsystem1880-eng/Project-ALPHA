"""Generic job classification is conservative for absent commands."""

from alpha_cli.catalog import classify_generic_command


def test_empty_generic_command_is_unknown() -> None:
    assert classify_generic_command([]) == "unknown"
