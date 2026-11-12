# Read-only backfill status and safe recovery planning

Canonical requirement: W05/W02, market-data amendment delivery slice C, with the
page-42 bounded-acquisition/status requirement. Source read directly from canonical
Library libfile_181ac6079dcc8191b222b76c1f10bf17, version 9,
Project_ALPHA_Comprehensive_Feature_Readiness_Checklist_2026-10-27_reconciled.docx,
lines 2529–2545 and 2609–2611 (pages 41–43). Slice F supplies the CLI-first access
crosswalk. This bounded implementation does not close W05/W02, C or F.

Gap verified in preserved tree 4780d89df72d070fa80fccfbff545e8ea8f3e1a8: backfill
executes/resumes, dry-run plans without artifact verification, and profile-batches uses
another checkpoint model. No command inspects v1 backfill completion evidence and
reports pending/blocked work without executing resume. The successor starts from that
exact integrated tree on base 3f7b23185c29b2542605bd41b9485016c2ef3e79. No original
candidate, export, Library bundle or receipt is modified.

```json
{
  "schema_version": 1,
  "title": "Read-only backfill status and safe recovery planning",
  "context": "W05/W02 canonical-v9 delivery slice C: inspect retained progress/evidence and expose honest gaps/next action through existing CLI without fetching, consuming quota, creating a store or activating accounting.",
  "assumptions": [
    {"statement": "Existing completion verifier establishes byte/request/quality/retirement binding without acquiring provider data or running a write probe.", "verified_by": "_crypto_backfill_evidence.verify_completed_window and CryptoBulkStore.verify_readable"},
    {"statement": "Status is a read-only observed ledger snapshot, not execution ownership or operational admission.", "verified_by": "No exclusive/admission lock or ControlStore opener is called; final progress hash recheck detects observed source changes"}
  ],
  "alternatives_considered": ["Use run_backfill dry-run as status: rejected; no artifact verification or honest evidence result.", "Wire inactive accounting into status: rejected; unadopted operational scope and excluded owner.", "Invent a new checkpoint catalog or provider probe: rejected; existing ledger/store/verifier suffice."],
  "pre_mortem": ["Missing progress becomes healthy empty history.", "A status refresh fetches, initializes, takes a write lock or runs a storage write probe.", "Malformed retained exception/cause text leaks through inspection output.", "Inspection completion is mistaken for source coverage, freshness, quota or resume authority."],
  "slices": [
    {"title": "Bound readonly ledger/topology inspection", "verify": "Public synthetic unit cases and existing run/split/resume regressions", "expected": "Optional read/plan caps preserve old defaults; shared topology; missing/corrupt/orphan/limit/stale results without mutation", "rollback": "Remove additive inspection APIs; JSONv1 and immutable artifacts unchanged", "status": "done"},
    {"title": "Compose evidence status and safe operator preview", "verify": "New CLI status/recovery tests plus scoped lint/types/import/plan and independent source review", "expected": "Actual raw/normalized verification, truthful quality/unknowns, no effects, safe existing --dry-run preview", "rollback": "Remove status command before helper; preserve all retained evidence/readers", "status": "done"}
  ],
  "tier_impact": ["determinism"],
  "docs_to_update": ["docs/superpowers/plans/2026-11-08-backfill-readonly-status.md"],
  "out_of_scope": ["Real providers/stores/credentials", "Accounting or ControlStore activation", "New budgets/provider policy", "Freshness/rights/PIT or full history qualification", "Protected/full gates", "Science/Qlib/paper/frontend", "Shared generated docs", "Installations/transfers/publication"],
  "files": ["apps/alpha-cli/src/alpha_cli/_crypto_backfill.py", "apps/alpha-cli/src/alpha_cli/_crypto_backfill_inspection.py", "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py", "tests/unit/test_crypto_backfill_inspection.py", "tests/integration/test_crypto_backfill_status_cli.py"]
}
```

## Operator journey

