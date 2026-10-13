"""The shared registry bounds concurrent create and acquired-child reservations."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from alpha_cli import investigation_workspace as workspace
from alpha_cli import investigation_workspace_data as data
from alpha_cli.investigation_case import Case
from alpha_cli.investigation_workspace_contracts import (
    ComparisonDraftRequest,
    ComparisonProxy,
    InvestigationCreate,
)
from alpha_core import DataError
from tests.unit.test_investigation_workspace import root_with_run


def test_create_and_acquired_child_compete_for_one_durable_registry_slot(tmp_path: Path) -> None:
    root = root_with_run(tmp_path)
    parent = workspace.create(root, InvestigationCreate(run_id="1234567890abcdef", question="Why?"))
    case = Case.open(workspace._directory(root, parent.id))
    case.call("inspect_execution")
    case.call("inspect_losses")
    preview = data.draft(
        root,
        parent.id,
        ComparisonDraftRequest(
            series=[ComparisonProxy(symbol="SPY", asset_class="etf", role="market")]
        ),
    )
    script = tmp_path / "compete.py"
    script.write_text("""import sys,time
from pathlib import Path
from alpha_cli import investigation_workspace as w,investigation_workspace_data as d
from alpha_cli import comparison_acquisition as a,comparison_acquisition_worker as worker
from alpha_cli.investigation_case import Case
from alpha_cli.investigation_workspace_contracts import InvestigationCreate,ComparisonAcquireRequest
from tests.unit.test_comparison_acquisition import provider_result,fixture_dispatch
root=Path(sys.argv[1]); mode=sys.argv[4]
w.MAX_WORKSPACES=2
worker._fetch=provider_result;a._dispatch=fixture_dispatch
original=Case.create
arrival=root.parent / (mode+"-arrived")
other=root.parent / (("child" if mode=="create" else "create")+"-arrived")
def gated(*args,**kwargs):
 arrival.touch()
 deadline=time.monotonic()+1
 while not other.exists() and time.monotonic()<deadline: time.sleep(.01)
 return original(*args,**kwargs)
Case.create=staticmethod(gated)
try:
 if mode=="create": w.create(root,InvestigationCreate(run_id="1234567890abcdef",question="New"))
 else: d.acquire(root,sys.argv[2],ComparisonAcquireRequest(plan_sha256=sys.argv[3]))
except Exception as exc:
 print(type(exc).__name__+":"+str(exc),flush=True)
""")
    env = {
        **os.environ,
        "ALPHA_TIINGO_API_KEY": "fixture",
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
    }
    children = [
        subprocess.Popen(
            [sys.executable, str(script), str(root), parent.id, preview.plan_sha256, mode],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for mode in ("create", "child")
    ]
    try:
        for child in children:
            stdout, stderr = child.communicate(timeout=20)
            assert child.returncode == 0, stdout + stderr
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            child.communicate(timeout=5)
    entries = [p for p in (root / "investigations").iterdir() if p.name != ".registry.lock"]
    assert len(entries) == 2
    assert len(workspace.list_cases(root, parent.run_id)) == 2
    before = {
        p: (p.stat().st_mtime_ns, p.stat().st_size)
        for p in (root / "investigations").rglob("*")
        if p.is_file()
    }
    workspace.list_cases(root, parent.run_id)
    assert before == {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in before}


def test_pending_reservation_consumes_capacity_and_symlink_lock_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "investigations" / ("a" * 32)
    monkeypatch.setattr(workspace, "MAX_WORKSPACES", 1)
    staging = workspace._reserve_staging(target)
    assert staging.is_dir()
    with pytest.raises(DataError, match="limit"):
        workspace._reserve_staging(target.with_name("b" * 32))
    lock = target.parent / ".registry.lock"
    lock.unlink()
    lock.symlink_to(tmp_path / "outside")
    with pytest.raises(OSError):
        workspace._reserve_staging(target)
    assert not (tmp_path / "outside").exists()


def test_listing_existing_empty_registry_creates_no_lock(tmp_path: Path) -> None:
    root = root_with_run(tmp_path)
    directory = root / "investigations"
    directory.mkdir()
    before = directory.stat().st_mtime_ns
    assert workspace.list_cases(root, "1234567890abcdef") == []
    assert list(directory.iterdir()) == []
    assert directory.stat().st_mtime_ns == before
