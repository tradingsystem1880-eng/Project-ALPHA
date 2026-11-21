---
owner: command line application
sources:
  - apps/alpha-cli/src/**
  - apps/alpha-cli/pyproject.toml
verified: 7ed8392630bbf74c
---

# alpha-cli: code map and change loop

Where things are in the `alpha` command line, and how a change to it is checked. The routing page is [CONTEXT.md](CONTEXT.md).

## Code map

The `alpha` CLI composes data, strategies, the engine, validation, research and models, and owns the SQLite control store (projects, jobs, evidence, owner
receipts). It may import every package below it; nothing but the surfaces' public seams may import it, and the web app and MCP server call it as a subprocess.
It must never grant authority the owner did not give, and never route live capital.

Code: `apps/alpha-cli/src/alpha_cli/` (`_name.py` = private helper; `*_cmds.py` = command group, wired in `main.py`). Where to look:

| Sub-area | Modules (count) | Tests in `tests/unit/` |
|---|---|---|
| Research cases | `research_*` (22), `_research_cmd_parts`, `_research_artifact_io`, `_structural_digest`, `study_semantic` | `test_research_*` |
| Control store | `control_store`, `_control_*`, `owner_auth*`, `durable_lease`, `job_capacity`, `project_*` | `test_control_*`, `test_owner_*` |
| Rule tests, tools, setups | `{test,results,tool,partner,setup}_cmds`, `spine/`, `toolbox/` | `test_{spine,setup,toolbox}_*`, `test_contact_*`,
`test_look*` |
| Front door | `next_cmds` (read-only; reuses `spine/stores`, `spine/trial_reader`, `rdagent_discussion`) | `test_next_cmd`, `smoke/test_next_smoke` |
| Portfolio book | `spine/book` (pure maths); `results correlate` in `results_cmds`, `follow book` in `follow_cmds` | `test_book_math`, `test_results_correlate`, `test_follow_book_view` |
| Rule-test reading | `spine/reading` (pure), `spine/reading_read` (stored runs); text in `test_cmds`, `results_cmds`, `next_cmds`, `nightly_run` | `test_reading_rule` |
| Rule context gate (plan only) | `_context_gate` (gate vector), `_context_plan` (`alpha test --plan`); spec fields in `spine/spec` | `test_rule_context_gate`, `test_rule_context_identity`, `test_rule_context_plan` |
| Idea cards and the idea file | `idea_cmds`, `spine/idea_card` (cards under `<home>/ideas/`; the spec link is in no identity), `spine/idea_file`, `idea_map`, `idea_file_text` (read-only page per idea) | `test_idea_card`, `test_idea_file` |
| Library of published ideas | `library_cmds`, `spine/library` (records in `research/library/published/`, private notes under `<home>/library/private/`) | `test_library` |
| Forward follow | `follow_*` (10: `cmds`, `store`, `source`, `journal`, `chain`, `update`, `update_check`, `replay`, `book`, `show`; writes only `<home>/forward/`; no research module may import them) | `test_follow_*`, `smoke/test_follow_smoke` |
| Nightly real run | `nightly_*` (6: `cmds`, `config`, `run`, `steps`, `record`, `status`; runs real commands in child processes) | `test_nightly`, `smoke/test_nightly_smoke` |
| Runs, validation | `_artifacts`, `_identity`, `_seeds`, `_runner`, `_gauntlet`, `_optim`, `run_*`, `_suite*` | `test_run*`, `test_gauntlet*`,
`test_suite_*` |
| Market data, macro | `*crypto_*`, `data_cmds`, `_data_health`, `context*_cmds` | `test_{crypto,tiingo,alpaca,context,data_health}_*` |
| Native jobs | `_native_*` (20), `native_*` (6), `daily_*` (3) | `test_native_*`, `test_daily_*` |
| RD-Agent ledger, discussion and `alpha rdagent run`/`status` | `rdagent_*` (incl. `rdagent_cmds`, `rdagent_run_config`, `rdagent_run_status`), `_rdagent_*`, `spine/trial_*`, `ledger_cmds` | `test_rdagent_*`, `test_trial_*`, `test_ledger_cmds` |
| Machine learning, labels | `ml_*` (6), `_ml_*` (2), `_forecast*` (3), `forecast_cmds`, `labels_cmds` | `test_ml_*`, `test_forecast_*` |
| Paper, providers | `paper_*` (5), `_paper`, `_ibkr_paper`, `ibkr_what_if`, `provider*` (3) | `test_paper_*`, `test_provider_*` |
| Advisory models | `assistant_*` (6), `codex_*` (5), `investigation_*` (8), `comparison_acquisition*` | `test_assistant_*`, `test_codex_*` |

Many integration tests in `tests/integration/` use the same prefixes. Shared helpers live once: `_cli_json` (JSON emit and
option parsing), `_research_artifact_io` (D1/D2 artifact publication and reads) and `alpha_core.atomic` (atomic file writes);
do not add a private copy.

- Check: `uv run python scripts/gate.py check`. Engine imports stay lazy; `import alpha_cli` stays light (`test_public_seams.py`).
  RD-Agent: thirds, ties, gaps `_rdagent_membership`; identity, rescaling `_rdagent_identity`; inference `_rdagent_{stats,twins}`; `_rdagent_stability`.
- [Rule-test periods](../../research/tools/rule-test.md) · [Data health](../../research/tools/data-health.md)
  · [Tools](../../docs/reference/project/components/toolbox.md): market, risk, trades, costs, intervals.
- Setup trades report percent and stop-risk returns. [RD-Agent journeys](../../research/tools/rdagent-journey.md) and proposals explain verdicts and checks.
- Tests for the changed sub-area (above); a bias guard for any new data read; an integration test through the real command for any new command.

## Change loop

- A new or changed command: run `uv run python scripts/commands_reference.py` and commit the page.
  If the web or MCP surface exposes it, also run `uv run python scripts/check_openapi_operations.py --write`.
- The owning document: the sub-area's `docs/reference/invariants/cli-*.md` file (`alpha context` includes offline Bybit import/read:
  [data layer § Context data](../../docs/reference/project/components/data-layer.md#context-data));
  regenerated `docs/reference/commands.md` when commands change.

## Approvals bind structure

- Owner approvals bind code structure, not bytes ([ADR-0045](../../docs/adr/0045-approvals-bind-code-structure.md)): editing
  `research_intake.py`, `research_runtime.py`, `research_crypto_data.py` or `research_crypto_runtime.py` invalidates them only
  when behaviour changes (comments and formatting are free); every `alpha_cli` file the daily rule lane runs through
  (control store, owner auth, `research_runtime.py` and more; see the native file) feeds daily native rule approvals
  the same way, and `tests/unit/test_daily_guard_boundary.py` fails when a bound file imports an unbound one.
  `_structural_digest.py` itself is guarded: any edit invalidates every approval.

## Also read
| Read | Section | When |
|---|---|---|
| [architecture](../../docs/ARCHITECTURE.md) | Runtime data-directory layout | adding a folder under the data directory |
| [bounded discovery workflow](../../docs/operations/bounded-research-workflow.md) | — | running a bounded discovery or frozen-rule study |
| [Codex investigations runbook](../../docs/operations/codex-investigations.md) | — | running or changing a recorded-run investigation |
| [local operations runbook](../../docs/operations/README.md) | — | daily Tiingo data, IBKR Paper setup or the acceptance steps |
| [toolbox](../../docs/reference/project/components/toolbox.md) | — | `alpha tool`, `toolbox/`: adding a test, its honesty rules, what is not built yet |
