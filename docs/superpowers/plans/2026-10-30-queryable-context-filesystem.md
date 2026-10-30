# Source-bound queryable context filesystem

**Delivery state:** Implemented candidate; aggregate acceptance and independent review remain required.

```json
{
  "schema_version": 1,
  "title": "Source-bound queryable context filesystem",
  "context": "H26 in the canonical feature readiness checklist requests lean queryable context. Main f847581 has identity, routing, stage contracts and Atlas provenance; intent, feature and task retrieval still requires manual search. Extend Atlas over existing sources without another graph or ledger.",
  "assumptions": [
    {"statement": "Public tracked documents retain their own authority and dated claims.", "verified_by": "CLAUDE.md, docs/context/README.md and Atlas README inspected on f847581."},
    {"statement": "ICM is an architectural reference, not backup or autonomous-performance evidence.", "verified_by": "Read primary arXiv2603.16021v2 PDF, 21 pages, sections 3-6; companion README and _core/CONVENTIONS.md at 02ba5d85c7871b75c7c702a2d8da6524723d53d4."}
  ],
  "alternatives_considered": ["Keep manual grep only; rejected because reusable source-bound handoffs and invalidation remain missing.", "Create a second knowledge store or numbered folder hierarchy; rejected in favor of on-demand Atlas views."],
  "pre_mortem": ["Search follows a link into owner data or private tests; use tracked direct source allowlists and reject symlinks before opening.", "A saved excerpt outlives its source or silently drops contrary status; retain source sections, all matching exclusion references, source corpus digest, expiry and exact replay checks."],
  "slices": [
    {"title": "Extract bounded tracked source sections and deterministic scoped queries", "verify": "Atlas tests/test_context.py, Ruff, strict mypy", "expected": "Project, feature, task, decision and history excerpts with exact source hashes and line ranges; no private inputs.", "rollback": "Remove only new context modules and their tests.", "status": "done"},
    {"title": "Bind handoff receipts to source bytes, policy, query and expiry", "verify": "Fresh, changed, deleted, added, expired and tampered receipt regressions", "expected": "JSON receipts and readable Markdown/plain text; validation rejects stale or modified payloads without updating them.", "rollback": "Remove receipt and CLI slice while preserving source extractor.", "status": "done"},
    {"title": "Preserve configured ML cache across the existing web-to-CLI boundary", "verify": "Failing-first cache regression, existing credential isolation checks and both real capability-route regressions", "expected": "Installed-worker capability reads use the configured UV cache without forwarding HOME or provider credentials; no ML schema or PDF source changes.", "rollback": "Restore only the canonical cache-name allowlist entry and its public cache regressions.", "status": "done"},
    {"title": "Route, demonstrate, regenerate and independently review final candidate", "verify": "Atlas component, root consistency, canonical full gate and exact final-tree independent review", "expected": "Working source-backed demonstrations, preserved patch, explicit acceptance blockers and no backup claim.", "rollback": "Restore only this task's documentation and generated output changes from f847581.", "status": "in_progress"}
  ],
  "tier_impact": ["dag"],
  "docs_to_update": ["tools/alpha-atlas/README.md", "docs/context/README.md", "CLAUDE.md", "docs/BUILD-STATUS.md"],
  "out_of_scope": ["Software Team control policy", "Research runtime and scientific context receipt admission", "General refactor", "Bulk document storage and Mac backup", "Protected test content", "Publication or merge without parent coordination"],
  "files": ["tools/alpha-atlas/src/alpha_atlas/context_sources.py", "tools/alpha-atlas/src/alpha_atlas/context.py", "tools/alpha-atlas/tests/test_context.py", "apps/alpha-web/src/alpha_web/_catalog.py", "tests/unit/test_web_invoke.py", "tools/alpha-atlas/README.md", "docs/context/README.md", "CLAUDE.md", "docs/BUILD-STATUS.md", "architecture/atlas/generated/inputs.json", "architecture/atlas/generated/graph.json", "architecture/atlas/generated/views/unknowns.json"]
}
```

## Research mapping and scope

