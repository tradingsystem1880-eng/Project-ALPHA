# Proposed context ownership and test-layout pilot

```json
{
  "schema_version": 1,
  "title": "Proposed context ownership and one-module test-layout pilot",
  "context": "Read-only audit of bf5baa75c8db0de8e85623c218fd89b1d4f5f668 found navigation gaps, one unavailable historical reference and large public test modules. This plan proposes bounded follow-up; no test move or policy change is accepted or implemented. Slice one is now authorized as a documentation-only candidate from accepted main dd5a924d709b8d60c97492043f2a82dac976105a; slice two is now a separate draft PR69 and slice three is an authorized bounded implementation candidate from accepted main c1fdba82a32c7aa01bedeb34306a26613e7f7bac.",
  "assumptions": [
    {
      "statement": "Existing operating, domain, evidence and gate authorities remain controlling.",
      "verified_by": "AGENTS.md, CLAUDE.md, capability authority matrix and scripts/git_guard.py inspected at the source base."
    },
    {
      "statement": "The original four-file archive remains preserved; future implementation and rollback must use the reviewed integrated documentation baseline, including its three added navigation lines.",
      "verified_by": "The original archive manifest verifies the preserved draft bytes; refresh baseline hashes for the reviewed integrated documentation before future implementation."
    }
  ],
  "alternatives_considered": [
    "Keep the current layout and improve links first; prefer this until retrieval demonstrates a gap.",
    "Reject mass moves, date-history rewrites, a second knowledge graph and test consolidation based only on file size."
  ],
  "pre_mortem": [
    "A nested test path silently changes platform selection because tests/_tiers.py uses exact parent keys; keep the pilot in tests/unit with the test_research_ prefix and prove parity.",
    "Historical unavailable policy text is mistaken for current authority; preserve provenance, label the reference unavailable and do not infer or restore protected content.",
    "Generated Atlas or API files are edited as authorities; use their existing producers and freshness checks."
  ],
  "slices": [
    {
      "title": "Assign artifact stewardship and validate existing entrypoint retrieval",
      "verify": "Review existing ownership roles and six two-hop retrieval routes; run bounded task-local positive/negative link, heading and Git source-anchor drift checks, focused existing checks, independent diff review and the unchanged exact-tree full gate.",
      "expected": "Documentation-only candidate with explicit missing relationships and syntactic freshness separated from semantic correctness and executed evidence. Keep in_progress pending parent review.",
      "rollback": "Preserve the original archive; restore the reviewed integrated documentation baseline, including its three added navigation lines, using refreshed baseline hashes; discard only the independently reviewed follow-up patch.",
      "status": "in_progress"
    },
    {
      "title": "Resolve one unavailable historical reference without recovering protected content",
      "verify": "Check the exact referring paragraph and public path metadata; preserve its historical claim with an explicit unavailable-reference annotation.",
      "expected": "No dead clickable target or inferred policy; no change to current gate/private-suite policy.",
      "rollback": "Restore the exact referring paragraph from the implementation base.",
      "status": "pending"
    },
    {
      "title": "Pilot one public research-store test module split with parity",
      "verify": "Before/after collection, marker/tier/fixture metadata, AST and outcome parity plus affected existing consistency checks and exact-tree full gate.",
      "expected": "Only the two selected test functions move; all parametrized cases, assertions, fixtures and authority behavior remain unchanged.",
      "rollback": "Restore original test module and remove only newly introduced pilot files from the isolated patch; restore generated outputs using the original inputs.",
      "status": "in_progress"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/superpowers/plans/2026-10-16-context-ownership-and-test-layout-pilot.md",
    "docs/BUILD-STATUS.md"
  ],
  "out_of_scope": [
    "Slice-two historical-reference edits in this pilot; keep its separate draft PR69 and recovery unchanged",
    "Hidden/private test content or missing-policy recovery",
    "Changes to product logic, test assertions, fixtures, thresholds, markers, tier classification rules or gate requirements",
    "Mass moves, deletions, history rewrites, provisioning repairs, manual installation, commit, push or publication; canonical gate behavior remains unchanged"
  ],
  "files": [
    "docs/superpowers/plans/2026-10-16-context-ownership-and-test-layout-pilot.md",
    "tests/unit/test_research_control_store.py",
    "tests/unit/test_research_semantic_payload.py",
    "tests/fixtures/research_semantic_payload_fixtures.py",
    "docs/BUILD-STATUS.md",
    "architecture/atlas/generated/inputs.json",
    "architecture/atlas/generated/graph.json",
    "architecture/atlas/generated/views/unknowns.json"
  ]
}
```

