"""Exact-origin Touch ID ceremonies for closed research-lifecycle owner actions."""

from __future__ import annotations

import json
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException
from pydantic import Field

from alpha_cli.owner_auth import (
    OWNER_ACTION_TYPES,
    action_binding,
    authentication_options,
    derive_action_artifact_hash,
    finish_registration,
    registration_options,
    verify_action_assertion,
)
from alpha_core import DataError
from alpha_web._catalog import _run_json
from alpha_web.api._common import data_dir
from alpha_web.api.models import StrictModel

router = APIRouter(prefix="/api/owner-auth", tags=["owner-auth"])


class OwnerRegistrationStart(StrictModel):
    token: str = Field(min_length=20, max_length=512)


class OwnerRegistrationFinish(OwnerRegistrationStart):
    challenge_id: str
    credential: dict[str, Any]


class OwnerActionChallengeRequest(StrictModel):
    action_type: Literal[
        "screen_source_claim",
        "reject_source_claim",
        "revise_source_claim",
        "freeze_source_pack",
        "approve_exploration",
        "reject_exploration",
        "revise_exploration",
        "launch_d1",
        "approve_confirmation",
        "reject_confirmation",
        "launch_d2",
        "record_final_disposition",
        "record_semantic_event",
    ]
    project_id: str
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_case_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    consequence_summary: str = Field(min_length=1, max_length=2_000)
    reason: str = Field(min_length=1, max_length=8_192)
    payload: dict[str, Any]


class OwnerActionPerformRequest(StrictModel):
    challenge_id: str
    credential: dict[str, Any]
    payload: dict[str, Any]


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value or "\x00" in value:
        raise DataError(f"owner action payload requires {key}")
    return value


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise DataError(f"owner action payload requires a non-empty {key} list")
    return cast(list[str], value)


def _action_argv(
    *,
    action_type: str,
    project_id: str,
    payload: dict[str, Any],
    actor: str,
    reason: str,
) -> list[str]:
    if action_type == "record_semantic_event":
        raise DataError("semantic owner action is not a CLI action")
    if action_type == "screen_source_claim":
        return [
            "research",
            "sources",
            "claim",
            "screen",
            project_id,
            _string(payload, "claim_id"),
            "--actor",
            actor,
            "--json",
        ]
    if action_type in {"reject_source_claim", "revise_source_claim"}:
        verb = "reject" if action_type == "reject_source_claim" else "revise"
        args = [
            "research",
            "sources",
            "claim",
            verb,
            project_id,
            _string(payload, "claim_id"),
            "--actor",
            actor,
            "--reason",
            reason,
        ]
        if verb == "revise":
            revision = payload.get("revision", {})
            if not isinstance(revision, dict):
                raise DataError("owner claim revision payload must be an object")
            args += ["--revision-json", _canonical_json(revision)]
        return [*args, "--json"]
    if action_type == "freeze_source_pack":
        args = ["research", "sources", "freeze", project_id]
        for source_id in _string_list(payload, "source_ids"):
            args += ["--source-id", source_id]
        definition = payload.get("definition", {})
        if not isinstance(definition, dict):
            raise DataError("owner source-pack definition must be an object")
        return [*args, "--definition-json", _canonical_json(definition), "--json"]
    if action_type in {
        "approve_exploration",
        "reject_exploration",
        "approve_confirmation",
        "reject_confirmation",
    }:
        decision, scope = action_type.split("_", 1)
        return [
            "research",
            decision,
            scope,
            project_id,
            _string(payload, "contract_id"),
            "--actor",
            actor,
            "--reason",
            reason,
            "--json",
        ]
    if action_type == "revise_exploration":
        args = [
            "research",
            "revise",
            project_id,
            "--source-pack-id",
            _string(payload, "source_pack_id"),
            "--actor",
            actor,
            "--reason",
            reason,
        ]
        answers = payload.get("answers")
        if not isinstance(answers, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in answers.items()
        ):
            raise DataError("owner exploration revision requires an answers object")
        for key, value in sorted(answers.items()):
            args += ["--answer", f"{key}={value}"]
        dataset = payload.get("dataset")
        if dataset is not None:
            if not isinstance(dataset, str) or not dataset:
                raise DataError("owner exploration revision dataset is invalid")
            args += ["--dataset", dataset]
        return [*args, "--json"]
    if action_type == "launch_d1":
        return ["research", "run", "deep", project_id, "--json"]
    if action_type == "launch_d2":
        return ["research", "run", "confirm", project_id, "--json"]
    if action_type == "record_final_disposition":
        return [
            "research",
            "decide",
            project_id,
            "--outcome",
            _string(payload, "outcome"),
            "--disposition",
            _string(payload, "disposition"),
            "--actor",
            actor,
            "--reason",
            reason,
            "--json",
        ]
    raise DataError(f"unsupported owner action type {action_type!r}")


@router.post("/enrollment/options")
def start_registration(body: OwnerRegistrationStart) -> dict[str, object]:
    try:
        return registration_options(data_dir=data_dir(), token=body.token)
    except (DataError, RuntimeError, OSError) as exc:
        raise _bad_request(exc) from exc


@router.post("/enrollment/finish")
def complete_registration(body: OwnerRegistrationFinish) -> dict[str, object]:
    try:
        return finish_registration(
            data_dir=data_dir(),
            token=body.token,
            challenge_id=body.challenge_id,
            credential=body.credential,
        )
    except (DataError, RuntimeError, OSError) as exc:
        raise _bad_request(exc) from exc


@router.post("/actions/challenge")
def start_action(body: OwnerActionChallengeRequest) -> dict[str, object]:
    try:
        if body.action_type not in OWNER_ACTION_TYPES:  # defensive drift guard
            raise DataError("unsupported owner action")
        derived_hash = derive_action_artifact_hash(
            data_dir=data_dir(),
            action_type=body.action_type,
            project_id=body.project_id,
            payload=body.payload,
        )
        if derived_hash != body.artifact_hash:
            raise DataError("owner action artifact hash does not match the exact payload")
        binding = action_binding(
            data_dir=data_dir(),
            action_type=body.action_type,
            project_id=body.project_id,
            artifact_hash=derived_hash,
            expected_case_revision=body.expected_case_revision,
            consequence_summary=body.consequence_summary,
            reason=body.reason,
            payload=body.payload,
        )
        return authentication_options(data_dir=data_dir(), binding=binding)
    except (DataError, RuntimeError, OSError) as exc:
        raise _bad_request(exc) from exc


@router.post("/actions/perform")
def perform_action(body: OwnerActionPerformRequest) -> dict[str, object]:
    """Consume one fresh assertion, then execute only its server-derived closed action."""
    try:
        authorization = verify_action_assertion(
            data_dir=data_dir(),
            challenge_id=body.challenge_id,
            credential=body.credential,
            payload=body.payload,
        )
        binding = cast(dict[str, object], authorization["binding"])
        action_type = str(binding["action_type"])
        if action_type == "record_semantic_event":
            return {"authorization": authorization, "result": authorization}
        project_id = str(binding["project_id"])
        argv = _action_argv(
            action_type=action_type,
            project_id=project_id,
            payload=body.payload,
            actor=str(authorization["actor"]),
            reason=str(binding["reason"]),
        )
        result = _run_json(argv, data_dir=data_dir(), timeout_seconds=3_600)
        return {"authorization": authorization, "result": result}
    except (DataError, RuntimeError, OSError) as exc:
        raise _bad_request(exc) from exc


__all__ = ["router"]
