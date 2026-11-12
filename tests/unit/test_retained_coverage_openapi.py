"""Generated production contract for the read-only coverage extension."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_web.app import create_app
from scripts.check_openapi_operations import _classification
from tests.fixtures.retained_coverage_web_fixture import cli


def test_retained_coverage_generated_schema_matches_real_router_and_is_read_only() -> None:
    path = "/api/crypto-data/quality/{manifest_id}/retained-coverage"
    root = Path(__file__).resolve().parents[2]
    spec = json.loads((root / "apps/alpha-web/frontend/openapi.json").read_text())
    actual = create_app().openapi()
    assert spec == actual
    operation = spec["paths"][path]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "RetainedCoverageRequest"
    )
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "RetainedCoverageResponse"
    )
    mode, reason = _classification("POST", path, operation)
    assert mode == "fixture_backed" and "Read-only" in reason and "no acquisition" in reason
    request = spec["components"]["schemas"]["RetainedCoverageRequest"]
    assert request["additionalProperties"] is False
    assert request["properties"]["expected_cadence_seconds"]["const"] == 86400


@pytest.mark.parametrize(
    "args", [["crypto-data", "acquire"], ["provider", "check"], ["data", "pull"]]
)
def test_production_browser_fixture_refuses_effectful_commands_before_root_change(
    tmp_path: Path, args: list[str]
) -> None:
    before = Path.cwd()
    with pytest.raises(ValueError, match="closed read-only"):
        cli(tmp_path, args)
    assert Path.cwd() == before and list(tmp_path.iterdir()) == []
