"""Touch ID owner-presence ceremonies for the local Workstation.

This module verifies WebAuthn cryptography and persists single-use, action-bound authority in the
CLI-owned control store. It grants no broker, order, holdout, paper-entry, risk-override, or
research-gate-override capability.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, cast

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from alpha_cli.control_store import (
    OWNER_ACTION_TYPES,
    ControlStore,
    OwnerActionType,
    research_case_revision,
)
from alpha_core import DataError

OWNER_RP_ID: Final = "localhost"
OWNER_ORIGIN: Final = "http://localhost:8801"
OWNER_RP_NAME: Final = "Project ALPHA"
OWNER_USER_NAME: Final = "owner"
CHALLENGE_LIFETIME_SECONDS: Final = 60
ENROLLMENT_LIFETIME_SECONDS: Final = 300
_MAX_ACTION_JSON_BYTES: Final = 65_536


def _now() -> datetime:
    return datetime.now(UTC)


def _canonical_json(value: object, label: str) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError(f"invalid owner auth {label}") from exc
    if len(encoded.encode()) > _MAX_ACTION_JSON_BYTES:
        raise DataError(f"owner auth {label} exceeds {_MAX_ACTION_JSON_BYTES} bytes")
    return encoded


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise DataError(f"owner auth {label} must be a JSON object")
    result = dict(value)
    _canonical_json(result, label)
    return result


def _token_hash(token: str) -> str:
    if not token or len(token) > 512 or "\x00" in token:
        raise DataError("owner enrollment token is invalid")
    return hashlib.sha256(token.encode()).hexdigest()


def _credential_id(credential: Mapping[str, object]) -> str:
    value = credential.get("id")
    if not isinstance(value, str) or not value:
        raise DataError("owner WebAuthn credential id is missing")
    return value


def derive_action_artifact_hash(
    *,
    data_dir: Path,
    action_type: str,
    project_id: str,
    payload: Mapping[str, object],
) -> str:
    """Derive the immutable artifact commitment for one closed owner action."""
    clean_payload = _object(payload, "action payload")
    if action_type in {"screen_source_claim", "reject_source_claim", "revise_source_claim"}:
        identifier = clean_payload.get("claim_id")
    elif action_type in {
        "approve_exploration",
        "reject_exploration",
        "approve_confirmation",
        "reject_confirmation",
    }:
        identifier = clean_payload.get("contract_id")
    elif action_type == "freeze_source_pack":
        return hashlib.sha256(_canonical_json(clean_payload, "action payload").encode()).hexdigest()
    elif action_type in OWNER_ACTION_TYPES:
        identifier = (
            ControlStore(data_dir).research_case_summary(project_id).get("active_contract_id")
        )
    else:
        raise DataError(f"unsupported owner action type {action_type!r}")
    if not isinstance(identifier, str):
        raise DataError("owner action artifact identifier is missing")
    prefix, separator, digest = identifier.partition("_")
    if not separator or prefix not in {"sc", "rc"} or len(digest) != 64:
        raise DataError("owner action artifact is not content-addressed")
    if any(char not in "0123456789abcdef" for char in digest):
        raise DataError("owner action artifact digest must be lowercase SHA-256")
    return digest


def issue_enrollment(
    *,
    data_dir: Path,
    reason: str,
    replace_existing: bool,
    now: datetime | None = None,
) -> dict[str, object]:
    """Issue the only browser enrollment entry point from the trusted local CLI."""
    issued_at = _now() if now is None else now
    token = secrets.token_urlsafe(32)
    request = ControlStore(data_dir).create_owner_enrollment_request(
        token_hash=_token_hash(token),
        reason=reason,
        replace_existing=replace_existing,
        now=issued_at,
        expires_at=issued_at + timedelta(seconds=ENROLLMENT_LIFETIME_SECONDS),
    )
    return {
        **request,
        "url": f"{OWNER_ORIGIN}/owner-auth/enroll#token={token}",
    }


def registration_options(
    *, data_dir: Path, token: str, now: datetime | None = None
) -> dict[str, object]:
    issued_at = _now() if now is None else now
    store = ControlStore(data_dir)
    token_hash = _token_hash(token)
    enrollment = store.get_owner_enrollment_request(token_hash=token_hash, now=issued_at)
    challenge_bytes = secrets.token_bytes(32)
    challenge = store.create_owner_auth_challenge(
        ceremony="registration",
        challenge=challenge_bytes,
        binding={"token_hash": token_hash},
        enrollment_request_id=str(enrollment["request_id"]),
        now=issued_at,
        expires_at=issued_at + timedelta(seconds=CHALLENGE_LIFETIME_SECONDS),
    )
    existing = store.list_active_owner_credentials()
    options = generate_registration_options(
        rp_id=OWNER_RP_ID,
        rp_name=OWNER_RP_NAME,
        user_name=OWNER_USER_NAME,
        user_display_name="Project ALPHA owner",
        user_id=hashlib.sha256(b"project-alpha-local-owner").digest(),
        challenge=challenge_bytes,
        timeout=CHALLENGE_LIFETIME_SECONDS * 1000,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(str(item["credential_id"])))
            for item in existing
        ],
    )
    return {
        "challenge_id": challenge["challenge_id"],
        "expires_at": challenge["expires_at"],
        "public_key": json.loads(options_to_json(options)),
    }


def finish_registration(
    *,
    data_dir: Path,
    token: str,
    challenge_id: str,
    credential: Mapping[str, object],
    now: datetime | None = None,
) -> dict[str, object]:
    completed_at = _now() if now is None else now
    store = ControlStore(data_dir)
    token_hash = _token_hash(token)
    enrollment = store.get_owner_enrollment_request(token_hash=token_hash, now=completed_at)
    challenge = store.get_owner_auth_challenge(
        challenge_id, ceremony="registration", now=completed_at
    )
    if challenge["enrollment_request_id"] != enrollment["request_id"]:
        raise DataError("owner registration challenge does not match the enrollment request")
    try:
        verification = verify_registration_response(
            credential=dict(credential),
            expected_challenge=cast(bytes, challenge["challenge"]),
            expected_rp_id=OWNER_RP_ID,
            expected_origin=OWNER_ORIGIN,
            require_user_presence=True,
            require_user_verification=True,
        )
    except Exception as exc:
        raise DataError("Touch ID registration could not be verified") from exc
    response = credential.get("response")
    transports: list[str] = []
    if isinstance(response, Mapping):
        raw_transports = response.get("transports")
        if isinstance(raw_transports, list) and all(
            isinstance(item, str) for item in raw_transports
        ):
            transports = cast(list[str], raw_transports)
    return store.complete_owner_registration(
        token_hash=token_hash,
        challenge_id=challenge_id,
        credential_id=bytes_to_base64url(verification.credential_id),
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=transports,
        now=completed_at,
    )


def action_binding(
    *,
    data_dir: Path,
    action_type: str,
    project_id: str,
    artifact_hash: str,
    expected_case_revision: str,
    consequence_summary: str,
    reason: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    if action_type not in OWNER_ACTION_TYPES:
        raise DataError(f"unsupported owner action type {action_type!r}")
    store = ControlStore(data_dir)
    current_revision = research_case_revision(store.research_case_summary(project_id))
    if expected_case_revision != current_revision:
        raise DataError("research case changed; refresh before requesting Touch ID")
    if len(artifact_hash) != 64 or any(char not in "0123456789abcdef" for char in artifact_hash):
        raise DataError("owner action artifact hash must be lowercase SHA-256")
    payload_object = _object(payload, "action payload")
    return {
        "action_type": cast(OwnerActionType, action_type),
        "project_id": project_id,
        "artifact_hash": artifact_hash,
        "expected_case_revision": current_revision,
        "consequence_summary": consequence_summary,
        "reason": reason,
        "request_hash": hashlib.sha256(
            _canonical_json(payload_object, "action payload").encode()
        ).hexdigest(),
    }


def authentication_options(
    *, data_dir: Path, binding: Mapping[str, object], now: datetime | None = None
) -> dict[str, object]:
    issued_at = _now() if now is None else now
    store = ControlStore(data_dir)
    credentials = store.list_active_owner_credentials()
    challenge_bytes = secrets.token_bytes(32)
    challenge = store.create_owner_auth_challenge(
        ceremony="action",
        challenge=challenge_bytes,
        binding=binding,
        now=issued_at,
        expires_at=issued_at + timedelta(seconds=CHALLENGE_LIFETIME_SECONDS),
    )
    options = generate_authentication_options(
        rp_id=OWNER_RP_ID,
        challenge=challenge_bytes,
        timeout=CHALLENGE_LIFETIME_SECONDS * 1000,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(str(item["credential_id"])))
            for item in credentials
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return {
        "challenge_id": challenge["challenge_id"],
        "expires_at": challenge["expires_at"],
        "binding": challenge["binding"],
        "public_key": json.loads(options_to_json(options)),
    }


def verify_action_assertion(
    *,
    data_dir: Path,
    challenge_id: str,
    credential: Mapping[str, object],
    payload: Mapping[str, object],
    now: datetime | None = None,
) -> dict[str, object]:
    """Verify and consume one assertion before any action executor is called."""
    verified_at = _now() if now is None else now
    store = ControlStore(data_dir)
    challenge = store.get_owner_auth_challenge(challenge_id, ceremony="action", now=verified_at)
    binding = _object(challenge["binding"], "action binding")
    project_id = binding.get("project_id")
    expected_revision = binding.get("expected_case_revision")
    if not isinstance(project_id, str) or not isinstance(expected_revision, str):
        raise DataError("owner action binding is incomplete")
    current_revision = research_case_revision(store.research_case_summary(project_id))
    if current_revision != expected_revision:
        raise DataError("research case changed after the Touch ID challenge was issued")
    payload_hash = hashlib.sha256(
        _canonical_json(dict(payload), "action payload").encode()
    ).hexdigest()
    if payload_hash != binding.get("request_hash"):
        raise DataError("owner action payload changed after the Touch ID challenge was issued")
    credential_id = _credential_id(credential)
    active = {str(item["credential_id"]): item for item in store.list_active_owner_credentials()}
    stored = active.get(credential_id)
    if stored is None:
        raise DataError("Touch ID credential is not enrolled or has been revoked")
    current_sign_count = cast(int, stored["sign_count"])
    try:
        verification = verify_authentication_response(
            credential=dict(credential),
            expected_challenge=cast(bytes, challenge["challenge"]),
            expected_rp_id=OWNER_RP_ID,
            expected_origin=OWNER_ORIGIN,
            credential_public_key=cast(bytes, stored["public_key"]),
            credential_current_sign_count=current_sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        raise DataError("Touch ID assertion could not be verified") from exc
    assertion_hash = hashlib.sha256(
        _canonical_json(dict(credential), "assertion").encode()
    ).hexdigest()
    receipt = store.record_owner_action_authorization(
        challenge_id=challenge_id,
        credential_id=credential_id,
        previous_sign_count=current_sign_count,
        new_sign_count=verification.new_sign_count,
        assertion_hash=assertion_hash,
        outcome={"status": "assertion_consumed"},
        now=verified_at,
    )
    return {**receipt, "binding": binding}


__all__ = [
    "CHALLENGE_LIFETIME_SECONDS",
    "ENROLLMENT_LIFETIME_SECONDS",
    "OWNER_ACTION_TYPES",
    "OWNER_ORIGIN",
    "OWNER_RP_ID",
    "action_binding",
    "authentication_options",
    "derive_action_artifact_hash",
    "finish_registration",
    "issue_enrollment",
    "registration_options",
    "verify_action_assertion",
]
