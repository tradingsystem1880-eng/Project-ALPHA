# Guard unscheduled ML membership claims

**Current status — 2026-10-23:** Local protective slice implemented on base `99f2d472dd4511b446e1198ae80201e7207d089d`; focused synthetic checks passed, including web projection regressions. Independent review found and verified a web visibility gap; a narrow additive membership-status field now carries the validated declaration through result, evaluation and tear-sheet APIs. Independent re-review approved the final slice with no remaining blocker. Full gate, commit and merge were not requested and were not performed.

**Delivery state:** Completed (bounded local protective slice only; no point-in-time schedule support).

```json
{
  "schema_version": 1,
  "title": "Reject unscheduled point-in-time ML membership claims",
  "context": "At main 99f2d472dd4511b446e1198ae80201e7207d089d, schema versions 1 and 2 accept a point_in_time label without carrying a membership schedule. New raw and project exports converge on prepare_exchange. Historical result inspection shares request integrity validation with worker execution and replay, so the guard must distinguish inspection from execution and must not rewrite frozen files.",
  "assumptions": [
    {
      "statement": "No current ML request schema can verify date-specific membership; schema_version 2 identifies the ensemble recipe and does not add a membership schedule.",
      "verified_by": "Exact request field sets in apps/alpha-cli/src/alpha_cli/ml_contract.py and workers/qlib/src/alpha_qlib_worker/contract.py."
    },
    {
      "statement": "Current-membership requests remain usable only with their explicit nonempty survivorship warning; promotion eligibility remains unchanged.",
      "verified_by": "Existing ALPHA and worker request validators plus canonical replay promotion_eligible=false policy."
    }
  ],
  "alternatives_considered": [
    "Reject point_in_time at new preparation while retaining immutable legacy artifacts for clearly marked read-only inspection.",
    "Do not add a schedule-bearing contract version or date-varying model support in this slice."
  ],
  "pre_mortem": [
    "A global request-validator rejection could make old result bundles uninspectable; keep persisted integrity reads permissive and test hashes before and after inspection.",
    "An old frozen request could still be re-executed or replayed; guard CLI/worker execution and replay-signal generation.",
    "Schema version 2 could be mistaken for a membership-capable protocol; reject unscheduled point_in_time for every currently supported request version."
  ],
  "slices": [
    {
      "title": "Add synthetic regressions for new ingress and historical inspection",
      "verify": "Focused ML contract, project exporter, and worker tests.",
      "expected": "Raw prepare and project export reject point_in_time; current_membership with warning succeeds; a frozen legacy point_in_time result remains inspectable without byte or hash changes and is explicitly marked unverified; execution and replay reject it.",
      "rollback": "Revert only the new regression cases and fixture edits.",
      "files": ["tests/unit/test_ml_contract.py", "tests/unit/test_ml_input.py", "tests/unit/test_ml_boundary_guards.py", "workers/qlib/tests/test_fake_worker.py"],
      "status": "done"
    },
    {
      "title": "Add narrow preparation, inspection, and execution boundaries",
      "verify": "Run the focused ML contract, exporter, CLI integration, and worker tests; inspect immutable artifact hashes and final diff.",
      "expected": "No new unscheduled point_in_time exchange can be published; legacy results remain readable with declared_unverified status; worker training and ALPHA replay cannot consume that claim; current-membership warning behavior and promotion gates stay intact.",
      "rollback": "Restore only the touched validator, CLI, worker, tests, and current-state documentation from the local diff; no frozen artifacts are modified.",
      "files": ["apps/alpha-cli/src/alpha_cli/ml_contract.py", "apps/alpha-cli/src/alpha_cli/ml_cmds.py", "workers/qlib/src/alpha_qlib_worker/contract.py", ".claude/rules/alpha-cli.md", "docs/BUILD-STATUS.md"],
      "status": "done"
    },
    {
      "title": "Carry unverified membership status through read-only web projections",
      "verify": "Focused web API/unit response tests and regenerated OpenAPI/TypeScript contracts.",
      "expected": "Prepared and completed legacy point_in_time exchanges remain read-only and explicitly declared_unverified in list/detail plus result, evaluation and tear-sheet responses; current-membership projections remain typed and labeled as warning-bearing.",
      "rollback": "Revert only the additive projection fields, tests and generated API contracts; preserve the CLI and worker guard behavior.",
      "files": ["apps/alpha-web/src/alpha_web/_ml.py", "apps/alpha-web/src/alpha_web/api/ml.py", "tests/unit/test_web_ml.py", "tests/integration/test_web_api_ml.py", "apps/alpha-web/frontend/openapi.json", "apps/alpha-web/frontend/src/api/generated.ts"],
      "status": "done"
    }
  ],
  "tier_impact": ["none"],
  "docs_to_update": [".claude/rules/alpha-cli.md", "docs/BUILD-STATUS.md", "docs/superpowers/plans/2026-10-23-ml-membership-claim-guard.md"],
  "out_of_scope": [
    "Membership schedule v2, date-varying universes, or point-in-time model support",
    "Any changes to downstream promotion gates or promotion eligibility",
    "Private data or holdout access, full gate, dependency installation, commit, push, publication, or merge"
  ],
  "files": ["apps/alpha-cli/src/alpha_cli/ml_contract.py", "apps/alpha-cli/src/alpha_cli/ml_cmds.py", "workers/qlib/src/alpha_qlib_worker/contract.py", "apps/alpha-web/src/alpha_web/_ml.py", "apps/alpha-web/src/alpha_web/api/ml.py", "tests/unit/test_ml_contract.py", "tests/unit/test_ml_input.py", "tests/unit/test_ml_boundary_guards.py", "tests/integration/test_ml_cli.py", "tests/unit/test_web_ml.py", "tests/integration/test_web_api_ml.py", "workers/qlib/tests/test_fake_worker.py", "apps/alpha-web/frontend/openapi.json", "apps/alpha-web/frontend/src/api/generated.ts"]
}
```
