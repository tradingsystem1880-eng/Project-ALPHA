"""Real processes verify CLI signals and parent death cannot orphan the RPC group."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from alpha_cli.investigation_case import Case
from tests.unit.test_research_execution import run_fixture


def _alive(pid: int) -> bool:
    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return (
        result.returncode == 0
        and bool(result.stdout.strip())
        and not result.stdout.strip().startswith("Z")
    )


@pytest.mark.parametrize("ending", ["term", "int", "kill", "deadline"])
def test_nested_rpc_processes_terminate_and_reservations_survive(
    tmp_path: Path, ending: str
) -> None:
    case = Case.create(
        tmp_path / "case", run_fixture(tmp_path), "2020-01-02", "Why?", "gpt-6-astra"
    )
    peer = tmp_path / "peer.py"
    peer.write_text("""import json,os,subprocess,sys
from pathlib import Path
child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])
Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid]))
for line in sys.stdin:
 m=json.loads(line)
 if "id" not in m: continue
 method=m["method"]
 if method=="initialize": result={}
 elif method.startswith("thread/"):
  result=dict(model="gpt-6-astra",approvalPolicy="never",thread={"id":"t"},activePermissionProfile={"id":"investigation","extends":None},sandbox={"type":"readOnly","networkAccess":False})
 elif method=="mcpServerStatus/list":
  tools=dict.fromkeys(["inspect_execution","inspect_losses","suggest_followups"])
  result={"data":[{"name":"alpha_investigation","tools":tools}]}
 else: result={"turn":{"id":"u"}}
 print(json.dumps({"id":m["id"],"result":result}),flush=True)
""")
    host = tmp_path / "host.py"
    host.write_text("""import os,sys
from pathlib import Path
from alpha_cli import codex_environment,investigation_lifecycle
from alpha_cli.investigation_case import Case
async def probe(*args): return {"test_double":True}
case=Case.open(Path(sys.argv[1]))
command=[sys.executable,sys.argv[2],sys.argv[3]]
codex_environment.prepare=lambda path: (command,path,dict(os.environ))
codex_environment.preflight=probe
if sys.argv[4]=="deadline":
 original=investigation_lifecycle.watched_argv
 def short(argv):
  result=original(argv);result[4]="1.5";return result
 investigation_lifecycle.watched_argv=short
investigation_lifecycle.run(case)
""")
    pids_file = tmp_path / "pids.json"
    process = subprocess.Popen(
        [sys.executable, str(host), str(case.path), str(peer), str(pids_file), ending],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pids: list[int] = []
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state_file = case.path / "codex-session.json"
            state = json.loads(state_file.read_text()) if state_file.exists() else {}
            if state.get("turns") and state["turns"][-1]["status"] == "running":
                break
            if process.poll() is not None:
                pytest.fail("host exited before reserving its turn")
            time.sleep(0.03)
        else:
            pytest.fail("host did not start bounded turn")
        pids = json.loads(pids_file.read_text())
        if ending != "deadline":
            os.kill(
                process.pid,
                {"term": signal.SIGTERM, "int": signal.SIGINT, "kill": signal.SIGKILL}[ending],
            )
        process.wait(timeout=10)
        deadline = time.monotonic() + 5
        while any(_alive(pid) for pid in pids) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert all(not _alive(pid) for pid in pids)
        state = json.loads(state_file.read_text())
        assert len(state["turns"]) == 1
        assert (case.path / "codex-turn-1.json").exists()
        assert (
            state["turns"][0]["status"]
            == {
                "term": "interrupted",
                "int": "interrupted",
                "kill": "running",
                "deadline": "failed",
            }[ending]
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for pid in pids:
            if _alive(pid):
                os.kill(pid, signal.SIGKILL)
