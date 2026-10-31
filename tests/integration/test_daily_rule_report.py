"""Read-only report integration from artificial raw data and actual canonical replay.

The publication wrapper is simulated. These tests establish neither native-process
acceptance nor real-market evidence, owner approval, or trading authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alpha_cli._native_daily_rule_artifacts import publish_daily_rule_run
from alpha_cli.artifact_contract import artifact_contract
from alpha_cli.daily_rule_report import daily_rule_evidence
from alpha_cli.main import app
from alpha_core import DataError
from alpha_web.api.models import DailyRuleEvidenceResponse
from alpha_web.app import create_app
from tests.unit.test_native_daily_rule_artifacts import make_daily_fixture


@pytest.fixture
def published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    root, _, contract, receipt = make_daily_fixture(tmp_path, monkeypatch)
    manifest = publish_daily_rule_run(
        root,
        project_id="fixture-project",
        contract_id="rc_fixture",
        contract=contract,
        execution_fingerprint="f" * 64,
        native_receipt=receipt,
        native_receipt_bytes=json.dumps(receipt, sort_keys=True).encode(),
    )
    return root, manifest, receipt


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    assert isinstance(value, dict)
    return value


def _rehash_manifest(root: Path) -> None:
    """Adversarial fixture rewrite: hashes alone must not create semantic authority."""
    manifest = _json(root / "manifest.json")
    manifest["artifacts"] = artifact_contract(root)
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))


def _rehash_projection_and_parent(parent: Path, projection: Path, role: str) -> None:
    _rehash_manifest(projection)
    selectors = _json(parent / "projections.json")
    selectors["roles"][role]["manifest_sha256"] = hashlib.sha256(
        (projection / "manifest.json").read_bytes()
    ).hexdigest()
    (parent / "projections.json").write_text(json.dumps(selectors, sort_keys=True))
    _rehash_manifest(parent)


def test_parent_and_role_selector_reports_agree_with_actual_recorded_results(
    published: tuple[Path, dict[str, Any], dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest, receipt = published
    parent_id = manifest["run_id"]
    before = {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }

    def forbidden_engine(*args: object, **kwargs: object) -> None:
        pytest.fail("read-only report re-executed the numerical engine")

    monkeypatch.setattr("alpha_backtest.engine.run_backtest", forbidden_engine)
    report = daily_rule_evidence(parent_id, data_dir=root, role="control", limit=2)
    assert report["available"] is True
    assert report["outcome"] == receipt["economics"]["outcome"]
    assert report["outcome"] in {"exploratory_complete", "accounting_rejection_inconclusive"}
    assert report["parent_run_id"] == parent_id
    assert report["data_origin"] == "artificial_fixture"
    assert report["provenance"]["point_in_time_claim"] is False
    assert report["provenance"]["scientific_acceptance"] == "not_admitted"
    assert "ARTIFICIAL" in report["watermark"]
    for role in ("baseline", "control"):
        selector = report["selectors"]["roles"][role]
        projection = root / "runs" / selector["run_id"]
        assert (
            selector["manifest_sha256"]
            == hashlib.sha256((projection / "manifest.json").read_bytes()).hexdigest()
        )
        from_role = daily_rule_evidence(selector["run_id"], data_dir=root, role=role, limit=2)
        assert from_role["roles"] == report["roles"]
        assert from_role["parent_run_id"] == parent_id
        actual = receipt["economics"][role]
        summary = report["roles"][role]
        assert summary["final_equity"] == pytest.approx(actual["equity_curve"][-1][1])
        terminal = summary["terminal"]
        assert terminal["valuation_at"] == actual["equity_curve"][-1][0]
        assert (
            terminal["opening_quote_at"]
            == json.loads((root / "runs" / parent_id / "query.json").read_text())["rows"][-1][
                "open_time"
            ]
        )
        assert terminal["final_decision_at"] == actual["decision_trace"][-1]["ts"]
        assert terminal["valuation_basis"] == "last_admitted_open_quote"
        assert terminal["terminal_liquidation"] is False
        assert terminal["terminal_decision"] == "unfilled_without_next_admitted_quote"
        assert summary["fills"] == actual["fills"]
        assert summary["fees_total"] == pytest.approx(
            receipt["economics"]["accounting"][role][-1]["fees_total"]
        )
    assert before == {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    DailyRuleEvidenceResponse.model_validate(report)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    plain = CliRunner().invoke(app, ["report", parent_id])
    assert plain.exit_code == 0, plain.output
    for role in ("baseline", "control"):
        terminal = report["roles"][role]["terminal"]
        assert f"final_equity={report['roles'][role]['final_equity']:.4f}" in plain.output
        assert f"last admitted opening quote {terminal['opening_quote_at']}" in plain.output
        assert f"valuation event {terminal['valuation_at']}" in plain.output
        assert (
            f"Final decision {terminal['final_decision_at']}: no next admitted quote recorded"
            in plain.output
        )
    assert "No forced liquidation" in plain.output
    assert "no next admitted quote" in plain.output
    assert "final-close performance" not in plain.output


def test_accounting_page_is_bounded_and_never_changes_selected_role(
    published: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    root, manifest, receipt = published
    first = daily_rule_evidence(manifest["run_id"], data_dir=root, role="control", limit=2)
    second = daily_rule_evidence(
        manifest["run_id"], data_dir=root, role="control", limit=2, offset=2
    )
    assert first["accounting"]["rows"] == receipt["economics"]["accounting"]["control"][:2]
    assert second["accounting"]["rows"] == receipt["economics"]["accounting"]["control"][2:4]
    assert first["accounting"]["has_more"] is True
    assert first["accounting"]["next_offset"] == 2
    exhausted = daily_rule_evidence(manifest["run_id"], data_dir=root, offset=100000)
    assert exhausted["accounting"]["rows"] == []
    assert exhausted["accounting"]["has_more"] is False
    assert exhausted["roles"] == first["roles"]  # Terminal clocks never use the selected page.


@pytest.mark.parametrize(
    "terminal",
    [
        None,
        {},
        {"valuation_basis": "unknown"},
        {
            "valuation_basis": "last_admitted_open_quote",
            "valuation_at": "2007-04-05T00:00:00.000001+00:00",
            "opening_quote_at": "2007-04-05T00:00:00+00:00",
            "terminal_liquidation": False,
            "terminal_decision": "unfilled_without_next_admitted_quote",
            "final_decision_at": "2007-04-06T00:00:00+00:00",
        },
    ],
)
def test_plain_report_reflects_terminal_provenance_without_inventing_missing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal: object
) -> None:
    import alpha_cli.report_cmds as commands

    monkeypatch.setattr(
        commands,
        "_find_manifest",
        lambda *_: {"command": "research_daily_rule_native_v1", "__dir": str(tmp_path)},
    )
    monkeypatch.setattr(
        "alpha_cli.daily_rule_report.daily_rule_evidence",
        lambda *_args, **_kwargs: {
            "claim_scope": "artificial presentation fixture",
            "data_origin": "artificial_fixture",
            "outcome": None,
            "roles": {
                "baseline": {
                    "run_id": "fixture",
                    "net_pnl": 0,
                    "final_equity": 1000,
                    "fees_total": 0,
                    "fills": 0,
                    "n_trades": 0,
                    "terminal": terminal,
                }
            },
        },
    )
    result = CliRunner().invoke(app, ["report", "fixture"])
    assert result.exit_code == 0, result.output
    assert "final_equity=1000.0000" in result.output
    assert "2022" not in result.output
    if isinstance(terminal, dict) and terminal.get("valuation_at"):
        assert terminal["valuation_at"] in result.output
        assert terminal["opening_quote_at"] in result.output
        assert terminal["final_decision_at"] in result.output
        assert "No forced liquidation" in result.output
        assert ": no next admitted quote recorded; no fill inferred" in result.output
    else:
        assert "not recorded" in result.output
        assert "No forced liquidation" not in result.output
        assert "no fill inferred" not in result.output
        assert "last admitted opening quote" not in result.output


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role": "benchmark"},
        {"limit": 0},
        {"limit": 1001},
        {"limit": True},
        {"offset": -1},
        {"offset": 100001},
        {"offset": True},
    ],
)
def test_reader_rejects_invalid_role_and_page_bounds(
    tmp_path: Path, kwargs: dict[str, Any]
) -> None:
    with pytest.raises(DataError):
        daily_rule_evidence("missing", data_dir=tmp_path, **kwargs)


def test_unrelated_legacy_run_returns_explicit_unavailable(tmp_path: Path) -> None:
    run_id = "a" * 16
    run = tmp_path / "runs" / run_id
    run.mkdir(parents=True)
    (run / "manifest.json").write_text(json.dumps({"run_id": run_id, "command": "backtest_run"}))
    report = daily_rule_evidence(run_id, data_dir=tmp_path)
    assert report["available"] is False
    assert report["roles"] == {}
    assert report["accounting"]["rows"] == []
    DailyRuleEvidenceResponse.model_validate(report)


def test_reader_rejects_rehashed_selector_role_substitution(
    published: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    root, manifest, _ = published
    parent = root / "runs" / manifest["run_id"]
    selectors = _json(parent / "projections.json")
    selectors["roles"]["control"] = selectors["roles"]["baseline"]
    (parent / "projections.json").write_text(json.dumps(selectors))
    _rehash_manifest(parent)
    with pytest.raises(DataError):
        daily_rule_evidence(manifest["run_id"], data_dir=root)


@pytest.mark.parametrize("artifact", ["equity", "lineage", "query"])
def test_reader_rejects_semantic_tampering_even_after_all_local_hashes_are_recomputed(
    published: tuple[Path, dict[str, Any], dict[str, Any]], artifact: str
) -> None:
    root, manifest, _ = published
    parent = root / "runs" / manifest["run_id"]
    selectors = _json(parent / "projections.json")
    projection = root / "runs" / selectors["roles"]["baseline"]["run_id"]
    if artifact == "equity":
        path = projection / "equity_curve.parquet"
        frame = pl.read_parquet(path).with_columns((pl.col("equity") + 100).alias("equity"))
        frame.write_parquet(path)
        _rehash_projection_and_parent(parent, projection, "baseline")
    elif artifact == "lineage":
        path = projection / "lineage.json"
        lineage = _json(path)
        lineage["query_sha256"] = "0" * 64
        path.write_text(json.dumps(lineage))
        _rehash_projection_and_parent(parent, projection, "baseline")
    else:
        path = parent / "query.json"
        query = _json(path)
        query["rows"][0]["close"] += 10
        path.write_text(json.dumps(query))
        _rehash_manifest(parent)
    with pytest.raises(DataError):
        daily_rule_evidence(manifest["run_id"], data_dir=root)


def test_malformed_projection_parent_binding_fails_with_typed_error(
    published: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    root, manifest, _ = published
    parent = root / "runs" / manifest["run_id"]
    selectors = _json(parent / "projections.json")
    projection = root / "runs" / selectors["roles"]["baseline"]["run_id"]
    projected = _json(projection / "manifest.json")
    projected["daily_rule"] = []
    (projection / "manifest.json").write_text(json.dumps(projected))
    _rehash_projection_and_parent(parent, projection, "baseline")
    with pytest.raises(DataError):
        daily_rule_evidence(manifest["run_id"], data_dir=root)


def test_cli_and_api_expose_artificial_exploratory_recorded_evidence(
    published: tuple[Path, dict[str, Any], dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest, _ = published
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    result = CliRunner().invoke(app, ["report", manifest["run_id"]])
    assert result.exit_code == 0, result.output
    assert "ARTIFICIAL FIXTURE / NO MARKET EVIDENCE" in result.stdout
    assert "exploratory_reconstructed_discovery_history" in result.stdout
    assert "baseline:" in result.stdout and "control:" in result.stdout
    # The filesystem observation is an artificial fixture and cannot be inherited
    # by an OS subprocess. Exercise the real CLI JSON handler through an explicit
    # test transport; this does not establish subprocess or durable-host acceptance.
    transported: list[list[str]] = []

    def cli_transport(arguments: list[str], *, data_dir: Path) -> object:
        assert data_dir == root
        assert arguments[:3] == ["report", manifest["run_id"], "--json"]
        transported.append(arguments)
        cli_result = CliRunner().invoke(app, arguments)
        if cli_result.exit_code:
            raise RuntimeError("artificial CLI request was rejected")
        return json.loads(cli_result.stdout)

    monkeypatch.setattr("alpha_web.api.runs._run_json", cli_transport)
    with TestClient(create_app()) as client:
        response = client.get(
            f"/api/runs/{manifest['run_id']}/daily-rule-evidence",
            params={"role": "control", "limit": 2},
        )
        assert response.status_code == 200, response.text
        model = DailyRuleEvidenceResponse.model_validate(response.json())
        assert model.available is True
        assert model.outcome in {"exploratory_complete", "accounting_rejection_inconclusive"}
        assert model.accounting.role == "control"
        assert len(model.accounting.rows) == 2
        assert transported[-1][-6:] == ["--role", "control", "--limit", "2", "--offset", "0"]
        assert (
            client.get(
                f"/api/runs/{manifest['run_id']}/daily-rule-evidence", params={"role": "benchmark"}
            ).status_code
            == 422
        )
        assert (
            client.get(
                f"/api/runs/{manifest['run_id']}/daily-rule-evidence", params={"limit": 0}
            ).status_code
            == 422
        )


@pytest.mark.parametrize("field", ["research_fingerprints", "project_id"])
def test_malformed_parent_semantic_metadata_raises_typed_error(
    published: tuple[Path, dict[str, Any], dict[str, Any]], field: str
) -> None:
    root, manifest, _ = published
    parent = root / "runs" / manifest["run_id"]
    modified = _json(parent / "manifest.json")
    if field == "research_fingerprints":
        modified[field] = []
    else:
        del modified[field]
    (parent / "manifest.json").write_text(json.dumps(modified))
    with pytest.raises(DataError):
        daily_rule_evidence(manifest["run_id"], data_dir=root)


def test_reader_rejects_oversized_run_before_decoding_sidecars(tmp_path: Path) -> None:
    run_id = "b" * 16
    run = tmp_path / "runs" / run_id
    run.mkdir(parents=True)
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "schema_version": 3,
                "command": "research_daily_rule_native_v1",
                "project_id": "artificial-fixture",
                "research_fingerprints": {"code": "c" * 64},
            }
        )
    )
    with (run / "oversized.json").open("wb") as stream:
        stream.truncate(32 * 1024 * 1024 + 1)
    with pytest.raises(DataError, match="artifact bound"):
        daily_rule_evidence(run_id, data_dir=tmp_path)


def test_daily_chart_uses_exact_frozen_snapshot_hash_through_actual_cli(
    published: tuple[Path, dict[str, Any], dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.run_projection import chart_bundle

    root, manifest, _ = published
    selectors = _json(root / "runs" / manifest["run_id"] / "projections.json")
    role_id = selectors["roles"]["baseline"]["run_id"]
    projected = _json(root / "runs" / role_id / "manifest.json")
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    arguments = [
        "data",
        "candles",
        "BTC/USDT",
        "--snapshot",
        projected["snapshot_id"],
        "--expected-snapshot-hash",
        projected["snapshot_hash"],
        "--json",
    ]
    output = CliRunner().invoke(app, arguments)
    assert output.exit_code == 0, output.output
    assert len(json.loads(output.stdout)["bars"]) == 1096
    bundle = chart_bundle(role_id, data_dir=root, limit=10, bar_limit=10)
    assert bundle["bars_status"] == "available"
    assert len(bundle["bars"]) == 10
    assert bundle["provenance"]["snapshot_hash"] == projected["snapshot_hash"]


def test_rehashed_changed_chart_snapshot_never_displays_under_old_report_identity(
    published: tuple[Path, dict[str, Any], dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.run_projection import chart_bundle

    root, manifest, _ = published
    selectors = _json(root / "runs" / manifest["run_id"] / "projections.json")
    role_id = selectors["roles"]["baseline"]["run_id"]
    projected = _json(root / "runs" / role_id / "manifest.json")
    snapshot = root / "snapshots" / projected["snapshot_id"]
    snapshot_manifest = _json(snapshot / "manifest.json")
    member = snapshot_manifest["symbols"]["BTC/USDT"]
    bars_path = snapshot / member["bars_file"]
    frame = pl.read_parquet(bars_path).with_columns(
        *((pl.col(key) + 50).alias(key) for key in ("open", "high", "low", "close"))
    )
    frame.write_parquet(bars_path)
    member["bars_sha256"] = hashlib.sha256(bars_path.read_bytes()).hexdigest()
    (snapshot / "manifest.json").write_text(json.dumps(snapshot_manifest, sort_keys=True))
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    output = CliRunner().invoke(
        app,
        [
            "data",
            "candles",
            "BTC/USDT",
            "--snapshot",
            projected["snapshot_id"],
            "--expected-snapshot-hash",
            projected["snapshot_hash"],
            "--json",
        ],
    )
    assert output.exit_code != 0
    assert "frozen report identity" in output.output
    bundle = chart_bundle(role_id, data_dir=root, limit=10, bar_limit=10)
    assert bundle["bars_status"] == "snapshot_unavailable"
    assert bundle["bars"] == []


@pytest.mark.parametrize("mutation", ["null", "missing"])
def test_daily_chart_without_frozen_hash_never_displays_prices(
    published: tuple[Path, dict[str, Any], dict[str, Any]], mutation: str
) -> None:
    from alpha_cli.run_projection import chart_bundle

    root, manifest, _ = published
    selectors = _json(root / "runs" / manifest["run_id"] / "projections.json")
    role_id = selectors["roles"]["baseline"]["run_id"]
    projected_path = root / "runs" / role_id / "manifest.json"
    projected = _json(projected_path)
    if mutation == "null":
        projected["snapshot_hash"] = None
    else:
        del projected["snapshot_hash"]
    projected_path.write_text(json.dumps(projected))
    # A v3 snapshot selector without its hash is invalid even before candle loading.
    with pytest.raises(DataError, match="snapshot_hash"):
        chart_bundle(role_id, data_dir=root, limit=10, bar_limit=10)


def test_manifest_only_authority_relabeling_is_rejected_before_reader_or_browser_display(
    published: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    import copy
    import os

    from alpha_web import _runs

    root, manifest, _ = published
    run_id = manifest["run_id"]
    parent = root / "runs" / run_id
    path = parent / "manifest.json"
    original = path.read_bytes()
    timestamp = path.stat()
    artifacts = {
        item.name: item.read_bytes()
        for item in parent.iterdir()
        if item.is_file() and item.name != "manifest.json"
    }
    # Prewarm browser caching; preserving mtime must never bypass fresh claim checks.
    assert (
        _runs.run_record("runs", run_id, data_dir=root)["research_gate_watermark"]
        == "ARTIFICIAL FIXTURE / NO MARKET EVIDENCE"
    )
    for mutation in (
        "watermark",
        "gate_watermark",
        "eligibility",
        "places_orders",
        "passed",
        "verdict",
        "promotion_badge",
        "scientific_acceptance",
        "origin_flip",
        "gate_state",
        "context_state",
        "context_project",
    ):
        modified = copy.deepcopy(manifest)
        if mutation == "watermark":
            modified["watermark"] = "SUPPORTED / LIVE READY"
        elif mutation == "gate_watermark":
            modified["research_gate"]["watermark"] = "SUPPORTED / LIVE READY"
        elif mutation == "eligibility":
            modified["eligible_for_holdout_or_execution"] = True
        elif mutation == "places_orders":
            modified["places_orders"] = True
        elif mutation == "passed":
            modified["passed"] = True
        elif mutation == "verdict":
            modified["verdict"] = {"overall": "pass"}
        elif mutation == "promotion_badge":
            modified["paper_ready"] = True
        elif mutation == "scientific_acceptance":
            modified["scientific_acceptance"] = "accepted"
        elif mutation == "origin_flip":
            # Make all manifest-level origin flags consistent. Only immutable study
            # provenance can prevent this manufactured real-market label.
            modified["data_origin"] = "captured_provider_history"
            modified["synthetic"] = False
            modified["real_market_evidence"] = True
            modified["daily_rule"]["data_origin"] = "captured_provider_history"
            modified["research_gate"]["watermark"] = (
                "EXPLORATORY / RECONSTRUCTED DISCOVERY; NOT PROMOTED"
            )
            if "watermark" in modified:
                modified["watermark"] = modified["research_gate"]["watermark"]
        elif mutation == "gate_state":
            modified["research_gate"]["state"] = "confirmed"
        elif mutation == "context_state":
            modified["run_context"]["research_gate_state"] = "completed"
        else:
            modified["run_context"]["project_id"] = "another-project"
        path.write_text(json.dumps(modified))
        os.utime(path, ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns))
        for reader in ("daily", "verified_manifest", "browser_record"):
            with pytest.raises(DataError):
                if reader == "daily":
                    daily_rule_evidence(run_id, data_dir=root)
                elif reader == "verified_manifest":
                    _runs._verified_manifest(parent)
                else:
                    _runs.run_record("runs", run_id, data_dir=root)
        assert artifacts == {
            item.name: item.read_bytes()
            for item in parent.iterdir()
            if item.is_file() and item.name != "manifest.json"
        }
    path.write_bytes(original)
