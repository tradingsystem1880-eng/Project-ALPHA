"""Static historical control-store schemas; transactions remain in control_store."""

from __future__ import annotations

import re
from typing import Final

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    falsification_criterion TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'accepted', 'rejected', 'archived')),
    current_version_id TEXT,
    current_experiment_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS strategy_versions (
    version_id TEXT PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    parameter_space_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS project_versions (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, version_id)
) STRICT;

CREATE TABLE IF NOT EXISTS experiment_specs (
    experiment_id TEXT PRIMARY KEY,
    strategy_version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    snapshot_id TEXT NOT NULL,
    universe_json TEXT NOT NULL,
    split_policy_json TEXT NOT NULL,
    costs_json TEXT NOT NULL,
    seeds_json TEXT NOT NULL,
    stage_config_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS project_experiments (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS project_scope_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    current_version_id TEXT REFERENCES strategy_versions(version_id),
    current_experiment_id TEXT REFERENCES experiment_specs(experiment_id),
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS stage_run_links (
    link_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    stage TEXT NOT NULL,
    run_id TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    UNIQUE (project_id, experiment_id, stage, run_id)
) STRICT;

CREATE TABLE IF NOT EXISTS stage_state_events (
    link_id TEXT NOT NULL REFERENCES stage_run_links(link_id),
    sequence INTEGER NOT NULL,
    state TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (link_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS experiment_stage_events (
    project_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    state TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (project_id, experiment_id, stage, sequence),
    FOREIGN KEY (project_id, experiment_id)
        REFERENCES project_experiments(project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS attempt_records (
    attempt_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    config_fingerprint TEXT NOT NULL,
    run_id TEXT,
    error TEXT,
    details_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS holdout_state (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    sealed_at TEXT NOT NULL,
    sealed_by TEXT NOT NULL,
    sealed_version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    seal_reason TEXT NOT NULL,
    revealed_at TEXT,
    revealed_by TEXT,
    revealed_version_id TEXT REFERENCES strategy_versions(version_id),
    reveal_reason TEXT,
    contaminated_at TEXT,
    contamination_reason TEXT,
    PRIMARY KEY (project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS holdout_specs (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    spec_hash TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    PRIMARY KEY (project_id, experiment_id),
    FOREIGN KEY (project_id, experiment_id)
        REFERENCES project_experiments(project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS holdout_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    event TEXT NOT NULL CHECK (event IN ('sealed', 'revealed', 'contaminated')),
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    version_id TEXT NOT NULL REFERENCES strategy_versions(version_id)
) STRICT;

CREATE TABLE IF NOT EXISTS decision_packets (
    packet_id TEXT PRIMARY KEY,
    packet_hash TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    strategy_version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    verdict TEXT NOT NULL CHECK (verdict IN ('accept', 'reject', 'revise')),
    packet_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (project_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    project_id TEXT REFERENCES projects(project_id),
    experiment_id TEXT REFERENCES experiment_specs(experiment_id),
    request_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    result_run_id TEXT,
    terminal_error TEXT,
    last_sequence INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS job_events (
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (job_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS evidence_revisions (
    evidence_id TEXT NOT NULL REFERENCES evidence_items(evidence_id),
    revision INTEGER NOT NULL,
    parent_revision INTEGER,
    status TEXT NOT NULL,
    claim TEXT NOT NULL,
    assets_json TEXT NOT NULL,
    frozen_universe_json TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    method TEXT NOT NULL,
    market_data_cutoff TEXT,
    knowledge_at TEXT NOT NULL,
    project_id TEXT REFERENCES projects(project_id),
    strategy_version_id TEXT,
    experiment_id TEXT,
    metric_name TEXT,
    metric_value REAL,
    metric_unit TEXT,
    source_run_id TEXT,
    source_artifact TEXT,
    source_field TEXT,
    row_selector_json TEXT NOT NULL,
    counterevidence_json TEXT NOT NULL,
    contradiction_ids_json TEXT NOT NULL,
    author TEXT NOT NULL,
    author_kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (evidence_id, revision)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_project_versions_project ON project_versions(project_id);
CREATE INDEX IF NOT EXISTS idx_project_experiments_project ON project_experiments(project_id);
CREATE INDEX IF NOT EXISTS idx_project_scope_project
    ON project_scope_events(project_id, occurred_at, sequence);
CREATE INDEX IF NOT EXISTS idx_attempt_project ON attempt_records(project_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_experiment_stage
    ON experiment_stage_events(project_id, experiment_id, stage, sequence);
CREATE INDEX IF NOT EXISTS idx_job_project ON jobs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_knowledge ON evidence_revisions(knowledge_at, created_at);
"""

_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS project_research_governance (
    project_id TEXT PRIMARY KEY REFERENCES projects(project_id),
    research_required INTEGER NOT NULL CHECK (research_required IN (0, 1)),
    origin TEXT NOT NULL CHECK (
        origin IN ('strategy_development', 'research_capture', 'legacy_import')
    ),
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_source_records (
    source_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    title TEXT NOT NULL,
    locator TEXT NOT NULL,
    provider TEXT NOT NULL,
    access_mode TEXT NOT NULL
        CHECK (access_mode IN ('metadata_only', 'open_access', 'owner_provided')),
    content_hash TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    doi TEXT,
    year INTEGER,
    authors_json TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS research_source_claims (
    claim_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    source_id TEXT NOT NULL REFERENCES research_source_records(source_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    claim_text TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN (
        'supports', 'contradicts', 'contextualizes', 'method'
    )),
    strength TEXT NOT NULL CHECK (strength IN ('weak', 'moderate', 'strong')),
    method_summary TEXT NOT NULL,
    sample_summary TEXT NOT NULL,
    markets_json TEXT NOT NULL,
    limitations TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'screened')),
    author TEXT NOT NULL,
    author_kind TEXT NOT NULL CHECK (author_kind IN ('owner', 'agent')),
    screened_by TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, revision)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_research_source_claims_project
    ON research_source_claims(project_id, created_at, claim_id);

CREATE TABLE IF NOT EXISTS research_source_packs (
    pack_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    source_ids_json TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_contracts (
    contract_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    scope TEXT NOT NULL CHECK (scope IN ('exploration', 'confirmation')),
    parent_contract_id TEXT REFERENCES research_contracts(contract_id),
    payload_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    author_kind TEXT NOT NULL CHECK (author_kind IN ('human', 'agent')),
    created_at TEXT NOT NULL,
    UNIQUE (project_id, contract_id)
) STRICT;

CREATE TABLE IF NOT EXISTS research_contract_review_events (
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    sequence INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    scope TEXT NOT NULL CHECK (scope IN ('exploration', 'confirmation')),
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    actor TEXT NOT NULL,
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('human', 'agent')),
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (contract_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_phase_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    phase TEXT NOT NULL CHECK (phase IN (
        'captured', 'triage', 'exploration_review', 'pilot', 'deep_research',
        'confirmation_review', 'sealed_confirmation', 'research_decision', 'closed'
    )),
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    next_action TEXT NOT NULL,
    responsibility TEXT NOT NULL CHECK (responsibility IN ('owner', 'codex')),
    blocker TEXT,
    recovery TEXT,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_execution_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    state TEXT NOT NULL CHECK (state IN (
        'idle', 'queued', 'running', 'paused', 'blocked', 'failed'
    )),
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    next_action TEXT NOT NULL,
    responsibility TEXT NOT NULL CHECK (responsibility IN ('owner', 'codex')),
    active_job_id TEXT,
    checkpoint TEXT,
    blocker TEXT,
    recovery TEXT,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_d2_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    state TEXT NOT NULL CHECK (state IN ('sealed', 'authorized', 'consumed', 'contaminated')),
    boundary_hash TEXT NOT NULL,
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_launch_reservations (
    reservation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    phase TEXT NOT NULL CHECK (phase = 'pilot'),
    kind TEXT NOT NULL,
    launch_number INTEGER NOT NULL CHECK (launch_number BETWEEN 1 AND 3),
    config_fingerprint TEXT NOT NULL,
    budget_reserved_json TEXT NOT NULL,
    execution_sequence INTEGER NOT NULL,
    reserved_at TEXT NOT NULL,
    UNIQUE (project_id, contract_id, kind, launch_number),
    UNIQUE (project_id, execution_sequence),
    FOREIGN KEY (project_id, execution_sequence)
        REFERENCES research_execution_events(project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_attempt_records (
    attempt_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    phase TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    config_fingerprint TEXT NOT NULL,
    budget_used_json TEXT NOT NULL,
    run_id TEXT,
    error TEXT,
    details_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_launch_attempt_links (
    reservation_id TEXT PRIMARY KEY
        REFERENCES research_launch_reservations(reservation_id),
    attempt_id TEXT NOT NULL UNIQUE REFERENCES research_attempt_records(attempt_id),
    linked_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_decision_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    outcome TEXT NOT NULL CHECK (
        outcome IN ('SUPPORTED', 'CONTRADICTED', 'INCONCLUSIVE', 'INVALID')
    ),
    disposition TEXT NOT NULL CHECK (
        disposition IN ('advance_to_strategy', 'revise', 'park', 'reject')
    ),
    actor TEXT NOT NULL,
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('human', 'agent')),
    occurred_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence),
    UNIQUE (project_id, contract_id)
) STRICT;

CREATE TABLE IF NOT EXISTS research_gate_override_events (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS research_contract_strategy_links (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, version_id),
    UNIQUE (project_id, contract_id, version_id)
) STRICT;

CREATE TABLE IF NOT EXISTS research_contract_experiment_links (
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    linked_at TEXT NOT NULL,
    PRIMARY KEY (project_id, experiment_id),
    UNIQUE (project_id, contract_id, experiment_id)
) STRICT;

CREATE TABLE IF NOT EXISTS research_context_packets (
    packet_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    packet_kind TEXT NOT NULL CHECK (packet_kind IN (
        'asset', 'research_case', 'experiment', 'chart', 'validation', 'strategy_promotion'
    )),
    protocol_id TEXT,
    protocol_content_hash TEXT,
    payload_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_case_notes (
    note_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL,
    note_kind TEXT NOT NULL CHECK (note_kind IN (
        'critique', 'confounder_review', 'test_design', 'completeness_review', 'synthesis'
    )),
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    author_kind TEXT NOT NULL CHECK (author_kind IN ('owner', 'agent')),
    context_packet_id TEXT REFERENCES research_context_packets(packet_id),
    created_at TEXT NOT NULL,
    UNIQUE (project_id, sequence)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_research_context_packets_project
    ON research_context_packets(project_id, created_at, packet_id);
CREATE INDEX IF NOT EXISTS idx_research_case_notes_project
    ON research_case_notes(project_id, sequence);

CREATE TABLE IF NOT EXISTS research_dataset_refs (
    ref_id TEXT PRIMARY KEY,
    dataset_kind TEXT NOT NULL CHECK (dataset_kind IN (
        'store_slice', 'snapshot', 'quantpad_receipt'
    )),
    instrument TEXT NOT NULL,
    provider TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT NOT NULL,
    bar_duration_minutes INTEGER,
    origin_json TEXT NOT NULL,
    research_only INTEGER NOT NULL CHECK (research_only = 1),
    registered_by TEXT NOT NULL,
    registered_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_dataset_audits (
    ref_id TEXT NOT NULL REFERENCES research_dataset_refs(ref_id),
    sequence INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    run_id TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (ref_id, sequence)
) STRICT;

CREATE TABLE IF NOT EXISTS monte_carlo_reviews (
    review_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    experiment_id TEXT NOT NULL REFERENCES experiment_specs(experiment_id),
    decision TEXT NOT NULL CHECK (decision IN ('continue', 'revise', 'reject')),
    actor TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_hashes_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (project_id, experiment_id)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_monte_carlo_reviews_project
    ON monte_carlo_reviews(project_id, recorded_at, review_id);

CREATE INDEX IF NOT EXISTS idx_research_dataset_refs_instrument
    ON research_dataset_refs(instrument, registered_at, ref_id);
CREATE INDEX IF NOT EXISTS idx_research_dataset_audits_project
    ON research_dataset_audits(project_id, recorded_at);

CREATE INDEX IF NOT EXISTS idx_research_source_records_project
    ON research_source_records(project_id, created_at, source_id);
CREATE INDEX IF NOT EXISTS idx_research_packs_project
    ON research_source_packs(project_id, created_at, pack_id);
CREATE INDEX IF NOT EXISTS idx_research_contracts_project
    ON research_contracts(project_id, created_at, contract_id);
CREATE INDEX IF NOT EXISTS idx_research_phase_project
    ON research_phase_events(project_id, occurred_at, sequence);
CREATE INDEX IF NOT EXISTS idx_research_attempt_records_project
    ON research_attempt_records(project_id, recorded_at, attempt_id);
CREATE INDEX IF NOT EXISTS idx_research_launch_reservations_project
    ON research_launch_reservations(project_id, reserved_at, reservation_id);
CREATE INDEX IF NOT EXISTS idx_research_launch_attempt_links_attempt
    ON research_launch_attempt_links(attempt_id);
"""

_SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS owner_enrollment_requests (
    request_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    replace_existing INTEGER NOT NULL CHECK (replace_existing IN (0, 1)),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS owner_credentials (
    credential_id TEXT PRIMARY KEY,
    public_key BLOB NOT NULL,
    sign_count INTEGER NOT NULL CHECK (sign_count >= 0),
    actor TEXT NOT NULL,
    transports_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS owner_credential_events (
    event_id TEXT PRIMARY KEY,
    credential_id TEXT REFERENCES owner_credentials(credential_id),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'enrollment_requested', 'enrolled', 'revoked', 'replaced', 'recovery_failed'
    )),
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS owner_auth_challenges (
    challenge_id TEXT PRIMARY KEY,
    ceremony TEXT NOT NULL CHECK (ceremony IN ('registration', 'action')),
    challenge BLOB NOT NULL,
    enrollment_request_id TEXT REFERENCES owner_enrollment_requests(request_id),
    binding_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    verified_credential_id TEXT REFERENCES owner_credentials(credential_id)
) STRICT;

CREATE TABLE IF NOT EXISTS owner_action_receipts (
    receipt_id TEXT PRIMARY KEY,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES owner_auth_challenges(challenge_id),
    credential_id TEXT NOT NULL REFERENCES owner_credentials(credential_id),
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN (
        'screen_source_claim', 'reject_source_claim', 'revise_source_claim',
        'freeze_source_pack', 'approve_exploration', 'reject_exploration',
        'revise_exploration', 'launch_d1', 'approve_confirmation',
        'reject_confirmation', 'launch_d2', 'record_final_disposition'
    )),
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    artifact_hash TEXT NOT NULL,
    expected_case_revision TEXT NOT NULL,
    consequence_summary TEXT NOT NULL,
    reason TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    assertion_hash TEXT NOT NULL,
    outcome_json TEXT NOT NULL,
    performed_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_source_claim_owner_events (
    claim_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    decision TEXT NOT NULL CHECK (decision IN ('reject', 'revise')),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, sequence)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_owner_credentials_active
    ON owner_credentials(revoked_at, created_at, credential_id);
CREATE INDEX IF NOT EXISTS idx_owner_auth_challenges_expiry
    ON owner_auth_challenges(ceremony, expires_at, used_at);
CREATE INDEX IF NOT EXISTS idx_owner_action_receipts_project
    ON owner_action_receipts(project_id, performed_at, receipt_id);
CREATE INDEX IF NOT EXISTS idx_source_claim_owner_events_project
    ON research_source_claim_owner_events(project_id, occurred_at, claim_id);

CREATE TRIGGER IF NOT EXISTS owner_action_receipts_no_update
BEFORE UPDATE ON owner_action_receipts
BEGIN SELECT RAISE(ABORT, 'owner action receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS owner_action_receipts_no_delete
BEFORE DELETE ON owner_action_receipts
BEGIN SELECT RAISE(ABORT, 'owner action receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS owner_credential_events_no_update
BEFORE UPDATE ON owner_credential_events
BEGIN SELECT RAISE(ABORT, 'owner credential events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS owner_credential_events_no_delete
BEFORE DELETE ON owner_credential_events
BEGIN SELECT RAISE(ABORT, 'owner credential events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_source_claim_owner_events_no_update
BEFORE UPDATE ON research_source_claim_owner_events
BEGIN SELECT RAISE(ABORT, 'source claim owner events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_source_claim_owner_events_no_delete
BEFORE DELETE ON research_source_claim_owner_events
BEGIN SELECT RAISE(ABORT, 'source claim owner events are append-only'); END;
"""

_SCHEMA_V4 = """
CREATE TABLE IF NOT EXISTS literature_discoveries (
    discovery_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    query TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    artifact_relpath TEXT NOT NULL,
    budget_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_document_texts (
    extraction_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL UNIQUE REFERENCES research_source_records(source_id),
    source_sha256 TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    artifact_relpath TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'extracted', 'encrypted', 'image_only', 'truncated', 'parser_failed'
    )),
    page_count INTEGER NOT NULL CHECK (page_count >= 0),
    character_count INTEGER NOT NULL CHECK (character_count >= 0),
    parser_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_source_claim_anchors (
    claim_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    extraction_id TEXT NOT NULL REFERENCES research_document_texts(extraction_id),
    page INTEGER NOT NULL CHECK (page >= 1),
    char_start INTEGER NOT NULL CHECK (char_start >= 0),
    char_end INTEGER NOT NULL CHECK (char_end > char_start),
    exact_text_sha256 TEXT NOT NULL,
    PRIMARY KEY (claim_id, revision),
    FOREIGN KEY (claim_id, revision) REFERENCES research_source_claims(claim_id, revision)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_literature_discoveries_project
    ON literature_discoveries(project_id, created_at, discovery_id);
CREATE INDEX IF NOT EXISTS idx_research_document_texts_source
    ON research_document_texts(source_id, created_at, extraction_id);
CREATE INDEX IF NOT EXISTS idx_research_claim_anchors_extraction
    ON research_source_claim_anchors(extraction_id, claim_id, revision);

CREATE TRIGGER IF NOT EXISTS literature_discoveries_no_update
BEFORE UPDATE ON literature_discoveries
BEGIN SELECT RAISE(ABORT, 'literature discoveries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS literature_discoveries_no_delete
BEFORE DELETE ON literature_discoveries
BEGIN SELECT RAISE(ABORT, 'literature discoveries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_document_texts_no_update
BEFORE UPDATE ON research_document_texts
BEGIN SELECT RAISE(ABORT, 'research document texts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_document_texts_no_delete
BEFORE DELETE ON research_document_texts
BEGIN SELECT RAISE(ABORT, 'research document texts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_source_claim_anchors_no_update
BEFORE UPDATE ON research_source_claim_anchors
BEGIN SELECT RAISE(ABORT, 'research source claim anchors are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_source_claim_anchors_no_delete
BEFORE DELETE ON research_source_claim_anchors
BEGIN SELECT RAISE(ABORT, 'research source claim anchors are append-only'); END;
"""

_SCHEMA_V5_RECEIPT = """
CREATE TABLE IF NOT EXISTS owner_action_receipts (
    receipt_id TEXT PRIMARY KEY,
    challenge_id TEXT NOT NULL UNIQUE REFERENCES owner_auth_challenges(challenge_id),
    credential_id TEXT NOT NULL REFERENCES owner_credentials(credential_id),
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN (
        'screen_source_claim', 'reject_source_claim', 'revise_source_claim',
        'freeze_source_pack', 'approve_exploration', 'reject_exploration',
        'revise_exploration', 'launch_d1', 'approve_confirmation',
        'reject_confirmation', 'launch_d2', 'record_final_disposition',
        'record_semantic_event'
    )),
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    artifact_hash TEXT NOT NULL,
    expected_case_revision TEXT NOT NULL,
    consequence_summary TEXT NOT NULL,
    reason TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    assertion_hash TEXT NOT NULL,
    outcome_json TEXT NOT NULL,
    performed_at TEXT NOT NULL
) STRICT;
"""

_SCHEMA_V5 = (
    _SCHEMA_V5_RECEIPT
    + """
CREATE TABLE IF NOT EXISTS research_semantic_events (
    event_id TEXT PRIMARY KEY,
    event_sha256 TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    sequence INTEGER NOT NULL CHECK (sequence >= 1),
    event_type TEXT NOT NULL CHECK (event_type IN ('definition', 'review', 'freeze')),
    case_contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    source_contract_id TEXT NOT NULL REFERENCES research_contracts(contract_id),
    case_revision TEXT NOT NULL,
    prior_semantic_head_sha256 TEXT NOT NULL,
    semantic_artifact_id TEXT NOT NULL,
    semantic_artifact_sha256 TEXT NOT NULL,
    verified_read_sha256 TEXT NOT NULL,
    projection_sha256 TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cutoff_confirmed_at TEXT NOT NULL,
    definition_id TEXT NOT NULL,
    review_id TEXT,
    review_decision TEXT CHECK (review_decision IN ('approve', 'reject')),
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    receipt_id TEXT NOT NULL UNIQUE REFERENCES owner_action_receipts(receipt_id),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (project_id, sequence),
    UNIQUE (project_id, semantic_artifact_id),
    FOREIGN KEY (project_id, case_contract_id)
        REFERENCES research_contracts(project_id, contract_id),
    FOREIGN KEY (project_id, source_contract_id)
        REFERENCES research_contracts(project_id, contract_id),
    FOREIGN KEY (project_id, definition_id)
        REFERENCES research_semantic_events(project_id, semantic_artifact_id),
    FOREIGN KEY (project_id, review_id)
        REFERENCES research_semantic_events(project_id, semantic_artifact_id),
    CHECK (event_id = 'se_' || event_sha256),
    CHECK (length(event_sha256) = 64),
    CHECK (length(case_revision) = 64),
    CHECK (length(prior_semantic_head_sha256) = 64),
    CHECK (length(semantic_artifact_sha256) = 64),
    CHECK (length(verified_read_sha256) = 64),
    CHECK (length(projection_sha256) = 64),
    CHECK (length(payload_sha256) = 64),
    CHECK (length(run_id) = 16),
    CHECK (
        (event_type = 'definition'
            AND substr(semantic_artifact_id, 1, 3) = 'sd_'
            AND definition_id = semantic_artifact_id
            AND review_id IS NULL AND review_decision IS NULL)
        OR
        (event_type = 'review'
            AND substr(semantic_artifact_id, 1, 3) = 'sr_'
            AND substr(definition_id, 1, 3) = 'sd_'
            AND review_id = semantic_artifact_id
            AND review_decision IS NOT NULL)
        OR
        (event_type = 'freeze'
            AND substr(semantic_artifact_id, 1, 3) = 'sf_'
            AND substr(definition_id, 1, 3) = 'sd_'
            AND substr(review_id, 1, 3) = 'sr_'
            AND review_id IS NOT NULL
            AND review_decision IS NULL)
    ),
    CHECK (semantic_artifact_sha256 = substr(semantic_artifact_id, 4))
) STRICT;

CREATE INDEX IF NOT EXISTS idx_owner_action_receipts_project
    ON owner_action_receipts(project_id, performed_at, receipt_id);
CREATE TRIGGER IF NOT EXISTS owner_action_receipts_no_update
BEFORE UPDATE ON owner_action_receipts
BEGIN SELECT RAISE(ABORT, 'owner action receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS owner_action_receipts_no_delete
BEFORE DELETE ON owner_action_receipts
BEGIN SELECT RAISE(ABORT, 'owner action receipts are append-only'); END;

CREATE INDEX IF NOT EXISTS idx_research_semantic_events_contract
    ON research_semantic_events(project_id, case_contract_id, sequence);
CREATE INDEX IF NOT EXISTS idx_research_semantic_events_source
    ON research_semantic_events(project_id, source_contract_id, sequence);
CREATE INDEX IF NOT EXISTS idx_research_semantic_events_artifact
    ON research_semantic_events(project_id, verified_read_sha256, sequence);
CREATE UNIQUE INDEX IF NOT EXISTS idx_research_semantic_events_one_review
    ON research_semantic_events(project_id, definition_id)
    WHERE event_type = 'review';
CREATE UNIQUE INDEX IF NOT EXISTS idx_research_semantic_events_one_freeze
    ON research_semantic_events(project_id, definition_id)
    WHERE event_type = 'freeze';

CREATE TRIGGER IF NOT EXISTS research_semantic_events_no_update
BEFORE UPDATE ON research_semantic_events
BEGIN SELECT RAISE(ABORT, 'research semantic events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_semantic_events_no_delete
BEFORE DELETE ON research_semantic_events
BEGIN SELECT RAISE(ABORT, 'research semantic events are append-only'); END;
"""
)

# Executed exactly once, inside the schema-v2 writer transaction (migration or fresh creation).
# It must never run on a steady-state open: a re-executed backfill would silently re-derive a
# lost governance row from the caller-controlled ``created_at`` date rule, and the write lock it
# takes would make read-only projections contend with concurrent writers.
_GOVERNANCE_BACKFILL = """
INSERT OR IGNORE INTO project_research_governance (
    project_id, research_required, origin, recorded_at
)
SELECT
    project_id,
    CASE WHEN created_at < '2026-08-06T00:00:00.000000Z' THEN 0 ELSE 1 END,
    CASE
        WHEN created_at < '2026-08-06T00:00:00.000000Z' THEN 'legacy_import'
        ELSE 'strategy_development'
    END,
    created_at
FROM projects;
"""

_DDL_OBJECT_NAME = re.compile(r"CREATE (?:TABLE|INDEX|TRIGGER) IF NOT EXISTS (\w+)")
_EXPECTED_SCHEMA_OBJECTS: Final = frozenset(
    _DDL_OBJECT_NAME.findall(_SCHEMA)
    + _DDL_OBJECT_NAME.findall(_SCHEMA_V2)
    + _DDL_OBJECT_NAME.findall(_SCHEMA_V3)
    + _DDL_OBJECT_NAME.findall(_SCHEMA_V4)
)
_PROTECTED_V5_SCHEMA_OBJECTS: Final = frozenset(
    {
        "owner_action_receipts",
        "idx_owner_action_receipts_project",
        "owner_action_receipts_no_update",
        "owner_action_receipts_no_delete",
        "research_semantic_events",
        "idx_research_semantic_events_contract",
        "idx_research_semantic_events_source",
        "idx_research_semantic_events_artifact",
        "idx_research_semantic_events_one_review",
        "idx_research_semantic_events_one_freeze",
        "research_semantic_events_no_update",
        "research_semantic_events_no_delete",
    }
)
_EXPECTED_HEALABLE_SCHEMA_OBJECTS: Final = _EXPECTED_SCHEMA_OBJECTS - _PROTECTED_V5_SCHEMA_OBJECTS

# v6 distinguishes local intent from historical verified WebAuthn presence.
_SCHEMA_V6_RECEIPT = (
    _SCHEMA_V5_RECEIPT.replace(
        "credential_id TEXT NOT NULL REFERENCES owner_credentials(credential_id)",
        "credential_id TEXT REFERENCES owner_credentials(credential_id)",
    )
    .replace(
        "'record_semantic_event'",
        "'record_semantic_event', 'pause_research', 'resume_research', 'cancel_research'",
    )
    .replace(
        "performed_at TEXT NOT NULL",
        """performed_at TEXT NOT NULL,
    authorization_method TEXT NOT NULL DEFAULT 'webauthn'
        CHECK (authorization_method IN ('webauthn', 'local_confirmation')),
    CHECK ((authorization_method = 'webauthn' AND credential_id IS NOT NULL)
        OR (authorization_method = 'local_confirmation' AND credential_id IS NULL))""",
    )
)
