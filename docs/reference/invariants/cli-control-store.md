---
owner: command line control plane
sources:
  - apps/alpha-cli/src/alpha_cli/control_store.py
  - apps/alpha-cli/src/alpha_cli/_control_*.py
  - apps/alpha-cli/src/alpha_cli/owner_auth*.py
  - apps/alpha-cli/src/alpha_cli/durable_lease.py
  - apps/alpha-cli/src/alpha_cli/job_capacity.py
  - apps/alpha-cli/src/alpha_cli/project_*.py
  - apps/alpha-cli/src/alpha_cli/evidence_cmds.py
  - tests/unit/test_control_*.py
  - tests/unit/test_owner_*.py
  - tests/unit/test_durable_job_lease.py
  - tests/unit/test_job_capacity.py
  - tests/unit/test_project_workspace.py
  - tests/unit/test_research_control_store.py
  - tests/integration/test_control_cli.py
verified: aa600e57932d
---

# Command line control plane invariants

What must not break when changing the SQLite control plane (`ControlStore` in `control_store.py`), its schema and
migrations, owner confirmation receipts, the semantic event ledger, durable jobs and leases, holdouts and project
workspaces. [ADR-0014](../../adr/0014-cli-owned-development-control-plane.md)

## One mutable authority

- `data_dir/control/workstation.sqlite3` is the only mutable authority for projects, versions, experiments, stages,
  attempts, holdouts, jobs, evidence and research governance. Never attach workflow state by editing a run manifest.
- Only `alpha_cli` opens the database. The web and MCP surfaces never query it directly; they call CLI commands or
  supported `alpha_cli` seams. [ADR-0002](../../adr/0002-cli-sole-composer-subprocess-surfaces.md)
- Refuse symlinks: the `control/` root and the database file must be real paths (`ControlStore._database_path`).
- Every writable connection (`ControlStore._open`) sets `foreign_keys=ON`, `busy_timeout=5000` and `synchronous=FULL`. WAL is negotiated only after
  migration, because changing journal mode is a database-wide write that would race the migration lock.
- Mutations are atomic transactions. Writers take `BEGIN IMMEDIATE`; multi-part projections read from one read
  transaction so they see one snapshot.
- `_control_json.py` is a pure codec and `_control_schema.py` is static historical SQL; transactions, migrations and
  authority stay in `control_store.py`.
- The public surface of `control_store` is pinned by `tests/unit/test_control_store_interface.py` (golden file
  `tests/fixtures/control_store_interface.json`) while the store is split: code that reads a patched module attribute must
  stay in `control_store.py`, and any interface change is made deliberately (`--write`), never by accident.
- WAL negotiation (`_enable_wal`) retries only `SQLITE_BUSY`, outside a transaction, within the connection's
  existing `busy_timeout`, then restores it; any other error or an exhausted budget raises.

## Schema migrations

- The current schema is `SCHEMA_VERSION = 7` (`PRAGMA user_version`). Opening a store at versions 1 to 6 migrates
  forward step by step; any other version fails loud.
- Never edit historical schema text. `_SCHEMA` through `_SCHEMA_V5` and `_GOVERNANCE_BACKFILL` are byte-pinned by
  `tests/unit/test_control_schema.py`. Add a new versioned script and a new migration step instead.
- Each migration of an existing store first writes one exact backup `workstation.sqlite3.v<N>.bak` (integrity-checked,
  same version). An existing backup is accepted only if its logical schema-and-row fingerprint matches the locked source.
- Rebuilds must prove they changed nothing: row tuples (receipts, reservations, attempt links) are compared before and
  after, plus `PRAGMA foreign_key_check`; any difference rolls the whole migration back.
- A store already at the current version opens with a read-only completeness probe. Missing healable objects are
  recreated with idempotent DDL only; the governance backfill never reruns.
- Protected objects (owner receipts with `record_semantic_event`, the semantic event table with its exact column list,
  research launch reservations and attempt links) are never healed. If missing or malformed, open fails closed and
  needs owner-approved forensic forward recovery.
- Governed projects that existed before the research gate are grandfathered only by the migration (`legacy_import`);
  normal APIs cannot create that state.

## Append-only records

- Owner action receipts, owner credential events, source-claim owner events, literature discoveries, document texts,
  claim anchors and semantic events have SQL triggers that abort any UPDATE or DELETE (`_control_schema.py`).
- Research launch reservations, decision events, Monte Carlo reviews and evidence revisions are append-only by code;
  never add an update path.
- The Monte Carlo owner review (`review-monte-carlo`) applies only to a stage in `warning`, binds the exact evidence
  hashes, is recorded once, and stays CLI-only (absent from REST and MCP).
  [ADR-0029](../../adr/0029-four-family-monte-carlo-validation.md)
