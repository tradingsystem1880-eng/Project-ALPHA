"""Public worker boundary checks; real pinned imports only in bounded offline children."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from tests.unit._native_stock_test_support import record
from tests.unit.test_native_stock_inspect import REQUEST

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "workers/rdagent"


def entry() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "stock_entry_contract", WORKER / "stock_fixture_entry.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkerEntryTests(unittest.TestCase):
    def test_closed_request_parser_has_no_environment_or_runtime_effect(self) -> None:
        module = entry()
        payload = REQUEST.payload()
        with patch.object(os.environ, "clear", side_effect=AssertionError("parse is pure")):
            self.assertEqual(module.parse_request(json.dumps(payload).encode()), payload)
            for raw in (b"[]", b"null", b'"text"', b'{"x":1,"x":2}', b"x" * 8193):
                with self.subTest(raw_kind=raw[:12]), self.assertRaises(ValueError):
                    module.parse_request(raw)
            for key, value in (
                ("mode", {}),
                ("cpu_milliseconds", True),
                ("loop_steps", 5.0),
                ("job_id", None),
                ("manifest_sha256", "g" * 64),
                ("extra", "invented-dummy-value"),
            ):
                with self.subTest(field=key), self.assertRaises(ValueError) as error:
                    module.parse_request(json.dumps(payload | {key: value}).encode())
                self.assertNotIn("invented-dummy-value", str(error.exception))

    def test_audit_denies_text_and_byte_credential_names_without_opening(self) -> None:
        module = entry()
        for name in (
            "/unopened/.codex/auth.json",
            b"/unopened/.env",
            b"/unopened/.aws/credentials",
        ):
            with (
                self.subTest(path_type=type(name).__name__),
                self.assertRaisesRegex(RuntimeError, "credential read denied"),
            ):
                module.offline("open", (name, "r", 0))

    def test_audit_handles_malformed_argv_and_preserves_metadata_allowlist(self) -> None:
        module = entry()
        for args in (
            (),
            ("unused", None),
            ("unused", [{"bad": 1}]),
            ("unused", "uname -p"),
            ("/unopened/other-executable", ["uname", "-p"]),
            (b"/unopened/other-executable", ["/sbin/ldconfig", "-p"]),
        ):
            with (
                self.subTest(argv_shape=str(type(args[-1]) if args else None)),
                self.assertRaisesRegex(RuntimeError, "external effect denied"),
            ):
                module.offline("subprocess.Popen", args)
        for command in (["uname", "-p"], ("/sbin/ldconfig", "-p")):
            self.assertIsNone(module.offline("subprocess.Popen", (command[0], command, None, None)))

    def test_source_finder_keeps_pinned_namespace_and_normal_imports_separate(self) -> None:
        module = entry()
        finder = module.SourceFinder(Path("/public/pinned-source"))
        package = finder.find_spec("rdagent")
        self.assertEqual(package.submodule_search_locations, ["/public/pinned-source/rdagent"])
        self.assertIsNone(finder.find_spec("unrelated"))
        with patch("importlib.machinery.PathFinder.find_spec", return_value=None) as find:
            self.assertIsNone(finder.find_spec("rdagent.core"))
            find.assert_called_once_with("rdagent.core", ["/public/pinned-source/rdagent"])


NATIVE_BOUNDARY = r"""
import asyncio, hashlib, json, pathlib, sys
from contextlib import redirect_stdout
worker, source, mode = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0,str(worker))
import stock_fixture_entry as entry
from source_pin import verify_source
verify_source(source)
sys.meta_path.insert(0,entry.SourceFinder(source))
sys.addaudithook(entry.offline)
with redirect_stdout(sys.stderr):
    import stock_fixture as stock
    from rdagent.core.proposal import Hypothesis, ExperimentFeedback
    from rdagent.core.experiment import Experiment, Task
    if mode=='missing_guard':
        scenario=stock.SyntheticScenario()
        trace=stock.GuardedTrace(scenario)
        hypothesis=Hypothesis('fixture',*['fixture']*5)
        experiment=Experiment([Task('fixture')],hypothesis=hypothesis)
        feedback=stock.HypothesisFeedback(reason='fixture',decision=False,acceptable=False)
        calls=[lambda:stock.Generator(scenario).gen(trace),
               lambda:stock.Coder(scenario).develop(experiment),
               lambda:stock.Runner(scenario).develop(experiment),
               lambda:stock.Summarizer(scenario).generate_feedback(experiment,trace),
               lambda:trace.sync_dag_parent_and_hist((experiment,feedback),0),
               lambda:trace.sync_dag_parent_and_hist(exp_and_fb=(experiment,feedback),cur_loop_id=0)]
        for call in calls:
            try:call()
            except RuntimeError as error:
                assert str(error)=='stock fixture active guard is unavailable'
            else:raise AssertionError('unguarded component accepted')
        assert stock.ACTIVE.get() is None and experiment.sub_results=={}
        assert experiment.result is None and trace.hist==[]
        assert not pathlib.Path('stock-progress.json').exists()
        result={'status':'guard_denied','callbacks':len(calls),'actual_model_calls':0}
    else:
        assert mode in {'missing_hypothesis','feedback_shape'}
        if mode=='missing_hypothesis':
            original=stock.Converter.convert
            def convert(self,hypothesis,trace):
                experiment=original(self,hypothesis,trace)
                experiment.hypothesis=None
                return experiment
            stock.Converter.convert=convert
        else:
            def feedback(self,experiment,trace,exception=None):
                stock.active_effects().charge('feedback','model')
                return ExperimentFeedback(reason='synthetic malformed fixture',decision=False)
            stock.Summarizer.generate_feedback=feedback
        manifest={name:hashlib.sha256((worker/name).read_bytes()).hexdigest()
                  for name in ('stock_fixture.py','stock_fixture_entry.py','source_pin.py')}
        request=entry.parse_request(json.dumps({'schema':'StockRDLoopFixtureRequestV1',
            'job_id':'fixture','reservation_id':'fixture-reservation','owner_id':'fixture-owner',
            'spec_sha256':'a'*64,'manifest_sha256':stock.digest(manifest),
            'loop_steps':5,'model_calls':2,'tool_calls':2,'cpu_milliseconds':1000,'mode':'resume'}).encode())
        try:asyncio.run(stock.run(request))
        except RuntimeError as error:
            assert str(error)=='stock native result hypothesis or feedback shape differs'
        else:raise AssertionError('malformed native evidence accepted')
        progress=json.loads(pathlib.Path('stock-progress.json').read_text())
        assert progress['state']=='failed' and progress['attempted_stages']==stock.STAGES
        assert not pathlib.Path('stock-receipt.json').exists()
        assert not pathlib.Path('stock-trace.json').exists()
        result={'status':'malformed_result_denied','mode':mode,'actual_model_calls':0,'charged_stages':progress['attempted_stages']}
