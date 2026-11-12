"""Capture fresh synthetic risk UI inputs through the existing HTTP/CLI path.

Version 1 completes a deferred generated deliverable; it does not recover old bytes.
Only documented anchors, conventions, base return/drawdown and legacy parity are
independent checks. Other scenario numbers are captured UI inputs, not goldens.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from functools import partial
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import polars as pl

    from alpha_cli._identity import RunIdentity

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_NAME = "riskMetricBasis.json"
PROVENANCE_NAME = "riskMetricBasis.provenance.json"
COMMAND = "SYNTHETIC_C04_UI_FIXTURE_V1"
WEALTH = {"later": (900.0, 950.0, 1000.0), "loss": (1000.0, 900.0, 1000.0)}
TIMESTAMPS = tuple(datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(3))
# Closed-form checks from the public C04 contract, never learned from captures.
EXPECTED = {"later": (1 / 9, 0.0), "loss": (0.0, -0.1)}
BASIS = {
    "schema_version": 1,
    "anchor_kind": "first_recorded_equity",
    "anchor_ts": TIMESTAMPS[0].isoformat(),
    "anchor_units": "recorded_equity_units",
    "initial_capital_status": "unknown",
    "external_cash_flow_status": "unknown",
    "return_accumulation": "compounded_simple_returns",
    "drawdown_convention": "non_positive_fraction_from_scenario_wealth_peaks",
    "benchmark_adjustment": "none_by_projection",
    "pre_anchor_losses": "not_measured",
}
SOURCE_PATHS = (
    "scripts/capture_c04_risk_basis_fixture.py",
    "apps/alpha-web/src/alpha_web/_catalog.py",
    "apps/alpha-web/src/alpha_web/_risk.py",
    "apps/alpha-web/src/alpha_web/api/risk.py",
    "apps/alpha-web/src/alpha_web/api/models.py",
)


def encode(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def decode(text: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"nonstandard JSON constant: {value}")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique)


def _case_source(case: str) -> tuple[pl.DataFrame, RunIdentity]:
    import polars as pl

    from alpha_cli import _runner

    inputs = {"wealth": WEALTH[case], "ts": [ts.isoformat() for ts in TIMESTAMPS]}
    frame = pl.DataFrame(
        {"ts": TIMESTAMPS, "equity": WEALTH[case]},
        schema={"ts": pl.Datetime("us", "UTC"), "equity": pl.Float64()},
    )
    identity = _runner.run_identity_for(
        {"command": COMMAND, "case": case, **inputs},
        source_fingerprint=hashlib.sha256(encode(inputs)).hexdigest(),
    )
    return frame, identity


def _case_record(identity: RunIdentity, equity_sha256: str) -> dict[str, str]:
    return {
        "run_id": identity.run_id,
        "equity_sha256": equity_sha256,
        "execution_fingerprint": identity.execution_fingerprint,
        "source_fingerprint": identity.source_fingerprint,
    }


@contextmanager
def isolated_runtime(directory: Path) -> Iterator[None]:
    """Keep .env, stores and caches disposable; restore the caller even on failure."""
    environment, cwd, paths = dict(os.environ), Path.cwd(), sys.path[:]
    bytecode = sys.dont_write_bytecode
    sources = sorted([*ROOT.glob("packages/*/src"), *ROOT.glob("apps/*/src")])
    runtime_bin = Path(sys.executable).parent
    if not (runtime_bin / "alpha").is_file():
        raise RuntimeError("use an existing ALPHA Python environment with its alpha entry point")
    for name in ("home", "cache", "tmp", "data", "bulk"):
        (directory / name).mkdir()
    try:
        os.environ.clear()
        os.environ.update(
            PATH=os.pathsep.join((str(runtime_bin), "/usr/bin", "/bin")),
            PYTHONPATH=os.pathsep.join(str(path) for path in sources),
            HOME=str(directory / "home"),
            XDG_CACHE_HOME=str(directory / "cache"),
            UV_CACHE_DIR=str(directory / "cache"),
            MPLCONFIGDIR=str(directory / "cache"),
            TMPDIR=str(directory / "tmp"),
            TZ="UTC",
            LANG="C.UTF-8",
            PYTHONDONTWRITEBYTECODE="1",
            ALPHA_DATA_DIR=str(directory / "data"),
            ALPHA_BULK_DATA_DIR=str(directory / "bulk"),
            ALPHA_PAPER_ENABLED="false",
            ALPHA_IBKR_PAPER_ENABLED="false",
            ALPHA_FORECAST_LOCAL_ONLY="true",
        )
        sys.path[:0] = [str(path) for path in sources]
        sys.dont_write_bytecode = True
        os.chdir(directory)
        yield
    finally:
        os.chdir(cwd)
        sys.path[:] = paths
        sys.dont_write_bytecode = bytecode
        os.environ.clear()
        os.environ.update(environment)


def validate_fixture(fixture: dict[str, Any], records: dict[str, Any]) -> None:
    from alpha_web.api.models import RiskReport

    encode(fixture)  # Reject non-finite values in every field, including captured metrics.
    if set(fixture) != set(WEALTH) or set(records) != set(WEALTH):
        raise ValueError("fixture must contain exactly the two documented synthetic cases")
    for case, wealth in WEALTH.items():
        pair, record = fixture[case], records[case]
        frame, identity = _case_source(case)
        buffer = io.BytesIO()
        frame.write_parquet(buffer)
        expected_record = _case_record(identity, hashlib.sha256(buffer.getvalue()).hexdigest())
        if record != expected_record:
            raise ValueError("case record differs from fixed inputs and current execution source")
        if set(pair) != {"legacy", "disclosed"}:
            raise ValueError("each case needs legacy and disclosed responses")
        for response in pair.values():
            RiskReport.model_validate(response, strict=True)
            provenance = response["provenance"]
            if (
                response["run_id"] != record["run_id"]
                or provenance["source_run_id"] != record["run_id"]
                or provenance["source_artifact_sha256"] != record["equity_sha256"]
                or provenance["source_command"] != COMMAND
                or provenance["as_of"] != TIMESTAMPS[-1].isoformat()
                or provenance["periods_per_year"] != 252
                or response["confidence"] != 0.95
                or provenance["confidence"] != 0.95
            ):
                raise ValueError("response does not match captured source and request")
        legacy, disclosed = pair["legacy"], deepcopy(pair["disclosed"])
        if "metric_basis" in legacy["provenance"]:
            raise ValueError("legacy response unexpectedly contains metric_basis")
        basis = disclosed["provenance"].pop("metric_basis", None)
        if basis != {**BASIS, "anchor_value": wealth[0]}:
            raise ValueError("metric basis differs from documented synthetic expectations")
        if disclosed != legacy:
            raise ValueError("disclosure changes legacy fields")
        bases = [row for row in legacy["scenarios"] if row["name"] == "base"]
        if len(bases) != 1:
            raise ValueError("expected exactly one base scenario")
        for field, expected in zip(("total_return", "max_drawdown"), EXPECTED[case], strict=True):
            if not math.isclose(bases[0][field], expected, abs_tol=1e-12, rel_tol=0):
                raise ValueError(f"{case} {field} differs from independent closed-form expectation")


def _provenance(fixture: dict[str, Any], records: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "producer": SOURCE_PATHS[0],
        "producer_version": 1,
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "origin": "fresh_synthetic_http_cli_capture_not_historical_recovery",
        "fixture_sha256": hashlib.sha256(encode(fixture)).hexdigest(),
        "random_seed": None,
        "seed_reason": "fixed inputs; existing deterministic scenario projection uses no sampling",
        "inputs": {
            case: {
                "equity": list(wealth),
                "ts": [ts.isoformat() for ts in TIMESTAMPS],
                "declared_starting_cash": 1000.0,
            }
            for case, wealth in WEALTH.items()
        },
        "requests": {
            "method": "GET",
            "path": "/api/risk/scenario",
            "confidence": 0.95,
            "include_metric_basis": [False, True],
        },
        "cases": records,
        "independent_checks": {
            "basis": BASIS,
            "anchors": {case: wealth[0] for case, wealth in WEALTH.items()},
            "base_total_return": {"later": "1000/900 - 1 = 1/9", "loss": "1000/1000 - 1 = 0"},
            "base_max_drawdown": {"later": "0 (monotone path)", "loss": "900/1000 - 1 = -1/10"},
            "numeric_absolute_tolerance": 1e-12,
            "legacy_parity": "all fields equal after removing only disclosed metric_basis",
            "sources": [
                "docs/superpowers/plans/2026-11-08-c04-risk-anchor-disclosure.md",
                "tests/integration/test_c04_risk_anchor_disclosure.py",
                "tests/integration/test_c04_web_metric_basis.py",
            ],
        },
        "scope": (
            "Actual HTTP/CLI payloads are UI test inputs. Other scenario metrics are not "
            "independent numerical oracles; no research, capital/flow verification or "
            "admission is established."
        ),
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCE_PATHS
        },
        "runtime": {
            "python": sys.version.split()[0],
            **{
                name: version(name)
                for name in ("polars", "numpy", "scipy", "pydantic", "fastapi", "httpx")
            },
        },
    }


def capture_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    with (
        tempfile.TemporaryDirectory(prefix="alpha-risk-basis-v1-") as temporary,
        isolated_runtime(Path(temporary)),
    ):
        from fastapi.testclient import TestClient

        from alpha_cli import _artifacts
        from alpha_web.app import create_app

        for name, module in tuple(sys.modules.items()):
            origin = getattr(module, "__file__", None)
            if (
                name.startswith("alpha_")
                and origin
                and not Path(origin).resolve().is_relative_to(ROOT)
            ):
                raise RuntimeError(f"capture requires candidate source, not preloaded {name}")

        records: dict[str, Any] = {}
        fixture: dict[str, Any] = {}
        with TestClient(create_app()) as client:
            for case in WEALTH:
                frame, identity = _case_source(case)
                directory = Path(os.environ["ALPHA_DATA_DIR"]) / "runs" / identity.run_id
                _artifacts.publish_artifact(directory / "equity_curve.parquet", frame.write_parquet)
                _artifacts.write_manifest(
                    directory,
                    {
                        "run_id": identity.run_id,
                        "command": COMMAND,
                        "data_origin": "artificial_fixture",
                        "status": "synthetic_unadmitted",
                        "metadata": {"starting_cash": 1000.0},
                        **identity.manifest_fields(),
                    },
                )
                records[case] = _case_record(
                    identity,
                    hashlib.sha256((directory / "equity_curve.parquet").read_bytes()).hexdigest(),
                )
                fixture[case] = {}
                for mode, include in (("legacy", False), ("disclosed", True)):
                    response = client.get(
                        "/api/risk/scenario",
                        params={
                            "run_id": identity.run_id,
                            "confidence": 0.95,
                            "include_metric_basis": include,
                        },
                    )
                    if response.status_code != 200:
                        raise ValueError(
                            f"synthetic {case}/{mode} capture failed: HTTP {response.status_code}"
                        )
                    fixture[case][mode] = decode(response.text)
        validate_fixture(fixture, records)
        return fixture, _provenance(fixture, records)


def write_fixture(output: Path, fixture: dict[str, Any], provenance: dict[str, Any]) -> None:
    output = output.resolve()
    with (
        tempfile.TemporaryDirectory(prefix="alpha-risk-basis-publish-v1-") as temporary,
        isolated_runtime(Path(temporary)),
    ):
        from alpha_cli._artifacts import publish_artifact

        validate_fixture(fixture, provenance["cases"])
        if provenance != _provenance(fixture, provenance["cases"]):
            raise ValueError("fixture provenance does not match producer, source or output")
        files = {FIXTURE_NAME: encode(fixture), PROVENANCE_NAME: encode(provenance)}
        # Preflight both outputs before writing either; never replace prior evidence.
        for name, raw in files.items():
            path = output / name
            if path.is_symlink() or (
                path.exists() and (not path.is_file() or path.read_bytes() != raw)
            ):
                raise ValueError(f"existing output differs: {path}")
        for name, raw in files.items():
            publish_artifact(output / name, partial(Path.write_bytes, data=raw))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    fixture, provenance = capture_fixture()
    write_fixture(args.output_dir.resolve(), fixture, provenance)
    print(f"Fresh synthetic fixture v1: {provenance['fixture_sha256']}")


if __name__ == "__main__":
    main()
