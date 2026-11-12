"""Fresh synthetic HTTP/CLI capture, not numerical golden-file acceptance."""

import hashlib
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import capture_c04_risk_basis_fixture as capture
import pytest


@pytest.fixture(scope="module")
def captured() -> tuple[dict[str, Any], dict[str, Any]]:
    return capture.capture_fixture()


def test_capture_is_real_typed_repeatable_and_independently_checked(
    captured: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    fixture, provenance = captured
    again = capture.capture_fixture()
    assert again == captured
    assert set(fixture) == {"later", "loss"}
    assert provenance["producer_version"] == 1
    assert provenance["origin"] == "fresh_synthetic_http_cli_capture_not_historical_recovery"
    assert provenance["random_seed"] is None
    assert provenance["fixture_sha256"] == hashlib.sha256(capture.encode(fixture)).hexdigest()
    assert (
        provenance["producer_sha256"]
        == hashlib.sha256(Path(capture.__file__).read_bytes()).hexdigest()
    )
    assert fixture["later"]["disclosed"]["provenance"]["metric_basis"]["anchor_value"] == 900
    for case, expected_return, expected_drawdown in [("later", 1 / 9, 0), ("loss", 0, -0.1)]:
        pair = fixture[case]
        assert pair["legacy"]["run_id"] == provenance["cases"][case]["run_id"]
        assert (
            pair["legacy"]["provenance"]["source_artifact_sha256"]
            == provenance["cases"][case]["equity_sha256"]
        )
        assert "metric_basis" not in pair["legacy"]["provenance"]
        without = deepcopy(pair["disclosed"])
        del without["provenance"]["metric_basis"]
        assert without == pair["legacy"]
        base = next(row for row in pair["legacy"]["scenarios"] if row["name"] == "base")
        assert base["total_return"] == pytest.approx(expected_return, abs=1e-12, rel=0)
        assert base["max_drawdown"] == pytest.approx(expected_drawdown, abs=1e-12, rel=0)


@pytest.mark.parametrize(
    "mutation",
    [
        "anchor",
        "version",
        "convention",
        "parity",
        "return",
        "drawdown",
        "source_hash",
        "run_id",
        "extra",
        "nonfinite",
        "missing_case",
    ],
)
def test_bad_capture_cannot_publish(
    captured: tuple[dict[str, Any], dict[str, Any]], tmp_path: Path, mutation: str
) -> None:
    fixture, provenance = deepcopy(captured)
    pair = fixture["later"]
    basis = pair["disclosed"]["provenance"]["metric_basis"]
    if mutation == "anchor":
        basis["anchor_value"] = 1000
    elif mutation == "version":
        basis["schema_version"] = True
    elif mutation == "convention":
        basis["initial_capital_status"] = "verified"
    elif mutation == "parity":
        pair["disclosed"]["scenarios"][0]["annual_vol"] += 1
    elif mutation in {"return", "drawdown", "nonfinite"}:
        for report in pair.values():
            base = next(row for row in report["scenarios"] if row["name"] == "base")
            base[
                {"return": "total_return", "drawdown": "max_drawdown", "nonfinite": "annual_vol"}[
                    mutation
                ]
            ] = float("nan") if mutation == "nonfinite" else 0.5
    elif mutation == "source_hash":
        for report in pair.values():
            report["provenance"]["source_artifact_sha256"] = "a" * 64
    elif mutation == "run_id":
        for report in pair.values():
            report["run_id"] = "a" * 16
    elif mutation == "extra":
        pair["legacy"]["extra"] = "unexpected"
    else:
        del fixture["loss"]
    message = {
        "anchor": "metric basis differs",
        "version": "schema_version",
        "convention": "initial_capital_status",
        "parity": "disclosure changes legacy fields",
        "return": "total_return differs from independent",
        "drawdown": "max_drawdown differs from independent",
        "source_hash": "response does not match captured source",
        "run_id": "response does not match captured source",
        "extra": "Extra inputs are not permitted",
        "nonfinite": "Out of range float values",
        "missing_case": "exactly the two documented synthetic cases",
    }[mutation]
    # Prove the actual check fails, independently of the later output-hash check.
    with pytest.raises(ValueError, match=message):
        capture.validate_fixture(fixture, provenance["cases"])
    with pytest.raises(ValueError):
        capture.write_fixture(tmp_path, fixture, provenance)
    assert list(tmp_path.iterdir()) == []


def test_immutable_idempotent_publication_and_provenance(
    captured: tuple[dict[str, Any], dict[str, Any]], tmp_path: Path
) -> None:
    fixture, provenance = captured
    capture.write_fixture(tmp_path, fixture, provenance)
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    capture.write_fixture(tmp_path, fixture, provenance)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == original
    assert json.loads(original[capture.FIXTURE_NAME]) == fixture
    assert json.loads(original[capture.PROVENANCE_NAME]) == provenance
    (tmp_path / capture.PROVENANCE_NAME).write_text("preserve existing evidence")
    with pytest.raises(ValueError, match="existing"):
        capture.write_fixture(tmp_path, fixture, provenance)
    assert (tmp_path / capture.PROVENANCE_NAME).read_text() == "preserve existing evidence"
    assert (tmp_path / capture.FIXTURE_NAME).read_bytes() == original[capture.FIXTURE_NAME]


@pytest.mark.parametrize("text", ['{"x": NaN}', '{"x": Infinity}', '{"x": 1, "x": 2}'])
def test_nonstandard_json_is_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        capture.decode(text)


@pytest.mark.parametrize(
    "field", ["fixture_sha256", "producer_sha256", "producer_version", "inputs"]
)
def test_wrong_provenance_cannot_publish(
    captured: tuple[dict[str, Any], dict[str, Any]], tmp_path: Path, field: str
) -> None:
    fixture, provenance = deepcopy(captured)
    provenance[field] = "wrong"
    with pytest.raises(ValueError, match="provenance"):
        capture.write_fixture(tmp_path, fixture, provenance)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "field", ["execution_fingerprint", "source_fingerprint", "equity_sha256", "run_id"]
)
@pytest.mark.parametrize("missing", [False, True])
def test_forged_or_incomplete_case_records_cannot_publish(
    captured: tuple[dict[str, Any], dict[str, Any]], tmp_path: Path, field: str, missing: bool
) -> None:
    fixture, provenance = deepcopy(captured)
    if missing:
        del provenance["cases"]["later"][field]
    else:
        provenance["cases"]["later"][field] = "a" * 64
    with pytest.raises(ValueError, match="case record"):
        capture.write_fixture(tmp_path, fixture, provenance)
    assert list(tmp_path.iterdir()) == []