**Status (2026-10-17):** Slice one is present in accepted main; slice two remains separate in draft PR69. Slice three is an authorized implementation candidate, in progress pending frozen validation and independent parent review.
**Source inspected:** `bf5baa75c8db0de8e85623c218fd89b1d4f5f668`.
No runtime or test acceptance follows from source inspection or this plan's validation.
The schema tier value `none` describes this documentation proposal only; reclassify the actual
implementation diff under existing rules before starting. Slice one remains documentation-only; no test edit is authorized by this candidate.

## Scope and ownership

Stewardship below identifies the responsible artifact role, not a named maintainer or new authority.

| Artifact | Canonical owner/source | Freshness and retrieval |
|---|---|---|
| Operating instructions | [AGENTS](../../../AGENTS.md), [manual](../../../CLAUDE.md), applicable [rules](../../../.claude/rules/) | Existing manual size/link/relocation and awareness checks; context maps link back. |
| Current architecture and permissions | [Architecture](../../ARCHITECTURE.md), generated [authority matrix](../../governance/capability-authority-matrix.md) | Source boundaries and `check_openapi_operations.py`; no copied counts. |
| Decisions, intent, history | [ADR index](../../adr/README.md), dated specs/plans, append-only [build history](../../BUILD-STATUS.md) | Preserve status and supersession; no historical claim becomes current evidence. |
| Discovery | [Atlas](../../../tools/alpha-atlas/README.md), curated definitions, schemas, explicit CLI cache | Existing input hashes, resolved symbols, computed evidence and `generate --check`; never hand-edit outputs. |
| Navigation | [Context index](../../context/README.md), [Software Team](../../context/software-team.md), [ALPHA Quant Platform](../../context/alpha-quant-platform.md) | Preserve the current draft; any subsequent revision gets link/anchor checks and independent review. |
| Tests and fixtures | Owning public test layer and [test rules](../../../.claude/rules/tests.md) | Collection/tier/fixture/outcome parity; tests remain behavior evidence, not product authority. |

No deeper topical folders are proposed now. Add one only after repeated retrieval failures show
several active documents share a topic and a responsible steward; map all inbound links first.
Keep date-indexed plans, evidence archives, fixture goldens and generated artifacts in place.

## Retrieval acceptance before structural work

Demonstrate six tasks from the context index: locate a CLI change boundary, a new data-family
boundary, D2 authority, the randomized-price null, cloud readiness, and the current full-gate rule.
For each, reach the governing decision, plan/spec, source and representative public test in at most
two navigation hops where a relationship exists. Record missing relationships explicitly; do not
invent a source to meet the hop target. Source inspection records base commit/anchors separately
from command, exit, scope and tested-tree evidence. Keep private links and archive content excluded.
The October 14 corpus has 46 files and 296 links privately verified per the user; public intake
remains pending and it is not in GitHub. This plan imports none of that corpus.

## Slice-one candidate acceptance

Implementation base: `dd5a924d709b8d60c97492043f2a82dac976105a`; preserve the integrated baseline
and original archives. Independent pre-edit review selected a documentation-only implementation:
reuse the existing task-local link checker with synthetic negative cases rather than extending tests
and triggering Atlas input regeneration. This checker is retained with private task evidence, not
installed as a new persistent gate. Generated outputs, source, tests and all four Monte Carlo guides
remain unchanged. Existing authority roles above are reused rather than copied into another inventory.

- Reach decision, plan/spec, source and representative public check from the context index in at most
  two clickable hops where identified; state each missing relationship and representative-check limit.
