**Delivery state:** Completed with scoped owner exception (2026-09-28); exact-tree receipts govern guarded delivery.

# Codex second-model seam repair

```json
{
  "schema_version": 1,
  "title": "Codex second-model seam repair",
  "context": "Owner asked to verify that Claude Code can reach Codex. codex-cli 0.154.0 removed the `mcp-server` subcommand that `.mcp.json` launched (every session reported codex CONNECTION_CLOSED), retired the bridge default model gpt-5.3-codex-spark, and the desktop Codex apps rewrite the shared models cache with an older client's model list, flipping the bridge probe to a false unavailable.",
  "assumptions": [
    {"statement": "`codex exec` and every flag the bridge passes still exist in codex-cli 0.154.", "verified_by": "`codex exec --help`; live research and review round-trips returned available: true"},
    {"statement": "gpt-6-astra is the right default: it is the owner's own Codex default and supports efforts low..ultra.", "verified_by": "~/.codex/config.toml and models_cache.json inspection; unit test pins the literal"},
    {"statement": "No MCP-serving mode replaces `codex mcp-server` in 0.154; `codex app-server` speaks its own JSON-RPC.", "verified_by": "`codex --help`, `codex mcp --help`, stdin probe of `codex app-server`"}
  ],
  "alternatives_considered": ["Keep the dead `.mcp.json` entry and tolerate the per-session connection error: rejected, it masks real failures.", "Write a local MCP shim over `codex exec`: rejected as a new surface; the codex-liaison agent already covers Claude→Codex.", "Drop the models-cache pre-check entirely: rejected, it gives a clear reason when a model really is unknown."],
  "pre_mortem": ["Another Codex client rewrites the cache again: the probe ignores a cache whose client_version differs from `codex --version`.", "`codex --version` itself fails: the probe fails loud with `unavailable: codex --version unreadable`, never a silent pass.", "Default reverts to the retired slug: `test_model_resolution_order` pins the literal gpt-6-astra."],
  "slices": [
    {"title": "1 Default model and dead MCP entry", "verify": "bridge unit tests; `codex_bridge.py probe`; doctor", "expected": "probe available: true; no codex MCP entry; docs and agent/command descriptions name gpt-6-astra", "rollback": "git checkout the nine files", "status": "done"},
    {"title": "2 Cache client_version guard and medium default effort", "verify": "unit tests for match, mismatch and unreadable-version branches; live liaison research call", "expected": "stale cache ignored; unreadable version is unavailable, not a pass; DEFAULT_EFFORT is medium (owner decision 2026-09-28)", "rollback": "revert cached_models/_cli_version", "status": "done"},
    {"title": "3 Review, gate, commit", "verify": "independent review APPROVE bound to the exact tree; `gate.py full` stamp; Git guard", "expected": "guarded commit on main", "rollback": "reviewed revert only", "status": "done"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": ["docs/BUILD-STATUS.md", "docs/adr/0034-agent-operating-system-v2.md", "docs/operations/codex-second-model-runbook.md", "docs/operations/owner-actions-checklist.md"],
  "out_of_scope": ["Multi-turn Codex sessions (`codex exec resume`)", "New MCP, REST or Trader Terminal surfaces", "Any owner-authority, paper, broker or promotion change", "Upgrading the Codex CLI or desktop apps"],
  "files": ["scripts/codex_bridge.py", "tests/unit/test_claude_harness_codex_bridge.py", ".mcp.json", ".codex/config.toml", ".claude/agents/codex-liaison.md", ".claude/commands/codex-review.md", "docs/"]
}
```

## Hidden suite status

`tests/holdout` is absent from this checkout and from available Git history. The 2026-09-17
and 2026-09-19 owner exceptions were each restricted to their own commit and grant nothing
here. Hidden tests are therefore **UNVERIFIED** for this change; no test was fabricated or
read. On 2026-09-28, after the assistant explicitly asked whether a one-time exception
covered this commit, the owner replied "yes one time acception commit". This is recorded
narrowly for the Codex seam repair commit only, not as a standing waiver. Hidden tests remain
**UNVERIFIED**; other tests, independent review and the installed Git guards stay mandatory.
No research approval, sealed-data access, promotion or trading authority is granted.

## Verified execution evidence

Live on this tree, 2026-09-28: `codex_bridge.py probe` available with gpt-6-astra; `research`
(PSR question) returned two cited claims; `review` on a toy diff returned five schema-valid
findings; the `codex-liaison` agent round-trip returned two cited claims on White (2000). An
earlier full-gate run passed every backend step (mutation gate included) but did not stamp
because review fixes changed the tree mid-run. Slice 3 is complete only when the committed
tree carries its own full stamp and tree-bound APPROVE verdict; those receipts under
`.alpha/state/` and the installed Git guard are the authority, not this sentence.
