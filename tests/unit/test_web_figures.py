"""The figure endpoints, with the CLI faked so no real render is spawned.

Two properties matter most here and neither is about pixels: the web process must never
pull matplotlib or the renderer into memory, and a cache hit must not spawn a process.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from alpha_web import _catalog, _figures
from alpha_web.app import create_app

_RUN = "0123456789abcdef"
_KEY_ENVIRONMENT: dict[str, Any] = {
    "renderer_version": 1,
    "matplotlib_version": "3.11.0",
    "theme_id": "alpha-dark",
    "theme_digest": "d" * 64,
    "figures": [
        {
            "figure_id": "equity_underwater",
            "title": "Equity and drawdown",
            "summary": "Growth of one unit of capital, with drawdowns beneath.",
            "section": "performance",
            "panel_count": 2,
            "required_artifacts": ["equity_curve.parquet"],
            "optional_artifacts": [],
            "width_in": 11.0,
            "height_in": 5.0,
            "dpi": 144,
        }
    ],
}


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    data_dir = tmp_path / "data"
    rdir = data_dir / "runs" / _RUN
    rdir.mkdir(parents=True)
    (rdir / "equity_curve.parquet").write_bytes(b"not really parquet")
    (rdir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": _RUN,
                "command": "validate",
                "artifact_contract_version": 3,
                "artifacts": {"equity_curve.parquet": {"sha256": "a" * 64}},
            }
        )
    )
    monkeypatch.setenv("ALPHA_DATA_DIR", str(data_dir))
    _figures.reset_environment_cache()
    yield data_dir
    _figures.reset_environment_cache()


@pytest.fixture
def spawns(monkeypatch: pytest.MonkeyPatch, store: Path) -> list[list[str]]:
    """Replace the CLI with a fake that writes a plausible cache entry."""
    calls: list[list[str]] = []

    def fake(args: list[str], *, data_dir: Path, timeout_seconds: float = 60.0) -> Any:
        calls.append(list(args))
        if args[:2] == ["figures", "list"] and "--run" not in args:
            return _KEY_ENVIRONMENT
        if args[:2] == ["figures", "list"]:
            return {
                "run_id": _RUN,
                "kind": "validate",
                "items": [
                    {
                        "figure_id": "equity_underwater",
                        "title": "Equity and drawdown",
                        "summary": "Growth of one unit of capital.",
                        "section": "performance",
                        "panel_count": 2,
                        "available": True,
                        "unavailable_reason": None,
                    }
                ],
            }
        if args[:2] == ["figures", "render"]:
            figure_id = args[args.index("--figure") + 1]
            fmt = args[args.index("--format") + 1]
            image, sidecar, _ = _figures._cache_entry(_RUN, figure_id, fmt, data_dir)
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'/>")
            sidecar.write_text(
                json.dumps(
                    {
                        "figure_id": figure_id,
                        "title": "Equity and drawdown",
                        "subtitle": "AMZN",
                        "caption": "run 0123456789abcdef",
                        "alt_text": "Growth of one unit of capital.",
                        "x_label": "Date (UTC)",
                        "question": "How did capital grow?",
                        "plain_language_answer": "It grew.",
                        "uncertainty": "One path.",
                        "caveat": "Fees only.",
                        "truncation_note": None,
                        "source_artifacts": ["equity_curve.parquet"],
                        "panels": [
                            {
                                "panel_id": "equity",
                                "y_label": "Growth of 1",
                                "y_unit": "multiple",
                                "note": None,
                                "legend": ["Equity"],
                            }
                        ],
                        "renderer_version": 1,
                        "cache_key": "unused",
                        "format": fmt,
                        "width_in": 11.0,
                        "height_in": 5.0,
                    }
                )
            )
            return {"run_id": _RUN, "figures": [], "skipped": [], "failed": []}
        raise AssertionError(f"unexpected CLI call {args}")

    monkeypatch.setattr(_figures, "_run_json", fake)
    monkeypatch.setattr(_catalog, "_run_json", fake)
    return calls


@pytest.fixture
def client(store: Path, spawns: list[list[str]]) -> TestClient:
    return TestClient(create_app())


def _renders(calls: list[list[str]]) -> int:
    return sum(1 for call in calls if call[:2] == ["figures", "render"])


class TestImage:
    def test_a_miss_renders_once_and_serves_the_bytes(
        self, client: TestClient, spawns: list[list[str]]
    ) -> None:
        response = client.get(f"/api/runs/{_RUN}/figures/equity_underwater/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert _renders(spawns) == 1

    def test_a_hit_spawns_no_process(self, client: TestClient, spawns: list[list[str]]) -> None:
        """The reason the key is computed in-process instead of shelled out for."""
        client.get(f"/api/runs/{_RUN}/figures/equity_underwater/image")
        spawns.clear()
        assert client.get(f"/api/runs/{_RUN}/figures/equity_underwater/image").status_code == 200
        assert _renders(spawns) == 0

    def test_if_none_match_returns_304_without_a_body(self, client: TestClient) -> None:
        first = client.get(f"/api/runs/{_RUN}/figures/equity_underwater/image")
        again = client.get(
            f"/api/runs/{_RUN}/figures/equity_underwater/image",
            headers={"If-None-Match": first.headers["etag"]},
        )
        assert again.status_code == 304
        assert not again.content

    def test_a_pinned_key_is_immutable_and_an_unpinned_one_revalidates(
        self, client: TestClient
    ) -> None:
        meta = client.get(f"/api/runs/{_RUN}/figures/equity_underwater").json()
        pinned = client.get(
            f"/api/runs/{_RUN}/figures/equity_underwater/image", params={"key": meta["cache_key"]}
        )
        plain = client.get(f"/api/runs/{_RUN}/figures/equity_underwater/image")
        assert "immutable" in pinned.headers["cache-control"]
        assert "must-revalidate" in plain.headers["cache-control"]

    def test_a_stale_pinned_key_conflicts_rather_than_silently_serving_other_bytes(
        self, client: TestClient
    ) -> None:
        response = client.get(
            f"/api/runs/{_RUN}/figures/equity_underwater/image", params={"key": "0" * 16}
        )
        assert response.status_code == 409
        assert "current key is" in response.json()["detail"]


class TestErrors:
    def test_an_unknown_run_is_404(self, client: TestClient) -> None:
        assert client.get("/api/runs/ffffffffffffffff/figures").status_code == 404

    def test_a_traversal_figure_id_never_reaches_the_filesystem(self, client: TestClient) -> None:
        response = client.get(f"/api/runs/{_RUN}/figures/..%2F..%2Fetc%2Fpasswd/image")
        assert response.status_code in {404, 422}

    def test_an_unknown_figure_is_refused(self, client: TestClient) -> None:
        assert client.get(f"/api/runs/{_RUN}/figures/no_such_figure/image").status_code == 404


class TestMetadata:
    def test_metadata_carries_the_text_a_screen_reader_needs(self, client: TestClient) -> None:
        """SVG text is glyph outlines, so this JSON is the only accessible copy."""
        document = client.get(f"/api/runs/{_RUN}/figures/equity_underwater").json()
        for field in ("alt_text", "question", "plain_language_answer", "uncertainty", "caveat"):
            assert document[field].strip()
        assert document["image_url"].endswith(document["cache_key"])


def test_the_web_process_never_imports_matplotlib_or_the_renderer() -> None:
    """The architecture's load-bearing claim for this feature, asserted rather than assumed."""
    script = (
        "import sys; import alpha_web.app, alpha_web._figures; "
        "app = alpha_web.app.create_app(); "
        "banned = {'matplotlib', 'alpha_research', 'alpha_research.figures'} & set(sys.modules); "
        "print(sorted(banned))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]", result.stdout
