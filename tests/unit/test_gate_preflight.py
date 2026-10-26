"""Synthetic coverage for read-only qualification diagnostics."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import gate
import gate_components
import gate_preflight

QUANT_PATHS = (
    "packages/alpha-validation/src/alpha_validation/synthetic_metric.py",
    "packages/alpha-research/src/alpha_research/synthetic_metric.py",
)
API_OUTPUT = "apps/alpha-web/frontend/src/api/generated.ts"
SPA_OUTPUT = "apps/alpha-web/src/alpha_web/static/app/index.html"
_DEFAULT_BASE = object()


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _synthetic_repo(root: Path) -> Path:
    root.mkdir()
    _git(root, "init", "--quiet")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    paths = set(gate_preflight.EXPECTED_PUBLIC_FILES)
    paths.update(gate.HARNESS_SCRIPTS)
    paths.update(
        {
            "scripts/check_openapi_operations.py",
            "scripts/generate_web_openapi.py",
            "scripts/wheel_smoke.py",
            "tests/unit/test_claude_md_relocation.py",
            "tools/alpha-eval/tests/test_synthetic.py",
            *QUANT_PATHS,
            API_OUTPUT,
            SPA_OUTPUT,
        }
    )
    for rel in paths:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic public fixture\n")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "synthetic")
    return root


def _set_ref(root: Path, name: str = "refs/remotes/origin/main") -> str:
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    _git(root, "update-ref", name, head)
    return head


def _selection(root: Path, base: object = _DEFAULT_BASE) -> dict[str, Any]:
    with patch.dict(os.environ):
        if base is _DEFAULT_BASE:
            os.environ.pop("ALPHA_GATE_BASE", None)
        else:
            os.environ["ALPHA_GATE_BASE"] = str(base)
        return gate_preflight.mutation_selection(root)


def _backend_mutation_targets(root: Path, base: object = _DEFAULT_BASE) -> list[str]:
    with patch.dict(os.environ):
        if base is _DEFAULT_BASE:
            os.environ.pop("ALPHA_GATE_BASE", None)
        else:
            os.environ["ALPHA_GATE_BASE"] = str(base)
        step = next(
            (
                command
                for name, _, command in gate_components.component_steps(root, "backend")
                if name == "mutation gate"
            ),
            None,
        )
        return [] if step is None else step[5:]


class TestGatePreflight(unittest.TestCase):
    def test_manual_size_check_uses_the_shared_limit_at_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CLAUDE.md").write_bytes(b"x" * 3_000)
            (root / "AGENTS.md").write_bytes(b"x" * 3_000)
            self.assertEqual(gate_preflight.manual_size_check(root), (True, 6_000))
            (root / "AGENTS.md").write_bytes(b"x" * 3_001)
            self.assertEqual(gate_preflight.manual_size_check(root), (False, 6_001))

    def test_git_metadata_timeout_returns_a_blocker_instead_of_raising(self) -> None:
        with patch(
            "gate_preflight.subprocess.run",
            side_effect=subprocess.TimeoutExpired("git", timeout=10),
        ):
            result = gate_preflight._git(Path("/synthetic/missing"), "rev-parse", "HEAD")
        self.assertEqual(result.returncode, 127)

    def test_cli_root_timeout_still_emits_valid_blocked_json(self) -> None:
        output = StringIO()
        with (
            patch.object(
                gate,
                "repo_root",
                side_effect=subprocess.TimeoutExpired("git", timeout=10),
            ),
            redirect_stdout(output),
        ):
            self.assertEqual(gate.main(["preflight", "--json"]), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["blockers"], ["candidate_root"])
        self.assertEqual(report["checks"][0]["status"], "blocked")

    def test_sparse_public_prerequisite_is_reported_from_tracked_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            missing_paths = (
                root / ".semgrep" / "fixtures" / "float_contract.py.txt",
                root / ".github" / "workflows" / "nightly.yml",
                root / "pyproject.toml",
                root / "uv.lock",
                root / "tools" / "alpha-eval" / "tests" / "test_synthetic.py",
            )
            for path in missing_paths:
                path.unlink()
            result = gate_preflight.public_prerequisites(root)
            self.assertEqual(result["status"], "blocked")
            self.assertIn(".semgrep/fixtures/float_contract.py.txt", result["missing"])
            self.assertIn(".github/workflows/nightly.yml", result["missing"])
            self.assertIn("pyproject.toml", result["missing"])
            self.assertIn("uv.lock", result["missing"])
            self.assertIn("tools/alpha-eval/tests/test_synthetic.py", result["missing"])
            self.assertGreater(result["tracked_file_count"], 0)

    def test_temporary_and_missing_git_alternates_are_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            temporary_objects = Path(temporary) / "alternate-objects"
            temporary_objects.mkdir()
            alternate_file = Path(_git_path(root, "objects/info/alternates"))
            alternate_file.parent.mkdir(parents=True, exist_ok=True)
            alternate_file.write_text(str(temporary_objects) + "\n")
            result = gate_preflight.git_object_storage(root)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("temporary", result["detail"])

            alternate_file.write_text(str(Path(temporary) / "missing-objects") + "\n")
            result = gate_preflight.git_object_storage(root)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("missing", result["detail"])

            regular_file = Path(temporary) / "not-an-object-directory"
            regular_file.write_text("synthetic\n")
            alternate_file.write_text(str(regular_file) + "\n")
            result = gate_preflight.git_object_storage(root)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("object directories", result["detail"])

            target = Path(temporary) / "alternate-metadata"
            target.write_text(str(temporary_objects) + "\n")
            alternate_file.unlink()
            alternate_file.symlink_to(target)
            result = gate_preflight.git_object_storage(root)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("symlink", result["detail"])

    def test_full_gate_mypy_scope_includes_tests(self) -> None:
        self.assertTrue(gate_preflight.mypy_covers_tests(gate.FULL_GATE_MYPY_COMMAND))
        self.assertFalse(gate_preflight.mypy_covers_tests(("uv", "run", "mypy", "packages")))
        commands = dict(gate.gate_steps("full"))
        self.assertEqual(commands["mypy"], list(gate.FULL_GATE_MYPY_COMMAND))

    def test_candidate_venv_check_reports_missing_and_local_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(gate_preflight.local_venv(root)["status"], "blocked")
            venv = root / ".venv"
            interpreter_rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
            interpreter = venv / interpreter_rel
            interpreter.parent.mkdir(parents=True)
            (venv / "pyvenv.cfg").write_text("home = /usr/bin\n")
            interpreter.write_text("synthetic interpreter\n")
            if os.name != "nt":
                interpreter.chmod(0o755)
            self.assertEqual(gate_preflight.local_venv(root)["status"], "passed")

    def test_mypy_availability_is_checked_without_claiming_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = gate_preflight.local_mypy(root)
            self.assertEqual(result["status"], "blocked")
            executable = root / ".venv" / ("Scripts/mypy.exe" if os.name == "nt" else "bin/mypy")
            executable.parent.mkdir(parents=True)
            executable.write_text("synthetic executable\n")
            if os.name != "nt":
                executable.chmod(0o755)
            self.assertEqual(gate_preflight.local_mypy(root)["status"], "passed")

    def test_cli_parser_exposes_json_preflight(self) -> None:
        args = gate.build_parser().parse_args(["preflight", "--json"])
        self.assertEqual(args.command, "preflight")
        self.assertTrue(args.json)

    def test_atlas_freshness_reuses_component_check_without_uv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seen: dict[str, Any] = {}

            def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                seen["command"] = command
                seen["cwd"] = kwargs["cwd"]
                seen["timeout"] = kwargs["timeout"]
                return subprocess.CompletedProcess(command, 1, "", "stale generated atlas output")

            result = gate_preflight.atlas_freshness(
                root,
                python_executable="/python312",
                python_version=(3, 12),
                runner=runner,
            )
            command = seen["command"]
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["mode"], "executed")
            self.assertEqual(command[0:2], ["/python312", "-B"])
            self.assertNotIn("uv", command)
            self.assertTrue(command[-1] == "--check")
            self.assertEqual(seen["timeout"], 120)
            self.assertEqual(result["issue_type"], "generated_drift")

    def test_explicit_valid_base_reports_exact_changed_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            base = _set_ref(root, "refs/heads/explicit-base")
            changed = root / QUANT_PATHS[0]
            changed.write_text("changed quant module\n")

            result = _selection(root, "explicit-base")

            self.assertEqual(result["base_source"], "environment")
            self.assertEqual(result["requested_ref"], "explicit-base")
            self.assertEqual(result["ref_status"], "available")
            self.assertEqual(result["resolved_ref"], base)
            self.assertEqual(result["merge_base_status"], "available")
            self.assertEqual(result["merge_base"], base)
            self.assertEqual(result["selection_mode"], "exact_diff")
            self.assertEqual(result["selected_target_count"], 1)
            self.assertFalse(result["all_quant_selection"])
            self.assertEqual(result["status"], "passed")
            self.assertEqual(_backend_mutation_targets(root, "explicit-base"), [QUANT_PATHS[0]])

    def test_default_ref_present_can_exactly_select_all_quant_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            base = _set_ref(root)
            for rel in QUANT_PATHS:
                (root / rel).write_text("changed quant module\n")

            result = _selection(root)

            self.assertEqual(result["base_source"], "default")
            self.assertEqual(result["requested_ref"], "origin/main")
            self.assertEqual(result["ref_status"], "available")
            self.assertEqual(result["resolved_ref"], base)
            self.assertEqual(result["selection_mode"], "exact_diff")
            self.assertEqual(result["selected_target_count"], 2)
            self.assertTrue(result["all_quant_selection"])
            self.assertEqual(result["status"], "passed")
            self.assertNotIn("blocks_preflight", result)
            self.assertEqual(set(_backend_mutation_targets(root)), set(QUANT_PATHS))

    def test_missing_default_and_invalid_explicit_refs_report_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            missing_default = _selection(root)
            self.assertEqual(missing_default["base_source"], "default")
            self.assertEqual(missing_default["ref_status"], "unavailable")
            self.assertEqual(missing_default["selection_mode"], "conservative_fallback")
            self.assertEqual(missing_default["selected_target_count"], 2)
            self.assertTrue(missing_default["all_quant_selection"])
            self.assertEqual(missing_default["status"], "warning")
            self.assertEqual(missing_default["warning_type"], "missing_default_base")
            self.assertTrue(missing_default["blocks_preflight"])
            self.assertEqual(set(_backend_mutation_targets(root)), set(QUANT_PATHS))

            invalid_explicit = _selection(root, "does-not-exist")
            self.assertEqual(invalid_explicit["base_source"], "environment")
            self.assertEqual(invalid_explicit["ref_status"], "unavailable")
            self.assertEqual(invalid_explicit["selection_mode"], "conservative_fallback")
            self.assertEqual(invalid_explicit["selected_target_count"], 2)
            self.assertEqual(invalid_explicit["warning_type"], "invalid_explicit_base")

    def test_empty_explicit_base_is_not_replaced_with_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            _set_ref(root)

            result = _selection(root, "")

            self.assertEqual(result["base_source"], "environment")
            self.assertEqual(result["requested_ref"], "")
            self.assertEqual(result["ref_status"], "unavailable")
            self.assertEqual(result["selection_mode"], "conservative_fallback")
            self.assertEqual(result["selected_target_count"], 2)
            self.assertEqual(result["warning_type"], "invalid_explicit_base")

    def test_mutation_selection_timeout_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            failed = subprocess.CompletedProcess(["git"], 127, "", "TimeoutExpired")
            with patch.object(gate_preflight, "_git", return_value=failed):
                result = _selection(root, "explicit-base")
            self.assertEqual(result["status"], "unverified")
            self.assertEqual(result["selection_mode"], "unknown")
            self.assertIsNone(result["selected_target_count"])
            self.assertEqual(result["ref_status"], "unknown")

    def test_freshness_index_alignment_distinguishes_unstaged_from_staged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            self.assertEqual(gate_preflight.freshness_index_alignment(root)["status"], "passed")

            api_output = root / API_OUTPUT
            api_output.write_text("intended generated candidate\n")
            unstaged = gate_preflight.freshness_index_alignment(root)
            self.assertEqual(unstaged["status"], "warning")
            self.assertEqual(unstaged["issue_type"], "index_setup")
            self.assertTrue(unstaged["blocks_preflight"])
            self.assertIn(API_OUTPUT, unstaged["changed_paths"])
            self.assertIn("not evidence of stale generated output", unstaged["detail"])

            _git(root, "add", API_OUTPUT)
            staged = gate_preflight.freshness_index_alignment(root)
            self.assertEqual(staged["status"], "passed")
            self.assertEqual(staged["changed_paths"], [])

            api_output.write_text("further unstaged candidate change\n")
            unstaged_after_stage = gate_preflight.freshness_index_alignment(root)
            self.assertEqual(unstaged_after_stage["status"], "warning")
            self.assertEqual(unstaged_after_stage["issue_type"], "index_setup")

    def test_freshness_index_alignment_blocks_sparse_skip_worktree_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for name, rel in (("api", API_OUTPUT), ("spa", SPA_OUTPUT)):
                with self.subTest(name=name):
                    root = _synthetic_repo(base / name)
                    _git(root, "update-index", "--skip-worktree", "--", rel)
                    (root / rel).unlink()

                    result = gate_preflight.freshness_index_alignment(root)

                    self.assertEqual(result["status"], "blocked")
                    self.assertEqual(result["issue_type"], "missing_freshness_target")
                    self.assertEqual(result["missing_paths"], [rel])

    def test_freshness_index_alignment_requires_both_canonical_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            api_cwd = root / "apps/alpha-web/frontend"
            only_api = [
                (
                    "API freshness",
                    api_cwd,
                    ["git", "diff", "--exit-code", "--", "src/api/generated.ts"],
                )
            ]
            with patch.object(gate_components, "component_steps", return_value=only_api):
                result = gate_preflight.freshness_index_alignment(root)

            self.assertEqual(result["status"], "unverified")
            self.assertEqual(result["issue_type"], "freshness_scope_unknown")
            self.assertEqual(result["missing_steps"], ["SPA freshness"])

    def test_actual_atlas_staleness_is_generated_drift_not_index_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")

            def stale_runner(
                command: list[str], **kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(command, 1, "", "stale generated atlas output")

            alignment = gate_preflight.freshness_index_alignment(root)
            stale = gate_preflight.atlas_freshness(
                root,
                python_executable="/python312",
                python_version=(3, 12),
                runner=stale_runner,
            )
            self.assertEqual(alignment["status"], "passed")
            self.assertEqual(stale["status"], "blocked")
            self.assertEqual(stale["issue_type"], "generated_drift")
            self.assertNotEqual(stale["issue_type"], alignment.get("issue_type"))

    def test_atlas_missing_interpreter_is_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def missing_runner(
                command: list[str], **kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                raise FileNotFoundError(command[0])

            result = gate_preflight.atlas_freshness(
                root,
                python_executable="/missing/python312",
                python_version=(3, 12),
                runner=missing_runner,
            )
            self.assertEqual(result["status"], "unverified")
            self.assertEqual(result["mode"], "executed")

    def test_preflight_reports_scope_without_claiming_mypy_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            with (
                patch.object(gate, "lint_harness", return_value=[]),
                patch.object(
                    gate_preflight,
                    "atlas_freshness",
                    return_value={
                        "name": "atlas_freshness",
                        "mode": "executed",
                        "status": "passed",
                        "detail": "fresh",
                    },
                ),
                patch("shutil.which", return_value="/usr/bin/uv"),
                patch.object(gate_preflight, "python_312_available", return_value=True),
            ):
                _, report = gate_preflight.run_preflight(root)
            checks = {check["name"]: check for check in report["checks"]}
            self.assertEqual(checks["full_gate_mypy_scope"]["mode"], "scope_only")
            self.assertEqual(checks["full_gate_mypy_scope"]["status"], "scope_only")
            self.assertEqual(checks["full_gate_mypy_execution"]["mode"], "not_run")
            self.assertEqual(checks["full_gate_mypy_execution"]["status"], "not_run")
            self.assertEqual(checks["candidate_mypy"]["status"], "blocked")
            self.assertNotEqual(checks["full_gate_mypy_scope"]["status"], "passed")
            self.assertNotEqual(checks["full_gate_mypy_execution"]["status"], "passed")
            rendered = gate_preflight.render_report(report)
            self.assertIn("SCOPE_ONLY [SCOPE_ONLY]: full_gate_mypy_scope", rendered)
            self.assertIn("NOT_RUN [NOT_RUN]: full_gate_mypy_execution", rendered)
            self.assertEqual(json.loads(json.dumps(report)), report)
            output = StringIO()
            with (
                patch.object(gate, "repo_root", return_value=root),
                patch.object(gate_preflight, "run_preflight", return_value=(0, report)),
                redirect_stdout(output),
            ):
                self.assertEqual(gate.main(["preflight", "--json"]), 0)
            emitted = json.loads(output.getvalue())
            emitted_checks = {check["name"]: check for check in emitted["checks"]}
            self.assertEqual(emitted_checks["candidate_mypy"]["status"], "blocked")
            self.assertEqual(emitted_checks["full_gate_mypy_scope"]["status"], "scope_only")
            self.assertEqual(emitted_checks["full_gate_mypy_execution"]["status"], "not_run")

    def test_preflight_json_separates_base_fallback_from_index_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            (root / API_OUTPUT).write_text("intended generated output\n")
            with (
                patch.dict(os.environ),
                patch.object(gate, "lint_harness", return_value=[]),
                patch.object(
                    gate_preflight,
                    "atlas_freshness",
                    return_value={
                        "name": "atlas_freshness",
                        "mode": "executed",
                        "status": "passed",
                        "detail": "fresh",
                    },
                ),
                patch("shutil.which", return_value="/usr/bin/uv"),
                patch.object(gate_preflight, "python_312_available", return_value=True),
            ):
                os.environ.pop("ALPHA_GATE_BASE", None)
                code, report = gate_preflight.run_preflight(root)

            checks = {check["name"]: check for check in report["checks"]}
            selection = checks["mutation_selection"]
            alignment = checks["freshness_index_alignment"]
            self.assertEqual(code, 1)
            self.assertEqual(selection["status"], "warning")
            self.assertEqual(selection["selection_mode"], "conservative_fallback")
            self.assertEqual(selection["warning_type"], "missing_default_base")
            self.assertEqual(alignment["status"], "warning")
            self.assertEqual(alignment["issue_type"], "index_setup")
            warnings = {warning["name"]: warning for warning in report["warnings"]}
            self.assertEqual(warnings["mutation_selection"]["issue_type"], "missing_default_base")
            self.assertEqual(warnings["freshness_index_alignment"]["issue_type"], "index_setup")
            self.assertIn("mutation_selection", report["blockers"])
            self.assertIn("freshness_index_alignment", report["blockers"])

    def test_preflight_report_is_json_serializable_and_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _synthetic_repo(Path(temporary) / "repo")
            before = sorted(
                (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
                for path in root.rglob("*")
                if path.is_file()
            )
            with (
                patch.object(gate, "lint_harness", return_value=[]),
                patch.object(
                    gate_preflight,
                    "atlas_freshness",
                    return_value={"name": "atlas_freshness", "status": "passed", "detail": "fresh"},
                ),
                patch("shutil.which", return_value="/usr/bin/uv"),
                patch.object(gate_preflight, "python_312_available", return_value=True),
            ):
                code, report = gate_preflight.run_preflight(root)
            self.assertEqual(code, 1)
            after = sorted(
                (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
                for path in root.rglob("*")
                if path.is_file()
            )
            self.assertEqual(before, after)
            json.dumps(report)
            self.assertIn("candidate", report)
            self.assertIn("resources", report)
            self.assertTrue(report["blockers"])

    def test_missing_candidate_and_unavailable_tools_return_json_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "missing"
            with (
                patch.object(gate, "lint_harness", return_value=["baseline missing"]),
                patch.object(
                    gate_preflight,
                    "atlas_freshness",
                    return_value={
                        "name": "atlas_freshness",
                        "mode": "executed",
                        "status": "unverified",
                        "detail": "Python unavailable",
                    },
                ),
                patch("shutil.which", return_value=None),
                patch.object(gate_preflight, "python_312_available", return_value=False),
            ):
                code, report = gate_preflight.run_preflight(root)
            self.assertEqual(code, 1)
            self.assertIn("uv", report["blockers"])
            self.assertIn("candidate_mypy", report["blockers"])
            self.assertIn("frontend_tools", report["blockers"])
            self.assertIn("atlas_freshness", report["blockers"])
            self.assertIsNone(report["resources"]["disk_free_bytes"])
            parsed = json.loads(json.dumps(report))
            self.assertEqual(parsed["candidate"]["root"], str(root.resolve()))


def _git_path(root: Path, path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-path", path],
        check=True,
        capture_output=True,
        text=True,
    )
    value = Path(result.stdout.strip())
    return str(value if value.is_absolute() else root / value)


if __name__ == "__main__":
    unittest.main()
