---
owner: command line research
sources:
  - apps/alpha-cli/src/alpha_cli/research_*.py
  - apps/alpha-cli/src/alpha_cli/study_semantic.py
  - apps/alpha-cli/src/alpha_cli/strategy_candidate*.py
  - tests/unit/test_research_*.py
  - tests/integration/test_research_*.py
verified: 1ac86fc02443
---

# Command line research invariants

What must not break when changing the governed Research Case commands (`alpha research ...`) and the
`research_*` modules that capture ideas, freeze contracts, run the D0/D1/D2 phases and project gate packets.
The project-wide rule lives in [research integrity § Research before strategy](research-integrity.md#research-before-strategy);
this file holds the command-line specifics.

## Phases and words used here

- A Research Case is the finite, governed study every new project starts with. `alpha research capture` and
  `alpha project create` both create one and enter triage atomically. [ADR-0019](../../adr/0019-governed-research-cases-before-strategy-development.md)
- D0 is the synthetic pilot: canned fixture data, no market claim. D1 is registered discovery on real research-only
  data. D2 is the one-shot sealed confirmation. D3 is the final holdout share; research never reads it.
- Gate 1 is the D0 gate. It runs only the contract-bound canonical `double_bottom` detector with
  `second_trough_confirmable` availability (`research_runtime.py`). Other contracts may be drafted but fail before execution.
- Never let a runner read outside its assigned share. `research_d1.py` executes strictly inside D1; `research_d2.py`
  inside D2, and never materialises D3 into its data view. The 60/20/20 group-atomic split itself is owned by
  `alpha_research` and pinned by `tests/unit/test_research_d2_boundary.py`.

## Contracts and approvals

- Never approve a contract with unresolved material: approval requires schema `ResearchContractV1`,
  `approval_ready=true`, zero `blocking_questions`, and no placeholder markers (`control_store.py`, `research_cmds.py`).
- `run deep` executes only the approval-frozen `analysis_plan` (`ResearchAnalysisPlanV1`: registered families, bounded
  grids, one primary plus frozen Holm/falsification multiplicity; blanket batteries rejected).
  [ADR-0025](../../adr/0025-empirical-d1-research-runner-admission.md)
- `draft-confirmation` derives the D2 contract mechanically from admitted clearing D1 evidence (one-variant primary family,
  direction, minimum effect, frozen 0.05/0.90 multiplicity) and fails loud on degenerate discovery intervals.
  [ADR-0026](../../adr/0026-d2-confirmation-readiness-gate-promotion-override.md)
- A `revise` before D2 may reuse a D2 boundary only as `unopened_sealed_reuse`, and only while no D2 share in the
  project was ever authorised. Otherwise it must use `non_overlapping_future` or `external_replication` data with a
  distinct boundary (`ControlStore._require_revision_d2_reuse`).

## Implementation hash

- Every approved contract freezes `code`, `dependency_lock`, `environment` and `evaluator` fingerprints
  (`research_cmds.py::_implementation_hashes`). Pilot and deep runs refuse to start, and D2 is marked contaminated,
  when any of them differs. Enforced by `tests/integration/test_research_cli.py` (fingerprint drift case).
- `code` hashes every `.py` file under `packages/alpha-research/src/alpha_research` plus the exact bytes of
  `alpha_cli/research_intake.py`, `research_runtime.py`, `research_crypto_data.py` and `research_crypto_runtime.py`.
  A cosmetic edit (comment, import order, formatting) to any of them invalidates every existing owner approval.
- `dependency_lock` is the repository `uv.lock` bytes, so a lock change has the same effect.
- Daily native rule contracts use a different fingerprint (`_native_rule_environment.rule_implementation_fingerprints`);
  see [command line native § Approval fingerprints](cli-native.md#approval-fingerprints).
- General rule: [engineering § Hash-bound source bytes](engineering.md#hash-bound-source-bytes).

## Mechanical evidence

- Never treat a producer flag as authority. D1 and D2 write raw measurements (`d1_analyses.json`, `d2_analyses.json`)
  and a `research_gate_evidence.json` whose finding statuses are recomputed by one classifier
  (`derive_d1_findings`, `derive_d2_findings`) at write time and again at every admission and read.
- Keep the bootstrap seed frozen at 7 (`_D1_SEED`, `_D2_SEED`); never derive it from `AlphaSettings.random_seed`, or
  re-verification would depend on the reader's configuration. Crash recovery is exact re-execution to the same run id.
- D0 completion is not a manifest boolean: the control plane re-checks the canonical `ResearchD0AcceptanceV1` bytes
  before admission and on every recovery, status and packet read (`validate_d0_acceptance_bytes`).
- D1 runs publish under an EXPLORATORY watermark; D2 runs under REGISTERED CONFIRMATORY. Research runs carry no orders,
  fills, sizing or costs.
- Statistical method rules: [research integrity § Statistical evidence](research-integrity.md#statistical-evidence).

## Launch budgets and recovery

- D0 has at most three lifetime launches per contract (`_D0_MAX_LAUNCHES`). The launch slot and fixed budget are reserved
  in the same transaction as the `running` event; a hard crash consumes the slot. Never refund or reset a slot.
- D2 allows the first attempt plus two retries (`attempt_number > 3` is refused) under the identical deterministic run id.
- Never auto-reconcile a stale D1/D2 job from a local PID check: `ALPHA_DATA_DIR` may be shared and there is no trusted
  owner-host identity. Stale-job reconciliation skips `research:event-study` jobs (`ControlStore`), and
  `alpha project job-status` refuses to set a terminal status on them (`project_cmds.py`).
- Recovery reuses a prior D1 publication only after full immutable-artifact and evidence re-verification.
- Active `cancel` only requests cancellation; ownership stays bound until checkpoint handling.

## Owner decisions

- `approve`, `reject` and `decide` are trusted-local owner actions. They are absent from MCP forever; REST reaches them
  only through the owner-action ceremony. Enforced by `tests/integration/test_research_mcp.py`.
  See [research integrity § Owner authority](research-integrity.md#owner-authority).
- The recorded actor string is audit text, not cryptographic identity or proof of presence; never claim otherwise.
- `record_research_decision` requires `actor_kind="human"`, and `advance_to_strategy` requires outcome SUPPORTED.
- After D2 the owner's outcome must equal the mechanical D2 classification, and `advance_to_strategy` also needs
  `promotion_readiness == "ready"`. A contaminated D2 can only be recorded as INVALID with revise, park or reject.
- An early decision (D2 still sealed) may only be INCONCLUSIVE or INVALID with revise, park or reject. CONTRADICTED is
  always refused on that path; no code path yet accepts the lineage-bound non-synthetic evidence it would need.
- Implementation drift or sealed-dataset byte drift contaminates D2 before the read; the only exit is INVALID.

## Strategy promotion and overrides

- A governed strategy version must link the approved confirmation contract and the owner's `advance_to_strategy`
  decision (`ControlStore` strategy-version creation). Only migrated pre-launch projects are grandfathered, and normal
  APIs can never grant grandfathering.
- `override-research-gate` is trusted-local, needs actor and reason, fails on grandfathered or already-passed gates, and
  a later pass re-locks the gate.
- Runs under an override carry the permanent `EXPLORATORY / RESEARCH GATE NOT COMPLETED` watermark, which forks run
  identity (`run_store.RESEARCH_GATE_OVERRIDE_WATERMARK`, `_artifacts.research_gate_override_identity`). Enforced by
  `tests/integration/test_research_gate_watermark_cli.py`.

## Projections and dossiers

- Readiness, scorecard, checklist, evidence hub and decision view are Python-authoritative projections
  (`research_gate_packet.py`, `research_readiness.py`). The scorecard reports enumerated states, never a numeric total.
  [ADR-0027](../../adr/0027-tiered-research-readiness-semantics.md)
- `status --json` carries `hypothesis_card` and `scorecard` as additive keys; the dossier-embedded
  `research_case_summary` shape never gains keys (its bytes are hash-pinned in the dossier).
- Dossiers under `data_dir/research/projects/<project_id>/` are deterministic, tamper-checked projections. Never parse
  them back into control state; SQLite is the only mutable authority.
- `research_study_status.py` and `study_semantic.py` are read-only and grant no authority.
- `research compare` is the legacy multi-strategy backtest ranking; it is not a Research Case runner and gives no evidence.

## Research data and crypto research

- `data register` binds a `research_only` `rd_<sha256>` reference to exact snapshot-manifest, provenance or QuantPad
  receipt bytes; `data audit` findings feed only the data dimension. [ADR-0023](../../adr/0023-research-dataset-registration-and-quantpad-lane.md)
- The crypto crowding lane re-verifies the bound qualified snapshot before every use (`research_crypto_binding.py`)
  and keeps the same mechanical-classification discipline as D1/D2. [ADR-0033](../../adr/0033-governed-crypto-crowding-research-and-sandbox-basis.md)
- The hedged-basis development candidate is sandbox-only: `hedged_basis_paper_preflight` always returns BLOCKED with
  no connection, order or readiness credit (`strategy_candidate.py`).

## Process boundaries

- `research_execution.run_child` must import nothing from the analysis stack (no `_artifacts`, `_runner`, numpy, scipy,
  polars). Enforced by `tests/unit/test_research_execution_import_boundary.py`. Load heavy research dependencies at their
  actual callers and keep receipt checks, process-group cleanup and budget semantics.
- The literature worker (`_run_literature_worker`) starts with a fixed minimal environment (no inherited credentials),
  `uv run --locked --no-sync`, `UV_OFFLINE=1`, its own session and resource limits. It keeps a valid explicit
  `UV_CACHE_DIR`, else uses a temporary cache removed afterwards; an invalid explicit cache fails before start.
  [ADR-0024](../../adr/0024-literature-acquisition-worker-and-claim-model.md)
- `research_acquisition.py` holds validation primitives only; it performs no request or download.
- Worker isolation in general: [research integrity § Models and isolated workers](research-integrity.md#models-and-isolated-workers).
