# Bounded comparison acquisition

**Delivery state:** Implemented; live-provider acceptance unverified

```json
{
  "schema_version": 1,
  "title": "Bounded comparison acquisition",
  "context": "Continue dd1c745: fill explicit comparison-data gaps through existing Tiingo receipt and quality contracts, in acquisition-private storage.",
  "assumptions": [
    {
      "statement": "Tiingo is the only current daily adapter with full v2 provenance/raw receipts; no configured Tiingo key is available in this process.",
      "verified_by": "Navigator checked AlphaSettings/provider registry presence booleans, adapter and pipeline source on 2026-10-04."
    }
  ],
  "alternatives_considered": [
    "Do not silently fall back to legacy Yahoo/Stooq/CCXT provenance.",
    "Keep model MCP read-only; acquire via explicit trusted CLI between cases.",
    "Reuse stage_and_promote only in an empty private store, never owner canonical storage."
  ],
  "pre_mortem": [
    "Timeout/crash followed by replay makes unbounded requests: atomically reserve one entire batch under parent case before dispatch; incomplete batches never retry.",
    "Source data falsely called qualified: bind raw response, parsed identity and reproducible quality reports; vintage and independent-source agreement remain unverified.",
    "Partial downloads silently alter proxy selection: publish a comparison plan only if every requested series passes.",
    "Provider key escapes via redirect or exception: bounded adapter forbids redirects; closed child environment carries only required credential and safe metadata."
  ],
  "slices": [
    {
      "title": "Case-bound acquisition plan",
      "verify": "uv run pytest -q tests/unit/test_comparison_acquisition.py",
      "expected": "Reject scope, dates, duplicate proxies and unsafe roots before network.",
      "rollback": "Remove optional CLI acquisition; retain parent cases and immutable acquired evidence.",
      "status": "done"
    },
    {
      "title": "Bounded provider transport",
      "verify": "uv run pytest -q tests/unit/test_tiingo_bounded_fetch.py",
      "expected": "Response bytes and redirects bounded; controller bounds whole child lifetime.",
      "rollback": "Remove optional CLI acquisition; retain parent cases and immutable acquired evidence.",
      "status": "done"
    },
    {
      "title": "Private acquisition, quality and receipts",
      "verify": "uv run pytest -q tests/unit/test_comparison_acquisition.py",
      "expected": "One reserved batch per parent, retained failures, isolated pipeline, immutable verified output.",
      "rollback": "Remove optional CLI acquisition; retain parent cases and immutable acquired evidence.",
      "status": "done"
    },
    {
      "title": "CLI handoff and acceptance",
      "verify": "uv run python scripts/gate.py full",
      "expected": "CLI fixture acquisition to frozen comparisons, legacy compatibility, independent review and full gate.",
      "rollback": "Remove optional CLI acquisition; retain parent cases and immutable acquired evidence.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "protected",
    "dag"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/operations/codex-investigations.md"
  ],
  "out_of_scope": [
    "Automatic provider choice, unrestricted model network access, canonical store updates, quarantine overrides or trading authority.",
    "No global retry budget across independently created cases; one retained acquisition batch per parent.",
    "No live-provider acceptance claim without a configured credential."
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/comparison_acquisition*.py",
    "apps/alpha-cli/src/alpha_cli/research_diagnostic_cmds.py",
    "packages/alpha-data/src/alpha_data/adapters/tiingo_adapter.py",
    "tests/unit/test_comparison_acquisition.py",
    "tests/unit/test_tiingo_bounded_fetch.py",
    "docs/"
  ]
}
```

One batch of at most four explicit Tiingo stock/ETF daily requests is bound to an inspected parent case and cutoff. A contiguous date window must cover its drawdown endpoints, stay inside the recorded run window/cutoff, and span at most ten years. Requests use USD/US/XNYS metadata explicitly; no alias, source, calendar or venue inference. The batch reserves all requests before networking and never automatically retries a failed or ambiguous attempt. Per-request response bytes and complete child lifetime are bounded. Parent case tool and model budgets are not replenished; a new investigation is an explicit new exposed case, not fresh holdout evidence.

The existing ingestion pipeline runs in new private storage under the parent case, retaining receipts and quarantine. Only all-pass batches publish a snapshot and comparison plan. Cached acquisition reads reverify artifacts and replay raw parsing/quality checks against a fresh temporary store. Comparisons still report general quality certification as not established: this separate receipt certifies only named provider checks, not vintage, cross-source agreement, benchmark suitability or causality. The new CLI comparison-root option freezes the private root using the existing v3 identity; legacy cases are unchanged. No estimator or import DAG changes.


## Implementation evidence

The CLI fixture runs through provider parsing, ingestion checks, private snapshot publication,
new-case comparison loading, and cached reads without a credential or network dispatch. Tests
exercise future-request/provider-row poison with leaky controls, quarantine replay, partial-batch
nonpublication, interrupted reservations, raw-to-snapshot tampering and bounded transport. A real
harmless subprocess test exercises deadline handling and owned process-group cleanup. No live
provider call was made; the absent Tiingo credential remains an explicit acceptance gap.

Independent implementation review identified missing parent-directory fsync after reservation;
the fix now persists the reservation directory before dispatch, with an ordering test. Artifact
traversal also has a count bound. Commit requires independent review binding of the final staged tree
and the canonical full gate; gate receipts record aggregate acceptance, not this implementation
narrative. No benchmark win, broad quality certification, or trading reliability is claimed.

Workstation integration is tracked in [the follow-on plan](2026-10-04-workstation-investigations.md).
Next: configure and retain live-provider acceptance, verify the combined workstation tree, and then
expand evidence-led diagnostics. The download seam alone does not add macro causality, regime
models or strategy engineering.
