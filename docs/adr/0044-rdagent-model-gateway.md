# ADR-0044: RD-Agent reaches its models through a local ALPHA gateway; Codex first

**Status:** Accepted
**Date:** 2026-11-14
**Deciders:** Project ALPHA owner (the route preference and the 50 USD ceiling) and AI build agents (the mechanism)

## Context

Pinned RD-Agent (`484776c`) calls models only through its `LiteLLMAPIBackend`
(`rdagent/oai/backend/litellm.py`): LiteLLM `completion` for chat and `embedding` for vectors.
Read from the pinned source:

- Settings come from `CHAT_MODEL`, `EMBEDDING_MODEL`, `OPENAI_API_BASE`/`OPENAI_API_KEY` and
  copies prefixed `LITELLM_` (`rdagent/oai/llm_conf.py`, `rdagent/core/conf.py`). Defaults:
  `gpt-4-turbo`, `text-embedding-3-small`, temperature 0.5, streaming on, `max_tokens` unset,
  `reasoning_effort` unset, ten retries.
- Every chat call sends `temperature`. Calls made with `json_mode=True` (hypothesis proposal,
  experiment design, coder and evaluator steps, feedback) send
  `response_format={"type":"json_object"}` and RD-Agent then parses the JSON itself and retries on
  failure (`rdagent/oai/backend/base.py`, `_create_chat_completion_auto_continue`).
- LiteLLM drops `response_format`, with only a warning, for a model name it does not know
  (`supports_response_schema`), so the endpoint would never learn that JSON was required. Its
  `lm_studio/` provider forwards `response_format` unchanged to any OpenAI-compatible base URL and
  needs no real key (`litellm/llms/lm_studio/chat/transformation.py`, LiteLLM 1.97.0).
- LiteLLM downloads its model price list from the internet at import unless
  `LITELLM_LOCAL_MODEL_COST_MAP=True`.

