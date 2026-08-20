"""Read-only backend: excerpt jail first, then graph/node/meta projections."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alpha_atlas.backend.app import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture()
def jailed_client(tmp_path: Path) -> TestClient:
    (tmp_path / "CLAUDE.md").write_text("# fake\n")
    generated = tmp_path / "architecture/atlas/generated"
    generated.mkdir(parents=True)
    graph = {
        "schema_version": 1,
        "inputs_hash": "x",
        "nodes": [],
        "edges": [],
        "stats": {"node_count": 0, "edge_count": 0},
    }
    (generated / "graph.json").write_text(json.dumps(graph))
    (generated / "inputs.json").write_text(json.dumps({"schema_version": 1, "files": {}}))
    (tmp_path / "inside.txt").write_text("hello\n")
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret\n")
    os.symlink(outside, tmp_path / "sneaky.txt")
    return TestClient(create_app(root=tmp_path))


class TestExcerptJail:
    def test_dot_dot_escape_is_rejected(self, jailed_client: TestClient) -> None:
        response = jailed_client.get("/api/excerpt", params={"path": "../outside-secret.txt"})
        assert response.status_code == 403

    def test_symlink_escape_is_rejected(self, jailed_client: TestClient) -> None:
        response = jailed_client.get("/api/excerpt", params={"path": "sneaky.txt"})
        assert response.status_code == 403

    def test_absolute_path_is_rejected(self, jailed_client: TestClient) -> None:
        response = jailed_client.get("/api/excerpt", params={"path": "/etc/hosts"})
        assert response.status_code == 400

    def test_inside_file_is_served(self, jailed_client: TestClient) -> None:
        response = jailed_client.get("/api/excerpt", params={"path": "inside.txt"})
        assert response.status_code == 200
        assert response.json()["lines"] == ["hello"]

    @pytest.mark.parametrize(
        "denied",
        [".env", "data/store/bars.parquet", "tests/holdout/test_hidden.py", ".claude/state/x"],
    )
    def test_denylist(self, client: TestClient, denied: str) -> None:
        response = client.get("/api/excerpt", params={"path": denied})
        assert response.status_code == 403


class TestProjections:
    def test_meta_reports_hash_and_staleness_shape(self, client: TestClient) -> None:
        payload = client.get("/api/meta").json()
        assert payload["schema_version"] == 1
        assert isinstance(payload["stale"], bool)
        assert payload["node_count"] > 400

    def test_graph_roundtrips(self, client: TestClient) -> None:
        payload = client.get("/api/graph").json()
        assert payload["stats"]["node_count"] == len(payload["nodes"])

    def test_node_projection_includes_incident_edges(self, client: TestClient) -> None:
        payload = client.get("/api/node/wf:research.d1").json()
        assert payload["node"]["id"] == "wf:research.d1"
        assert any(e["type"] == "validates" for e in payload["edges"])
        assert payload["neighbors"]

    def test_unknown_node_is_404(self, client: TestClient) -> None:
        assert client.get("/api/node/wf:research.nope").status_code == 404

    def test_excerpt_serves_the_d1_runner(self, client: TestClient) -> None:
        response = client.get(
            "/api/excerpt",
            params={
                "path": "apps/alpha-cli/src/alpha_cli/research_d1.py",
                "start": 1078,
                "end": 1082,
            },
        )
        assert response.status_code == 200
        assert any("def run_deep_research" in line for line in response.json()["lines"])

    def test_excerpt_is_capped_at_400_lines(self, client: TestClient) -> None:
        response = client.get(
            "/api/excerpt",
            params={"path": "apps/alpha-cli/src/alpha_cli/control_store.py", "end": 9000},
        )
        assert response.status_code == 200
        assert len(response.json()["lines"]) <= 400
