# W05 research integration successor

> Evidence navigation: `.alpha/state/` paths below name ignored, machine-local receipts.
> These are handoff locations, not repository links.
> Their contents and continued availability are not established by this checkout;
> retain the dated result and pending-evidence limits recorded below.

**Delivery state:** Completed local integration packet; aggregate qualification blocked pending native portability repair and final full gate.

**Successor (open):** [Combined Mac portability qualification](2026-10-26-mac-portability-qualification.md#handoff-and-next-action), pending slice "Independent review and final successor qualification".

```json
{
  "schema_version": 1,
  "title": "W05 integration into preserved research workflow",
  "context": "Reconcile reviewed PR92 prerequisites and one combined W05 patch into frozen W11/native/tabular a284; no missing query reconstruction.",
  "assumptions": [
    {
      "statement": "PR92 production/test delta is identical to the reviewed f0ba4 source.",
      "verified_by": ".alpha/state/w05-integration/source-lineage.json"
    }
  ],
  "alternatives_considered": [
    "Blindly stack patches: rejected because PR92 is absent and documentation diverged."
  ],
  "pre_mortem": [
    "Wrong editable source used by reused environment.",
    "Snapshot/query or cancellation tests mistaken for full acquisition or native acceptance."
  ],
  "slices": [
    {
      "title": "Reconcile complete PR92 redaction prerequisite",
      "verify": "Explicit Tiingo public regression plus source lineage",
      "expected": "Reviewed transport redaction preserved without unrelated base overwrite",
      "rollback": "Retain isolated candidate; original a284 unchanged",
      "status": "done"
    },
    {
      "title": "Integrate reviewed UTC and request budget once",
      "verify": "Explicit W05 public tests and new only-if-needed integration scenarios",
      "expected": "Offline bounded acquisition, PIT, immutable snapshot invariants hold",
      "rollback": "Use preserved a284; no real data touched",
      "status": "done"
    },
    {
      "title": "Review focused successor and publish local evidence",
      "verify": "Focused types/lint/import/plan/policy checks and independent Astra review",
      "expected": "Exact tested source and honest deferred canonical gate",
      "rollback": "Keep blocked candidate isolated",
      "status": "done"
    }
  ],
  "tier_impact": [],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/context/README.md",
    "docs/context/alpha-quant-platform.md"
  ],
  "out_of_scope": [
    "Real data",
    "Missing query/report/navigation patches",
    "Native-owner files",
    "Full gate pending native portability repair",
    "Commit or publication"
  ],
  "files": [
    "packages/alpha-data/src/alpha_data/adapters/tiingo_adapter.py",
    "packages/alpha-data/src/alpha_data/pit.py",
    "packages/alpha-data/src/alpha_data/crypto/providers/_wire.py",
    "packages/alpha-data/src/alpha_data/crypto/providers/binance.py",
    "apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py"
  ]
}
```

Existing context index → this plan → `.alpha/state/w05-integration/` records source lineage, initial failures, final identity and review. Parent baseline bc5; preserved predecessor a284. No statistical algorithms or import-layer permissions change. PIT UTC normalization must preserve availability boundaries and future-poison controls.


## Source and implementation

The complete prerequisite chain is `fc6da893` → independently reviewed transport tree
`1829d198` / commit `f0ba4c34`, merged with `e635e6cb` into PR92 base `98190e3b`.
The reviewed W05 patch from that base to `220b9b02` is applied once. All production and test
bytes match producer source except Ruff-only formatting in the CLI scope predicate.
The public source lineage, patch hashes and immutable predecessor identity are in
source-lineage.json (`.alpha/state/w05-integration/source-lineage.json`).

- [Tiingo redaction](../../../packages/alpha-data/src/alpha_data/adapters/tiingo_adapter.py) and
  [public regression](../../../tests/unit/test_tiingo_bounded_fetch.py) preserve PR92.
- [Aware bar cutoff](../../../packages/alpha-data/src/alpha_data/pit.py),
  [request budget](../../../packages/alpha-data/src/alpha_data/crypto/providers/_wire.py),
  [Binance transport](../../../packages/alpha-data/src/alpha_data/crypto/providers/binance.py),
  [CLI propagation](../../../apps/alpha-cli/src/alpha_cli/crypto_data_cmds.py).
- [Budget tests](../../../tests/unit/test_crypto_request_budget.py),
  [UTC/DST tests](../../../tests/unit/test_pit_tz.py) and
  [cross-boundary integration tests](../../../tests/integration/test_w05_research_integration.py).

## Evidence and limits

Consolidated public regression: **358 passed**, including eight new integration cases.
The regression command and exact log are in
final-public-regression.json (`.alpha/state/w05-integration/final-public-regression.json`).
The final evidence record (`.alpha/state/w05-integration/final-evidence.json`) binds the
candidate tree, source manifest, final focused checks and independent Astra review.
Initial red tests, fixture/typing repairs, formatting failure, mistaken test/module invocation,
and sandboxed uv failures are retained alongside successful checks. Pinned offline Semgrep
passed on the host after its sandbox launcher failed; no configuration was changed.

Tests use fake HTTP responses through the real opener; they make no provider requests.
They cover acquisition → normalization → immutable snapshot → existing member candle query,
REST revision identity, raw-lineage tampering, cadence-warning/partial-quarantine/future rejection,
second-page redirect/interruption without partial publication, legacy/provenance snapshots,
DST-equivalent cutoff reads and future-append invariance. The later-cutoff positive control
checks future visibility; existing public bias guards supply separate leaky controls.
The 100-page test stubs parsing and verifies loop/attempt limits only. Short pages do not prove
complete coverage; REST revisions retain identities without inventing archive correction policy.
Naive-cutoff rejection here is specific to bar `as_of`; inherited dividend cutoff behavior is unchanged.
Application attempts/body-byte accounting is not a socket/TLS/hidden-buffer bound.

No fresh full gate was run. Preserved a284 had scoped W11 approval but nine Darwin native typing
errors, 84 public backend failures and 91.63% coverage against 93%; their receipts remain authoritative
for that predecessor only. This packet neither suppresses nor reclassifies those failures.
No hidden tests were read/run, no private-suite evidence exists, and scientific qualification,
real acquisition/discovery dates, Qlib admission/charging and promotion remain unapproved.
Missing query/report/navigation sources remain blocked; `crypto_data_cmds.py` overlaps the query
predecessor and requires actual reviewed source before later reconciliation.

## Recovery, next action and status updates

Keep this candidate isolated; rollback means returning to preserved a284, never rewriting it or
producer archives. No real store or database was opened. There is no commit or publication.
Tests reused the unchanged locked predecessor runtime with explicit successor source paths and
no sync/install; the final import-identity receipt verifies all application packages resolve here.

Next: verify and reconcile the native owner's incremental repair in a separately identified tree,
retain all failure receipts, and run the canonical `uv run python scripts/gate.py full` once on that
final tree with an isolated writable runtime (do not sync the reused predecessor environment).
Use synthetic ALPHA_DATA_DIR, baseline bc5 and offline locked dependencies; check disk before setup.
All six components and coverage floor remain required. Then obtain exact-tree independent review.
Parent directs this combined qualification; neither Darwin checks nor imported Linux receipts alone
qualify native execution on this Mac.

To update status, follow context README → this plan → final-evidence.json. Record the new tree,
command/log hashes, executed host, failures and scoped review separately from aggregate gate and
scientific acceptance. Never copy an earlier gate stamp to later source. No GitHub push/PR/merge,
deployment, discovery activation, security change or live/paper route is authorized.

### Cloud qualification review notes, 2026-10-27

Open findings (not blockers): under a strict budget, an interrupted Binance body read re-raises the raw
`OSError`/`IncompleteRead` instead of a typed `DataError` (budget accounting is still correct; the
Tiingo adapter types the same case); a response exactly equal to the remaining `--max-total-bytes`
fails because EOF cannot be proven without one more read, which the CLI help should state; the
uncapped Tiingo path now drops `URLError.reason` on redaction.
