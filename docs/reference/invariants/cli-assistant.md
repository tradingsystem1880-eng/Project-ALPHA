---
owner: command line advisory assistants
sources:
  - apps/alpha-cli/src/alpha_cli/assistant_*.py
  - apps/alpha-cli/src/alpha_cli/codex_*.py
  - apps/alpha-cli/src/alpha_cli/investigation_*.py
  - apps/alpha-cli/src/alpha_cli/comparison_acquisition*.py
  - tests/unit/test_assistant_*.py
  - tests/unit/test_codex_*.py
  - tests/unit/test_investigation_*.py
  - tests/unit/test_comparison_acquisition*.py
verified: 1ac86fc02443
---

# Command line assistant invariants

What must not break when changing the advisory model surfaces: `alpha assistant` sessions, Codex investigations and
their workspaces, and the private comparison-acquisition worker, all of which are advisory. Project-wide rules:
[research integrity § Models and isolated workers](research-integrity.md#models-and-isolated-workers) and
[research integrity § Owner authority](research-integrity.md#owner-authority).

## No authority

- Assistant sessions, Codex investigations and their reports never admit evidence, run generated code or exercise owner
  authority. Investigation reports carry `authority: none` and `admitted: False` (`investigation_report.py`).
- A report may cite only existing, successful receipts; a citation binding is not proof that a finding is true.
- The browser supplies identifiers only, never evidence or filesystem paths (`assistant_contracts.py`,
  `investigation_workspace.py`). Context is resolved by the CLI (`assistant_context.py`).
- `assistant create|show|turn|check` are owner-only in generic launch classification; the web adapter calls this
  closed CLI vocabulary.

## Assistant sessions

- Model tools are disabled; the prompt states the model has no tools or execution authority (`assistant_runtime.py`).
- One inference runs at a time and is bounded by cancellation and a five-minute limit (`TIMEOUT_SECONDS = 300`).
- The session's context hash is re-checked before a draft is used (`assistant_service.py`); a changed context fails.
- A model reply must be exactly `text`, `citations` and `rule_draft`. Every citation must name a reference in the
  server-built context, and a `rule_draft` must parse through `alpha_strategies.rules`; it stays a draft.
- The session journal is separate from admitted research evidence.
- A session created with `rules_sha256` fails context resolution, at creation and on every `check`, when
  `alpha rules explain` reports a different hash for the saved rule; rerun the scan or choose the current rule.

## Cleanup and the global lock

- The watchdog (`assistant_worker.py`) runs outside the model process group and keeps the inherited global lock until
  cleanup completes. Parent loss, deadline and owner cancellation signal the model group, reap the direct child, and
  wait for the group to disappear before the lock is released.
- Caller cancellation asks the watchdog to stop and waits; never kill the lock holder first.
- Never send a destructive group signal after the leader is reaped, and never reuse a PID already reaped by
  `communicate()` to authorise another group signal.
- If the OS cannot reap a group, cleanup stays blocked. That is fail-closed, not a promise that shutdown ends in five
  minutes. Detached processes, and an external kill of the watchdog itself, are not contained. Enforced by `tests/unit/test_assistant_cleanup.py`.

## Codex investigations

- Codex runs with one scoped MCP service, network disabled, no web search, `approval_policy: never`, no inherited shell
  environment, and a fixed list of disabled features (`codex_policy.py`).
- Its filesystem is read-only on a dedicated workspace; `/`, the home directory, temp directories and the workspace
  parent are denied. A workspace at `/`, home or a temp root is refused.
- ALPHA owns scope, receipts and budgets; Codex only chooses among bounded tools (`codex_investigation.py`).
- Provider credentials (for example `ALPHA_TIINGO_API_KEY`) go only to the private acquisition worker process, never to
  Codex's model process (`comparison_acquisition.py`, `comparison_acquisition_worker.py`).
- Price comparisons are descriptive evidence, never causal attribution (`investigation_comparisons.py`).
