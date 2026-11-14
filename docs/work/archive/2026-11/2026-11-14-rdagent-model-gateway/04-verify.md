# Verification: RD-Agent model gateway

Measured on the Dell on 2026-11-14 with codex-cli 0.167.0 signed in with ChatGPT, LiteLLM 1.97.0
and pinned RD-Agent `484776c` (source digest checked by `scripts/setup.sh --with-stock-runtime`).
Model output below is data about the connection, not research evidence. All data were made up.

## How it was measured

- **Environment.** RD-Agent's Qlib factor and model code needs pandas, SciPy, PyTables and a few
  more packages that the pinned stock runtime deliberately leaves out. Measurement used a throwaway
  Python 3.11 environment outside the repository: the stock lock installed with
  `--require-hashes`, plus pandas 2.2.3, scipy 1.14.1, tables 3.10.1, fire and pandarallel. It is
  not part of ALPHA and nothing here depends on it.
- **Scenario.** RD-Agent's own `QlibFactorScenario` and `QlibModelScenario`, unmodified, except
  that their runtime probe (which needs conda or Docker) was replaced in a measurement-only
  subclass by a fixed description of that environment. Market data: a made-up `daily_pv.h5`
  (120 business days × 20 invented instruments, random walk, seed 20261114) in RD-Agent's own
  data-folder layout, so RD-Agent's own `get_data_folder_intro` described it.
- **Connection.** RD-Agent ran with `CHAT_MODEL=lm_studio/alpha-chat`,
  `EMBEDDING_MODEL=lm_studio/alpha-embed`, `LM_STUDIO_API_BASE`/`LM_STUDIO_API_KEY` from the
  gateway's session file, `LITELLM_LOCAL_MODEL_COST_MAP=True`, `MAX_RETRY=2`; the gateway ran with
  `--accept-unhonoured temperature --log-content` (content kept only in the scratch directory).
- **Prompts.** The 11 prompts in the table were produced by RD-Agent's own code, not written by
  hand: ten during the loop step below and its follow-on calls, one by RD-Agent's
  `QlibFactorExperiment2Feedback` on a made-up backtest result. Each was answered by `gpt-6.1-sol`
  (the default workhorse) inside RD-Agent, then the identical system and user text was sent to
  `gpt-6-astra` (the strongest listed for this login) through a second gateway. Effort `medium`
  for both.
- **Scoring.** JSON parses to an object; the keys RD-Agent's prompt asks for are present; the
  object passes the `TypeAdapter` type RD-Agent's caller uses; generated factor code parses and is
  run by RD-Agent's own `FactorFBWorkspace.execute` on the made-up data, then checked by RD-Agent's
  non-model evaluators (`FactorInfEvaluator`, `FactorSingleColumnEvaluator`,
  `FactorDatetimeDailyEvaluator`); generated model code parses and defines `model_cls` (it was not
  run: PyTorch is not installed in the measurement environment).

## Quality table

Time is the whole call through the gateway (seconds). Tokens are Codex's own counts; input
includes about 2,630 tokens of Codex's residual tool definitions (below). Paid route: not measured,
no key is configured (left empty on purpose; nobody was asked for a key).

