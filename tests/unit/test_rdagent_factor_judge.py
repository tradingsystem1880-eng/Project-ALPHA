"""Pure prefix comparison plus opt-in Python 3.11 RD-Agent contracts."""

# ruff: noqa: E501  (the embedded subprocess scripts are kept literal)

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pandas as pd
import pytest

WORKER = Path(__file__).resolve().parents[2] / "workers/rdagent"
spec = importlib.util.spec_from_file_location("alpha_factor_data", WORKER / "alpha_factor_data.py")
assert spec is not None and spec.loader is not None
data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data)


def test_prefix_comparison_includes_index_nan_and_tolerance() -> None:
    idx = pd.MultiIndex.from_product(
        [pd.date_range("2023-01-01", periods=3), ["A", "B"]], names=["datetime", "instrument"]
    )
    full = pd.DataFrame({"x": [float("nan"), 1.0, 2.0, 3.0, 4.0, 5.0]}, index=idx)
    assert data.compare_prefix(full, full.iloc[:4], "2023-01-02") is None
    changed = full.iloc[:4].copy()
    changed.loc[changed.index[1], "x"] = 1.0 + 1e-11
    assert data.compare_prefix(full, changed, "2023-01-02") is None
    changed.loc[changed.index[1], "x"] = 1.1
    assert data.compare_prefix(full, changed, "2023-01-02") is not None
    changed = full.iloc[:4].fillna(0)
    assert data.compare_prefix(full, changed, "2023-01-02") is not None
    assert data.compare_prefix(full, full.iloc[:3], "2023-01-02") is not None


RUNTIME = pytest.mark.skipif(
    not (os.environ.get("ALPHA_FACTOR_PYTHON") and os.environ.get("ALPHA_RDAGENT_SOURCE")),
    reason="requires ALPHA_FACTOR_PYTHON and ALPHA_RDAGENT_SOURCE",
)


@RUNTIME
def test_prepare_and_causal_and_leaky_factors(tmp_path: Path) -> None:
    script = r"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, sys.argv[1])
from alpha_factor_data import prepare, check_prefix_invariance
root = Path(sys.argv[2])
dates = pd.date_range('2020-12-01', '2023-12-31')
idx = pd.MultiIndex.from_product([dates.date, ['A', 'B']], names=['date','instrument'])
f = pd.DataFrame({'open':range(1,len(idx)+1)},index=idx).reset_index()
for col in ['close','low','high','volume','quote_volume']: f[col] = f['open'].astype(float)
f.to_parquet(root/'panel.parquet',index=False)
prepare(root/'panel.parquet', root/'prepared')
assert (root/'prepared/debug/README.md').exists()
import subprocess
for expression, expected in [
 ("f.groupby(level='instrument')['$close'].pct_change(5)", 'PASS'),
 ("f.groupby(level='instrument')['$close'].shift(-1)", 'LOOKAHEAD'),
 ("(f['$close']-f['$close'].mean())/f['$close'].std()", 'LOOKAHEAD')]:
 code = ("import pandas as pd\nf=pd.read_hdf('daily_pv.h5',key='data')\ns=" + expression + "\ns.to_frame('x').to_hdf('result.h5',key='data')\n").encode()
 work=root/'full'; work.mkdir(exist_ok=True)
 if not (work/'daily_pv.h5').exists(): (work/'daily_pv.h5').symlink_to(root/'prepared/full/daily_pv.h5')
 (work/'factor.py').write_bytes(code)
 subprocess.run([sys.executable,'factor.py'],cwd=work,check=True)
 full=pd.read_hdf(work/'result.h5',key='data')
 result=check_prefix_invariance(code,full,root/'prepared/cuts',sys.executable,30)
 assert result['status'] == expected, result
"""
    subprocess.run(
        [os.environ["ALPHA_FACTOR_PYTHON"], "-I", "-B", "-c", script, str(WORKER), str(tmp_path)],
        check=True,
        cwd=tmp_path,
        timeout=180,
    )


@RUNTIME
def test_upstream_imports_and_feedback_authority(tmp_path: Path) -> None:
    script = r"""
import sys, os, json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from factor_loop_entry import install_source
install_source(Path(sys.argv[2]))
import alpha_factor_judge as j
from rdagent.core.developer import Developer
from rdagent.core.proposal import Experiment2Feedback
from rdagent.scenarios.qlib.experiment.factor_experiment import QlibFactorScenario
assert issubclass(j.AlphaFactorScenario,QlibFactorScenario)
assert issubclass(j.AlphaFactorRunner,Developer)
assert issubclass(j.AlphaFactorFeedback,Experiment2Feedback)
os.environ['ALPHA_FACTOR_RUN_DIR']=sys.argv[3]
exp=SimpleNamespace(hypothesis=SimpleNamespace(hypothesis='test'),sub_tasks=[],stdout='ALPHA test',alpha_evaluation={'iteration':0,'decision':False})
scen=SimpleNamespace(get_scenario_all_desc=lambda:'scenario')
with patch.object(j,'APIBackend') as backend:
 backend.return_value.build_messages_and_create_chat_completion.return_value=json.dumps({'Replace Best Result':True})
 fb=j.AlphaFactorFeedback(scen).generate_feedback(exp,None)
 assert fb.decision is False
row=json.loads((Path(sys.argv[3])/'feedback.jsonl').read_text())
assert row['model_decision'] is True and row['alpha_decision'] is False
assert 'reply' not in row
runner=j.AlphaFactorRunner(scen)
base=SimpleNamespace(based_experiments=[],sub_tasks=[],result=None,stdout='')
runner.develop(base)
labels=['IC','1day.excess_return_without_cost.annualized_return','1day.excess_return_without_cost.max_drawdown']
assert list(base.result.loc[labels].index)==labels
"""
    subprocess.run(
        [
            os.environ["ALPHA_FACTOR_PYTHON"],
            "-I",
            "-B",
            "-c",
            script,
            str(WORKER),
            os.environ["ALPHA_RDAGENT_SOURCE"],
            str(tmp_path),
        ],
        check=True,
        cwd=tmp_path,
        timeout=60,
    )