def test_dangling_output_link_is_rejected_before_either_write(
    captured: tuple[dict[str, Any], dict[str, Any]], tmp_path: Path
) -> None:
    link = tmp_path / capture.PROVENANCE_NAME
    link.symlink_to(tmp_path / "absent")
    with pytest.raises(ValueError, match="existing"):
        capture.write_fixture(tmp_path, *captured)
    assert link.is_symlink()
    assert not (tmp_path / capture.FIXTURE_NAME).exists()
    assert not (tmp_path / "absent").exists()


def test_isolation_restores_environment_and_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_RANDOM_SEED", "999")
    monkeypatch.setenv("SYNTHETIC_OWNER_CANARY", "must not cross boundary")
    before, cwd = dict(os.environ), Path.cwd()
    with capture.isolated_runtime(tmp_path):
        assert Path.cwd() == tmp_path
        assert Path(os.environ["HOME"]).is_relative_to(tmp_path)
        assert Path(os.environ["ALPHA_DATA_DIR"]).is_relative_to(tmp_path)
        assert os.environ["ALPHA_PAPER_ENABLED"] == "false"
        assert os.environ["ALPHA_IBKR_PAPER_ENABLED"] == "false"
        assert "ALPHA_RANDOM_SEED" not in os.environ
        assert "SYNTHETIC_OWNER_CANARY" not in os.environ
        assert not Path(".env").exists()
    assert dict(os.environ) == before
    assert Path.cwd() == cwd


def test_preloaded_other_checkout_is_rejected_before_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    foreign = ModuleType("alpha_synthetic_foreign")
    foreign.__file__ = str(tmp_path / "foreign.py")
    monkeypatch.setitem(sys.modules, foreign.__name__, foreign)
    with pytest.raises(RuntimeError, match="requires candidate source"):
        capture.capture_fixture()
