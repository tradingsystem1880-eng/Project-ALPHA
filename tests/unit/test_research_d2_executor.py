"""The one-shot sealed D2 confirmation executor (spec §10, ADR-0026).

End-to-end over the registered Gate-4 daily lane: sealed-share-only execution,
mechanically derived classification/checks/claim, honest insufficient-event packets,
deterministic re-publication, final-holdout future-poison immunity, and admission-time
mechanical re-verification (producer flags never authority).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from alpha_cli.research_d2 import (
    D2_ANALYSES_ARTIFACT,
    D2_EVIDENCE_ARTIFACT,
    d2_execution_fingerprint,
    derive_d2_findings,
    run_confirmation,
    validate_d2_evidence_artifacts,
)
from alpha_core import DataError
from alpha_research import confirmation_classification_from_evidence
from tests.unit.test_research_gate4_lane import (
    _MOTIF,
    _empirical_contract,
    _registered_daily_ref,
    _sealed_boundary,
)

PROJECT_ID = "9e4908b1-a9cd-4c13-a47e-740d92175680"
CONTRACT_ID = "rc_" + "c" * 64


def _varied_daily_lows(blocks: int = 50) -> list[float]:
    lows: list[float] = []
    for block in range(blocks):
        lows.extend(_MOTIF)
        level = _MOTIF[-1]
        rise = 8.0 + 0.5 * (block % 5)
        for day in range(1):
            level = level + rise if day == 0 else level
            lows.append(level)
        lows.extend([100.0] * (block % 3))
    return lows


def _discovery_only_lows(blocks: int = 20) -> list[float]:
    """Motifs only inside the discovery share; the sealed share holds no events."""
    lows: list[float] = []
    for block in range(blocks):
        if block < 10:
            lows.extend(_MOTIF)
            level = _MOTIF[-1]
            rise = 1.2 + 0.15 * (block % 5)
            for day in range(14):
                level = level + rise if day < 4 else level
                lows.append(level)
            lows.extend([100.0] * 6)
        else:
            lows.extend([100.0] * 30)
    return lows


def _confirmation_contract(
    ref: dict[str, object], bars: Any, *, horizon_bars: int = 1
) -> dict[str, Any]:
    """A confirmation contract shaped exactly like the R6c drafting output."""
    contract = _empirical_contract(ref, bars)
    contract["scope"] = "confirmation"
    contract["parent_contract_id"] = "rc_" + "b" * 64
    contract["analysis_plan"] = {
        "schema": "ResearchAnalysisPlanV1",
        "families": [
            {
                "family": "event_study",
                "multiplicity": "primary",
                "rationale": "The one-shot D2 confirmation tests only the frozen primary.",
                "grid": {"horizon_bars": [horizon_bars]},
            }
        ],
    }
    contract["confirmation"] = {
        "variant_count": 1,
        "multiplicity_count": 1,
        "familywise_alpha": 0.05,
        "target_power": 0.90,
        "power_report": {"achieved_power": 0.95},
        "fingerprints": {"code": "git:a1b2c3d4e5f60718"},
    }
    return contract


def _prepared(tmp_path: Path, lows: list[float]) -> tuple[dict[str, Any], Any, Any]:
    ref = _registered_daily_ref(tmp_path, lows)
    from alpha_cli.research_d1 import load_registered_research_bars

    bars = load_registered_research_bars(tmp_path, ref=ref)
    contract = _confirmation_contract(dict(ref), bars)
    return contract, bars, _sealed_boundary(contract)


def _evidence(tmp_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    path = tmp_path / "runs" / str(manifest["run_id"]) / D2_EVIDENCE_ARTIFACT
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_one_shot_confirmation_supports_the_planted_claim_on_the_sealed_share(
    tmp_path: Path,
) -> None:
    contract, bars, boundary = _prepared(tmp_path, _varied_daily_lows())
    manifest = run_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    assert manifest["command"] == "research_confirm"
    assert manifest["evidence_zone"] == "D2"
    assert manifest["watermark"] == "REGISTERED CONFIRMATORY"
    assert manifest["real_market_evidence"] is True
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["places_orders"] is False
    assert manifest["dataset_hash"] == bars.dataset.content_sha256
    evidence = _evidence(tmp_path, manifest)
    assert evidence["confirmation_classification"] == "SUPPORTED"
    checks = evidence["confirmation_checks"]
    assert checks["corrected_primary_test_passed"] is True
    assert checks["economic_hurdle_cleared"] is True
    assert checks["interval_wholly_against_direction"] is False
    claim = evidence["confirmation_claim"]
    assert claim["direction"] == "positive"
    assert claim["alpha"] == 0.05
    assert claim["minimum_effect"] == 0.005
    # The gate-packet numeric binder accepts and reclassifies the exact same bytes.
    assert confirmation_classification_from_evidence(evidence) == "SUPPORTED"
    rendered = tmp_path / "runs" / str(manifest["run_id"]) / "d2-one-shot-confirmation.png"
    assert b"REGISTERED CONFIRMATORY" in rendered.read_bytes()


def test_empty_sealed_share_is_honestly_inconclusive_without_a_claim(tmp_path: Path) -> None:
    contract, bars, boundary = _prepared(tmp_path, _discovery_only_lows())
    manifest = run_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    evidence = _evidence(tmp_path, manifest)
    assert evidence["primary_result"]["status"] == "NOT_TESTED"
    assert evidence["confirmation_classification"] == "INCONCLUSIVE"
    assert "confirmation_claim" not in evidence
    assert confirmation_classification_from_evidence(evidence) == "INCONCLUSIVE"


def test_reruns_republish_identically(tmp_path: Path) -> None:
    contract, bars, boundary = _prepared(tmp_path, _varied_daily_lows())
    first = run_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    second = run_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    assert first == second


@pytest.mark.bias_guard
def test_confirmation_never_reads_the_final_holdout(tmp_path: Path) -> None:
    """Rewriting D3 sessions must not change any sealed-confirmation measurement."""
    lows = _varied_daily_lows()
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    contract, bars, boundary = _prepared(clean_dir, lows)
    manifest = run_confirmation(
        clean_dir,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    clean_analyses = (
        clean_dir / "runs" / str(manifest["run_id"]) / D2_ANALYSES_ARTIFACT
    ).read_bytes()
    stop = json.loads(clean_analyses)["measurements"]["topology"]["confirmation_stop"]

    poisoned_dir = tmp_path / "poisoned"
    poisoned_dir.mkdir()
    poisoned_lows = [*lows[:stop], *([5_000.0] * (len(lows) - stop))]
    poisoned_contract, poisoned_bars, poisoned_boundary = _prepared(poisoned_dir, poisoned_lows)
    poisoned_manifest = run_confirmation(
        poisoned_dir,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=poisoned_contract,
        bars=poisoned_bars,
        boundary=poisoned_boundary,
    )
    poisoned_analyses = (
        poisoned_dir / "runs" / str(poisoned_manifest["run_id"]) / D2_ANALYSES_ARTIFACT
    ).read_bytes()
    assert poisoned_analyses == clean_analyses


def test_confirmation_rejects_drifted_data_or_synthetic_authority(tmp_path: Path) -> None:
    contract, bars, boundary = _prepared(tmp_path, _varied_daily_lows())
    hashes = cast(dict[str, object], contract["hashes"])
    drifted = dict(contract)
    drifted["hashes"] = {**hashes, "data": "f" * 64}
    with pytest.raises(DataError, match="approval-frozen confirmation data hash"):
        run_confirmation(
            tmp_path,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=drifted,
            bars=bars,
            boundary=boundary,
        )
    synthetic = json.loads(json.dumps(contract))
    synthetic["protocol"]["boundary_authority"] = {
        "kind": "synthetic_acceptance_fixture",
        "real_market_evidence": False,
        "empirical_confirmation_authorized": False,
    }
    with pytest.raises(DataError, match="cannot authorize D2"):
        run_confirmation(
            tmp_path,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=synthetic,
            bars=bars,
            boundary=boundary,
        )
    exploration = dict(contract)
    exploration["scope"] = "exploration"
    with pytest.raises(DataError, match="approved confirmation contract"):
        run_confirmation(
            tmp_path,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=exploration,
            bars=bars,
            boundary=boundary,
        )


def _copy(contract: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(contract)))


def test_fingerprint_rejects_every_unfrozen_contract_mutation(tmp_path: Path) -> None:
    """d2_execution_fingerprint validates the complete frozen contract before hashing."""
    contract, _, _ = _prepared(tmp_path, _discovery_only_lows())
    assert len(d2_execution_fingerprint(contract)) == 64

    def set_schema(c: dict[str, Any]) -> None:
        c["schema"] = "ResearchContractV2"

    def unset_ready(c: dict[str, Any]) -> None:
        c["approval_ready"] = False

    def add_blocking(c: dict[str, Any]) -> None:
        c["blocking_questions"] = ["which venue?"]

    def drop_confirmation(c: dict[str, Any]) -> None:
        del c["confirmation"]

    def two_variants(c: dict[str, Any]) -> None:
        c["confirmation"]["variant_count"] = 2

    def loose_alpha(c: dict[str, Any]) -> None:
        c["confirmation"]["familywise_alpha"] = 0.10

    def drop_data_hash(c: dict[str, Any]) -> None:
        c["hashes"] = {}

    def strip_detector(c: dict[str, Any]) -> None:
        del c["protocol"]["d0_operator"]["operator"]["spec"]["min_rebound"]

    def two_families(c: dict[str, Any]) -> None:
        families = c["analysis_plan"]["families"]
        families.append(dict(families[0]))

    def wrong_family(c: dict[str, Any]) -> None:
        c["analysis_plan"]["families"][0]["family"] = "information_coefficient"

    def two_horizons(c: dict[str, Any]) -> None:
        c["analysis_plan"]["families"][0]["grid"]["horizon_bars"] = [1, 2]

    cases = [
        ("requires ResearchContractV1", set_schema),
        ("approval_ready=true", unset_ready),
        ("no blocking questions", add_blocking),
        ("frozen confirmation object", drop_confirmation),
        ("one-variant confirmation family", two_variants),
        ("0.05 alpha and 0.90 target power", loose_alpha),
        ("approval-frozen dataset hash", drop_data_hash),
        ("frozen registered detector spec", strip_detector),
        ("single primary family plan", two_families),
        ("one frozen primary event_study family", wrong_family),
        ("exactly one frozen primary horizon", two_horizons),
    ]
    for match, mutate in cases:
        mutated = _copy(contract)
        mutate(mutated)
        with pytest.raises(DataError, match=match):
            d2_execution_fingerprint(mutated)


def test_claim_resolution_rejects_malformed_primary_claims(tmp_path: Path) -> None:
    from alpha_cli.research_d2 import _claim

    contract, _, _ = _prepared(tmp_path, _discovery_only_lows())

    def drop_claim(c: dict[str, Any]) -> None:
        del c["primary_claim"]

    def sideways(c: dict[str, Any]) -> None:
        c["primary_claim"]["direction"] = "sideways"

    def negative_minimum(c: dict[str, Any]) -> None:
        c["primary_claim"]["minimum_effect_return"] = -0.01

    def loose_alpha(c: dict[str, Any]) -> None:
        c["confirmation"]["familywise_alpha"] = 0.75

    def scalar_confounders(c: dict[str, Any]) -> None:
        c["confounders"] = "weekday"

    cases = [
        ("one resolved primary claim", drop_claim),
        ("positive or negative", sideways),
        ("non-negative minimum_effect_return", negative_minimum),
        (r"familywise alpha must lie in \(0, 0.5\)", loose_alpha),
        ("list of strings", scalar_confounders),
    ]
    for match, mutate in cases:
        mutated = _copy(contract)
        mutate(mutated)
        with pytest.raises(DataError, match=match):
            _claim(mutated)


def _matched_measurements(
    estimate: float,
    ci_lower: float,
    ci_upper: float,
    p_value: float,
    *,
    low_cluster_count: bool = False,
) -> dict[str, Any]:
    return {
        "counts": {"events": 12, "controls": 40},
        "matched": {
            "estimate": estimate,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "p_value": p_value,
            "confidence": 0.95,
            "sample_size": 52,
            "effective_event_count": 6 if low_cluster_count else 12,
            "low_cluster_count": low_cluster_count,
        },
        "matched_pairs": 12,
        "unadjusted": None,
    }


def test_mechanical_classifier_covers_negative_claims_and_contradiction() -> None:
    negative_claim = {
        "direction": "negative",
        "minimum_effect_return": 0.005,
        "alpha": 0.05,
        "confounders": ["calendar and day of week", "volatility regime"],
    }
    clears = derive_d2_findings(
        _matched_measurements(-0.02, -0.03, -0.01, 0.001), claim=negative_claim
    )
    assert clears["confirmation_classification"] == "SUPPORTED"
    assert clears["primary_result"]["practical_magnitude"]["status"] == "CLEARS_HURDLE"
    assert clears["confirmation_checks"]["interval_registered_direction"] is True
    assert clears["confounders"]["resolved"] == ["calendar and day of week"]
    assert clears["confounders"]["unresolved"] == ["volatility regime"]

    below = derive_d2_findings(
        _matched_measurements(-0.002, -0.004, -0.001, 0.01), claim=negative_claim
    )
    assert below["primary_result"]["practical_magnitude"]["status"] == "BELOW_HURDLE"
    assert below["confirmation_checks"]["economic_hurdle_cleared"] is False

    straddling = derive_d2_findings(
        _matched_measurements(-0.004, -0.02, 0.01, 0.3), claim=negative_claim
    )
    assert straddling["primary_result"]["practical_magnitude"]["status"] == "INCONCLUSIVE"

    contradicted = derive_d2_findings(
        _matched_measurements(0.02, 0.01, 0.03, 0.9), claim=negative_claim
    )
    assert contradicted["confirmation_classification"] == "CONTRADICTED"
    assert contradicted["confirmation_checks"]["interval_wholly_against_direction"] is True
    assert "wholly against the registered claim" in str(contradicted["strongest_contradiction"])

    positive_claim = {**negative_claim, "direction": "positive"}
    positive_below = derive_d2_findings(
        _matched_measurements(0.002, 0.001, 0.004, 0.01), claim=positive_claim
    )
    assert positive_below["primary_result"]["practical_magnitude"]["status"] == "BELOW_HURDLE"

    low_clusters = derive_d2_findings(
        _matched_measurements(0.02, 0.01, 0.03, 0.001, low_cluster_count=True),
        claim=positive_claim,
    )
    assert low_clusters["confirmation_classification"] == "INCONCLUSIVE"
    assert low_clusters["power"]["status"] == "INCONCLUSIVE"
    assert low_clusters["promotion_readiness"]["state"] == "blocked"
    assert {blocker["code"] for blocker in low_clusters["promotion_readiness"]["blockers"]} == {
        "confirmation_not_supported",
        "power_not_passed",
    }
    assert "below the ten-cluster reliability floor" in str(low_clusters["power"]["summary"])

    with pytest.raises(DataError, match="registered claim direction"):
        derive_d2_findings(_matched_measurements(0.0, 0.0, 0.0, 1.0), claim={"direction": "up"})
    with pytest.raises(DataError, match="frozen claim hurdle"):
        derive_d2_findings(
            _matched_measurements(0.0, 0.0, 0.0, 1.0),
            claim={**positive_claim, "minimum_effect_return": True},
        )
    with pytest.raises(DataError, match="finite and JSON-compatible"):
        from alpha_cli.research_d2 import _canonical

        _canonical(float("nan"))


def test_run_confirmation_rejects_identity_and_boundary_mismatches(tmp_path: Path) -> None:
    contract, bars, boundary = _prepared(tmp_path / "a", _varied_daily_lows())
    with pytest.raises(DataError, match="canonical project_id"):
        run_confirmation(
            tmp_path / "a",
            project_id="not-a-uuid",
            contract_id=CONTRACT_ID,
            contract=contract,
            bars=bars,
            boundary=boundary,
        )
    with pytest.raises(DataError, match="content-addressed contract_id"):
        run_confirmation(
            tmp_path / "a",
            project_id=PROJECT_ID,
            contract_id="rc_short",
            contract=contract,
            bars=bars,
            boundary=boundary,
        )
    # A sealed boundary from a DIFFERENT registered dataset can never authorize this share.
    _, _, foreign_boundary = _prepared(tmp_path / "b", _discovery_only_lows())
    with pytest.raises(DataError, match="sealed boundary dataset fingerprint"):
        run_confirmation(
            tmp_path / "a",
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
            bars=bars,
            boundary=foreign_boundary,
        )


def test_uncomputable_frozen_statistic_is_recorded_honestly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The D1 skipped-family pattern: a statistic failure becomes NOT_TESTED, never a crash."""
    import alpha_cli.research_d2 as research_d2

    contract, bars, boundary = _prepared(tmp_path, _varied_daily_lows())

    def explode(*args: object, **kwargs: object) -> object:
        raise DataError("simulated degenerate matched statistic")

    monkeypatch.setattr(research_d2, "evaluate_matched_association", explode)
    manifest = run_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    analyses = json.loads((run_dir / D2_ANALYSES_ARTIFACT).read_text(encoding="utf-8"))
    measurements = analyses["measurements"]
    assert measurements["matched"] is None
    assert measurements["unadjusted"] is None
    assert measurements["statistic_error"] == "simulated degenerate matched statistic"
    evidence = _evidence(tmp_path, manifest)
    assert evidence["primary_result"]["status"] == "NOT_TESTED"
    assert evidence["confirmation_classification"] == "INCONCLUSIVE"
    verified = validate_d2_evidence_artifacts(
        run_dir,
        manifest,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )
    assert verified["confirmation_classification"] == "INCONCLUSIVE"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _doctored_manifest(manifest: dict[str, Any], path: Path, content: bytes) -> dict[str, Any]:
    """A forged manifest whose artifact hash matches rewritten bytes on disk."""
    import hashlib

    doctored = cast(dict[str, Any], json.loads(json.dumps(manifest)))
    doctored["artifacts"][path.name]["sha256"] = hashlib.sha256(content).hexdigest()
    path.write_bytes(content)
    return doctored


