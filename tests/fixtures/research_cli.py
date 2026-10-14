"""Shared public research CLI invocation for integration and future-poison tests."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from alpha_cli.main import app

runner = CliRunner()


def _invoke(*args: str) -> dict[str, object]:
    result = runner.invoke(app, ["research", *args, "--json"])
    assert result.exit_code == 0, result.output
    value: object = json.loads(result.output)
    assert isinstance(value, dict)
    return value