| # | RD-Agent prompt (caller) | JSON mode | gpt-6.1-sol: checks | s | in / out | gpt-6-astra: checks | s | in / out | paid key |
|---|---|---|---|---|---|---|---|---|---|
| 1 | factor hypothesis (`QlibFactorHypothesisGen`) | yes | JSON, keys, type: pass | 11.4 | 4,618 / 265 | pass | 11.9 | 4,618 / 245 | — |
| 2 | factor experiment, 4 factors (`QlibFactorHypothesis2Experiment`) | yes | pass | 20.2 | 4,612 / 834 | pass (4 factors) | 20.6 | 4,612 / 784 | — |
| 3 | factor code `reversal_5d` (`FactorMultiProcessEvolvingStrategy`) | yes | pass; runs; 2,400 rows; inf, one column, daily: pass | 8.1 | 4,417 / 222 | pass; runs; all three checks pass | 7.5 | 4,417 / 234 | — |
| 4 | factor code `relative_volume_5_20` | yes | pass; runs; all three checks pass | 8.1 | 4,479 / 250 | pass; runs; all three checks pass | 8.1 | 4,479 / 248 | — |
| 5 | output-format evaluator (`FactorOutputFormatEvaluator`) | yes | pass | 4.7 | 4,185 / 72 | pass | 4.8 | 4,185 / 72 | — |
| 6 | code critic (`FactorCodeEvaluator`, free text) | no | non-empty | 3.6 | 4,797 / 8 | non-empty | 4.9 | 4,797 / 7 | — |
| 7 | final-decision evaluator (`FactorFinalDecisionEvaluator`) | yes | pass | 5.0 | 4,527 / 59 | pass | 5.2 | 4,527 / 62 | — |
| 8 | factor feedback (`QlibFactorExperiment2Feedback`, made-up result) | yes | pass | 15.8 | 4,744 / 405 | pass | 14.7 | 4,744 / 381 | — |
| 9 | model hypothesis (`QlibModelHypothesisGen`) | yes | pass | 8.8 | 4,480 / 162 | pass | 8.7 | 4,480 / 162 | — |
| 10 | model experiment (`QlibModelHypothesis2Experiment`) | yes | pass | 28.3 | 4,316 / 1,264 | pass | 30.5 | 4,316 / 1,313 | — |
| 11 | model code (`ModelMultiProcessEvolvingStrategy`) | yes | parses, `model_cls`: pass (not run) | 17.9 | 4,576 / 702 | pass (not run) | 16.9 | 4,576 / 664 | — |

Every JSON reply was valid on the first attempt (no gateway JSON retry was needed in 29 successful JSON-mode
calls). Both models pass every check; these checks cannot tell the two apart. Whether one model's
hypotheses or code are *better research* is not measured here and needs real data. Codex reported
0 reasoning tokens on most calls at effort `medium` (100 and 43 on two `gpt-6.1-sol` calls, 64 on
one `gpt-6-astra` call); not verified whether that is how the model behaved or how it is reported.

## The Codex wrapper and its measured effect

- `codex debug prompt-input` with the gateway's switches and an empty Codex home (no model call)
  shows the model input as exactly RD-Agent's system message and user message. Without
  `model_instructions_file` and the `include_*`/`skills`/`agents` switches, Codex adds about
  21,500 characters of its own instructions, 16,000 of skills, 2,400 of agent roles plus
  environment, permission and collaboration text.
- What cannot be switched off: the definitions of three built-in tools (a JavaScript `exec` whose
  host is disabled so it fails closed, `wait`, `request_user_input`). Measured cost: a 20-character
  prompt with a 35-character system message is counted as 2,662 input tokens, so about 2,630
  tokens per call, nearly all cached. No call used a tool; a call that does is failed by the
  gateway.
- A/B on two prompts (rows 1 and 7) with Codex's default wrapper (system text pasted above the
  prompt, built-in instructions left on, tools still off): input 15,003 and 14,912 tokens instead
  of 4,618 and 4,527; both replies still valid JSON with the required keys; 14.9 s and 5.7 s. With
  two prompts this shows the wrapper costs about 10,400 tokens a call and did not break the format;
  it does not show that it never changes content, which is why the gateway removes it.

## RD-Agent parameters: honoured, enforced another way, refused