- Validate all local targets/Markdown headings in the three context pages. Check inspected-commit
  availability, anchor membership, current existence and staged/unstaged Git drift for capability-table
  implementation/check files. Use metadata only for protected targets; directory links are navigation.
- Demonstrate valid context passes and broken target/heading, unavailable commit and changed/missing
  source anchors are rejected with synthetic public fixtures. Preserve exact script, commands and exits.
- Distinguish syntactic link/byte freshness from semantic source correctness, test adequacy and executed
  receipts. Review public source separately; never recover unavailable policy or ingest private research.
- Run focused existing checks, independent exact-diff review and the unchanged canonical full gate on
  the final candidate. Record results and tree/diff hashes under ignored task-local evidence; append
  build history without asserting acceptance in advance. Return for parent review before commit/PR.

## One historical reference: bounded resolution

Only the referring paragraph in
[2026-10-08 repository hygiene](2026-10-08-repository-hygiene.md) is in scope.
It links to the unavailable filename `2026-10-09-engineering-holdout-policy.md`.
Do not read hidden suites, private archives, deleted protected-policy contents or owner stores.
Do not reconstruct the missing document or adopt its historical policy claim.

In a separately authorized implementation, confirm absence by public path metadata. Replace only
the dead Markdown link with its filename as inline code and append an annotation that the target
is unavailable in the inspected tree and supplies no current policy authority. Preserve the dated
claim as historical context; cite the existing manual and commit guard for current requirements.
Record the before/after paragraph, source commit and absence check. Accept only when the dead
clickable target is gone, all remaining local links resolve, and no current policy text changed.
If public evidence contradicts the proposed annotation, stop and revise the plan instead of guessing.

## One-module pilot: exact boundary

Source: [test_research_control_store.py](../../../tests/unit/test_research_control_store.py).
Move only these existing functions into proposed `tests/unit/test_research_semantic_payload.py`:

- `test_semantic_payload_accepts_the_frozen_study_second_precision_cutoff`
- `test_semantic_payload_requires_canonical_text`, retaining all three named parameter cases.

This is four collected cases at the inspected base; baseline collection must confirm that count.
All other tests remain in the original module. Do not use this pilot to reorganize other modules.
Both paths stay directly under `tests/unit/` with `test_research_` names, preserving the current
platform-prefix match; prove this through [the classifier](../../../tests/_tiers.py), not inference.

If sharing is needed, move only `_semantic_source`, `_semantic_definition_payload` and
`_semantic_review_payload` unchanged into proposed
`tests/fixtures/research_semantic_payload_fixtures.py`. Import them explicitly in both modules;
never import one test module from another or introduce wildcard imports/global conftest fixtures.
Retain constants and dependencies with identical values; defer the pilot if this requires a broader
fixture rewrite. Preserve function bodies, decorators, parameter values/IDs, raises/match checks,
assertions, database isolation, seeds, timestamps and cleanup exactly. No golden/data edits.

## Before/after evidence and exact acceptance

Prerequisite: an independently provisioned environment and a recorded clean implementation base.
Preserve the navigation draft hashes. Create an isolated implementation branch only after approval;
keep private suites outside this pilot's explicit collection and execution scope.

1. Before moving, collect the source module and all public Python layers with identical installed
   Python, pytest plugins and options. Use a temporary read-only collection plugin to record node ID,
   test name/parameter ID, markers, resolved fixture names and `classify_platform` result as JSON.
   Store supporting evidence under ignored `.alpha/state/`; do not change collection configuration.
2. Freeze an explicit mapping for the four moved node IDs: old file prefix → new file prefix;
   function and parameter suffixes stay exact. After moving, normalize only those four mapped paths.
   Require identical sorted case multisets, no extras/missing/duplicates, identical tier and markers,
   and identical resolved fixtures. Compare test ASTs including decorators and helper ASTs; permitted
   differences are module placement and explicit imports only. Counts alone are insufficient.
3. Execute the original module before and both pilot modules after, using the existing Linux process
   owner with the same options. Require identical per-case pass/skip/xfail/xpass outcomes and reasons,
   zero unexpected failures, and no changed fixture scope or test selection. Preserve original failures;
   diagnose them separately rather than changing assertions or weakening acceptance.
