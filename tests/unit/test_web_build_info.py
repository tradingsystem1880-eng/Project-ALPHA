"""The health route reports the commit of the built screen and of the running code."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from alpha_web import _build_info
from alpha_web.app import create_app


def test_build_info_is_read_from_the_bundle(tmp_path: Path) -> None:
    (tmp_path / "build-info.json").write_text(
        json.dumps({"commit": "abc123", "built_at": "2026-11-21T10:00:00Z"}), encoding="utf-8"
    )
    assert _build_info.read_build_info(tmp_path) == {
        "build_commit": "abc123",
        "build_time": "2026-11-21T10:00:00Z",
    }


def test_missing_or_broken_build_info_reads_as_unknown(tmp_path: Path) -> None:
    unknown = {"build_commit": "unknown", "build_time": "unknown"}
    assert _build_info.read_build_info(tmp_path) == unknown
    (tmp_path / "build-info.json").write_text("{not json", encoding="utf-8")
    assert _build_info.read_build_info(tmp_path) == unknown


def test_healthz_reports_both_commits() -> None:
    with TestClient(create_app(), base_url="http://localhost:8801") as client:
        body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "code_commit", "build_commit", "build_time"}
