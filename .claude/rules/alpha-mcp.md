---
paths:
  - "apps/alpha-mcp/**"
---
# alpha_mcp rules

Verbatim relocation from the pre-v2 CLAUDE.md MODULE MAP (drift-tested against `tests/fixtures/claude_md_v1.md`). The core `CLAUDE.md` DAG paragraph and golden rules still apply here.
### `alpha_mcp` (`apps/alpha-mcp/src/alpha_mcp/`) — MCP server (top of DAG; subprocesses the `alpha` CLI, composes nothing). Launch: `uv run alpha-mcp` (repo `.mcp.json` auto-launches it in Claude Code).
| Module | Responsibility | Key public symbols |
|---|---|---|
| `server.py` | FastMCP instance + 59 bounded tools + `main()` (stdio): 12 retained generic tools, 30 typed v3 tools, six Research Scientist capture/get/propose/launch/status/report tools, six ADR-0022 Codex-seam tools (get_research_brief, build/get_research_context_packet, add_research_note agent-authored-only, list/get_research_protocol), and five ADR-0023 read-only data-inventory tools (get_data_inventory/quality/candles ≤500 bars, list_snapshots, get_provider_registry). Research MCP cannot approve/decide or consume D2; no MCP tool reveals a holdout or places an order. | legacy actions/reads plus typed v3 control, evidence, and bounded research resources |
| `_invoke.py` | Subprocess core: run `alpha`, parse `-> run <id>`, read manifest, and lease/cancel/reap direct heavyweight children (fail-loud on non-zero exit or lease failure) | `run_alpha(args, *, data_dir, run_type)` |
| `_control.py` · `_types.py` | Subprocess typed CLI projections and strict bounded MCP response models | project/job/evidence/suite/chart projection helpers and Pydantic outputs |
| `_runs.py` | Filesystem reads over the run store | `get_run`, `list_runs` |

Retained action tools take typed common knobs plus a deprecated `options` compatibility dict whose
keys come from a closed, bounded per-tool vocabulary (`{"lookback":"5"}` → `--lookback 5`); it
does not accept arbitrary CLI flags. Strategy `params` are bounded and restricted to declared
`--param name=value` fields. Managed model/tokenizer values reject filesystem-like paths, and
run-producing action responses use capped manifest reads with declared v3 artifact verification.
Adding/removing a CLI command? Update `server.py`'s tool surface and compatibility allowlists to
match.

