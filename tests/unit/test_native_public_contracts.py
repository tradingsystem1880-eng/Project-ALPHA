"""Public synthetic fixtures only: fail-closed verifier contracts of the native rule modules.

Nothing here is a qualified native runtime, source pin or rule profile. Every fixture is
synthetic, so a passing check proves only that the verifier refuses or accepts these exact
bytes. Every `complete_rule_trial` guard after `authority.verify()` stays uncovered without
a qualified runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from alpha_cli import _native_rule_environment
from alpha_cli._native_loop_admission import (
    MAX_NATIVE_RECEIPT_BYTES,
    SOURCE_SHA256,
    WORKER,
    WORKER_FILES,
    NativeLaunch,
    measure_native_proposal,
)
from alpha_cli._native_rule_authority import RuleAuthority
from alpha_cli._native_rule_completion import complete_rule_trial
from alpha_cli._native_rule_environment import measure_rule_environment
from alpha_cli._native_rule_protocol import selected_study
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from tests.unit.test_research_control_store import (
    PROJECT_ID,
    _approved_native_d1,
    _native_d1_job,
    _project,
)

JOB = "4c657d82-fc1a-44d8-b49b-bfdcfe93c52c"
POSITIONS = ("alpha-core", "alpha-patterns", "alpha-strategies")
COSTED = (*POSITIONS, "alpha-backtest", "alpha-data")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha(data)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class SyntheticRuntime:
    """A synthetic, unqualified rule runtime; its digest says nothing about qualification."""

    def __init__(self, root: Path, *, costed: bool, profile_costed: bool | None = None) -> None:
        self.root = root
        self.worker = root / "workers" / "rdagent"
        self.costed = costed
        self.runtime = self.worker / (
            ".venv-economics-qualified" if costed else ".venv-rule-qualified"
        )
        as_costed = costed if profile_costed is None else profile_costed
        sources: dict[str, dict[str, dict[str, str]]] = {}
        for name in COSTED if as_costed else POSITIONS:
            module = name.replace("-", "_")
            package = root / "packages" / name
            source_files = {
                f"src/{module}/__init__.py": _write(
                    package / "src" / module / "__init__.py", f"# {name}\n".encode()
                ),
                "pyproject.toml": _write(
                    package / "pyproject.toml", f'[project]\nname = "{name}"\n'.encode()
                ),
            }
            sources[name] = {"source_files": source_files}
        site_files = {
            "synthetic_dep/__init__.py": _write(
                self.runtime / "lib/python3.12/site-packages/synthetic_dep/__init__.py",
                b"VALUE = 1\n",
            )
        }
        lock = "economics-requirements.lock" if costed else "rule-requirements.lock"
        self.profile: dict[str, Any] = {
            "schema": "AlphaRuleWorkerProfileV1",
            "profile": "costed" if as_costed else "positions",
            "sources": sources,
            "site_files": site_files,
            "requirements_sha256": _write(self.worker / lock, b"synthetic-lock==1\n"),
            "root_lock_sha256": _write(root / "uv.lock", b"# synthetic root lock\n"),
        }
        _write(self.runtime / "bin/python", b"synthetic interpreter bytes\n")
        _write(self.runtime / "pyvenv.cfg", b"home = /synthetic\n")
        self.write_profile(self.profile)

    def write_profile(self, profile: dict[str, Any]) -> None:
        _write(self.runtime / "rule-profile.json", json.dumps(profile).encode())

    def expected_digest(self) -> str:
        identity = {
            "profile": _sha((self.runtime / "rule-profile.json").read_bytes()),
            "python": _sha((self.runtime / "bin/python").read_bytes()),
            "pyvenv": _sha((self.runtime / "pyvenv.cfg").read_bytes()),
        }
        return _sha(_canonical(identity))


@pytest.fixture
def synthetic_rule_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., SyntheticRuntime]:
    """Public synthetic fixtures only; nothing here is a qualified rule runtime or profile."""

    def build(*, costed: bool = False, profile_costed: bool | None = None) -> SyntheticRuntime:
        runtime = SyntheticRuntime(tmp_path, costed=costed, profile_costed=profile_costed)
        monkeypatch.setattr(_native_rule_environment, "WORKER", runtime.worker)
        # Confinement: the verifier can only reach the synthetic tree, never a real profile.
        patched = vars(_native_rule_environment)["WORKER"]
        assert patched == runtime.worker and patched.parents[1] == tmp_path
        return runtime

    return build


def _symlink_in_place(path: Path) -> None:
    real = path.with_name(path.name + ".real")
    path.rename(real)
    path.symlink_to(real, target_is_directory=real.is_dir())


def _edit_profile(**changes: object) -> Callable[[SyntheticRuntime], None]:
    def apply(runtime: SyntheticRuntime) -> None:
        runtime.write_profile({**runtime.profile, **changes})

    return apply


def _drop_source(runtime: SyntheticRuntime) -> None:
    sources = dict(runtime.profile["sources"])
    sources.pop("alpha-patterns")
    runtime.write_profile({**runtime.profile, "sources": sources})


def _append(relative: str) -> Callable[[SyntheticRuntime], None]:
    def apply(runtime: SyntheticRuntime) -> None:
        path = runtime.root / relative
        path.write_bytes(path.read_bytes() + b"# changed\n")

    return apply


def _site_bytecode(runtime: SyntheticRuntime) -> None:
    _write(runtime.runtime / "lib/python3.12/site-packages/synthetic_dep/cache.pyc", b"\0")


SITE_FILE = (
    "workers/rdagent/.venv-rule-qualified/lib/python3.12/site-packages/synthetic_dep/__init__.py"
)


@pytest.mark.parametrize(
    "mutate,message",
    [
        (
            lambda r: _symlink_in_place(r.runtime),
            "rule runtime requires a fresh isolated environment",
        ),
        (
            lambda r: _symlink_in_place(r.runtime / "rule-profile.json"),
            "rule runtime metadata symlink is unsupported",
        ),
        (
            lambda r: _symlink_in_place(r.runtime / "pyvenv.cfg"),
            "rule runtime metadata symlink is unsupported",
        ),
        (_edit_profile(profile="costed"), "unknown fixed rule import profile"),
        (_drop_source, "unknown fixed rule import profile"),
        (_edit_profile(schema="AlphaRuleWorkerProfileV0"), "installed rule runtime bytes changed"),
        (_append(SITE_FILE), "installed rule runtime bytes changed"),
        (_site_bytecode, "rule runtime contains unqualified bytecode"),
        (
            _append("packages/alpha-core/src/alpha_core/__init__.py"),
            "rule source package bytes changed",
        ),
        (_append("packages/alpha-strategies/pyproject.toml"), "rule source package bytes changed"),
        (_append("workers/rdagent/rule-requirements.lock"), "rule dependency lock changed"),
        (_append("uv.lock"), "approved root dependency lock changed"),
    ],
)
def test_rule_environment_refuses_each_single_change(
    synthetic_rule_runtime: Callable[..., SyntheticRuntime],
    mutate: Callable[[SyntheticRuntime], None],
    message: str,
) -> None:
    runtime = synthetic_rule_runtime()
    assert measure_rule_environment() == runtime.expected_digest()  # valid before the change
    mutate(runtime)
    with pytest.raises(DataError, match=re.escape(message)):
        measure_rule_environment()


def test_rule_environment_identity_tracks_its_measured_bytes(
    synthetic_rule_runtime: Callable[..., SyntheticRuntime],
) -> None:
    runtime = synthetic_rule_runtime()
    first = measure_rule_environment()
    assert first == runtime.expected_digest() == measure_rule_environment()
    (runtime.runtime / "pyvenv.cfg").write_bytes(b"home = /synthetic/other\n")
    assert measure_rule_environment() == runtime.expected_digest() != first


def test_costed_rule_environment_is_its_own_profile(
    synthetic_rule_runtime: Callable[..., SyntheticRuntime],
) -> None:
    runtime = synthetic_rule_runtime(costed=True)
    assert measure_rule_environment(costed=True) == runtime.expected_digest()
    runtime.write_profile({**runtime.profile, "profile": "positions"})
    with pytest.raises(DataError, match="unknown fixed rule import profile"):
        measure_rule_environment(costed=True)


def test_positions_profile_is_refused_as_costed(
    synthetic_rule_runtime: Callable[..., SyntheticRuntime],
) -> None:
    synthetic_rule_runtime(costed=True, profile_costed=False)
    with pytest.raises(DataError, match="unknown fixed rule import profile"):
        measure_rule_environment(costed=True)


@pytest.fixture
def unpinned_source(tmp_path: Path) -> Path:
    source = (tmp_path / "native-source").resolve()
    source.mkdir()
    return source


def test_launch_constructor_refuses_unbound_or_mistyped_studies(unpinned_source: Path) -> None:
    study = selected_study(False)
    with pytest.raises(DataError, match="native scientific study blocked"):
        NativeLaunch(unpinned_source, "INCONCLUSIVE", study=study)
    imposter = cast(RuleAuthority, object())
    with pytest.raises(DataError, match="rule launch requires its exact typed study and authority"):
        NativeLaunch(unpinned_source, "INCONCLUSIVE", study=study, authority=imposter)


def test_launch_constructor_refuses_unknown_modes_and_unresolved_sources(
    unpinned_source: Path,
) -> None:
    with pytest.raises(DataError, match="invalid fixed native fixture source/mode"):
        NativeLaunch(unpinned_source, "APPROVED")
    alias = unpinned_source.parent / "alias"
    alias.symlink_to(unpinned_source, target_is_directory=True)
    with pytest.raises(DataError, match="invalid fixed native fixture source/mode"):
        NativeLaunch(alias, "INCONCLUSIVE")
    with pytest.raises(DataError, match="invalid fixed native fixture source/mode"):
        NativeLaunch(unpinned_source / ".." / unpinned_source.name, "INCONCLUSIVE")
    # A valid mode on an unpinned source is still refused: the constructor measures the pin.
    with pytest.raises(DataError, match="fixed native fixture requires pinned source"):
        NativeLaunch(unpinned_source, "INCONCLUSIVE")


def test_native_proposal_measurement_verifies_the_pinned_source(unpinned_source: Path) -> None:
    with pytest.raises(DataError, match="fixed native fixture requires pinned source"):
        measure_native_proposal(unpinned_source, "INCONCLUSIVE")
    module = unpinned_source / "rdagent" / "__init__.py"
    _write(module, b"# synthetic, not the pinned tree\n")
    with pytest.raises(DataError, match="pinned native source tree mismatch"):
        measure_native_proposal(unpinned_source, "INCONCLUSIVE")
    (unpinned_source / "rdagent" / "link.py").symlink_to(module)
    with pytest.raises(DataError, match="native source symlinks are unsupported"):
        measure_native_proposal(unpinned_source, "INCONCLUSIVE")


def _unadmitted_launch(source: Path) -> NativeLaunch:
    """Only for verify_result/command's own guards; the real constructor enforces the pin."""
    launch = NativeLaunch.__new__(NativeLaunch)
    fields = {"source": source, "mode": "INCONCLUSIVE", "study": None, "authority": None}
    for name, value in {**fields, "fingerprint": "0" * 64}.items():
        object.__setattr__(launch, name, value)
    return launch