The owner decided: the ChatGPT subscription with strong models first; an API key with a cheap
model only "if we can't get codex to work", capped at about 50 US dollars a month, "As long as it
doesn't drop quality or capability"
([owner decisions](../reference/project/owner-decisions.md#2026-11-14-api-spending-limit-for-rd-agents-models)).
ALPHA "owns budgets, data rules, experiment records, validation and approvals".

Routes considered, checked against OpenAI's own documentation on 2026-11-14:

- **A. The signed-in Codex program.** `codex exec` is OpenAI's documented non-interactive mode
  ("scripts and CI"); it reuses the saved sign-in, reports token usage in its `turn.completed`
  event and enforces `--output-schema` (learn.chatgpt.com/docs/non-interactive-mode). The
  configuration reference documents `model_instructions_file` as a "Replacement for built-in
  instructions" and the switches for skills, agents and web search
  (learn.chatgpt.com/docs/config-file/config-reference). The app-server and the `openai-codex`
  Python SDK are documented too (learn.chatgpt.com/docs/app-server, …/codex-sdk), but the CLI
  0.167.0 marks `app-server` experimental and it is an agent-thread interface; it offers nothing
  `codex exec` lacks for one-shot calls.
- **B. "Sign in with ChatGPT" token sharing.** The documentation describes plan usage for
  open-source local apps through the Responses API with a registered client
  (developers.openai.com/siwc/token-sharing-open-source); its limits are on a separate preview
  page (not read). It would mean ALPHA handling the owner's tokens and registering a client, and
  it has no embeddings.
- **C. LiteLLM's `chatgpt/` provider.** It presents itself as the Codex client; nothing found from
  OpenAI sanctions that use.

## Decision

- RD-Agent talks to `workers/rdagent/model_gateway.py`, a stdlib-only program owned by ALPHA that
  listens on `127.0.0.1` only and speaks the OpenAI chat-completions and embeddings formats. No
  ALPHA package imports it and it imports neither ALPHA nor RD-Agent. RD-Agent stays unmodified;
  it is configured with `CHAT_MODEL=lm_studio/alpha-chat`, `EMBEDDING_MODEL=lm_studio/alpha-embed`,
  `LM_STUDIO_API_BASE=<gateway>/v1`, `LM_STUDIO_API_KEY=<the gateway's session token>` and
  `LITELLM_LOCAL_MODEL_COST_MAP=True`.
- **Chat, route A (default).** Each call runs `codex exec` once in an empty temporary directory:
  read-only sandbox, ephemeral, user configuration ignored, web search off, every tool feature off
  (shell, apps, plugins, browser, image, agents, memories, hooks, skills), approvals never, and a
  scrubbed environment. RD-Agent's system message replaces Codex's built-in instructions
  (`model_instructions_file`); environment, permission, collaboration, skills and agent text are
  switched off. `codex debug prompt-input` with these switches (and an empty Codex home) shows the
  model sees exactly the system message and the user message, plus the definitions of three
  residual built-in tools (a JavaScript `exec` with no nested tools, `wait`, `request_user_input`)
  that cannot be removed by configuration. Any tool event in a reply fails the call.
  Workhorse model `gpt-6.1-sol`, effort `medium` unless RD-Agent sends `reasoning_effort`.
- **Embeddings.** Local Ollama `nomic-embed-text`, input passed unchanged.
- **Chat, paid fallback.** An OpenAI-compatible provider whose base URL and key the owner puts in
  the environment (`ALPHA_GATEWAY_API_BASE`, `ALPHA_GATEWAY_API_KEY`) together with the model and
  its prices; off unless configured; the key is never written or logged. There is no automatic
  switch between routes: a failing route returns an error, and changing route is a restart.
- **Fidelity.** Every request parameter is honoured, honoured another way (JSON validity checked
  with retries; `--output-schema` for a JSON schema; streaming replayed after the whole reply),
  dropped only if the operator listed it in `--accept-unhonoured` (then recorded as `waived` on
  every call), or refused with a clear error. Route A cannot honour `temperature`, `top_p`, `seed`,
  penalties or `max_tokens`; RD-Agent always sends `temperature`, so its launch profile accepts
  losing that one parameter, and the quality measurements were made with it dropped.
- **Budget.** Calls per run and per month, and estimated dollars for the paid route, are checked
  under a file lock before each model attempt and fail closed (`budget_exhausted`); the monthly
  dollar cap defaults to, and may not exceed, 50 US dollars. State lives under the data
  directory, which may not be inside a git tree; unreadable state refuses every call.
- **Records.** One JSON line per request: route, real model, effort, parameters honoured /
  enforced / waived / refused, attempts, JSON validity, tokens, dollars, queue and total time,
  status, and hashes and lengths of prompt and reply. No prompt or reply text unless
  `--log-content` is given.
- Route B is a reserve: it needs the owner to register a client and sign in, and an ADR of its
  own. Route C is not built and needs the owner's explicit approval.

## Consequences

- RD-Agent can run model-driven steps on the owner's ChatGPT allowance with no key on disk.
  Quality, latency and how far a real loop step gets are measured in
  [`04-verify.md`](https://github.com/tradingsystem1880-eng/Project-ALPHA/blob/pre-thin-2026-11-14/docs/work/archive/2026-11/2026-11-14-rdagent-model-gateway/04-verify.md); model output stays data,
  never evidence.
- Sampling diversity that RD-Agent expects from temperature 0.5 is not available on route A;
  the model's own sampling applies. This is visible in every log line.
- Each call starts a Codex process, so a call costs seconds of start-up on top of the model's time,
  and concurrency is limited (`--max-concurrency`, default 2).
- When the ChatGPT allowance runs out the gateway returns `codex_usage_limit`; the owner decides
  whether to restart on the paid route.
- A later Codex CLI may rename a feature switch; the call then fails visibly rather than running
  with a tool on.
