# Codex frozen comparison evidence

**Delivery state:** Completed

```json
{
  "schema_version": 1,
  "title": "Codex frozen comparison evidence",
  "context": "Continue e111377 with bounded snapshot comparison evidence inside existing loss inspection; primary UI checkout remains untouched.",
  "assumptions": [
    {
      "statement": "Existing snapshot and PIT seams can serve bounded daily comparison series; provenance is not a quality certificate or historical vintage proof.",
      "verified_by": "Navigator and root inspected snapshot.py, _runner.load_bars, store.py and capability-authority matrix."
    }
  ],
  "alternatives_considered": [
    "Automatic provider pulls deferred until a bounded acquisition contract exists; reuse explicit local snapshots now.",
    "Broad new MCP tools unnecessary: the existing inspect_losses tool can carry frozen comparisons.",
    "No forced date alignment, correlation fit, residual alpha or causal attribution from endpoint changes."
  ],
  "pre_mortem": [
    "Manifest verifies one path while the reader consumes another: require exact conventional paths, declared optional files and no symlinks.",
    "Current revised data masquerades as historical availability: expose fetch time and vintage unverified.",
    "Old investigations gain new scope or budgets: retain schema2 identities and tools; comparisons require a fresh schema3 case."
  ],
  "slices": [
    {
      "title": "Strict frozen comparison plan",
      "verify": "uv run pytest -q tests/unit/test_investigation_comparisons.py",
      "expected": "Reject unsafe selectors, changed hashes, undeclared files and ambiguous daily timestamps.",
      "rollback": "Revert additive comparison support; retain original cases and historical evidence.",
      "status": "done"
    },
    {
      "title": "Cutoff-safe episode comparisons",
      "verify": "uv run pytest -q tests/unit/test_investigation_comparisons.py",
      "expected": "Exact-date price changes, provenance blockers and future-poison control agree with hand calculations.",
      "rollback": "Revert additive comparison support; retain original cases and historical evidence.",
      "status": "done"
    },
    {
      "title": "Versioned case and CLI integration",
      "verify": "uv run pytest -q tests/unit/test_investigation_comparison_case.py tests/unit/test_investigation_case.py",
      "expected": "Old cases remain byte-compatible; new comparison evidence is frozen and reverified on cached reads.",
      "rollback": "Revert additive comparison support; retain original cases and historical evidence.",
      "status": "done"
    },
    {
      "title": "Acceptance and documentation",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Independent review, actual CLI/MCP fixture journey and six-component gate pass on the final tree.",
      "rollback": "Revert additive comparison support; retain original cases and historical evidence.",
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
    "Provider downloads, crypto bulk snapshot format, causal/regime models, chart UI and strategy deployment.",
    "No research admission, fresh holdout claim or automatic learning activation."
  ],
  "files": [
    "apps/alpha-cli/src/alpha_cli/investigation_comparisons.py",
    "apps/alpha-cli/src/alpha_cli/investigation_case.py",
    "apps/alpha-cli/src/alpha_cli/research_diagnostic_cmds.py",
    "apps/alpha-cli/src/alpha_cli/codex_investigation.py",
    "tests/unit/test_investigation_comparisons.py",
    "tests/unit/test_investigation_comparison_case.py",
    "docs/"
  ]
}
```

## Scope and success

Up to four explicitly selected daily snapshot series are compared over the existing top-three strategy drawdown peak-to-trough windows. Selection roles are hypotheses supplied by the operator, not inferred benchmarks. Hash verification establishes integrity; v2 pull provenance establishes declared instrument identity. Neither establishes source quality, historical vintage, causality or tradable excess return. Measurements use exact UTC session-date endpoints, split-adjusted prices excluding dividends and FX, with actual timestamps and observed interior counts. No forward fill or nearest-date substitution. Schedule completeness remains explicitly unverified. Missing provenance or endpoints produces a blocked measurement, while tampering or unsafe reads fails loudly.

All reads retain the run cutoff. Tests poison future prices with a discriminating leaky control. The case identity freezes selectors, expected snapshot hashes and data root; all comparison receipts are reverified. Existing three tools, request and turn budgets, Codex-only policy and schema2 cases remain unchanged. CLI remains the sole composer; no statistical estimator or package DAG changes.

## Acceptance record

Implementation and scoped live acceptance are delivered; commit acceptance separately requires a fresh full gate and independent exact-tree review. Forty-eight new comparison and integration tests pass, including future-price poisoning with a leaky control, unsafe paths, hash drift, sparse endpoints, metadata blockers, resource bounds, v2 compatibility and real MCP-to-CLI execution. The comparison module has 97.53% statement coverage in that focused run. The fast gate passed after correcting two test-only typing errors; the initial failing log is retained.

A real Codex session used a labeled synthetic fixture: 40% strategy drawdown, 20% SPY comparison price decline, three successful receipts, and one model turn. It reported unverified coverage/vintage/quality/causation and proposed accounting/exposure reconciliation. New-case checkpoint resume returned identical findings without another model call; the previous MSFT schema-v2 report also resumed unchanged. Raw acceptance artifacts remain private at `/private/tmp/alpha-codex-comparison-acceptance-20261003`; this is not real-market economic evidence or a broad judgment benchmark.

Independent review identified and the implementation fixed all-member hashing before size limits. Bounds now apply before hashing/decompression. Final verification uses `ALPHA_GATE_BASE=e111377`, four pytest workers and browser port 8817; it covers this increment rather than cumulative branch-vs-main changes. The canonical gate and review artifacts in `.alpha/state/` bind the final tree; the full log is retained at `/private/tmp/alpha-comparison-full.log`. No statistical estimator, new dependency, historical Claude evidence or active primary UI files changed.

## Next increment

Design bounded acquisition requests from these explicit blockers, qualify fresh provider data using existing quality contracts, freeze results into new snapshots/case revisions, and retain all exposure and search budgets. Do not fill missing prices or relabel metadata verification as data quality. Then integrate Codex controls/chart input with the reconciled workstation branch.