Primary source: Jake Van Clief and David McDermott,
[Interpretable Context Methodology, arXiv2603.16021v2](https://arxiv.org/pdf/2603.16021v2),
21 pages. Companion [pinned source](https://github.com/RinDig/Interpretable-Context-Methodology/tree/02ba5d85c7871b75c7c702a2d8da6524723d53d4).
Read the PDF through its discussion, validity limits and future directions, plus the pinned
README and conventions. Existing ALPHA research map is in the
[foundation stage contract](2026-10-26-native-rule-authority.md#foundation-stage-contract-and-handoff-icm-aligned-alpha-adaptation).

| ICM role | Existing ALPHA home | This increment |
| --- | --- | --- |
| Identity | AGENTS.md and CLAUDE.md | Query routes back to these authorities. |
| Routing | docs/context/README.md and Atlas | Add on-demand scoped text retrieval to Atlas. |
| Stage contracts | Dated active plans; existing protocol routes | Retrieve plan sections; protocols remain linked through existing routes and are not indexed here. Do not infer completion. |
| Stable references | ADRs, rules, specs, governance | Preserve versions, decisions and status text with citations. |
| Per-run artifacts | Existing .alpha/state receipts/checkpoints | Optional redirected query receipts; never index these as instructions. |

Hash-based invalidation and receipt expiry are labelled ALPHA adaptations. ICM section 6
proposes traceability and change propagation as future work; section 4.6 reports no controlled
quality comparison. This delivery demonstrates engineering behavior only. Search does not settle
contradictions, prove semantic completeness, authorize execution or certify that a feature works.
The canonical checklist remains the sole full-scope owner and is never rewritten by retrieval.

The tool belongs to the isolated Atlas project, outside the platform import DAG. It does not
read research datasets, change as-of handling or random seeds, execute plans, invoke an LLM,
or copy bulk documents. Git tracks durable source; ignored receipts remain local and require
separate preservation. Mac backup is separately owned and unavailable here.

## Implementation checkpoint

Two stdlib-only Atlas modules implement on-demand retrieval and source-bound JSON handoffs.
No source document is migrated or replaced. Focused context tests: 16 passed; strict mypy passed
for 25 Atlas source files. An earlier Atlas-wide candidate run passed 119 tests before the final
additional regression. Current aggregate results and final review belong to the exact-tree
task evidence; these earlier checks do not certify subsequent documentation/generated changes.

Git guards were installed using `uv run python scripts/git_guard.py install` in this checkout.
Patch checkpoints are retained under ignored `.alpha/state/context-delivery/`; no publication
or merge has occurred. Private-suite paths were checked by Git metadata only: no tracked
`tests/holdout/` files were found. No prior delivery's private-suite exception is adopted here;
private coverage and any required owner resolution remain separate acceptance obligations.

## Owner absence-only decision — 2026-10-30

The owner approved the bounded absence-only exception at 05:41 UTC for the four named
workstreams through delivery, including necessary integration corrections. The single supported
[policy record](../../../.claude/agents/independent-reviewer.md#four-workstream-through-delivery-absence-exception--2026-10-30)
preserves its scope and unchanged requirements; authorization provenance stays in private task
evidence. Private coverage remains UNVERIFIED. Earlier absence-only BLOCKs remain correct
history. Actual public failures still block, and final exact-tree checks and independent review
remain mandatory. Repository delivery follows the parent's coordinated authorization.

Before this approval record, all six public components passed on content tree
`34da43afed036d37379fc407b06bc29ccf8609a4` (`gate.compute_tree_hash`
`65bb2cd19462836e77c8619ea736399514d33f598fccfc91bc7fc2a73479f9ce`), based on
main `f847581f2703f6b5b36aeccdf877c4354a19e176`. The final full stamp was valid; independent
review found no blocking code defect and blocked solely on absent private coverage. That exact
patch, manifest, six receipts and review are preserved under ignored
`.alpha/state/context-delivery-pre-approval-20261030/`. This record changes the candidate and
does not extend that historical stamp to the new tree; final qualification/review evidence is
kept separately under `.alpha/state/context-delivery/`.

## Required integration repair: configured ML worker cache

The approval-record tree's real aggregate run failed two public safe-route checks:
`/api/ml/capabilities` and `/api/v3/ml/capabilities` returned 422 (6,695 passed, 61 skipped;
coverage 93.01% against the unchanged 93% floor). The approved private absence exception does
not waive these failures. Its failed receipt/log and the earlier passing tree remain preserved.

After the earlier full gate installed Qlib, capability inspection began invoking its installed
worker. The CLI worker already permits `UV_CACHE_DIR`, but the web's command-scoped environment
dropped that configured path. The worker's `uv` then failed at the protected fallback
`/home/agent/.cache/uv`; a direct CLI invocation inheriting the configured cache succeeded.
The producer initially repaired `_catalog._cli_environment` only for ML CLI commands.
Combined integration retains the Software Team correction: configured non-secret `UV_CACHE_DIR`
is a process resource shared by CLI commands; HOME and command-unrelated credentials remain
excluded. No cache-path fallback, error suppression, schema change, data read or in-process
ML import is added. The duplicate ML-only clause and contradictory cache-absence assertions
are excluded; capabilities/train credential-isolation checks complement the configured/absent
ML and generic-command regression.

The new public regression failed first on the missing variable. After the repair, that test,
the existing credential/auth-home isolation checks and both actual capability-route checks
passed (5 cases). Changed Python lint/format passed. Independent review and a new exact-tree
aggregate gate remain required. ML response-schema and PDF files stay with their separate owner;
this is a bounded transport integration repair under the approved through-delivery scope.
