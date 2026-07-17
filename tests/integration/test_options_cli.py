"""``alpha options`` — Black-Scholes greeks / implied vol / curve JSON projections."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app

runner = CliRunner()


def test_greeks_json() -> None:
    result = runner.invoke(
        app,
        [
            "options",
            "greeks",
            "100",
            "100",
            "--vol",
            "0.2",
            "--days",
            "365",
            "--rate",
            "0.05",
            "--json",
        ],
    )
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert d["price"] == pytest.approx(10.4506, abs=1e-3)
    assert d["delta"] == pytest.approx(0.6368, abs=1e-3)
    assert d["kind"] == "call"


def test_iv_round_trip() -> None:
    result = runner.invoke(
        app, ["options", "iv", "100", "100", "--price", "10.4506", "--days", "365", "--json"]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["implied_vol"] == pytest.approx(0.2, abs=1e-3)


def test_curve_json() -> None:
    result = runner.invoke(
        app, ["options", "curve", "100", "--vol", "0.2", "--days", "30", "--points", "11", "--json"]
    )
    assert result.exit_code == 0
    points = json.loads(result.stdout)["points"]
    assert len(points) == 11
    assert set(points[0]) == {"spot", "price", "delta", "gamma", "vega", "theta"}


def test_bad_input_fails_loud() -> None:
    result = runner.invoke(app, ["options", "greeks", "100", "100", "--vol", "-0.2", "--json"])
    assert result.exit_code != 0