ADMISSION: dict[str, object] = {"schema": "SyntheticNativeAdmissionV1", "job_id": JOB}


def _mapped_receipt() -> dict[str, object]:
    """Every field the synthetic mapping checks, as the verifier would expect it."""
    return {
        "admission": ADMISSION,
        "scientific_acceptance": "not_admitted",
        "authority": "none",
        "synthetic": True,
        "source_tree_sha256": SOURCE_SHA256,
        "binding_sha256": _sha(_canonical(ADMISSION)),
        "imported_worker_sha256": {
            name.removesuffix(".py"): _sha((WORKER / name).read_bytes())
            for name in WORKER_FILES
            if name.endswith(".py") and name != "fixture_entry.py"
        },
        "checks": {
            "events": ["direct_exp_gen", "coding", "running", "feedback", "record"],
            "label": "INCONCLUSIVE",
            "metrics": [["net_return", -0.125, "fraction"], ["cost", 0.03125, "fraction"]],
        },
        "checkpoint_binding_verified": True,
    }


def test_result_publication_must_be_a_bounded_regular_receipt(
    tmp_path: Path, unpinned_source: Path
) -> None:
    launch = _unadmitted_launch(unpinned_source)
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(DataError, match="publication missing or invalid"):
        launch.verify_result(work, ADMISSION)
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text(json.dumps(_mapped_receipt()))
    (work / "receipt.json").symlink_to(elsewhere)
    with pytest.raises(DataError, match="publication missing or invalid"):
        launch.verify_result(work, ADMISSION)
    (work / "receipt.json").unlink()
    (work / "receipt.json").write_bytes(b" " * (MAX_NATIVE_RECEIPT_BYTES + 1))
    with pytest.raises(DataError, match="exceeds fixed receipt limit"):
        launch.verify_result(work, ADMISSION)


