"""Every alpha_cli import of a bound module, at module or function level, must be
bound or REVIEWED_OUTSIDE with a reason the daily lane does not run it. Imports
under TYPE_CHECKING do not count. Packages below alpha_cli are outside this test:
the costed profile binds alpha-core, alpha-patterns, alpha-strategies,
alpha-backtest and alpha-data source bytes through hashes.environment. The worker
side is bound by WORKER_FILES, COSTED_FILES and daily_container_entry.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from alpha_cli import _native_rule_environment as environment

ROOT = Path(environment.__file__).parent
REVIEWED_OUTSIDE: dict[tuple[str, str], str] = {
    (
        "_artifacts.py",
        "_native_tearsheet.py",
    ): (
        "Only write_native_tearsheet; daily uses publish_artifact, run_dir, "
        "write_manifest, read_manifest."
    ),
    (
        "_ml_observation_store.py",
        "ml_contract.py",
    ): "W09 types; bound _scope refuses rule and native-owner records.",
    (
        "_ml_observation_store.py",
        "ml_native_plan.py",
    ): "W09 types; bound _scope refuses rule and native-owner records.",
    (
        "control_store.py",
        "ml_native_plan.py",
    ): "W09 types; bound _ml_observation_store._scope refuses rule and native-owner records.",
    (
        "control_store.py",
        "research_readiness.py",
    ): "record_research_decision D2 confirmation branch; daily is D1 discovery only.",
    (
        "_native_fixture_store.py",
        "_native_stock_launch.py",
    ): "Type identity checks; a daily launch is NativeLaunch.",
    (
        "native_supervisor.py",
        "_native_stock_launch.py",
    ): "Type identity checks; a daily launch is NativeLaunch.",
    (
        "_native_rule_artifacts.py",
        "_native_rule_projection.py",
    ): "publish_rule_run returns through publish_daily_rule_run before the synthetic branch.",
    (
        "_native_rule_environment.py",
        "_structural_digest.py",
    ): "The digest binds its own bytes as rules_sha256.",
    ("control_store.py", "_runner.py"): "Strategy candidate freeze and suite results.",
    (
        "control_store.py",
        "research_crypto_binding.py",
    ): "Research D0/D1/D2 evidence; rule contracts return earlier through is_rule_contract.",
    (
        "control_store.py",
        "research_crypto_runtime.py",
    ): "Research D0/D1/D2 evidence; rule contracts return earlier through is_rule_contract.",
    (
        "control_store.py",
        "research_d1.py",
    ): "Research D0/D1/D2 evidence; rule contracts return earlier through is_rule_contract.",
    (
        "control_store.py",
        "research_crypto_d2.py",
    ): "Research D0/D1/D2 evidence; rule contracts return earlier through is_rule_contract.",
    (
        "control_store.py",
        "research_d2.py",
    ): "Research D0/D1/D2 evidence; rule contracts return earlier through is_rule_contract.",
    ("control_store.py", "research_gate_packet.py"): "Strategy promotion packets.",
    ("control_store.py", "study_semantic.py"): "Blind semantic resolver.",
    (
        "control_store.py",
        "research_runtime.py",
    ): (
        "reserve_d0_research_launch calls validate_d0_pilot_contract, handing rules to bound "
        "_native_rule_protocol.validate_rule_contract first; "
        "research approvals bind research_runtime."
    ),
}


def imported_modules(source: str, root: Path = ROOT) -> set[str]:
    """Trace static imports, refusing forms that make the trace incomplete."""
    found: set[str] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.If) and (
            isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
            or isinstance(node.test, ast.Attribute)
            and node.test.attr == "TYPE_CHECKING"
        ):
            for statement in node.orelse:
                visit(statement)
            return
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import cannot be traced"
            module = node.module or ""
            assert module != "importlib" and not module.startswith("importlib."), "dynamic import"
            if module.startswith("alpha_cli."):
                found.add(module.split(".")[1] + ".py")
            elif module == "alpha_cli":
                found.update(
                    item.name + ".py"
                    for item in node.names
                    if (root / (item.name + ".py")).is_file()
                )
        if isinstance(node, ast.Import):
            for item in node.names:
                assert item.name != "importlib" and not item.name.startswith("importlib."), (
                    "dynamic import"
                )
                if item.name.startswith("alpha_cli."):
                    found.add(item.name.split(".")[1] + ".py")
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            assert name not in {"import_module", "__import__"}, "dynamic import"
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(ast.parse(source))
    return found


def _edges() -> set[tuple[str, str]]:
    return {
        (name, target)
        for name in environment.DAILY_GUARD_FILES
        if name.endswith(".py")
        for target in imported_modules((ROOT / name).read_text())
    }


def test_every_daily_import_is_bound_or_reviewed() -> None:
    unbound = {edge for edge in _edges() if edge[1] not in environment.DAILY_GUARD_FILES}
    assert not (unbound - REVIEWED_OUTSIDE.keys()), sorted(unbound - REVIEWED_OUTSIDE.keys())


def test_reviewed_edges_are_live_and_outside() -> None:
    unbound = {edge for edge in _edges() if edge[1] not in environment.DAILY_GUARD_FILES}
    assert not (REVIEWED_OUTSIDE.keys() - unbound), sorted(REVIEWED_OUTSIDE.keys() - unbound)
    assert all(reason.strip() for reason in REVIEWED_OUTSIDE.values())


def test_guard_files_are_unique_regular_non_symlinks() -> None:
    names = environment.DAILY_GUARD_FILES
    assert len(names) == len(set(names))
    assert all((ROOT / name).is_file() and not (ROOT / name).is_symlink() for name in names)


def test_static_trace_handles_scopes_and_type_checking(tmp_path: Path) -> None:
    (tmp_path / "local.py").write_text("")
    assert imported_modules(
        """
from alpha_cli.top.deep import value
import alpha_cli.direct
from alpha_cli import local, absent
if TYPE_CHECKING:
    from alpha_cli.types import Value
else:
    import alpha_cli.runtime
if typing.TYPE_CHECKING:
    import alpha_cli.more_types
else:
    from alpha_cli.fallback import value
def function():
    from alpha_cli.lazy import value
""",
        tmp_path,
    ) == {"top.py", "direct.py", "local.py", "runtime.py", "fallback.py", "lazy.py"}


@pytest.mark.parametrize(
    "source",
    [
        "from . import local",
        "import importlib",
        "from importlib import import_module",
        "import_module('alpha_cli.lazy')",
        "helper.import_module('alpha_cli.lazy')",
        "__import__('alpha_cli.lazy')",
    ],
)
def test_untraceable_imports_fail(source: str) -> None:
    with pytest.raises(AssertionError):
        imported_modules(source)
