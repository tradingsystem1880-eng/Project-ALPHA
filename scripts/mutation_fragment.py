"""Pinned mutmut 3 adapter for complete inventories and isolated exact-name fragments."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
import tempfile
from contextlib import chdir
from pathlib import Path
from typing import Any

import gate
import harness_quant

TOOL = "mutmut==3.8.0"
MAX_MUTANTS_PER_FRAGMENT = 96
COUNTS = ("killed", "survived", "timeout", "no_tests", "skipped", "suspicious", "segfault")
STATUSES = {
    1: "killed",
    3: "killed",
    0: "survived",
    5: "no_tests",
    33: "no_tests",
    34: "skipped",
    35: "suspicious",
    36: "timeout",
    -24: "timeout",
    24: "timeout",
    152: "timeout",
    255: "timeout",
    -11: "segfault",
    -9: "segfault",
}


def validate_no_tests_proof(
    proof: Any, source_sha256: str, expected: list[str], config_sha256: str, target: str
) -> None:
    """Accept only successful, fresh collection with no tracer associations."""
    if not isinstance(proof, dict):
        raise ValueError("Missing no-associated-tests certificate")
    durations = proof.get("durations")
    origins = proof.get("import_origins")
    if (
        proof.get("tool") != TOOL
        or proof.get("source_sha256") != source_sha256
        or proof.get("config_sha256") != config_sha256
        or len(config_sha256) != 64
        or proof.get("inventory") != expected
        or type(proof.get("collection_exit")) is not int
        or proof["collection_exit"] != 0
        or proof.get("associations") != {}
        or proof.get("tracer_hits") != []
        or not isinstance(origins, dict)
        or not set(origins) <= {target}
        or any(value != "staged" for value in origins.values())
        or not isinstance(durations, dict)
        or not durations
        or any(
            not isinstance(key, str)
            or not key
            or type(value) not in (int, float)
            or not math.isfinite(value)
            or value < 0
            for key, value in durations.items()
        )
        or sum(durations.values()) <= 0
    ):
        raise ValueError("Invalid no-associated-tests certificate")


class NoAssociatedTests(Exception):
    def __init__(self, proof: dict[str, Any]) -> None:
        self.proof = proof
        super().__init__("Successful collection found no associated tests")


def run_fragment(module: str, expected: list[str], assigned: list[str], workers: int) -> int:
    # Pinned default fork isolation collects in this process. Observe actual tool
    # state; do not catch upstream generic exits or match printed diagnostics.
    from mutmut import __main__ as tool  # type: ignore[import-not-found]
    from mutmut.state import state  # type: ignore[import-not-found]
    from mutmut.workers.isolation import ForkRunner  # type: ignore[import-not-found]

    source_sha = hashlib.sha256(Path(module).read_bytes()).hexdigest()
    config_sha = hashlib.sha256(Path("pyproject.toml").read_bytes()).hexdigest()
    target = module.removeprefix("src/").removesuffix(".py").replace("/", ".")
    original_factory = tool.get_mutant_runner

    def audited_factory(max_workers: int) -> Any:
        runner = original_factory(max_workers)
        if not isinstance(runner, ForkRunner):
            raise ValueError("Certified collection requires pinned default fork isolation")
        original_collect = runner.collect_stats

        def collect(tests: Any) -> int:
            if tests:
                raise ValueError("Certified collection requires complete test selection")
            if state().duration_by_test or state().tests_by_mangled_function_name or state()._stats:
                raise ValueError("Stats collection requires fresh tracer state")
            code = original_collect(tests)
            if type(code) is not int:
                raise ValueError("Malformed stats collection exit code")
            if code == 0 and not state().tests_by_mangled_function_name and not state()._stats:
                origins = {}
                for name, imported in list(sys.modules.items()):
                    if name == target:
                        origin = getattr(imported, "__file__", None)
                        origins[name] = (
                            "staged"
                            if origin
                            and Path(origin).resolve() == (Path("mutants") / module).resolve()
                            else "mismatched"
                        )
                proof = {
                    "tool": TOOL,
                    "source_sha256": source_sha,
                    "config_sha256": config_sha,
                    "inventory": expected,
                    "collection_exit": code,
                    "durations": dict(state().duration_by_test),
                    "associations": {},
                    "tracer_hits": [],
                    "import_origins": origins,
                }
                if hashlib.sha256(Path("pyproject.toml").read_bytes()).hexdigest() != config_sha:
                    raise ValueError("Mutation configuration changed during collection")
                validate_no_tests_proof(proof, source_sha, expected, config_sha, target)
                raise NoAssociatedTests(proof)
            return code

        runner.collect_stats = collect
        return runner

    tool.get_mutant_runner = audited_factory
    try:
        tool._run(assigned, workers)
    except NoAssociatedTests as certified:
        metadata_path = Path(f"mutants/{module}.meta")
        metadata = read_object(metadata_path)
        codes = metadata["exit_code_by_key"]
        if set(codes) != set(expected) or any(value is not None for value in codes.values()):
            raise ValueError(
                "No-tests certificate requires untouched complete metadata"
            ) from certified
        # Same conservative code used by the pinned mutation loop when a mutant
        # has no associated tests. No mutant execution or kill is claimed.
        codes.update(dict.fromkeys(assigned, 33))
        gate.write_json_atomic(metadata_path, metadata)
        gate.write_json_atomic(Path("mutants/no-tests-proof.json"), certified.proof)
        print("Certified successful stats collection: assigned mutants have no associated tests")
    finally:
        tool.get_mutant_runner = original_factory
    return 0


def read_object(path: Path) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate mutation metadata key: {key}")
            result[key] = value
        return result

    result = json.loads(path.read_text(), object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise ValueError("Mutation metadata must be an object")
    return result


def partitions(keys: list[str]) -> list[list[str]]:
    if (
        not keys
        or len(set(keys)) != len(keys)
        or any(
            not isinstance(key, str)
            or "__mutmut_" not in key
            or any(char in key for char in "*?[]")
            for key in keys
        )
    ):
        raise ValueError("Empty, duplicate or non-exact mutant inventory")
    ordered = sorted(keys)
    count = (len(ordered) + MAX_MUTANTS_PER_FRAGMENT - 1) // MAX_MUTANTS_PER_FRAGMENT
    return [ordered[index::count] for index in range(count)]


def generated_keys(module: str, source: str) -> list[str]:
    if importlib.metadata.version("mutmut") != "3.8.0":
        raise ValueError("Mutation generator version mismatch")
    # These are the same generator and path naming APIs used by the pinned CLI.
    # Staged configuration does not restrict covered lines or mutation operators.
    from mutmut.mutation.file_mutation import mutate_file_contents  # type: ignore[import-not-found]
    from mutmut.utils.format_utils import get_mutant_name  # type: ignore[import-not-found]

    generated = mutate_file_contents(module, source, None, None)
    keys = sorted(get_mutant_name(Path(module), name) for name in generated.mutant_names)
    partitions(keys)  # fail loud if generation produced no usable exact identities
    return keys


def fragment_stats(
    codes: dict[str, Any], expected: list[str], assigned: list[str]
) -> dict[str, Any]:
    partitions(expected)
    partitions(assigned)
    if set(codes) != set(expected) or not set(assigned) <= set(expected):
        raise ValueError("Generated mutation inventory mismatch")
    if any(code is not None for key, code in codes.items() if key not in assigned):
        raise ValueError("Unassigned mutant has a stale or duplicated measurement")
    results: dict[str, str] = {}
    for key in assigned:
        code = codes[key]
        if type(code) is not int or code not in STATUSES:
            raise ValueError("Unfinished, interrupted or unknown mutant verdict")
        results[key] = STATUSES[code]
    return {
        **{name: sum(status == name for status in results.values()) for name in COUNTS},
        "total": len(results),
        "check_was_interrupted_by_user": 0,
        "mutant_results": results,
        "mutant_inventory": expected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inventory", "run", "export"])
    parser.add_argument("--output", type=Path, default=Path("mutation-keys.json"))
    parser.add_argument("--module")
    parser.add_argument("--assignment", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.action == "inventory":
        root = gate.repo_root()
        modules = gate.all_quant_source_modules(root)
        # The generator reads mutation patterns from config(). Use the canonical staged
        # config rather than guessing source paths from the workspace layout.
        with tempfile.TemporaryDirectory(prefix="alpha-mutation-inventory-") as directory:
            staging = Path(directory)
            harness_quant.stage_mutation_tree(root, modules, staging)
            with chdir(staging):
                inventories = {
                    module: generated_keys(
                        f"src/{module.partition('/src/')[2]}", (root / module).read_text()
                    )
                    for module in modules
                    if harness_quant.mutation_backend(root / module) == "mutmut"
                }
        gate.write_json_atomic(args.output, inventories)
        return 0
    if args.module is None or args.assignment is None or not 1 <= args.workers <= 2:
        parser.error("module, assignment and bounded workers required")
    assignment = read_object(args.assignment)
    expected, assigned = assignment["expected"], assignment["assigned"]
    if generated_keys(args.module, Path(args.module).read_text()) != expected:
        raise ValueError("Regenerated complete inventory differs from frozen inventory")
    partitions(assigned)
    if not set(assigned) <= set(expected):
        raise ValueError("Assignment outside complete inventory")
    if args.action == "run":
        # Fresh staging and a new cache are mandatory; exact names force measurement.
        if Path("mutants").exists():
            raise ValueError("Mutation fragment requires fresh staging")
        return run_fragment(args.module, expected, assigned, args.workers)
    metadata = read_object(Path(f"mutants/{args.module}.meta"))
    stats = fragment_stats(metadata["exit_code_by_key"], expected, assigned)
    proof_path = Path("mutants/no-tests-proof.json")
    if proof_path.exists():
        proof = read_object(proof_path)
        validate_no_tests_proof(
            proof,
            hashlib.sha256(Path(args.module).read_bytes()).hexdigest(),
            expected,
            hashlib.sha256(Path("pyproject.toml").read_bytes()).hexdigest(),
            args.module.removeprefix("src/").removesuffix(".py").replace("/", "."),
        )
        if stats["no_tests"] != len(assigned):
            raise ValueError("Certified no-tests result contains other verdicts")
        stats["no_tests_proof"] = proof
    gate.write_json_atomic(Path("mutants/mutmut-cicd-stats.json"), stats)
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
