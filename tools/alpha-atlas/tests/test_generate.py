"""The pipeline is byte-deterministic and its outputs are internally consistent."""

import json
from pathlib import Path

from alpha_atlas.generate import GRAPH_PATH, INPUTS_PATH, UNKNOWNS_PATH, build_outputs


class TestDeterminism:
    def test_two_runs_are_byte_identical(self, repo_root: Path) -> None:
        first = build_outputs(repo_root)
        second = build_outputs(repo_root)
        assert first == second

    def test_no_timestamps_in_outputs(self, repo_root: Path) -> None:
        outputs = build_outputs(repo_root)
        graph = json.loads(outputs[GRAPH_PATH])
        assert set(graph) == {"schema_version", "inputs_hash", "nodes", "edges", "stats"}

    def test_inputs_hash_binds_the_inputs_file(self, repo_root: Path) -> None:
        import hashlib

        outputs = build_outputs(repo_root)
        graph = json.loads(outputs[GRAPH_PATH])
        digest = hashlib.sha256(outputs[INPUTS_PATH].encode("utf-8")).hexdigest()
        assert graph["inputs_hash"] == digest

    def test_inputs_never_include_generated_outputs(self, repo_root: Path) -> None:
        outputs = build_outputs(repo_root)
        inputs = json.loads(outputs[INPUTS_PATH])
        assert not any(p.startswith("architecture/atlas/generated/") for p in inputs["files"])
        assert not any(p.startswith("docs/atlas/") for p in inputs["files"])


class TestFullResolution:
    def test_unknowns_view_lists_exactly_the_unknown_nodes(self, repo_root: Path) -> None:
        outputs = build_outputs(repo_root)
        view = json.loads(outputs[UNKNOWNS_PATH])
        graph = json.loads(outputs[GRAPH_PATH])
        expected = sorted(n["id"] for n in graph["nodes"] if n["evidence"]["level"] == "unknown")
        assert view["unknown_node_ids"] == expected

    def test_documented_module_reaches_implemented_end_to_end(self, repo_root: Path) -> None:
        outputs = build_outputs(repo_root)
        graph = json.loads(outputs[GRAPH_PATH])
        levels = {n["id"]: n["evidence"]["level"] for n in graph["nodes"]}
        # research_d1.py has a MODULE MAP row and unit tests importing it.
        assert levels["module:alpha_cli.research_d1"] == "tested"
        assert levels["component:alpha-core"] in ("implemented", "connected", "tested")
