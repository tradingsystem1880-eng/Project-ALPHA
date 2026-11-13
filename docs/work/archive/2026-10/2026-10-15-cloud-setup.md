# Reproduce cloud root/frontend setup

**Current status — 2026-10-17:** Accepted through [PR #65](https://github.com/tradingsystem1880-eng/Project-ALPHA/pull/65) with seven successful required checks. Separate environment verification recorded on 2026-10-17 confirmed persistent caches and fresh-task startup, alpha info, and Chromium smoke; those environment checks are distinct from PR CI.

**Delivery state:** Completed (accepted provisioning delivery via PR #65 only; dated environment checks remain separate evidence).

Earlier dated status and incident entries are preserved as historical records.

```json
{
  "schema_version": 1,
  "title": "Reproduce cloud root/frontend setup",
  "context": "A fresh cloud session has Python/frontend dependencies but lacks writable cache settings and the pinned browser. Prepare an isolated synchronous installer without changing the frozen cleanup candidate.",
  "assumptions": [{"statement": "Cloud environment settings must supply cache variables to later shells and MCP processes.", "verified_by": "All six variables were absent in the inherited verification shell; subprocess exports cannot alter parent environments."}],
  "alternatives_considered": ["Do not reuse PR #52 background hooks, unlocked dependency fallbacks, browser aliases or suppressed failures. Use one synchronous entrypoint."],
  "pre_mortem": ["Read-only home caches break installs: export writable defaults before invoking tools.", "An installer hides download or browser errors: preserve original output/status and stop before subsequent steps."],
  "slices": [
    {"title": "Implement locked provisioning and failure tests", "verify": "python -m pytest -q tests/unit/test_cloud_setup.py --no-cov", "expected": "Ordered locked installs, exported paths and original failures verified offline", "rollback": "Remove new script and focused tests", "status": "done"},
    {"title": "Document environment settings and host prerequisites", "verify": "bash -n scripts/cloud_setup.sh; focused cloud setup tests; plan-check; manual-size guard; warm provisioned runtime evidence", "expected": "Later-shell settings and Linux browser-library prerequisites are explicit; aggregate acceptance remains a separate release gate", "rollback": "Remove setup documentation additions", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["README.md", "CLAUDE.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Frozen cleanup checkout", "Account/network/security settings", "Dependency or browser substitutions", "Worker/tool installation", "Quant, DAG, bias and determinism behavior", "Commit, publish or merge"]
}
```

**Historical delivery state before PR #65:** Completed implementation; exact-tree release acceptance was pending.

Exact-tree full, independent review and hosted acceptance are recorded separately in the delivery receipt.

Focused validation: eight offline provisioning tests and the existing manual-size guard pass.
A separate cold-bootstrap run passed in 62.55 seconds on source candidate `b2c43735`: the
environment began without a virtualenv, `node_modules`, five writable caches, or the pinned
browser. Its receipt is
`/Users/hunternovotny/Desktop/Project-ALPHA-reconciliation-evidence/cloud-setup-cold-bootstrap-receipt.json`
(SHA-256 `6098d7e75c5c2faaca2278d2528c76c360389cb812b29074439d5e3dd023d771`). It records locked
Python and npm installs, pinned Chromium setup, CLI smoke, and static-page Chromium runtime smoke.
This proves cold setup on that source candidate; it is not full-gate or release evidence for the
newer integrated tree. The existing real-backend case-capture browser journey also passes at
chromium-minimum (1 test, 48.3 seconds). The browser step exercises Chromium on a static page, not
the frontend app. Persistent environment variables for later shells and host browser libraries
remain prerequisites; exact-tree full, independent review, and hosted acceptance are tracked
separately.
