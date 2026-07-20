"""Bounded REST cancellation for CLI-owned durable jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from alpha_cli.control_store import ControlStore
from alpha_web.app import create_app


def test_general_durable_job_cancel_route_is_audited_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    store = ControlStore(tmp_path)
    job_id = "99999999-9999-4999-8999-999999999999"
    store.create_job(kind="ml_train", request={"test": "rest cancel"}, job_id=job_id)
    store.set_job_status(job_id, "running")
    client = TestClient(create_app())

    requested = client.delete(f"/api/development/jobs/{job_id}")
    repeated = client.delete(f"/api/v3/development/jobs/{job_id}")

    assert requested.status_code == 200, requested.text
    assert requested.json() == {"job_id": job_id, "status": "cancellation_requested"}
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == {"job_id": job_id, "status": "cancellation_requested"}
    assert store.job_cancellation_requested(job_id) is True
    events = cast(list[dict[str, Any]], store.get_job(job_id)["events"])
    assert sum(event["event_type"] == "cancel_requested" for event in events) == 1


def test_general_durable_job_cancel_route_rejects_unknown_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    response = TestClient(create_app()).delete(
        "/api/development/jobs/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    )
    assert response.status_code == 404
