# Paper-to-experiment provenance

**Delivery state:** The source-link, retention, and locked-worker launcher slices are complete. This successor adds a project-bound source-screen check and download for the exact retained owner PDF bytes; focused verification is recorded separately, and no full gate is claimed for this successor.

```json
{
  "schema_version": 1,
  "title": "Paper-to-experiment provenance",
  "context": "Connect owner-screened, page-anchored paper claims and their reported dataset/code references to the existing frozen source pack, registered research dataset, approved exploration contract, and D1 manifest.",
  "assumptions": [
    {"statement": "Existing source packs, SourceAnchorV1, rd_ registration, analysis-plan registry, and owner approval remain the authoritative seams.", "verified_by": "Current main source inspection at 3f7b23185c29b2542605bd41b9485016c2ef3e79."},
    {"statement": "Paper-reported links are untrusted references; recording a link grants no access, license, acquisition, code execution, or reproduction claim.", "verified_by": "Literature-review protocol and user scope."}
  ],
  "alternatives_considered": [
    "A new resource-link database table or MCP endpoint duplicates the immutable source pack and is out of scope.",
    "Inferring equivalence from a paper link would falsely claim reproduction; the owner must approve an explicit dataset mapping in the exploration contract, while code references remain provenance-only without a local code registry."
  ],
  "pre_mortem": [
    "A link could cross project boundaries or cite a draft claim instead of a screened, anchored claim.",
    "An unavailable or proprietary reference could be mistaken for acquired data or executable code.",
    "A mapping could name an unregistered dataset or analysis family omitted from the frozen plan."
  ],
  "slices": [
    {"title": "Freeze typed paper resource links", "verify": "uv run --locked --no-sync pytest -q tests/unit/test_paper_resources.py tests/unit/test_research_control_store.py", "expected": "Only screened same-project claims and verified page anchors enter the content-addressed pack; legacy packs remain readable.", "rollback": "Remove the additive paper_resources definition contract and its validation/tests.", "status": "done"},
    {"title": "Bind owner-reviewed mapping to D1", "verify": "uv run --locked --no-sync pytest -q tests/integration/test_research_cli.py::test_empirical_daily_draft_binds_the_registered_dataset_and_reaches_deep_research", "expected": "A proposed dataset mapping names an existing rd_ dataset and a family in the frozen plan; approval revalidates it and D1 records it. Code references without a local code registry remain blocked_data and not_executed.", "rollback": "Remove the additive draft mapping and D1 manifest projection; retain source packs and existing D1 behavior.", "status": "done"},
    {"title": "Retain original owner PDF bytes", "verify": "uv run --locked --no-sync pytest -q tests/unit/test_research_local_pdf.py", "expected": "Owner-selected PDF bytes are stored once below the fixed literature root, bound to the existing source id/hash, and reported available only after verified bounded reads; missing, corrupt, unsafe, and non-owner states remain explicit.", "rollback": "Remove the additive raw-PDF artifact methods and import binding; keep prior extracted-text behavior and report originals as unavailable.", "status": "done"},
    {"title": "Launch the locked worker module without resolving its build backend", "verify": "pytest -q tests/integration/test_research_cli.py::test_sources_fetch_drives_the_isolated_worker_with_closed_argv tests/integration/test_research_cli.py::test_literature_worker_preserves_an_explicit_cache_directory tests/integration/test_research_cli.py::test_literature_worker_rejects_an_unusable_explicit_cache tests/integration/test_research_cli.py::test_literature_worker_cleans_temporary_cache_after_subprocess_failure tests/integration/test_research_cli.py::test_literature_worker_requires_checked_out_module_source tests/integration/test_research_cli.py::test_literature_worker_safe_path_ignores_a_caller_directory_module", "expected": "Use the checked-out worker src directory and run `python -P -m literature_worker` with `--locked --no-sync`; require the worker environment to be prepared from its lock without installing the project.", "rollback": "Restore the console-script `uv run` command and its original launcher assertions.", "status": "done"},
    {"title": "Serve the retained original PDF from the Literature source list", "verify": "pytest -q tests/integration/test_research_cli.py::test_research_source_original_pdf_cli_verifies_before_returning_bytes tests/integration/test_web_api_research.py::test_original_pdf_api_serves_only_verified_same_project_bytes; npm test -- --run src/api/research.test.ts", "expected": "The mounted read-only source route returns status without bytes on HEAD and serves only size-, signature-, ownership-, and SHA-verified PDF bytes on GET; the Literature panel exposes explicit status and download controls; missing, corrupt, unavailable, and cross-project cases cannot return substituted bytes.", "rollback": "Remove the source-original-pdf API/client/panel seam while leaving the existing CLI source-screen status and retained original unchanged.", "status": "focused-verified"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["README.md", "docs/BUILD-STATUS.md", "docs/atlas/research-flow.md", "docs/atlas/cli-flow.md", "docs/atlas/system-map.md"],
  "out_of_scope": ["Network retrieval, downloads, credentials, code execution, provider changes, new database table, MCP endpoint, model calls, strategy promotion, and live execution."],
  "files": [
    "apps/alpha-cli/src/alpha_cli/paper_resources.py",
    "apps/alpha-cli/src/alpha_cli/local_pdf_cmds.py",
    "apps/alpha-cli/src/alpha_cli/control_store.py",
    "apps/alpha-cli/src/alpha_cli/research_cmds.py",
    "apps/alpha-cli/src/alpha_cli/research_d1.py",
    "apps/alpha-web/src/alpha_web/_research.py",
    "apps/alpha-web/src/alpha_web/api/research.py",
    "apps/alpha-web/frontend/openapi.json",
    "apps/alpha-web/frontend/src/api/generated.ts",
    "apps/alpha-web/frontend/src/api/client.ts",
    "apps/alpha-web/frontend/src/panels/EvidenceHub.tsx",
    "apps/alpha-web/frontend/src/api/research.test.ts",
    "apps/alpha-web/src/alpha_web/static/app/",
    "tests/unit/test_paper_resources.py",
    "tests/unit/test_research_control_store.py",
    "tests/unit/test_research_local_pdf.py",
    "tests/integration/test_research_cli.py",
    "tests/integration/test_web_api_research.py",
    "README.md",
    "docs/BUILD-STATUS.md",
    "tools/alpha-atlas/src/alpha_atlas/generators/frontend_scan.py",
    "tools/alpha-atlas/tests/test_frontend_scan.py",
    "tools/alpha-atlas/src/alpha_atlas/core/mermaid.py",
    "tools/alpha-atlas/tests/test_mermaid.py",
    "architecture/atlas/cache/cli-commands.json",
    "architecture/atlas/generated/graph.json",
    "architecture/atlas/generated/inputs.json",
    "architecture/atlas/generated/views/unknowns.json",
    "docs/atlas/cli-flow.md",
    "docs/atlas/research-flow.md",
    "docs/atlas/system-map.md"
  ]
}
```