@pytest.mark.parametrize(
    "field,value",
    [
        ("admission", {**ADMISSION, "job_id": "another"}),
        ("checks", {"events": ["direct_exp_gen"], "label": "SUPPORTED", "metrics": []}),
        ("scientific_acceptance", "admitted"),
        ("binding_sha256", "0" * 64),
    ],
)
def test_result_mapping_refuses_each_changed_field(
    tmp_path: Path, unpinned_source: Path, field: str, value: object
) -> None:
    launch = _unadmitted_launch(unpinned_source)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(_mapped_receipt()))
    # The faithful mapping reaches the final launch re-measurement, which refuses this unpinned
    # source; a single changed field is refused earlier, by the mapping check itself.
    with pytest.raises(DataError, match="fixed native fixture requires pinned source"):
        launch.verify_result(tmp_path, ADMISSION)
    receipt.write_text(json.dumps({**_mapped_receipt(), field: value}))
    with pytest.raises(DataError, match="changed its admitted identity or exact mapping"):
        launch.verify_result(tmp_path, ADMISSION)


def test_child_command_requires_a_reservation_and_unchanged_launch_bytes(
    unpinned_source: Path,
) -> None:
    launch = _unadmitted_launch(unpinned_source)
    with pytest.raises(DataError, match="native child requires its committed reservation"):
        launch.command(None)
    with pytest.raises(DataError, match="fixed native fixture requires pinned source"):
        launch.command(ADMISSION)


