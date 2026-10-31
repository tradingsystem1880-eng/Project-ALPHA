"""Identity for one fixed synthetic child, never an admission or settlement ledger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alpha_cli._native_rule_authority import RuleAuthority
    from alpha_cli._native_rule_study import SyntheticRuleStudy

from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli._native_rule_economics import CostedRuleStudy
from alpha_core import DataError

WORKER = Path(__file__).resolve().parents[4] / "workers" / "rdagent"
MAX_NATIVE_RECEIPT_BYTES = 100_000  # Existing fixed-fixture cap; enforce on the same bounded read.
SOURCE_SHA256 = "0266b2d63328f88fcaf6f239bf6d67f29c896b8161566f794ef69465b7788707"
MODES = {
    "SUPPORTED",
    "CONTRADICTED",
    "INCONCLUSIVE",
    "INVALID",
    "resume",
    "wait",
    "failure",
    "foreign_binding",
}
WORKER_FILES = (
    "fixture_entry.py",
    "source_pin.py",
    "native_fixture.py",
    "fixture_owner.py",
    "conformance.py",
    "admitted_probe.py",
    "uv.lock",
    "pyproject.toml",
)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class NativeLaunch:
    source: Path
    mode: str
    study: SyntheticRuleStudy | CostedRuleStudy | DailyRuleStudyV1 | None = None
    authority: RuleAuthority | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.study is not None and self.authority is None:
            raise DataError(
                "native scientific study blocked: no registered RuleSpec/control protocol "
                "with D0/approval and trial binding; isolated worker rule runtime unqualified"
            )
        if self.authority is not None:
            from alpha_cli._native_rule_authority import RuleAuthority
            from alpha_cli._native_rule_protocol import selected_study

            if (
                type(self.authority) is not RuleAuthority
                or (
                    not isinstance(self.study, DailyRuleStudyV1)
                    and self.study != selected_study(isinstance(self.study, CostedRuleStudy))
                )
                or self.mode != "INCONCLUSIVE"
            ):
                raise DataError("rule launch requires its exact typed study and authority")
            approved = self.authority.verify()
            if isinstance(self.study, DailyRuleStudyV1):
                from alpha_cli._native_daily_rule_protocol import study_from_contract

                if study_from_contract(approved) != self.study:
                    raise DataError("daily launch differs from exact approved request")
                if self.implementation_fingerprints() != approved.get("hashes"):
                    raise DataError("daily launch code/runtime differs from exact owner approval")
                self.authority.reopen_daily_inputs()
            plan = approved["analysis_plan"]
            if not isinstance(plan, dict) or plan["study"] != self.study.to_dict():
                raise DataError("native study differs from exact owner-approved request")
        if (
            self.mode not in MODES
            or self.source.is_symlink()
            or self.source != self.source.resolve()
        ):
            raise DataError("invalid fixed native fixture source/mode")
        object.__setattr__(self, "fingerprint", self.measure())

    def measure(self) -> str:
        return measure_native_proposal(self.source, self.mode, self.study)

    def implementation_fingerprints(self) -> dict[str, str | None]:
        """Measured fixture implementation identity; no scientific evaluator is qualified."""
        if self.study is not None:
            from alpha_cli._native_rule_environment import rule_implementation_fingerprints

            return rule_implementation_fingerprints(
                isinstance(self.study, CostedRuleStudy | DailyRuleStudyV1),
                daily_study=self.study if isinstance(self.study, DailyRuleStudyV1) else None,
            )
        return {
            "code": _digest(
                {
                    name: hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
                    for name in WORKER_FILES
                    if name.endswith(".py")
                }
            ),
            "dependency_lock": hashlib.sha256((WORKER / "uv.lock").read_bytes()).hexdigest(),
            "environment": _digest(
                {
                    "python": hashlib.sha256(
                        (WORKER / ".venv/bin/python").resolve().read_bytes()
                    ).hexdigest(),
                    "pyvenv": hashlib.sha256(
                        (WORKER / ".venv/pyvenv.cfg").read_bytes()
                    ).hexdigest(),
                }
            ),
            "evaluator": hashlib.sha256((WORKER / "admitted_probe.py").read_bytes()).hexdigest(),
            "data": None,
        }

    def verify_result(self, work: Path, admission: dict[str, object] | None) -> bytes:
        """Validate and return the SAME bounded receipt bytes observed after child cleanup."""
        if isinstance(self.study, DailyRuleStudyV1):
            from alpha_cli._native_daily_rule_artifacts import validate_daily_native_result

            helpers = {
                name.removesuffix(".py"): hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
                for name in (*WORKER_FILES, "rule_probe.py", "costed_probe.py")
                if name.endswith(".py") and name != "fixture_entry.py"
            }
            if self.measure() != self.fingerprint:
                raise DataError("daily worker changed after reservation")
            return validate_daily_native_result(work, admission, self.study, helpers)
        path = work / "receipt.json"
        if path.is_symlink() or not path.is_file():
            raise DataError("native synthetic result publication missing or invalid")
        with path.open("rb") as handle:
            receipt_bytes = handle.read(MAX_NATIVE_RECEIPT_BYTES + 1)
        if len(receipt_bytes) > MAX_NATIVE_RECEIPT_BYTES:
            raise DataError("native synthetic result publication exceeds fixed receipt limit")
        result = json.loads(receipt_bytes)
        if self.study is not None:
            from alpha_cli._native_rule_protocol import position_payload

            expected = position_payload(isinstance(self.study, CostedRuleStudy | DailyRuleStudyV1))
            helpers = {
                name.removesuffix(".py"): hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
                for name in WORKER_FILES
                if name.endswith(".py") and name != "fixture_entry.py"
            }
            helpers["rule_probe"] = hashlib.sha256(
                (WORKER / "rule_probe.py").read_bytes()
            ).hexdigest()
            if isinstance(self.study, CostedRuleStudy | DailyRuleStudyV1):
                helpers["costed_probe"] = hashlib.sha256(
                    (WORKER / "costed_probe.py").read_bytes()
                ).hexdigest()
            if (
                not isinstance(result, dict)
                or result.get("admission") != admission
                or result.get("rule_positions") != expected
                or result.get("authority") != "none"
                or result.get("synthetic") is not True
                or result.get("routes_enabled") is not False
                or result.get("imported_worker_sha256") != helpers
                or result.get("binding_sha256") != _digest(admission)
                or result.get("scientific_acceptance") != "not_admitted"
                or result.get("source_tree_sha256") != SOURCE_SHA256
                or result.get("checkpoint_binding_verified") is not True
                or result.get("checks")
                != {"events": ["direct_exp_gen", "coding", "running", "feedback", "record"]}
                or self.measure() != self.fingerprint
            ):
                raise DataError("native rule result changed its committed identity or positions")
            if isinstance(self.study, CostedRuleStudy | DailyRuleStudyV1):
                from alpha_cli._native_rule_economics import validate_costed_result

                validate_costed_result(result.get("economics"))
            for key in ("baseline", "control"):
                expected_artifact = {
                    "schema": "RulePositionArtifactV1",
                    "unit": "position",
                    "positions": expected[key],
                }
                path = work / (key + ".json")
                if path.is_symlink() or json.loads(path.read_text()) != expected_artifact:
                    raise DataError("native rule position artifact changed")
            return receipt_bytes
        expected_label = (
            self.mode
            if self.mode in {"SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "INVALID"}
            else "INCONCLUSIVE"
        )
        if (
            not isinstance(result, dict)
            or result.get("admission") != admission
            or result.get("scientific_acceptance") != "not_admitted"
            or result.get("authority") != "none"
            or result.get("synthetic") is not True
            or result.get("source_tree_sha256") != SOURCE_SHA256
            or result.get("binding_sha256") != _digest(admission)
            or result.get("imported_worker_sha256")
            != {
                name.removesuffix(".py"): hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
                for name in WORKER_FILES
                if name.endswith(".py") and name != "fixture_entry.py"
            }
            or result.get("checks")
            != {
                "events": ["direct_exp_gen", "coding", "running", "feedback", "record"],
                "label": expected_label,
                "metrics": [["net_return", -0.125, "fraction"], ["cost", 0.03125, "fraction"]],
            }
            or result.get("checkpoint_binding_verified") is not True
            or self.measure() != self.fingerprint
        ):
            raise DataError(
                "native synthetic result changed its admitted identity or exact mapping"
            )

        return receipt_bytes

    def command(self, admission: dict[str, object] | None) -> list[str]:
        if admission is None:
            raise DataError("native child requires its committed reservation")
        if self.measure() != self.fingerprint:
            raise DataError("native launch bytes changed after admission")
        if isinstance(self.study, DailyRuleStudyV1):
            assert self.authority is not None
            self.authority.reopen_daily_inputs()
        return [
            str(
                WORKER
                / (
                    ".venv"
                    if self.study is None
                    else ".venv-economics-qualified"
                    if isinstance(self.study, CostedRuleStudy | DailyRuleStudyV1)
                    else ".venv-rule-qualified"
                )
                / "bin/python"
            ),
            "-I",
            *(["-B"] if self.study is not None else []),
            str(WORKER / "fixture_entry.py"),
            str(self.source),
            "admitted",
            "@daily-admission.json"
            if isinstance(self.study, DailyRuleStudyV1)
            else json.dumps(admission, sort_keys=True),
        ]


def measure_native_proposal(
    source: Path,
    mode: str,
    study: SyntheticRuleStudy | CostedRuleStudy | DailyRuleStudyV1 | None = None,
) -> str:
    if not (source / "rdagent").is_dir():
        raise DataError("fixed native fixture requires pinned source")
    files = {}
    for path in sorted((source / "rdagent").rglob("*")):
        if path.is_symlink():
            raise DataError("native source symlinks are unsupported")
        if path.is_file() and "__pycache__" not in path.parts:
            files[str(path.relative_to(source))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if _digest(files) != SOURCE_SHA256:
        raise DataError("pinned native source tree mismatch")
    worker_files = {}
    for name in WORKER_FILES:
        path = WORKER / name
        if path.is_symlink():
            raise DataError("native worker source must not be a symlink")
        worker_files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    runtime = (
        ".venv"
        if study is None
        else ".venv-economics-qualified"
        if isinstance(study, CostedRuleStudy | DailyRuleStudyV1)
        else ".venv-rule-qualified"
    )
    extra: dict[str, object] = {}
    if isinstance(study, DailyRuleStudyV1):
        from alpha_cli._native_daily_rule_container import daily_container_profile
        from alpha_cli._native_daily_rule_protocol import DAILY_CHILD_ENV
        from alpha_cli._native_rule_environment import rule_implementation_fingerprints

        if daily_container_profile()["image_id"] != study.container_image_id:
            raise DataError("daily runtime image differs from exact owner-approved study")
        extra["daily_enforcement"] = {
            "approved_guard_code_sha256": rule_implementation_fingerprints(True, daily_study=study)[
                "code"
            ],
            "environment": DAILY_CHILD_ENV,
            "container_profile": daily_container_profile(),
            "container_watchdog_sha256": hashlib.sha256(
                (WORKER / "daily_container_entry.py").read_bytes()
            ).hexdigest(),
            "container_owner_sha256": hashlib.sha256(
                Path(__file__).with_name("_native_daily_rule_container.py").read_bytes()
            ).hexdigest(),
        }
    if study is not None:
        from alpha_cli._native_rule_environment import (
            COSTED_FILES,
            RULE_FILES,
            measure_rule_environment,
        )

        extra = {
            **extra,
            "rule_profile": measure_rule_environment(
                isinstance(study, CostedRuleStudy | DailyRuleStudyV1)
            ),
            "study": study.content_sha256,
        }
        for name in (
            COSTED_FILES if isinstance(study, CostedRuleStudy | DailyRuleStudyV1) else RULE_FILES
        ):
            if (WORKER / name).is_symlink():
                raise DataError("rule worker source symlink is unsupported")
        worker_files.update(
            {
                name: hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
                for name in (
                    COSTED_FILES
                    if isinstance(study, CostedRuleStudy | DailyRuleStudyV1)
                    else RULE_FILES
                )
            }
        )
    python = WORKER / runtime / "bin/python"
    return _digest(
        {
            **extra,
            "schema": "SyntheticNativeLaunchV1",
            "mode": mode,
            "source_tree_sha256": SOURCE_SHA256,
            "worker_files": worker_files,
            "python_sha256": hashlib.sha256(python.resolve().read_bytes()).hexdigest(),
            "pyvenv_sha256": hashlib.sha256(
                (WORKER / runtime / "pyvenv.cfg").read_bytes()
            ).hexdigest(),
            "authority": "none",
        }
    )