- Evidence is cited, revisioned and time-aware; experiment and version links must match immutable lineage.
  Each revision records `knowledge_at` separately from `market_data_cutoff`, and `evidence list --as-of` returns only
  what was knowable at that cutoff. [ADR-0015](../../adr/0015-evidence-ledger-not-agent-memory.md)
- `AgentBrief` (`project agent-brief`) filters selection, stage and link events by timestamp inside one read snapshot,
  so a later holdout run, reveal, contamination or strategy selection never enters an earlier brief.
- `project experiment` on a research-governed version must pass the exact `--research-contract-id` already bound to
  that version; a missing or different id fails before the experiment is created.

## Owner authority

- Project-wide rule: [research integrity § Owner authority](research-integrity.md#owner-authority).
- The closed action list is `OWNER_ACTION_TYPES` in `control_store.py`. Adding an action is a governance change, not
  a refactor. [ADR-0038](../../adr/0038-local-confirmation-and-terminal-archive-charts.md)
- Every confirmation is bound to action type, project, artifact hash, current case revision, consequence summary,
  reason and request-payload hash (`owner_auth.action_binding`). A changed case, payload or artifact fails before use.
- Challenges expire after 60 seconds (`CHALLENGE_LIFETIME_SECONDS`) and are single-use: the consuming transaction
  rejects a used or expired challenge. Enforced by `tests/unit/test_owner_auth_store.py` and
  `tests/unit/test_owner_local_confirmation.py`.
- The receipt records the actual method (`local_confirmation` or `webauthn`). Local confirmation proves local intent,
  not human presence; never describe it as biometric. Legacy WebAuthn stays optional.
  [ADR-0030](../../adr/0030-touch-id-owner-presence-for-research-actions.md) is partly superseded by ADR-0038.
- `alpha owner-auth enroll|recover` is a trusted local ceremony; never expose it to MCP or generic jobs.
- Owner confirmation grants no broker, order, holdout, paper-entry, risk-override or research-gate-override capability.
- Owner-auth enrollment is optional: ordinary owner actions need only local confirmation, and a legacy
  biometric enrollment never turns it into verified presence.

## Semantic event ledger

- `record_semantic_event` is the one action that writes the semantic ledger. The credential counter, challenge
  consumption, receipt and canonical event commit in one transaction (`record_semantic_event_authorization`).
- There is no direct semantic-write CLI command. `recover_semantic_event_authorization` only returns an already
  committed result for a consumed challenge; it never re-authorises.
- Reads of events and their verified head come from one read transaction (`read_semantic_events`, `read_semantic_state`).
- Owner-only D1, D2 and promotion authority is unchanged by the ledger.
  [ADR-0035](../../adr/0035-generic-study-composition-and-external-capability-adapters.md)

## Jobs, leases and capacity

- Qlib and Kronos work share one heavyweight capacity class of size 1 (`job_capacity.py`). `HEAVYWEIGHT_JOB_KINDS` also
  reserves `research:event-study` and `research:ml`, so generic job creation can never mint those kinds.
- Only `ControlStore.create_research_job` creates `research:event-study`, and only for the approved active D1 or D2 phase.
- `DurableJobLease` heartbeats every 5 seconds by default; intervals above 10 seconds are refused. Failed renewal or
  cancellation sends TERM to the whole process group, waits a grace period, sends KILL, and reaps the direct child.
- Lease liveness follows the process group, not the leader PID. Cleanup failure keeps the job non-terminal and the slot
  reserved; the caller joins the lease loop before publishing any later terminal state.
- Never treat a stored PID as proof. Stale reconciliation fails only non-research, non-native jobs, and a surviving
  orphan must be confirmed and reaped by an operator before relaunch. There is no automatic PID recovery.

## Holdouts

- A dated final holdout must be sealed before any research attempt or run, and its window may not overlap a window
  already revealed in the same lineage.
- Reveal is one-shot and audited. Contaminated holdout evidence cannot complete a gate, and promotion requires an
  uncontaminated one-shot reveal.

## Project workspaces

- `project_workspace.py` writes disposable, hash-only indexes under `data_dir/strategy-workspaces/`. It never rewrites
  SQLite or immutable artifacts and grants no research, promotion, sandbox, paper, broker or order authority.
- Project creation commits SQLite first; a failed workspace build cannot roll it back. A revision is verified before the
  atomic `current.json` swap, and tamper blocks sync until explicit quarantine recovery.

## Approval-bound bytes

- `control_store.py`, `_control_json.py`, `owner_auth.py` and `durable_lease.py` are in the daily native rule approval
  fingerprint. Any byte edit invalidates existing daily rule approvals; see
  [command line native § Approval fingerprints](cli-native.md#approval-fingerprints).