def _ledger(store: ControlStore) -> tuple[object, ...]:
    with store._transaction(write=False) as connection:
        rows: list[object] = []
        for table in (
            "research_attempt_records",
            "research_launch_attempt_links",
            "research_execution_events",
        ):
            rows.append([tuple(row) for row in connection.execute(f"SELECT * FROM {table}")])
        status = connection.execute("SELECT status FROM jobs WHERE job_id=?", (JOB,)).fetchone()
        rows.append(None if status is None else status[0])
        return tuple(rows)


@pytest.fixture
def reserved_store(tmp_path: Path) -> tuple[ControlStore, str]:
    store = ControlStore(tmp_path / "store")
    _project(store)
    contract, _ = _approved_native_d1(store)
    _native_d1_job(store, contract, job_id=JOB)
    return store, contract


def test_rule_completion_refuses_launches_it_cannot_trust(
    reserved_store: tuple[ControlStore, str], tmp_path: Path
) -> None:
    store, contract = reserved_store
    before = _ledger(store)
    untyped = cast(NativeLaunch, object())
    with pytest.raises(DataError, match="requires its approved typed native launch"):
        complete_rule_trial(store, JOB, untyped)
    with pytest.raises(DataError, match="requires its approved typed native launch"):
        complete_rule_trial(store, JOB, _unadmitted_launch(tmp_path))
    foreign = _unadmitted_launch(tmp_path)
    object.__setattr__(foreign, "study", selected_study(False))
    object.__setattr__(
        foreign, "authority", RuleAuthority(tmp_path / "other-store", PROJECT_ID, contract)
    )
    with pytest.raises(DataError, match="rule completion belongs to another store"):
        complete_rule_trial(store, JOB, foreign)
    # No accepted completion: no attempt, link, success status or completion event.
    assert _ledger(store) == before
    assert before[3] != "succeeded"
