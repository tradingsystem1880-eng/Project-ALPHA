# RD-Agent model gateway

**Delivery state:** Completed — built, measured and checked on branch `m5/rdagent-model-gateway`; done when its pull request merges.
**Build class:** standard — one new stdlib-only worker module plus its tests (built from a three-file brief); the documents are Claude's.

Filed straight into the archive, as `2026-11-14-project-layer` was: the work-in-progress ceiling
(34, a ratchet) admits no new live plan, and the work was finished in one sitting.

## For the owner

- RD-Agent gets a model to talk to: a small program on the Dell (`workers/rdagent/model_gateway.py`)
  that only this computer can reach. RD-Agent asks it for answers; it passes them to the Codex
  program you are already signed in to with ChatGPT, and gets text comparisons ("embeddings") from
  the Ollama program already on the Dell. No key is stored anywhere.
- It never quietly changes what RD-Agent asked for: anything it cannot do is refused with a clear
  message, or, for a setting you accept losing (RD-Agent's "temperature"), recorded on every call.
- It keeps a hard budget: calls per run and per month, and dollars for the paid fallback (at most
  50 US dollars a month). When a cap is reached it stops.
- The paid fallback stays off until you set a key yourself; nothing here asks you for one.
- You will see: a quality table and how far one real RD-Agent step got, in `04-verify.md` and
  ADR-0044. It does not start research runs or make any result count as evidence.

```json
{
  "schema_version": 1,
  "title": "RD-Agent model gateway",
  "context": "RD-Agent's pinned LiteLLM backend needs an OpenAI-compatible chat and embedding endpoint; the owner chose the ChatGPT subscription first and an API key capped at 50 USD a month only as a fallback, without loss of quality.",
  "assumptions": [
    {"statement": "Pinned RD-Agent calls litellm completion with temperature 0.5, stream on, and response_format json_object for json_mode, and checks JSON itself; settings come from CHAT_MODEL, EMBEDDING_MODEL and LITELLM_-prefixed copies.", "verified_by": "reading rdagent/oai/backend/litellm.py, base.py, llm_conf.py and core/conf.py at the pinned source"},
    {"statement": "LiteLLM drops response_format for a model it does not know, but its lm_studio provider forwards it unchanged to an OpenAI-compatible base URL without needing a real key.", "verified_by": "litellm 1.97.0 supports_response_schema and llms/lm_studio/chat/transformation.py in the stock runtime"},
    {"statement": "codex exec accepts model_instructions_file and switches that remove Codex's built-in instructions, environment, permission, skills and agent text, leaving the system prompt and the user prompt.", "verified_by": "codex debug prompt-input with the gateway's flags and an empty CODEX_HOME (no model call), and OpenAI's configuration reference"},
    {"statement": "codex exec reports token usage in its turn.completed JSON event.", "verified_by": "OpenAI's non-interactive mode documentation"}
  ],
  "alternatives_considered": [
    "Codex app-server or the openai-codex Python SDK: documented, but marked experimental in codex-cli 0.167.0 and an agent interface with threads and approvals; codex exec is the documented scripting route the repository already confines.",
    "Sign in with ChatGPT token sharing (Responses API): needs client registration and handling the owner's tokens, has no embeddings; kept as a reserve that needs the owner.",
    "LiteLLM's chatgpt/ provider: presents itself as the Codex client with no sign that OpenAI sanctions that use; not built.",
    "A custom RD-Agent backend class: rejected, RD-Agent's own LiteLLM backend already does the job."
  ],
  "pre_mortem": [
    "Codex adds hidden instructions or tools that change answers: measured with codex debug prompt-input and input-token counts; any tool event fails the call.",
    "RD-Agent's temperature cannot be set on Codex: refused unless the operator accepts losing it, and then recorded on every call; quality measured with it dropped.",
    "Codex's ChatGPT allowance runs out mid-run: the gateway returns a clear usage-limit error and never switches to the paid route by itself.",
    "Budget state is lost or edited: malformed state refuses every call instead of resetting."
  ],
  "slices": [
    {"title": "Gateway module, fidelity rules, budget and unit tests (Codex build)", "verify": "uv run pytest -q tests/unit/test_rdagent_model_gateway.py", "expected": "all pass", "rollback": "delete workers/rdagent/model_gateway.py and its tests", "files": ["workers/rdagent/model_gateway.py", "tests/unit/test_rdagent_model_gateway.py"], "status": "done"},
    {"title": "Offline smoke check, including RD-Agent's own APIBackend through LiteLLM against the fake route", "verify": "uv run python scripts/run_owned_test.py -- uv run pytest -q -m smoke -n 0 tests/smoke/test_rdagent_model_gateway_smoke.py", "expected": "all pass with ALPHA_RDAGENT_SOURCE and ALPHA_STOCK_PYTHON set", "rollback": "delete the smoke file", "files": ["tests/smoke/test_rdagent_model_gateway_smoke.py"], "status": "done"},
    {"title": "Quality measurement on RD-Agent's own prompts and one real loop step through the gateway", "verify": "04-verify.md records the table, the call count and how far the step got", "expected": "under 200 model calls", "rollback": "none needed", "status": "done"},
    {"title": "ADR, component page, capability map, roadmap and status", "verify": "uv run python scripts/gate.py check --all", "expected": "All checks passed", "rollback": "revert the document changes", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/reference/project/components/rd-agent.md", "docs/roadmap/rd-agent-in-alpha.md", "docs/roadmap/capabilities.toml", "docs/adr/0044-rdagent-model-gateway.md", "docs/reference/model-routing.md", "workers/rdagent/README.md"],
  "out_of_scope": ["RD-Agent source", "scripts/codex_bridge.py", "scripts/handoff.py", "approval and hashing code", "CI workflows", "the closed synthetic fixture loops", "real-data research runs", "LiteLLM chatgpt/ provider"],
  "files": [
    "workers/rdagent/model_gateway.py",
    "tests/unit/test_rdagent_model_gateway.py",
    "tests/smoke/test_rdagent_model_gateway_smoke.py",
    "docs/work/archive/2026-11/2026-11-14-rdagent-model-gateway/",
    "docs/adr/0044-rdagent-model-gateway.md",
    "docs/adr/README.md",
    "docs/reference/project/components/rd-agent.md",
    "docs/roadmap/rd-agent-in-alpha.md",
    "docs/roadmap/capabilities.toml",
    "docs/roadmap/README.md",
    "docs/reference/model-routing.md",
    "workers/rdagent/README.md",
    "STATUS.md"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [worker invariants](../../../../reference/invariants/workers.md) | Shared rules, RD-Agent worker | always |
| [research integrity](../../../../reference/invariants/research-integrity.md) | Models and isolated workers, Owner authority | always |
| [RD-Agent component](../../../../reference/project/components/rd-agent.md) | — | always |
| [model routing](../../../../reference/model-routing.md) | Task classes | the Codex build |

## Slices

As in the JSON block. The code is built by Codex from a brief listing only the three code files
(so the build is classed on those); Claude reviews it, measures it and writes the documents.

## Test plan

Unit tests call the gateway class directly: the parameter policy (honoured, enforced, waived,
refused), JSON enforcement and retries, the budget caps and fail-closed state, the exact Codex
command line and environment through a fake `codex` program, and that logs hold no prompt text,
token or key. The smoke check starts the real server on loopback with the fake route and drives it
over HTTP, then drives it with RD-Agent's own `APIBackend` through LiteLLM when the RD-Agent source
and stock runtime are installed. Quality is measured by hand and recorded, not asserted in tests.

## Look-ahead, determinism and import impact

No ALPHA package imports the gateway; it imports no ALPHA package and no RD-Agent code. It touches
no market data, clock, fill, statistic or approval. Model output stays data: nothing it returns is
evidence. Model answers are not deterministic; every call's prompt and reply are recorded by hash.