| Parameter RD-Agent sends | Route A (Codex) | How |
|---|---|---|
| `model`, `messages` (system + user) | honoured | system text replaces Codex's instructions; user text is the prompt |
| more turns (chat sessions) | enforced another way | rendered as a `[role]` transcript, recorded as `messages_rendered_as_transcript` |
| `stream=True` (RD-Agent's default) | enforced another way | whole reply, then sent as server-sent events; recorded |
| `response_format={"type":"json_object"}` | enforced another way | reply must parse to a JSON object; up to 2 repeats; else 502 |
| `response_format` JSON schema | enforced another way | passed to Codex as `--output-schema`, then checked |
| `reasoning_effort` | honoured | passed as Codex's reasoning effort; default `medium` |
| `temperature` (always 0.5) | cannot be honoured | refused unless `--accept-unhonoured temperature`; then recorded as `waived` on every call |
| `top_p`, `seed`, penalties ≠ 0, `max_tokens` | cannot be honoured | refused unless listed in `--accept-unhonoured` |
| `n`>1, `stop`, `tools`, functions, logprobs, images, unknown keys | refused | always, 400 naming the parameter |
| embeddings `model`, `input`, `encoding_format=float` | honoured | Ollama `nomic-embed-text`, input unchanged |

RD-Agent's defaults also mean `max_tokens` and `seed` are not sent, so in practice only
`temperature` is waived. Long outputs: replies up to 1,313 tokens came back whole; Codex sets its
own output limit and the gateway always reports `finish_reason` `stop` (RD-Agent's "continue if cut
off" path is therefore never used; not verified for replies near Codex's own limit). Concurrency:
two parallel calls worked (the replay ran two at a time); the default limit is 2. Latency: 3 to
31 s per call through the gateway, about 3 s of which is Codex starting.

Route B (ChatGPT token sharing) was not built or measured: route A met every need above except
temperature, which route B's restricted Responses API would not honour either (that restriction is
Codex's lead; OpenAI's page defers to a limitations page not read here).

## The real loop step, end to end

RD-Agent's own `FactorRDLoop` (`rdagent/app/qlib_rd_loop/factor.py`) with RD-Agent's default
classes, `FACTOR_CoSTEER_max_loop=2`, through the gateway on `gpt-6.1-sol`:

1. **Propose — passed.** One hypothesis: four simple daily factors (5-day reversal, 20-day momentum
   skipping 5 days, 5/20-day relative volume, close location in the day's range).
2. **Experiment design — passed.** Four factor tasks with descriptions, formulas and variables.
3. **Coding (CoSTEER) — passed.** Four `factor.py` files written by the model; RD-Agent ran each on
   the made-up data, its format, critic and final-decision evaluators (12 model calls) accepted all
   four in the first round, and it stored them in its knowledge base with 8 embedding calls to
   Ollama through the gateway.
4. **Running — stopped here.** RD-Agent's `QlibFactorRunner` needs Qlib's `qrun` (in its Docker
   image); it is not installed in this environment, so RD-Agent logged "failed to run command
   'qrun'" and skipped the loop, as it is designed to. Feedback and record were not reached in the
   loop; the feedback prompt (row 8) was exercised separately on a made-up result.

So the gateway carried every model and embedding call the loop needed, up to the point where
Qlib itself is required. Running that step belongs to the Qlib work (W09), not to this task.

## Budget, records and calls made

- Budget: each gateway data directory kept `budget.json` (`{"months":{"2026-11":{"calls":32,...}}}`
  for the main run) and refused nothing because no cap was reached; fail-closed behaviour (caps per
  run, month and dollars, the 50 USD ceiling, unreadable state) is covered by the unit tests, not
  by a live run. The budget is per data directory: use one data directory for RD-Agent so the
  monthly cap means what it says.
- Records: one line per request in `calls.jsonl` with the fields in ADR-0044; no prompt or reply
  text unless `--log-content`; the session token never appears (checked by the tests).
- Model calls on the ChatGPT allowance: 38 in total — 24 through the main gateway (2 checks, 18 in
  the loop, 1 feedback, 3 model-side; one of the checks was refused by the first build for a
  notice item, see the pull request), 11 replays on `gpt-6-astra`, 2 A/B calls and 1 by hand to
  read Codex's event stream. Plus Codex's own building of the gateway (one `handoff.py` build,
  2 rounds) and one review. Ollama: 8 embedding calls.

## Checks run

- `uv run pytest -q tests/unit/test_rdagent_model_gateway.py`: 75 passed.
- `uv run python scripts/run_owned_test.py -- uv run pytest -q -m smoke -n 0
  tests/smoke/test_rdagent_model_gateway_smoke.py` with `ALPHA_RDAGENT_SOURCE` and
  `ALPHA_STOCK_PYTHON` set: 2 passed (the second drives RD-Agent's own `APIBackend` through
  LiteLLM's `lm_studio/` provider against the fake route: JSON mode reached the gateway and was
  enforced; embeddings returned).
- `uv run python scripts/gate.py check --all`: all checks passed (fast tier, 2026-11-14).

## Not verified

- Research quality of the answers (only format, schema and RD-Agent's own mechanical checks).
- Behaviour when the ChatGPT allowance runs out (the usage-limit wording is the one `handoff.py`
  assumes; not seen live).
- The paid route against a real provider (no key configured).
- Generated model code running (no PyTorch here); the Qlib runner step.