Run `alpha crypto-data backfill-status bybit funding --symbols ETHUSDT,BTCUSDT
--quote USDT --start 2024-01-01 --end 2024-03-01 --ledger resume
--max-ledger-bytes 100000 --max-windows 20 --max-verify-artifact-bytes 1000000 --json`.
The numbers here are example explicit inspection limits, not provider quotas or defaults.
All three limits are required, positive, and local to inspection.

The receipt reports pending_unrecorded, recorded_failure, completed_verified,
unavailable, unverifiable or not_checked leaves. Missing/unreadable/invalid progress,
invalid topology and exceeded limits yield blocked receipts with unknown counts where
inspection could not establish them. Missing progress is never synthesized as proof of
zero history or quota. Old error/cause text is omitted; fixed stage reason codes describe
failures without displaying retained exceptions, URLs or source bodies.

Completed verification reuses exact root identity, active retirement, normalized/raw
hashes, request/effective identity and quality binding. Warning/quarantined captures keep
their quality state; completed_verified describes retained completion evidence only.
Requested frequency is labelled requested, including funding's existing native effective
identity. No publication availability, freshness, historical coverage or provider rights
are established. Last verified checkpoint is a requested-window reference, not a coverage
watermark. Historical quota use remains null and execution_authority remains false.

When inspection completes, safe_next_command_argv supplies the existing backfill command
with --dry-run forced. The CLI test actually executes that preview with effect guards;
no fetch, DB opening, write probe or artifact/progress mutation occurs. Actual acquisition
still requires its existing admission/authorization and fresh locked resume preflight.
Nothing here releases reservations, clears failures, repairs evidence, grants retries or
starts a service. Blocked/stale receipts instead request reconciliation/reinspection.

## Bounds and observational limits

Ledger reads retain regular-file/symlink/hardlink/descriptor checks, with an additive
optional byte cap; old executing writers keep their default behavior. Plan generation
can stop at an additive optional window limit. A single visit budget spans every root
and split node before projection allocation. Shared topology logic preserves production
split/orphan detection. Retained entry scan work is constrained by supplied ledger bytes;
no unrelated malformed entry is silently treated as a requested completion.

One ArtifactVerificationBudget counts repeated raw/normalized artifact hashing, retains
charges on failure and stops later verification after a budget-aborting error. Metadata
JSON, retirement records, local capacity/identity queries (including existing Mac
identity lookup), filesystem read-ahead and wall time are outside that artifact counter.
No total metadata traversal/RSS/I/O deadline is claimed; the receipt lists exclusions.
No provider budget/default, policy or scientific execution default changes.

Inspection acquires no progress ownership, creates no sidecar or directory, and invokes
no store initialization, verify_ready, admission_lock, ControlStore or network route.
It may read a progress file while a participating writer owns it. A final bounded re-read
compares hashes; observed change or loss marks the receipt stale. This does not create an
atomic transaction across progress and artifacts, prove concurrent non-mutation between
checks or replace execution's cooperative lock. Cancellation propagates without writes.

README review: status adds a CLI inspection journey, so later integrated shared docs should
mention backfill-status with explicit caps and advisory-only evidence. Shared README,
manual/build and generated outputs are excluded here; this candidate-local plan records
that proposed update without claiming final release documentation complete.

Review environment: no callable Claude review tool/session was exposed; command -v claude
returned no executable. No install, credential/auth changes or provider invocation was
attempted to obtain it. Independent review uses an available Codex subagent and records
its actual exact-tree source verdict separately, never labels it Claude/native approval.
Public scoped passes are not private-suite, full-gate, live-data or scientific qualification.
QuantPad remains excluded.

Independent Codex review found a malformed-entry state case: JSON list/object states
could raise TypeError during set membership. Shared Ledger.entry now checks string type
first, preserving typed fail-closed behavior for execution and sanitized status reporting.
Two red/green synthetic regression cases and the original review finding are preserved
in separate delivery receipts. No other required review findings were identified.
