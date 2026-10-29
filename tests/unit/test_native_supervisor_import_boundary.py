"""Synthetic owner start-up must not import the native-loop admission stack it does not use."""

import json
import subprocess
import sys

import pytest

from alpha_core import DataError

_PROBE = """
import json, sys
import alpha_cli.native_supervisor
heavy = [m for m in ("alpha_cli._native_loop_admission", "alpha_research", "scipy")
         if m in sys.modules]
print(json.dumps(heavy))
"""


def test_supervisor_import_skips_native_loop_admission() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _PROBE], capture_output=True, text=True, timeout=120, check=True
    )
    assert json.loads(result.stdout) == []


# The controller's pre-launch status read and the owner's claim both enter through this edge.
_STATUS_PROBE = """
import json, sys
from alpha_core import DataError
from alpha_cli.control_store import ControlStore
from alpha_cli.native_supervisor import synthetic_workspace
with synthetic_workspace() as root:
    try:
        ControlStore(root).native_fixture_status("missing-job")
    except DataError:
        pass
heavy = [m for m in ("alpha_cli._native_fixture_store", "alpha_cli._native_rule_economics",
                     "alpha_cli._native_loop_admission", "alpha_research", "scipy")
         if m in sys.modules]
print(json.dumps(heavy))
"""


@pytest.mark.skipif(sys.platform != "linux", reason="requires the Linux native owner profile")
def test_status_and_claim_path_skips_rule_economics() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _STATUS_PROBE],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert json.loads(result.stdout) == ["alpha_cli._native_fixture_store"]


@pytest.mark.skipif(sys.platform != "linux", reason="requires the Linux native owner profile")
def test_native_launch_type_identity_is_still_enforced() -> None:
    from alpha_cli import native_supervisor
    from alpha_cli._native_loop_admission import NativeLaunch

    class Imposter(NativeLaunch):
        pass

    impostor = Imposter.__new__(Imposter)
    with native_supervisor.synthetic_workspace() as root:
        with pytest.raises(DataError, match="requires its fixed launch identity"):
            native_supervisor.start_synthetic_owner(
                root, "job", fixture="native_loop", native=impostor
            )
        with pytest.raises(DataError, match="requires its fixed launch identity"):
            native_supervisor.start_synthetic_owner(root, "job", fixture="wait", native=impostor)


# The owner's claim validates its reserved contract, which needs the analytical boundary package.
_CLAIM_IMPORT_PROBE = """
import contextlib, json, sys
from pathlib import Path
from alpha_cli import native_supervisor as supervisor
from alpha_cli.control_store import ControlStore
root = Path(sys.argv[1]); job = sys.argv[2]; seen = []
transaction = ControlStore._transaction
@contextlib.contextmanager
def counted(self, *, write):
    with transaction(self, write=write) as connection:
        before = len(sys.modules)
        yield connection
        seen.append({"write": write, "imported": len(sys.modules) - before})
ControlStore._transaction = counted
init = supervisor._Owner.__init__
def observed(self, *args, **kwargs):
    seen.append({"deadline_start_loaded": "alpha_research" in sys.modules})
    init(self, *args, **kwargs)
supervisor._Owner.__init__ = observed
with supervisor._open_lock(root, job) as lock:
    supervisor._run_owner(root, job, "success", 10, lock)
print(json.dumps(seen))
"""


@pytest.mark.skipif(sys.platform != "linux", reason="requires the Linux native owner profile")
def test_owner_claim_imports_nothing_while_holding_the_store_write_lock() -> None:
    from alpha_cli.control_store import ControlStore
    from alpha_cli.native_supervisor import synthetic_workspace
    from tests.unit.test_native_fixture_lifecycle import JOB
    from tests.unit.test_research_control_store import (
        _approved_native_d1,
        _native_d1_job,
        _project,
    )

    with synthetic_workspace() as root:
        store = ControlStore(root)
        _project(store)
        contract, _ = _approved_native_d1(store)
        _native_d1_job(store, contract, job_id=JOB)
        result = subprocess.run(
            [sys.executable, "-c", _CLAIM_IMPORT_PROBE, str(root), JOB],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    seen = json.loads(result.stdout.splitlines()[-1])
    # Loaded before the owner's deadline starts, and the claim (its first write) imports nothing.
    assert seen[0] == {"deadline_start_loaded": True}
    claim = next(entry for entry in seen[1:] if entry.get("write") is True)
    assert claim["imported"] == 0