def test_admission_rejects_manifest_identity_mismatches(tmp_path: Path) -> None:
    contract, bars, boundary = _prepared(tmp_path, _discovery_only_lows())
    manifest = run_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])

    def check(doctored: dict[str, Any], match: str, **ids: str) -> None:
        with pytest.raises(DataError, match=match):
            validate_d2_evidence_artifacts(
                run_dir,
                doctored,
                project_id=ids.get("project_id", PROJECT_ID),
                contract_id=ids.get("contract_id", CONTRACT_ID),
                contract=contract,
            )

    check({**manifest, "command": "backtest"}, "research_confirm D2 manifest")
    check(manifest, "project does not match", project_id="9e4908b1-a9cd-4c13-a47e-740d92175681")
    check(manifest, "contract does not match", contract_id="rc_" + "d" * 64)
    check({**manifest, "d2_evidence_artifact": "other.json"}, "typed evidence artifact")
    stripped = cast(dict[str, Any], json.loads(json.dumps(manifest)))
    del stripped["artifacts"][D2_ANALYSES_ARTIFACT]
    check(stripped, "does not declare immutable artifact")


def test_admission_rejects_every_tampered_artifact_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alpha_cli.research_d2 as research_d2

    contract, bars, boundary = _prepared(tmp_path, _varied_daily_lows())
    manifest = run_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    analyses_path = run_dir / D2_ANALYSES_ARTIFACT
    evidence_path = run_dir / D2_EVIDENCE_ARTIFACT
    original_analyses = analyses_path.read_bytes()
    original_evidence = evidence_path.read_bytes()
    analyses = json.loads(original_analyses)
    evidence = json.loads(original_evidence)

    def check(doctored: dict[str, Any], match: str) -> None:
        with pytest.raises(DataError, match=match):
            validate_d2_evidence_artifacts(
                run_dir,
                doctored,
                project_id=PROJECT_ID,
                contract_id=CONTRACT_ID,
                contract=contract,
            )

    # A silent post-admission rewrite of the raw measurements fails the manifest hash.
    analyses_path.write_bytes(original_analyses.replace(b"matched", b"m4tched"))
    check(cast(dict[str, Any], dict(manifest)), "does not match its immutable manifest hash")
    analyses_path.write_bytes(original_analyses)

    # Doctoring the manifest hash alongside the bytes still fails the deeper checks.
    pretty = json.dumps(analyses, sort_keys=True, indent=2).encode("utf-8")
    check(_doctored_manifest(manifest, analyses_path, pretty), "canonical JSON bytes")
    wrong_schema = _canonical_bytes({**analyses, "schema": "SomethingElseV9"})
    check(_doctored_manifest(manifest, analyses_path, wrong_schema), "unsupported schema")
    no_measurements = _canonical_bytes({"schema": analyses["schema"], "schema_version": 1})
    check(_doctored_manifest(manifest, analyses_path, no_measurements), "no raw measurements")
    analyses_path.write_bytes(original_analyses)
    monkeypatch.setattr(research_d2, "_MAX_ARTIFACT_BYTES", 16)
    check(cast(dict[str, Any], dict(manifest)), "exceeds the bounded JSON size")
    monkeypatch.setattr(research_d2, "_MAX_ARTIFACT_BYTES", 4 * 1024 * 1024)

    # Forged findings diverge from exact mechanical recomputation of the raw measurements.
    flipped = _canonical_bytes({**evidence, "confirmation_classification": "CONTRADICTED"})
    check(_doctored_manifest(manifest, evidence_path, flipped), "exact mechanical recomputation")

    # Every artifact-link violation fails closed.
    links = evidence["artifact_links"]
    unlinked = {key: value for key, value in evidence.items() if key != "artifact_links"}
    check(
        _doctored_manifest(manifest, evidence_path, _canonical_bytes(unlinked)),
        "must link its immutable measurement artifacts",
    )
    check(
        _doctored_manifest(
            manifest, evidence_path, _canonical_bytes({**evidence, "artifact_links": ["x"]})
        ),
        "links must be objects",
    )
    unnamed = [{**links[0], "artifact_id": 7}]
    check(
        _doctored_manifest(
            manifest, evidence_path, _canonical_bytes({**evidence, "artifact_links": unnamed})
        ),
        "must name their artifacts",
    )
    foreign_run = [{**links[0], "run_id": "f" * 16}]
    check(
        _doctored_manifest(
            manifest, evidence_path, _canonical_bytes({**evidence, "artifact_links": foreign_run})
        ),
        "bind their own run",
    )
    wrong_hash = [{**links[0], "content_sha256": "e" * 64}]
    check(
        _doctored_manifest(
            manifest, evidence_path, _canonical_bytes({**evidence, "artifact_links": wrong_hash})
        ),
        "link hash does not match the manifest",
    )
    chart_sha = str(manifest["artifacts"]["chart-data.json"]["sha256"])
    off_target = [
        {
            "run_id": manifest["run_id"],
            "artifact_id": "chart-data.json",
            "content_sha256": chart_sha,
            "media_type": "application/json",
        }
    ]
    check(
        _doctored_manifest(
            manifest, evidence_path, _canonical_bytes({**evidence, "artifact_links": off_target})
        ),
        "must link the raw measurements artifact",
    )
    evidence_path.write_bytes(original_evidence)

    # A symlink with byte-identical content is still not a regular immutable file.
    hidden = run_dir / "hidden-analyses.json"
    hidden.write_bytes(original_analyses)
    analyses_path.unlink()
    analyses_path.symlink_to(hidden)
    check(cast(dict[str, Any], dict(manifest)), "not a regular immutable file")


def test_mechanical_verification_rejects_flipped_d2_classification(tmp_path: Path) -> None:
    contract, bars, boundary = _prepared(tmp_path, _discovery_only_lows())
    manifest = run_confirmation(
        tmp_path,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
        bars=bars,
        boundary=boundary,
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    verified = validate_d2_evidence_artifacts(
        run_dir,
        manifest,
        project_id=PROJECT_ID,
        contract_id=CONTRACT_ID,
        contract=contract,
    )
    assert verified["confirmation_classification"] == "INCONCLUSIVE"

    evidence_path = run_dir / D2_EVIDENCE_ARTIFACT
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["confirmation_classification"] = "SUPPORTED"
    forged = json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False)
    evidence_path.write_text(forged, encoding="utf-8")
    with pytest.raises(DataError):
        validate_d2_evidence_artifacts(
            run_dir,
            manifest,
            project_id=PROJECT_ID,
            contract_id=CONTRACT_ID,
            contract=contract,
        )
