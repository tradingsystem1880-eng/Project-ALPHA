# Codex recorded-run investigations

This is the first CLI increment of the [Codex-first plan](../superpowers/plans/2026-10-03-codex-research-runtime.md).
Codex reasons and chooses tools. ALPHA verifies the fixed run, enforces budgets and validates
receipt references. The output is retrospective advice, not admitted research or proof of edge.

## Run and resume

Use the isolated research checkout with `uv sync --locked` and an existing local Codex login.
The runtime currently requires a local `auth.json`; keychain-only authentication is not supported.
It references that file through a symlink in a dedicated Codex home; it never copies credentials.
Keep the entire case directory private and outside Git, including Codex conversation history.

```bash
uv run alpha research diagnostic investigate /absolute/private/cases/example \
  --run-id RUN_ID --as-of YYYY-MM-DD \
  --question 'Investigate this drawdown and identify the most useful next test.'

uv run alpha research diagnostic investigate /absolute/private/cases/example --resume
```

`RUN_ID` is an existing 16-hex v3 backtest/validation run in `ALPHA_DATA_DIR/runs` with the exact
recorded `research_cutoff`. Ordinary runs without that contract fail; the tool never rewrites a
historical manifest to make it eligible. Existing `diagnostic run-plan` can produce bounded runs.
Model defaults to `gpt-6-astra`; new cases can select another available Codex model explicitly.
Resume uses the frozen model/question/run/cutoff. Changing the question or scope requires a new
case and does not make previously exposed evidence untouched.

The completed checkpoint is reverified and returned without another model call. Explicit resume
after a known failure uses the same Codex thread and spent budgets. A crash leaving an ambiguous
reservation blocks replay. Do not delete reservations to replenish a budget. Transport events
support streaming, active-turn steering and interruption through `InvestigationTurn`; workstation
controls are not wired in this increment. CLI interruption closes the process group.

## Capabilities and limits

Only three parameterless tools are exposed:

| Tool | Result |
|---|---|
| `inspect_execution` | Verified execution counts, constraints, costs and coverage status |
| `inspect_losses` | Measured drawdown episodes from the exact equity artifact |
| `suggest_followups` | Grounded starting questions, not executed follow-up experiments |

Execution inspection must succeed first. Source and policy hashes are reverified on every result,
including cached results. Each case permits at most six distinct action attempts, twelve total
requests including repeated/denied requests, and four model turns including failures. Each turn
has a five-minute collection deadline, six observed MCP calls and a bounded event count. Limits
persist across processes; concurrent sessions cannot reserve the same last slot. These are call
and time limits, not a claim of a hard token/dollar ceiling.

Case SQLite and conversation JSON are advisory sidecars. ControlStore remains authoritative for
governed research. An evidence receipt binds source bytes and an observation; it does not establish
that a model's causal explanation or recommendation is true. Final reports label that distinction
and reject nonexistent/unsuccessful citations. Rejected model completions are retained locally.

## Runtime boundary

The installed Codex 0.159.0 App Server protocol supplies stdio JSONL threads, resume, streaming,
steer and interrupt. Each process uses a dedicated configuration and an empty model workspace.
Shell, web, browser, apps, plugins, image generation, memory and subagent capabilities are disabled.
The code-mode host remains enabled because this CLI version requires it for native MCP discovery.
The only MCP server is the fixed-case facade, which subprocesses supported CLI commands.
Its three exact tools are preauthorized by configuration; generic approval requests are rejected.
No ordinary workspace MCP, arbitrary paths, provider credentials, owner actions or execution
commands are exposed to the model. There is no new public REST or trading surface.

Before a model turn, the actual App Server execution path must pass canaries for allowed input
read, denied owner-home/common-temp/sibling reads, denied symlink escape, denied writes and denied
network access. Start/resume must report the named `investigation` profile, read-only sandbox,
network disabled, exact model and no approval prompts. MCP inventory must match the three tools.
This certifies the tested local configuration; it is not a general proof against every Codex or OS
vulnerability. The trusted host and MCP service necessarily access the selected source run.

Protocol source: [official App Server documentation](https://learn.chatgpt.com/docs/app-server),
[MCP configuration](https://learn.chatgpt.com/docs/config-file/config-reference), and JSON schemas
generated from the installed CLI. No additional inference framework or model weights were added.

## Next acceptance work

This increment cannot collect missing comparison data, establish macro causes, fit causal regimes,
implement strategy operators or activate learned skills. Those remain explicit subsequent slices.
The next useful increment is frozen-snapshot comparison evidence and data qualification, followed
by workstation integration after reconciling concurrent UI changes. Native Codex chart input,
isolated strategy engineering and evaluated procedure learning remain in the accepted roadmap.
Large finance models stay research candidates for later GPU trials; local Qwen vision is not part
of the near-term design. Historical Claude benchmark artifacts remain unchanged.
