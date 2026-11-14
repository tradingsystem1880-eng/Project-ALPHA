"""RD-Agent extension classes: ALPHA measures factors and owns the search decision."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from rdagent.core.developer import Developer
from rdagent.core.exception import FactorEmptyError
from rdagent.core.proposal import Experiment2Feedback, HypothesisFeedback
from rdagent.oai.llm_utils import APIBackend
from rdagent.scenarios.qlib.experiment.factor_experiment import QlibFactorScenario
from rdagent.scenarios.qlib.experiment.quant_experiment import QlibQuantScenario
from rdagent.scenarios.qlib.proposal.factor_proposal import QlibFactorHypothesisGen
from rdagent.utils import convert2bool
from rdagent.utils.agent.tpl import T

from alpha_factor_data import check_prefix_invariance

LEGACY_KEYS = ["IC"] + [
    f"1day.excess_return_{cost}_cost.{metric}"
    for cost in ("without", "with")
    for metric in ("annualized_return", "max_drawdown")
]


class AlphaFactorScenario(QlibFactorScenario):
    def get_runtime_environment(self) -> str:
        # Upstream runs `python runtime_info.py` through a conda-derived PATH; without conda that
        # PATH has no `python`. Run RD-Agent's own probe with the factor runtime's interpreter.
        import rdagent.scenarios.shared.get_runtime_info as info

        script = Path(info.__file__).with_name("runtime_info.py")
        result = subprocess.run(
            [os.environ["FACTOR_CoSTEER_python_bin"], str(script)],  # noqa: SIM112
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
        if match is None:
            raise ValueError("RD-Agent runtime probe printed no JSON")
        return json.dumps(json.loads(match.group()), indent=2)

    @property
    def simulator(self) -> str:
        return (
            "A factor is judged by ALPHA's rank IC with inference and a cost-aware replay; there "
            "is no Qlib model. Decide at the close of UTC day d, fill at open d+1, exit at open "
            "d+2. ALPHA canonical synchronized long-only replay (not Nautilus), top third equal "
            "weighted, against the equal-weight basket; 10 bps fee plus 6 bps slippage per side, "
            "365 days/year. Direction chosen in-sample. BH q < 0.10 screens the cross-run trial "
            "ledger; only screened factors are replayed. Positive net excess makes an exploratory "
            "candidate, never admission, evidence, approval or promotion."
        )

    @property
    def experiment_setting(self) -> str:
        return (
            "15 surviving Binance USDT spot coins, daily bars. History only: "
            "2017-08-17..2020-12-31; exploration decisions: 2021-01-01..2023-12-24; panel ends "
            "2023-12-31. 2024-01-01 onward is reserved and never available to this loop. "
            "Prefix-invariance checks at quarter ends and 2023-12-24 detect some look-ahead, "
            "not all. "
            "exploratory, not admitted, not yet confirmed."
        )


class AlphaFactorRunner(Developer):
    def develop(self, exp: Any) -> Any:
        if exp.based_experiments and exp.based_experiments[-1].result is None:
            self.develop(exp.based_experiments[-1])
        if not exp.sub_tasks:
            exp.result = pd.Series(dict.fromkeys(LEGACY_KEYS, float("nan")))
            exp.stdout = "baseline: no factors; ALPHA evaluates factors standalone"
            return exp
        run = Path(os.environ["ALPHA_FACTOR_RUN_DIR"])
        evaluations = run / "evaluations.jsonl"
        iteration = len(evaluations.read_bytes().splitlines()) if evaluations.exists() else 0
        folder = run / "evaluations" / f"iter-{iteration}"
        folder.mkdir(parents=True, exist_ok=False)
        factors, frames = [], []
        if not (len(exp.sub_tasks) == len(exp.sub_workspace_list) == len(exp.prop_dev_feedback)):
            raise ValueError("factor tasks, workspaces and feedback lengths differ")
        for task, workspace, feedback in zip(
            exp.sub_tasks, exp.sub_workspace_list, exp.prop_dev_feedback, strict=True
        ):
            if workspace is None or "factor.py" not in (workspace.file_dict or {}):
                # No code: identify the trial by the proposed task itself, so distinct failed
                # proposals stay distinct trials and the same proposal failing twice is a repeat.
                code = b""
                identity = b"no factor.py\0" + task.get_task_information().encode()
            else:
                code = workspace.file_dict["factor.py"].encode()
                identity = code
            factor = {
                "name": task.factor_name,
                "code_sha256": hashlib.sha256(identity).hexdigest(),
                "status": "FAILED",
                "lookahead": {"status": "NOT_RUN"},
            }
            if code and feedback:
                execution, values = workspace.execute("All")
                if values is not None:
                    check = check_prefix_invariance(
                        code,
                        values,
                        run / "factor_data/cuts",
                        os.environ["FACTOR_CoSTEER_python_bin"],  # noqa: SIM112
                        120.0,
                    )
                    factor["lookahead"] = check
                    factor["status"] = "OK" if check["status"] == "PASS" else "LOOKAHEAD"
                    if factor["status"] == "OK":
                        if len(values.columns) != 1:
                            raise ValueError("one output column required per factor task")
                        frame = values.copy()
                        frame.columns = [task.factor_name]
                        frame.index.names = ["date", "instrument"]
                        frames.append(frame)
                else:
                    factor["failure_detail"] = execution
            factors.append(factor)
        if frames:
            values_frame = pd.concat(frames, axis=1).sort_index().reset_index()
            values_frame["date"] = pd.to_datetime(values_frame.date, utc=True).dt.date
        else:
            values_frame = pd.DataFrame(
                {"date": pd.Series(dtype="datetime64[ns]"), "instrument": pd.Series(dtype="str")}
            )
        values_frame.to_parquet(folder / "factors.parquet", index=False)
        request = {
            "schema": "AlphaRdagentFactorRequestV1",
            "iteration": iteration,
            "hypothesis_sha256": hashlib.sha256(str(exp.hypothesis).encode()).hexdigest(),
            "factors": factors,
            "values_file": "factors.parquet",
        }
        (folder / "request.json").write_text(json.dumps(request, sort_keys=True) + "\n")
        command = [
            os.environ["ALPHA_FACTOR_EVAL_PYTHON"],
            "-I",
            "-m",
            "alpha_cli.rdagent_factor_eval",
            "evaluate",
            "--run-dir",
            str(run),
            "--request",
            str(folder / "request.json"),
            "--out",
            str(folder / "result.json"),
            "--ledger",
            os.environ["ALPHA_FACTOR_TRIAL_LEDGER"],
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
        if result.returncode:
            lines = result.stderr.strip().splitlines()
            raise FactorEmptyError(
                lines[-1] if lines else f"ALPHA evaluator exit {result.returncode}"
            )
        record = json.loads((folder / "result.json").read_bytes())
        exp.result = pd.Series(record["legacy_result"])
        exp.stdout = record["feedback_text"]
        exp.alpha_evaluation = record
        if all(f["status"] == "FAILED" for f in factors):
            raise FactorEmptyError("ALPHA recorded every factor as FAILED")
        return exp


class AlphaFactorHypothesisGen(QlibFactorHypothesisGen):
    def prepare_context(self, trace: Any) -> tuple[dict[str, Any], bool]:
        context, flag = super().prepare_context(trace)
        ledger_name = os.environ.get("ALPHA_FACTOR_TRIAL_LEDGER")
        if ledger_name and Path(ledger_name).exists():
            rows = [json.loads(line) for line in Path(ledger_name).read_bytes().splitlines()]
            if rows:
                heading = (
                    "\nALPHA trial ledger (all runs; exploratory, not admitted; "
                    "15 surviving coins only)\n"
                )
                lines, seen = [], set()
                for row in reversed(rows):
                    if row.get("schema") != "AlphaRdagentFactorTrialV1":
                        raise ValueError("invalid ALPHA trial ledger schema")
                    if row["code_sha256"] in seen or row["status"] == "REPEAT":
                        continue
                    seen.add(row["code_sha256"])
                    lines.append(
                        f"{row['name']}: {row['status']}; "
                        f"mean rank IC {row['screen'].get('mean_ic')}; "
                        f"q {row['q']}; run {row['run_id']}"
                    )
                    if len(lines) == 30:
                        break
                context["hypothesis_and_feedback"] += (heading + "\n".join(lines))[:4000]
        return context, flag


class AlphaFactorFeedback(Experiment2Feedback):
    def generate_feedback(self, exp: Any, trace: Any, exception: Exception | None = None) -> Any:
        scenario = (
            self.scen.get_scenario_all_desc(action="factor")
            if isinstance(self.scen, QlibQuantScenario)
            else self.scen.get_scenario_all_desc()
        )
        system = T("scenarios.qlib.prompts:factor_feedback_generation.system").r(scenario=scenario)
        user = T("scenarios.qlib.prompts:factor_feedback_generation.user").r(
            hypothesis_text=exp.hypothesis.hypothesis,
            task_details=[
                task.get_task_information_and_implementation_result() for task in exp.sub_tasks
            ],
            combined_result=exp.stdout,
        )
        reply = APIBackend().build_messages_and_create_chat_completion(
            user_prompt=user,
            system_prompt=system,
            json_mode=True,
            json_target_type=dict[str, str | bool | int],
        )
        response = json.loads(reply)
        feedback = HypothesisFeedback(
            observations=response.get("Observations", "No observations provided"),
            hypothesis_evaluation=response.get("Feedback for Hypothesis", "No feedback provided"),
            new_hypothesis=response.get("New Hypothesis", "No new hypothesis provided"),
            reason=response.get("Reasoning", "No reasoning provided"),
            decision=convert2bool(response.get("Replace Best Result", "no")),
        )
        record = exp.alpha_evaluation
        feedback.decision = record["decision"]
        row = {
            "iteration": record["iteration"],
            "model_decision": response.get("Replace Best Result", "no"),
            "alpha_decision": feedback.decision,
            "reply_sha256": hashlib.sha256(reply.encode()).hexdigest(),
        }
        with (Path(os.environ["ALPHA_FACTOR_RUN_DIR"]) / "feedback.jsonl").open("a") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        return feedback
