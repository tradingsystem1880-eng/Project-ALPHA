# Backend CI setup ownership

**Delivery state:** Completed — merged via PR #113

**Historical delivery state (as first recorded):** Implementation complete; delivery acceptance requires exact-tree full-gate and independent-review receipts.

```json
{
  "schema_version": 1,
  "title": "Backend CI setup ownership",
  "context": "Remove repeated root setup in the same hosted backend job without changing canonical component commands. Original baseline 5da0a965; reconciled onto main 30246d08 after PR112. Other active feature owners retain their source and checklist sections.",
  "assumptions": [
    {"statement": "Backend component bootstrap is stdlib-only until its existing locked setup.", "verified_by": "gate.py and gate_components.py source inspection and real offline setup fixtures."},
    {"statement": "Worker and frontend setup cannot be removed on the same evidence.", "verified_by": "Separate hosted jobs, isolated worker project directories, and Playwright provisioning before frontend component installation."}
  ],
  "alternatives_considered": ["Keep repeated root setup: correct but unnecessary before the backend component's own setup.", "Skip warm installs or add setup stamps: rejected because dependency freshness and failure behavior must remain unchanged."],
  "pre_mortem": ["Cold bootstrap could depend on project packages: exercise it before a virtual environment exists.", "Changed configuration or unavailable dependencies could reach checks: retain real lock/sync failure and stop-before-check fixtures."],
  "slices": [
    {"title": "Verify setup ownership and remove backend pre-install", "verify": "uv run pytest -q tests/unit/test_ci_backend_bootstrap.py tests/unit/test_gate_components.py", "expected": "Cold/warm/repair succeed; changed config and invalid lock fail; failed sync cannot reach checks.", "rollback": "Restore the backend job's original install step and launcher.", "status": "done"},
    {"title": "Qualify the final integrated candidate", "verify": "README evidence, Atlas freshness, canonical full gate and exact-tree independent review", "expected": "Every existing check and the 93% coverage floor pass; private coverage stays explicitly unverified if absent.", "rollback": "Revert only this scoped workflow slice.", "status": "in_progress"}
  ],
  "tier_impact": [],
  "docs_to_update": ["CLAUDE.md", "docs/operations/development-loop.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Other active feature source and canonical checklist", "Research/model execution", "Private test source or an inherited absence exception", "New framework, gate bypass, Mac work or data acquisition"],
  "files": [".github/workflows/ci.yml", "tests/unit/test_ci_backend_bootstrap.py", "CLAUDE.md", "docs/operations/development-loop.md", "docs/BUILD-STATUS.md"]
}
```

Before: the backend job explicitly executes `uv sync --locked`, starts a project-aware
`uv run` (which may synchronize), then executes the component's `uv lock --check`
and `uv sync --locked`. After: `uv run --no-project --python 3.12` starts the same
stdlib-only gate, whose canonical lock and sync commands remain unchanged. This removes
one explicit sync and the launcher's implicit project synchronization. No elapsed CI
speedup is claimed; hosted validation remains pending. Separate jobs keep their setup.

The editable fixtures use a tiny local wheel with networking disabled. They execute
the actual workflow launcher and component's real setup commands, substituting only
the expensive checks after setup with a dependency import. They verify setup behavior,
not full-gate acceptance. A deliberately unavailable wheel after successful lock
validation exercises a real sync failure. Earlier fixture/type failures remain in task
evidence and were corrected before qualification.

At intake, preflight found generated Atlas drift, and Git metadata identified no tracked
`tests/holdout/` files. This new optimization does not inherit a previous task's private
absence exception. Regenerate Atlas only after final integration; do not run aggregate
qualification in a loop while prerequisites or owner-scope decisions remain unresolved.
No publication or merge is claimed by that historical checkpoint.

## Approved sequential integration — 2026-11-04

The owner approved this bounded change, necessary fixes and its own absence-only
private-suite exception through normal guarded delivery. The durable scope is in the
[reviewer instructions](../../../../records/2026-11-hidden-suite-exceptions.md#backend-ci-setup-through-delivery-absence-exception--2026-11-02).
Private coverage remains UNVERIFIED. No earlier exception is reused. The parent
released the sequencing hold after PR112 merged at `30246d08`; the original patch,
six-file hashes and content identity were verified before reconciliation. The only
source reconciliation conflict was the appended build history; both owners' entries
are retained. This slice changes no application DAG, point-in-time semantics or seeds.

README's local locked setup and unchanged full-gate instructions remain accurate;
this internal hosted-bootstrap change is documented in the existing development loop.
Generated Atlas outputs and native README/review attestations bind the final candidate.
Qualification results belong to those exact-tree receipts, not the earlier 98-test run.
