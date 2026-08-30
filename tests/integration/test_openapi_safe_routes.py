"""Every parameter-free safe route must survive an isolated empty store without 422/5xx."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_web.app import create_app

ROOT = Path(__file__).parents[2]
ROWS = json.loads(
    (ROOT / "docs/governance/openapi-operation-classification.json").read_text(encoding="utf-8")
)["operations"]
AUTOMATIC = [row for row in ROWS if row["mode"] == "automatic"]


@pytest.mark.parametrize("row", AUTOMATIC, ids=lambda row: row["operation_id"])
def test_parameter_free_safe_route_has_no_contract_or_server_error(
    row: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_BULK_DATA_DIR", str(tmp_path / "bulk"))
    # The automatic-route contract test owns an isolated empty configuration; it must not
    # inherit the owner's machine-local Expansion UUID/path from .env.
    monkeypatch.setenv("ALPHA_BULK_VOLUME_UUID", "")
    response = TestClient(create_app()).request(row["method"], row["path"])
    assert response.status_code != 422, (row, response.text)
    assert response.status_code < 500, (row, response.text)
