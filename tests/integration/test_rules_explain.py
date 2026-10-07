"""Real CLI and HTTP explanation relay over isolated canonical bars."""

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_web.app import create_app
from tests.fixtures.cli_fixtures import seed_store

SPEC = {
    "name": "checklist",
    "history": 5,
    "long_when": [{"left": {"source": "close"}, "op": ">", "right": {"value": 1}}],
    "short_when": [],
}
runner = CliRunner()


def seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, n=20)
    saved = runner.invoke(app, ["rules", "save", "checklist", "--spec", json.dumps(SPEC), "--json"])
    assert saved.exit_code == 0, saved.output


def test_explain_cli_matches_scan_and_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed(tmp_path, monkeypatch)
    args = ["rules", "explain", "checklist", "SPY", "--as-of", "2020-01-10", "--json"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["signal"] == 1 and payload["error"] is None
    assert payload["as_of"] == "2020-01-10"
    assert payload["bar_ts"] == 1578614400
    assert payload["conditions"][0]["status"] == "pass"
    assert payload["authority"] == "none"
    saved = runner.invoke(app, ["scan", "save", "scan", "--rules", "checklist", "--symbols", "SPY"])
    assert saved.exit_code == 0, saved.output
    scan = runner.invoke(app, ["scan", "run", "scan", "--as-of", "2020-01-10", "--json"])
    assert scan.exit_code == 0, scan.output
    scan_payload = json.loads(scan.stdout)
    assert scan_payload["rules_sha256"] == payload["rules_sha256"]
    assert scan_payload["rows"][0]["signal"] == payload["signal"]
    assert scan_payload["rows"][0]["bar_ts"] == payload["bar_ts"]
    response = TestClient(create_app()).post(
        "/api/rules/evaluate",
        json={
            "rules_id": "checklist",
            "symbol": "SPY",
            "as_of": "2020-01-10",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == payload


@pytest.mark.parametrize("symbol,as_of", [("MISSING", None), ("SPY", "2020-01-03")])
def test_no_data_or_insufficient_history_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, symbol: str, as_of: str | None
) -> None:
    seed(tmp_path, monkeypatch)
    response = TestClient(create_app()).post(
        "/api/rules/evaluate",
        json={
            "rules_id": "checklist",
            "symbol": symbol,
            "as_of": as_of,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["signal"] is None and payload["error"]
    assert payload["conditions"][0]["status"] == "unavailable"


@pytest.mark.parametrize(
    "extra",
    [
        {"snapshot": "frozen"},
        {"manifest_id": "a" * 64},
        {"run_id": "a" * 16},
        {"as_of": "tomorrow"},
    ],
)
def test_request_rejects_unsupported_context_not_current_store_fallback(
    extra: dict[str, str],
) -> None:
    response = TestClient(create_app()).post(
        "/api/rules/evaluate",
        json={
            "rules_id": "checklist",
            "symbol": "SPY",
            **extra,
        },
    )
    assert response.status_code == 422


def test_unknown_saved_rule_never_becomes_flat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    response = TestClient(create_app()).post(
        "/api/rules/evaluate",
        json={
            "rules_id": "absent",
            "symbol": "SPY",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["signal"] is None
    assert response.json()["rules_sha256"] is None
    assert response.json()["error"]


@pytest.mark.bias_guard
def test_explanation_ignores_future_poison_with_leaky_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polars as pl

    from alpha_cli.rules_cmds import explain_saved_rule
    from alpha_data.store import ParquetStore

    seed(tmp_path, monkeypatch)
    cutoff = date(2020, 1, 10)
    before = explain_saved_rule("checklist", "SPY", data_dir=tmp_path, as_of=cutoff)
    store = ParquetStore(tmp_path / "store")
    frame = store.read_bars("SPY")
    poisoned = frame.with_columns(
        [
            pl.when(pl.col("ts").dt.date() > cutoff)
            .then(pl.lit(9000.0))
            .otherwise(pl.col(name))
            .alias(name)
            for name in ("open", "high", "low", "close")
        ]
    )
    store.write_bars("SPY", poisoned)
    assert explain_saved_rule("checklist", "SPY", data_dir=tmp_path, as_of=cutoff) == before
    leaky = explain_saved_rule("checklist", "SPY", data_dir=tmp_path)
    with pytest.raises(AssertionError):
        assert leaky["conditions"] == before["conditions"]


@pytest.mark.parametrize("as_of", ["20200110", "not-a-date", "2020-02-30"])
def test_cli_rejects_malformed_cutoff(as_of: str) -> None:
    result = runner.invoke(
        app, ["rules", "explain", "checklist", "SPY", "--as-of", as_of, "--json"]
    )
    assert result.exit_code == 2 and "YYYY-MM-DD" in result.output


def test_relay_failure_is_not_a_successful_flat_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    from alpha_web.api import rules as routes

    def failed(*args: object, **kwargs: object) -> None:
        raise RuntimeError("CLI projection timed out")

    monkeypatch.setattr(routes, "_run_json", failed)
    response = TestClient(create_app()).post(
        "/api/rules/evaluate", json={"rules_id": "checklist", "symbol": "SPY"}
    )
    assert response.status_code == 503
