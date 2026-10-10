"""Fragment measurements must account for exactly every generated mutant."""

from __future__ import annotations

from pathlib import Path

import pytest
from mutation_fragment import fragment_stats, partitions, read_object


def test_partitions_exhaustive_deterministic_disjoint() -> None:
    keys = [f"pkg.x_f__mutmut_{i}" for i in range(23)]
    parts = partitions(keys)
    assert parts == partitions(list(reversed(keys)))
    assert len(parts) == 4 and max(map(len, parts)) - min(map(len, parts)) <= 1
    assert sorted(key for part in parts for key in part) == sorted(keys)
    assert partitions(keys[:2]) == [[keys[0]], [keys[1]]]


@pytest.mark.parametrize("keys", [[], ["same", "same"], ["pkg.*__mutmut_1"]])
def test_partitions_reject_empty_duplicate_or_pattern_keys(keys: list[str]) -> None:
    with pytest.raises(ValueError):
        partitions(keys)


def test_fragment_counts_preserve_conservative_verdicts() -> None:
    codes = [1, 0, 36, 33, 34, 35, -11, 3]
    keys = [f"pkg.x_f__mutmut_{i}" for i in range(len(codes) + 1)]
    meta = {**dict(zip(keys[:-1], codes, strict=True)), keys[-1]: None}
    result = fragment_stats(meta, keys, keys[:-1])
    assert result["total"] == 8 and result["killed"] == 2
    assert all(
        result[name] == 1
        for name in ("survived", "timeout", "no_tests", "skipped", "suspicious", "segfault")
    )
    assert result["mutant_results"][keys[2]] == "timeout"


@pytest.mark.parametrize("code", [None, 2, 99, True, "1"])
def test_fragment_rejects_unfinished_unknown_or_malformed(code: object) -> None:
    with pytest.raises(ValueError):
        fragment_stats({"pkg.x_f__mutmut_1": code}, ["pkg.x_f__mutmut_1"], ["pkg.x_f__mutmut_1"])


def test_fragment_rejects_changed_inventory_and_stale_unassigned_results() -> None:
    keys = ["pkg.x_f__mutmut_1", "pkg.x_f__mutmut_2"]
    with pytest.raises(ValueError):
        fragment_stats({keys[0]: 1}, keys, keys[:1])
    with pytest.raises(ValueError):
        fragment_stats(dict.fromkeys(keys, 1), keys, keys[:1])


def test_metadata_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"
    path.write_text('{"exit_code_by_key":{"mutant":1,"mutant":null}}')
    with pytest.raises(ValueError, match="Duplicate"):
        read_object(path)


def test_no_associated_tests_certificate_is_conservative() -> None:
    from mutation_fragment import validate_no_tests_proof

    inventory = ["pkg.x_f__mutmut_1"]
    proof = {
        "tool": "mutmut==3.8.0",
        "config_sha256": "c" * 64,
        "source_sha256": "a" * 64,
        "inventory": inventory,
        "collection_exit": 0,
        "durations": {"tests/unit/test_public.py::test_case": 0.1},
        "associations": {},
        "tracer_hits": [],
        "import_origins": {},
    }
    validate_no_tests_proof(proof, "a" * 64, inventory, "c" * 64, "pkg")
    for field, value in (
        ("collection_exit", 1),
        ("durations", {}),
        ("durations", {"test": float("nan")}),
        ("durations", {"test": 0.0}),
        ("associations", {"f": ["test"]}),
        ("tracer_hits", ["wrong.f"]),
        ("source_sha256", "b" * 64),
        ("config_sha256", "d" * 64),
        ("inventory", ["pkg.x_f__mutmut_2"]),
        ("import_origins", {"pkg": "workspace"}),
    ):
        with pytest.raises(ValueError):
            validate_no_tests_proof({**proof, field: value}, "a" * 64, inventory, "c" * 64, "pkg")


@pytest.mark.parametrize(
    "mode", ["certified", "failed", "empty", "stale", "wrong_hits", "wrong_import", "unfinished"]
)
def test_run_fragment_certifies_only_observed_fresh_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    import sys
    from types import ModuleType, SimpleNamespace

    from mutation_fragment import run_fragment

    monkeypatch.chdir(tmp_path)
    source = Path("src/pkg.py")
    source.parent.mkdir()
    source.write_text("def f(): return 1\n")
    Path("pyproject.toml").write_text("[tool.mutmut]\n")
    keys = ["pkg.x_f__mutmut_1", "pkg.x_f__mutmut_2"]
    observed = SimpleNamespace(duration_by_test={}, tests_by_mangled_function_name={}, _stats=set())
    state_module = ModuleType("mutmut.state")
    state_module.__dict__["state"] = lambda: observed
    tool = ModuleType("mutmut.__main__")
    package = ModuleType("mutmut")
    package.__dict__["__main__"] = tool
    monkeypatch.setitem(sys.modules, "mutmut", package)
    monkeypatch.setitem(sys.modules, "mutmut.state", state_module)
    monkeypatch.setitem(sys.modules, "mutmut.__main__", tool)
    imported = ModuleType("pkg")
    imported.__file__ = str(tmp_path / "mutants/src/pkg.py")
    if mode == "wrong_import":
        imported.__file__ = str(source.resolve())
    monkeypatch.setitem(sys.modules, "pkg", imported)

    def collect(_: object) -> int:
        if mode != "empty":
            observed.duration_by_test = {"test_public": 0.1}
        if mode == "wrong_hits":
            observed._stats = {"wrong.f"}
        return 1 if mode == "failed" else 0

    class ForkRunner(SimpleNamespace):
        pass

    isolation = ModuleType("mutmut.workers.isolation")
    isolation.__dict__["ForkRunner"] = ForkRunner
    monkeypatch.setitem(sys.modules, "mutmut.workers.isolation", isolation)
    runner = ForkRunner(collect_stats=collect)

    def factory(_: int) -> SimpleNamespace:
        return runner

    tool.__dict__["get_mutant_runner"] = factory

    def run(_: object, workers: int) -> None:
        meta = Path("mutants/src/pkg.py.meta")
        meta.parent.mkdir(parents=True)
        meta.write_text('{"exit_code_by_key":{"pkg.x_f__mutmut_1":null,"pkg.x_f__mutmut_2":null}}')
        if mode == "unfinished":
            meta.write_text('{"exit_code_by_key":{"pkg.x_f__mutmut_1":1,"pkg.x_f__mutmut_2":null}}')
        if mode == "stale":
            observed.duration_by_test = {"old_test": 0.1}
        tool.__dict__["get_mutant_runner"](workers).collect_stats([])
        raise SystemExit(1)  # Generic upstream failure must never be accepted.

    tool.__dict__["_run"] = run
    if mode == "certified":
        assert run_fragment("src/pkg.py", keys, keys[:1], 2) == 0
        codes = read_object(Path("mutants/src/pkg.py.meta"))["exit_code_by_key"]
        assert codes == {keys[0]: 33, keys[1]: None}
        assert read_object(Path("mutants/no-tests-proof.json"))["durations"] == {"test_public": 0.1}
    else:
        with pytest.raises((ValueError, SystemExit)):
            run_fragment("src/pkg.py", keys, keys[:1], 2)
        assert not Path("mutants/no-tests-proof.json").exists()
    assert tool.__dict__["get_mutant_runner"] is factory
