# Brief: retire the in-app AI (Codex Bench, investigations, Standalone Sandbox)

Branch: `chore/m78-retire-in-app-ai`. Rules: `docs/work/_common-rules-2026-11-21.md` (deletion-only build).

The owner decided on 2026-11-21 to retire the AI built into the Workstation screens. The owner works with an AI partner OUTSIDE the UI
(command line and the MCP front door); the UI is for seeing.

Scope to delete, after proving each part is unreached by anything that stays: the `research investigations …` commands and their modules
(`investigation_*.py`, `codex_*.py` in `apps/alpha-cli/src/alpha_cli/`), `apps/alpha-mcp/src/alpha_mcp/investigation_server.py` (the one
permitted edit under `apps/alpha-mcp/` for this brief: delete that file and its registration only), the web routes `api/investigations.py`
and `_investigations.py`, the panels CodexBench, AiConsole, AssistantDock, RunInvestigation ("Investigate this run" button) and the
Standalone Sandbox, their models, tests and Playwright specs, the capability `ai-investigations`, and the docs that describe them.

Keep: `alpha tool …` (the investigation TOOLBOX is a feature and stays: do not confuse it with "investigations"), every stored tool result,
the MCP front-door tools, RD-Agent, and anything the research-case lane still needs to run (that lane is retired in later steps: if a
research-case module imports an investigation module, cut the import in the smallest way and say so). If "Investigate this run" is the only
door to a kept feature, keep that feature reachable another way and say how.

Done: as in brief m76, plus the list of what you kept and why.