4. Inspect callers/imports, `tests/_tiers.py`, `tests/conftest.py`, explicit CI/gate file selections,
   coverage source/omit settings, Atlas test-node references and documentation links. Regenerate Atlas
   only through its existing producer in the authorized implementation; inspect the resulting diff.
   No unrelated graph/API/SPA regeneration or classification changes belong in the pilot.
5. Require focused public checks, lint/type/import checks appropriate to the actual helper imports,
   documentation/Atlas consistency and freshness, independent final-diff review, and the existing
   exact-tree canonical full gate before commit. No absent/private coverage is represented as passed.
   A missing environment or required receipt blocks acceptance; it is not a new exception.

Command shapes for the future implementation (not executed or accepted by this plan):

```sh
.venv/bin/python scripts/run_owned_test.py -- .venv/bin/python -m pytest --collect-only -q -p no:cacheprovider tests/unit/test_research_control_store.py
.venv/bin/python scripts/run_owned_test.py -- .venv/bin/python -m pytest --collect-only -q -p no:cacheprovider tests/unit tests/integration tests/bias_guards tests/oracles tests/holdout_seed
.venv/bin/python scripts/run_owned_test.py -- .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_research_control_store.py
.venv/bin/python scripts/run_owned_test.py -- .venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_research_control_store.py tests/unit/test_research_semantic_payload.py
uv run python scripts/gate.py full
```

After-state collection adds the new module explicitly to the first command; the public-layer command
already discovers it. Attach the temporary metadata plugin to both states; define its exact invocation
and retain its hash before executing the pilot. These command shapes alone do not prove metadata parity.
The full gate is unchanged and has its existing scope; running it requires separate authorization.

## Rollback and release boundary

Retain the original module/helper bytes, node mapping, input hashes and generated-output snapshot.
Rollback the isolated pilot by restoring those exact bytes and withdrawing only its new files;
recheck original collection/tier/fixture metadata and Atlas freshness. Preserve all failure receipts.
Never reset shared work, remove the navigation draft or discard historical evidence.
Report each slice as pending until its stated checks and review pass. Delivery updates, if later
implemented, append to build history rather than rewriting it. Full-gate acceptance remains pending;
this proposal and its focused documentation checks confer no commit, push or publication approval.

## Slice-three candidate (2026-10-17)

Implementation base: `c1fdba82a32c7aa01bedeb34306a26613e7f7bac` on a separate pilot
branch. The PR69 historical-reference annotation is excluded. This authorization
supersedes the earlier proposal-only restrictions for this bounded pilot only.

Move exactly the two named test functions (four cases) and share the three named
constructors plus the unchanged `PROJECT_ID` constant through explicit imports.
No assertions, parameter values, fixture semantics, product behavior or decision
authority change. Protected classifier, conftest and runner implementations remain
unopened; the actual collected platform marker supplies the observed tier evidence.

Before/after observation collected 135 module cases and 5,839 public-layer cases.
After normalizing only the four approved node IDs, collection metadata, markers,
parameter IDs, selected fixture definitions and actual request scope groups match.
Both module executions passed all 135 cases, with matching per-phase outcomes,
fixture parameter indices and within-scope lifecycle order. The two tests, three
helpers and constant retain identical ASTs; other original non-import ASTs match.
The temporary metadata observer and command recorder received independent method
review before execution. No fixture values or protected source contents were read.

The documented Atlas producer may update its three generated JSON outputs and only
existing `docs/atlas/` Markdown outputs directly changed by this relocation. Preserve
explicit before/after manifests and review the exact generated diff; never hand-edit
these outputs. No API/SPA generation or unrelated source changes belong here.
Focused checks, independent final exact-diff/evidence review and this pilot's own
canonical full gate remain required on the frozen candidate. Actual Codex review
and public release remain pending; this record grants no publication or merge.

Rollback restores only this pilot's original module/plan bytes and its append-only
build entry, removes only the two newly introduced files, and restores the approved
producer outputs from preserved inputs. Preserve unrelated work and all failure
receipts; recheck collection, fixture/tier parity and Atlas freshness after rollback.
