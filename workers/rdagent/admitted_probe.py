"""Fixed child operator for the supervisor-owned synthetic admission probe."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

from conformance import _completed, _reject
from fixture_owner import FixtureOwner
from native_fixture import LABELS, NativeFixtureLoop


async def _run(admission: dict[str, object]) -> dict[str, object]:
    rule = admission.get("rule_request")
    extra = (
        {"rule_request", "rule_profile", "study_id", "trial_id", "owner_receipt_id"}
        if rule is not None
        else set()
    )
    if admission.get("schema") == "DailyNativeAdmissionV1":
        daily_fields = {
            "query_sha256",
            "cpu_milliseconds",
            "container_name",
            "image_id",
            "resource_fingerprint",
            "container_id",
            "deadline_monotonic_ns",
        }
        deadline = admission.get("deadline_monotonic_ns")
        if (
            not daily_fields.issubset(admission)
            or any(
                type(admission.get(key)) is not str or not admission[key]
                for key in ("container_name", "image_id", "resource_fingerprint", "container_id")
            )
            or type(deadline) is not int
            or deadline <= 0
        ):
            raise ValueError(
                "daily admission requires exact container and original deadline bindings"
            )
        extra.update(daily_fields)
    if set(admission) - extra != {
        "schema",
        "job_id",
        "reservation_id",
        "spec_sha256",
        "manifest_sha256",
        "owner_id",
        "mode",
        "loop_steps",
    } or admission["schema"] not in {"SyntheticNativeAdmissionV1", "DailyNativeAdmissionV1"}:
        raise ValueError("invalid synthetic admission identity")
    if Path.cwd().name != f"payload-{admission['job_id']}":
        raise ValueError("admitted native job/workspace mismatch")
    allowance = admission["loop_steps"]
    if type(allowance) is not int or allowance < 0:
        raise ValueError("invalid reserved loop allowance")
    mode = str(admission["mode"])
    if mode not in {*LABELS, "resume", "wait", "failure", "foreign_binding"}:
        raise ValueError("invalid fixed admitted mode")
    binding = hashlib.sha256(
        json.dumps(admission, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    owner = FixtureOwner(
        label=mode if mode in LABELS else "INCONCLUSIVE",
        allowance=min(5, allowance),
        admission_binding=binding,
    )
    if rule is not None:
        if not isinstance(rule, dict) or not isinstance(admission.get("rule_profile"), str):
            raise ValueError("invalid fixed rule admission")
        owner.loop.rule_request = rule
        owner.loop.rule_profile = str(admission["rule_profile"])
    (Path.cwd() / "payload.pid").write_text(str(os.getpid()))
    owner.fail_in_running = mode == "failure"
    try:
        costed = isinstance(rule, dict) and rule["study"].get("schema") in {
            "FrozenRuleCostedReplaySyntheticV1",
            "FrozenDailyRuleStudyV1",
        }
        checkpoint = await owner.start(step_n=3 if costed else 1)
        assert checkpoint is not None
        checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        restored = NativeFixtureLoop.load(checkpoint, checkout=False, replace_timer=False)
        assert type(restored) is NativeFixtureLoop
        assert restored.admission_binding == binding
        await _reject(owner.start(), "duplicate native start")
        await _reject(
            FixtureOwner(admission_binding="foreign").resume(checkpoint), "stale or foreign"
        )
        if mode == "foreign_binding":
            owner.admission_binding = "another-admitted-run"
        if mode in {"resume", "wait"}:
            owner.wait_in_running = True
            continuation = asyncio.create_task(owner.resume(checkpoint))
            await asyncio.wait_for(owner.running_entered.wait(), timeout=2)
            await _reject(owner.resume(checkpoint), "concurrent native continuation")
            (Path.cwd() / "running.ready").write_text(binding)
            if mode == "resume":
                owner.running_release.set()
            await continuation
        else:
            await owner.resume(checkpoint)
        result = _completed(owner) if rule is None else {"events": owner.loop.events}
        raw_result = owner.loop.trace.hist[-1][0].result
        if costed and not isinstance(raw_result, dict):
            raise ValueError("costed native checkpoint result must be a canonical mapping")
        rule_result = (
            {}
            if rule is None
            else (
                {"rule_positions": raw_result["positions"], "economics": raw_result["economics"]}
                if costed and isinstance(raw_result, dict)
                else {"rule_positions": raw_result}
            )
        )
        await _reject(owner.resume(checkpoint), "closed fixture")
        assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == checkpoint_hash
        return {
            **rule_result,
            "admission": admission,
            "binding_sha256": binding,
            "checks": result,
            "checkpoint_sha256": checkpoint_hash,
            "checkpoint_binding_verified": True,
            "duplicate_resume_rejected": True,
            "concurrent_resume_rejected": mode == "resume",
            "scientific_acceptance": "not_admitted",
            "routes_enabled": False,
        }
    finally:
        (Path.cwd() / "progress.json").write_text(
            json.dumps(
                {
                    "admission": admission,
                    "charged_stages": owner.charges,
                    "completed_stages": owner.loop.events,
                    "closed": owner.closed,
                },
                sort_keys=True,
            )
        )


def probe(admission: dict[str, object]) -> dict[str, object]:
    return asyncio.run(_run(admission))
