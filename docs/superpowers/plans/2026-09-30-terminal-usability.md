# Terminal usability, local confirmation and real market data

Owner direction: restore the Windows-style terminal in `Desktop/ALPHA-terminal-designs`, replace mandatory Touch ID with explicit local UI confirmation, and make stored external-drive market data usable. This supersedes the September 29 workflow-page visual direction; retain its repairs and routes.

```json
{
  "schema_version": 1,
  "title": "Terminal usability and real market data",
  "context": "Reference-driven compact terminal, local action confirmation and verified bulk chart access. The current picker hides external-drive data and ordinary coverage requests hash the entire drive.",
  "assumptions": [
    {
      "statement": "The application remains a trusted single-user loopback application",
      "verified_by": "Origin/host rejection tests and loopback server binding"
    },
    {
      "statement": "Discovery metadata is not artifact verification",
      "verified_by": "Selected-manifest integrity, lineage and cutoff regression tests"
    }
  ],
  "alternatives_considered": [
    "Replacing the chart engine: retain the existing Apache-2.0 Lightweight Charts engine and improve its tools and data integration",
    "Merging XRP/USD and XRP/USDT: rejected because quote and venue differ",
    "Removing only the biometric UI: rejected because backend confirmation and audit must change coherently"
  ],
  "pre_mortem": [
    "Compact chrome must not make controls unreachable",
    "Click confirmation cannot claim verified biometric presence",
    "Bulk derivatives must remain distinct from spot and cannot implicitly become backtest inputs",
    "Whole-drive verification can make ordinary navigation appear broken"
  ],
  "slices": [
    {
      "title": "Local confirmation contract and negative request tests",
      "verify": "Targeted owner authentication Python tests",
      "expected": "Explicit expiring action-bound confirmation with honest audit and origin checks",
      "rollback": "Restore biometric default with historical receipts preserved",
      "status": "done"
    },
    {
      "title": "Confirmation UI and receipt messaging",
      "verify": "Owner action unit and browser tests",
      "expected": "Actions complete without biometric enrollment; stale and rejected actions remain blocked",
      "rollback": "Restore previous owner action component",
      "status": "done"
    },
    {
      "title": "Fast bulk discovery and selected verified chart data",
      "verify": "CLI/API integrity and future-cutoff regression tests",
      "expected": "External drive bars are selectable with venue, market type and exact dataset identity",
      "rollback": "Remove new discovery/chart routes without touching owner data",
      "status": "done"
    },
    {
      "title": "Reference terminal chrome and chart workspace",
      "verify": "Frontend types, tests and browser screenshots at three viewports",
      "expected": "Windows-style chrome, linked watchlist, large chart, resizable working space and reachable tasks",
      "rollback": "Restore workflow shell only",
      "status": "done"
    },
    {
      "title": "End-to-end data and action journeys",
      "verify": "Isolated real-backend browser suite and owner read-only smoke",
      "expected": "Recorded function coverage and honest live-provider limitations",
      "rollback": "Revert each reproducing repair separately",
      "status": "done"
    },
    {
      "title": "Independent review, documentation and full gate",
      "verify": "uv run python scripts/gate.py full",
      "expected": "Current-tree acceptance with external limitations recorded",
      "rollback": "Revert this feature only",
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "docs/ARCHITECTURE.md",
    ".claude/rules/alpha-web.md",
    ".claude/rules/alpha-cli.md",
    "docs/adr/",
    "apps/alpha-web/frontend/README.md"
  ],
  "out_of_scope": [
    "Live capital routing",
    "Weakening research admission or point-in-time checks",
    "Rewriting historical biometric receipts",
    "Executing arbitrary indicator code in the browser",
    "Unrelated benchmark changes"
  ],
  "files": [
    "apps/alpha-web/",
    "apps/alpha-cli/",
    "tests/unit/",
    "tests/integration/",
    "docs/",
    "CLAUDE.md",
    ".claude/rules/"
  ]
}
```

Implement in small testable patches within each slice. CLI/ControlStore remain authoritative; no engine imports in web, no statistical formula changes or seed changes. Market visualization is non-authoritative and must verify exact selected artifacts. Browser mutation tests use disposable stores. Existing uncommitted work is preserved.

Implementation and owner read-only smoke are verified; independent reviews found no remaining blockers by inspection. Final Python: 4,740 passed, 93.11% coverage. Frontend component: PASS, including 196 browser tests. Full repository acceptance remains blocked by the concurrent benchmark PDF scratch script failing global ruff; slice 6 remains in progress. **Acceptance (2026-10-05):** the canonical full gate passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC, all six components, 969 s); see the 2026-10-05 record in `docs/BUILD-STATUS.md`. The blocker was the benchmark scratch script, since archived outside the repository. See [delivery audit](../../audit/2026-09-30-terminal-usability.md).
