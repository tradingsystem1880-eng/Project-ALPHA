"""Development-only validator for the fixed, non-executable RD-Agent foundation manifest.

This module accepts no runtime configuration and performs no I/O. Source symbols are inert
identifiers; parsing never imports or resolves them. The manifest is a review artifact, not an
ALPHA authority record or an RD-Agent adapter.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

_ALPHA_REPOSITORY = "tradingsystem1880-eng/Project-ALPHA"
_ALPHA_COMMIT = "99f2d472dd4511b446e1198ae80201e7207d089d"
_RDAGENT_REPOSITORY = "microsoft/RD-Agent"
_RDAGENT_COMMIT = "484776c211e4fbbeef03e0ec00d6bbee7362a4f4"
_SHA256 = re.compile(r"[0-9a-f]{64}")

# Five source anchors have supplied Git blob identities. proposal.py is an additional supporting
# source link but has no blob identity in the brief, so it is not claimed as a pinned inventory
# item. These strings are inert identifiers, never imports or filesystem paths.
_SOURCE_FILES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "rdagent/components/workflow/rd_loop.py",
        "f93c51f95bf24737a79a414c4e5436e4bef2a91f",
        (
            "rdagent.components.workflow.rd_loop.RDLoop",
            "rdagent.components.workflow.rd_loop.RDLoop.direct_exp_gen",
            "rdagent.components.workflow.rd_loop.RDLoop.coding",
            "rdagent.components.workflow.rd_loop.RDLoop.running",
            "rdagent.components.workflow.rd_loop.RDLoop.feedback",
            "rdagent.components.workflow.rd_loop.RDLoop.record",
        ),
    ),
    (
        "rdagent/utils/workflow/loop.py",
        "bfcb59679766ec0939a49f514c12ec2554d5cb11",
        (
            "rdagent.utils.workflow.loop.LoopBase",
            "rdagent.utils.workflow.loop.LoopMeta",
        ),
    ),
    (
        "rdagent/core/evaluation.py",
        "07783067494b95bb8a3a00de83d3667fd37aabf8",
        ("rdagent.core.evaluation.Feedback",),
    ),
    (
        "rdagent/core/scenario.py",
        "b333c069b16c383248b700e5530536edd6daeb78",
        ("rdagent.core.scenario.Scenario",),
    ),
    (
        "rdagent/core/experiment.py",
        "e77e15b2ef75a7d46072c5e0b06ccf1c7e05d7ef",
        (
            "rdagent.core.experiment.Experiment",
            "rdagent.core.experiment.ExperimentPlan",
            "rdagent.core.experiment.Task",
            "rdagent.core.experiment.Workspace",
        ),
    ),
)

_STAGES = ("direct_exp_gen", "coding", "running", "feedback", "record")


class ManifestValidationError(ValueError):
    """The input does not match the one fixed preparatory manifest contract."""


def _manifest_payload() -> dict[str, object]:
    """Return a fresh JSON-shaped copy of the fixed semantic payload."""
    return {
        "schema": "RDNativeFoundationManifestV1",
        "schema_version": 1,
        "authority": "none",
        "purpose": "preparatory_contract",
        "execution_enabled": False,
        "native_runtime_qualification": "not_run",
        "source_revisions": {
            "alpha": {"repository": _ALPHA_REPOSITORY, "commit": _ALPHA_COMMIT},
            "rd_agent": {"repository": _RDAGENT_REPOSITORY, "commit": _RDAGENT_COMMIT},
        },
        "source_inventory": [
            {"path": path, "git_blob_sha": blob, "symbols": list(symbols)}
            for path, blob, symbols in _SOURCE_FILES
        ],
        "intended_native_primitive": {
            "loop_base": "rdagent.utils.workflow.loop.LoopBase",
            "loop_metaclass": "rdagent.utils.workflow.loop.LoopMeta",
            "stages": list(_STAGES),
        },
        "authority_map": {
            "scientific_continuation": "rdagent_native_extension",
            "permission_revision_reservation_attempt_budgets": "alpha_cli_control_store",
            "data_snapshots_execution_results_evidence": (
                "existing_alpha_data_engine_evidence_services"
            ),
            "d1_launch_d2_closure_promotion": "human_owner_actions",
            "native_trace_checkpoints": "derived_references_only",
        },
        "contract_roles": {
            "workspace_reference": "StudyWorkspaceManifestV1",
            "d1_mandate_reference": "ExplorationMandateV1",
            "artifact_reference": "ResearchArtifactRef",
            "intermediate_feedback": "not_defined",
            "terminal_report": "ResearchGatePacketV1",
        },
    }


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _assert_exact(actual: object, expected: object, path: str) -> None:
    if type(expected) is dict:
        if type(actual) is not dict:
            raise ManifestValidationError(f"{path} must be an object")
        expected_keys = set(expected)
        actual_keys = set(actual)
        if actual_keys != expected_keys:
            missing = sorted(repr(key) for key in expected_keys - actual_keys)
            extra = sorted(repr(key) for key in actual_keys - expected_keys)
            raise ManifestValidationError(f"{path} keys differ; missing={missing}, extra={extra}")
        for key, expected_value in expected.items():
            _assert_exact(actual[key], expected_value, f"{path}.{key}")
        return
    if type(expected) is list:
        if type(actual) is not list or len(actual) != len(expected):
            raise ManifestValidationError(f"{path} must be a list of length {len(expected)}")
        for index, (actual_value, expected_value) in enumerate(zip(actual, expected, strict=True)):
            _assert_exact(actual_value, expected_value, f"{path}[{index}]")
        return
    if type(actual) is not type(expected) or actual != expected:
        raise ManifestValidationError(f"{path} does not match the pinned contract")


@dataclass(frozen=True, slots=True)
class RDNativeFoundationManifestV1:
    """Immutable handle for the one reviewed, data-only foundation declaration."""

    content_sha256: str

    def __post_init__(self) -> None:
        if type(self.content_sha256) is not str or _SHA256.fullmatch(self.content_sha256) is None:
            raise ManifestValidationError("content_sha256 must be a lowercase SHA-256 digest")
        if self.content_sha256 != _canonical_sha256(_manifest_payload()):
            raise ManifestValidationError("content_sha256 does not match the fixed manifest")

    def to_dict(self) -> dict[str, object]:
        payload = _manifest_payload()
        payload["content_sha256"] = self.content_sha256
        return payload

    def canonical_json(self) -> str:
        """Serialize the complete immutable manifest with ALPHA's canonical JSON convention."""
        return _canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> RDNativeFoundationManifestV1:
        if type(value) is not dict:
            raise ManifestValidationError("manifest must be a JSON object")
        expected = _manifest_payload()
        expected_keys = set(expected) | {"content_sha256"}
        actual_keys = set(value)
        if actual_keys != expected_keys:
            missing = sorted(repr(key) for key in expected_keys - actual_keys)
            extra = sorted(repr(key) for key in actual_keys - expected_keys)
            raise ManifestValidationError(f"manifest keys differ; missing={missing}, extra={extra}")

        digest = value["content_sha256"]
        if type(digest) is not str or _SHA256.fullmatch(digest) is None:
            raise ManifestValidationError("content_sha256 must be a lowercase SHA-256 digest")
        unsigned = {key: value[key] for key in expected}
        _assert_exact(unsigned, expected, "manifest")
        if digest != _canonical_sha256(unsigned):
            raise ManifestValidationError("content_sha256 does not match the semantic payload")
        return cls(digest)


def validate_manifest(value: object) -> RDNativeFoundationManifestV1:
    """Strictly parse the fixed disabled manifest without resolving any referenced contract."""
    return RDNativeFoundationManifestV1.from_dict(value)