print(json.dumps(result,sort_keys=True))
"""


@unittest.skipUnless(
    "ALPHA_RDAGENT_SOURCE" in os.environ and "ALPHA_STOCK_PYTHON" in os.environ,
    "explicit installed pinned offline assets required",
)
class NativeWorkerBoundaryTests(unittest.TestCase):
    def run_boundary(self, mode: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory(prefix="alpha-stock-rdloop-") as directory:
            root = Path(directory)
            env = {
                "PATH": os.defpath,
                "LANG": "C.UTF-8",
                "HOME": str(root),
                "TMPDIR": str(root),
                "LOG_TRACE_PATH": str(root / "logs"),
                "ARTIFACT_SIGNING_KEY": "synthetic-public-test-material-0000000000000000",
                "ARTIFACT_SIGNING_KEY_PATH": str(root / "synthetic.key"),
                "LITELLM_LOCAL_MODEL_COST_MAP": "True",
                "HF_HUB_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "STEP_SEMAPHORE": "1",
                "SUBPROC_STEP": "False",
                "ENABLE_MLFLOW": "False",
            }
            result = subprocess.run(
                [
                    os.environ["ALPHA_STOCK_PYTHON"],
                    "-I",
                    "-B",
                    "-c",
                    NATIVE_BOUNDARY,
                    str(WORKER),
                    os.environ["ALPHA_RDAGENT_SOURCE"],
                    mode,
                ],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                timeout=40,
            )
            output = Path(os.environ["ALPHA_STOCK_RECEIPTS"]) / ("worker-boundary-" + mode)
            output.mkdir()
            (output / "stdout.json").write_text(result.stdout)
            (output / "stderr.log").write_text(result.stderr)
            (output / "exit.json").write_text(json.dumps({"exit_code": result.returncode}) + "\n")
            self.assertEqual(result.returncode, 0, result.stderr)
            return record(json.loads(result.stdout))

    def test_native_callbacks_without_context_fail_before_effects(self) -> None:
        result = self.run_boundary("missing_guard")
        self.assertEqual(
            result, {"status": "guard_denied", "callbacks": 6, "actual_model_calls": 0}
        )

    def test_native_missing_hypothesis_cannot_publish_result(self) -> None:
        self.assertEqual(
            self.run_boundary("missing_hypothesis")["status"], "malformed_result_denied"
        )

    def test_native_feedback_shape_cannot_publish_result(self) -> None:
        self.assertEqual(self.run_boundary("feedback_shape")["status"], "malformed_result_denied")
