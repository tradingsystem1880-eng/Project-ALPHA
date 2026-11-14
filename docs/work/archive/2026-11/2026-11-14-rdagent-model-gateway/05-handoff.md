## What changed for you

- RD-Agent now has an AI model to talk to. A small program on the Dell, reachable only from the
  Dell itself, takes RD-Agent's questions and passes them to the Codex program you are already
  signed in to with your ChatGPT plan. Text comparisons ("embeddings") come from the Ollama
  program already on the Dell. No key or password is stored anywhere.
- It never quietly changes what RD-Agent asked for. Settings it cannot honour are refused with a
  clear message, or, for the one you are asked to accept (below), recorded on every call.
- It keeps a hard budget: calls per run and per month, and, for a paid fallback, dollars, at most
  50 US dollars a month. When a cap is reached it stops. It never switches to the paid route by
  itself; the paid route stays off unless you set it up.
- Tried for real: RD-Agent's own factor research loop proposed an idea, designed four factors,
  wrote their code and had its own checks accept them, on made-up data, through this connection.
  It stopped at the backtest step, which needs Qlib (the next piece of work). Both ChatGPT models
  tried (the everyday one and the strongest one) passed every format and code check on 11 of
  RD-Agent's own prompts. Nothing here is research evidence.

**One decision for you.** RD-Agent always asks for a "temperature" of 0.5 (a setting for how varied
answers are). The Codex route cannot set it. The program refuses it unless told to accept it; the
tests above were run with it accepted and recorded. If you are happy with that, reply "accept
temperature on the Codex route". If not, the paid route (which can honour it) would be needed.

**Only if you ever want the paid fallback** (not needed now; nothing was asked of you): on the
Dell, in a terminal, type `export ALPHA_GATEWAY_API_BASE=https://api.openai.com/v1`, then
`read -s ALPHA_GATEWAY_API_KEY` and paste your key (nothing shows; press Enter), then
`export ALPHA_GATEWAY_API_KEY`, then start the program with
`--chat-route api --api-model <model> --api-price-in-per-mtok <price> --api-price-out-per-mtok <price>`.
This way the key is never written to a file or to the terminal history; close the terminal to
forget it.

## How to see it

The decision and measurements: ADR-0044 and this task's `04-verify.md` on GitHub. To see the
budget on the Dell: `python3 workers/rdagent/model_gateway.py status --data-dir <your data folder>`.

## Checks run

- Unit tests of the program: 75 passed (no network; a fake Codex program checks the exact
  confinement switches and that logs hold no text, token or key).
- Smoke check: 2 passed, including RD-Agent's own model code talking to the program through
  LiteLLM with a fake model, JSON mode enforced, embeddings returned.
- Live measurement: 38 calls on your ChatGPT allowance in total (24 for the loop step and
  follow-on prompts, 11 on the strongest model, 2 to measure Codex's own wrapper, 1 by hand), plus 8
  embedding calls to Ollama; details in `04-verify.md`.
- `uv run python scripts/gate.py check --all`: passed (see CI below for the merge gate).
- Not run: the paid route against a real provider (no key); generated model code (no PyTorch in
  the measurement environment); the Qlib backtest step; a real usage-limit response.

## Who built and who reviewed

- Built by Codex (`gpt-6.1-sol`, effort high, standard class, from a written brief through
  `scripts/handoff.py`): 19m27s, 2 rounds (one fix round after the gate), 3,228,369 input tokens
  (3,052,928 cached), 73,983 output. No fallback.
- Reviewed by Claude (Opus 5.5). The first live call found two problems no offline test could:
  a Codex setting that 0.167.0 does not recognise, and a Codex notice item that the program
  treated as tool use. Claude fixed both by hand, plus two small record-keeping fixes (the
  opt-in content log keeps the system text; the paid route records streaming as replayed and does
  not send `stream_options` to a non-streaming call), with one added test.
- Codex reviewed Claude's edits and documents (`handoff.py review`, `gpt-6-astra`): one finding,
  medium — the new plan raised work in progress above the ceiling of 34. Fixed: the task folder is
  filed straight into the archive, as the project-layer task was.
- Investigation, measurement and documents: Claude.

## The one document updated

The RD-Agent component page (`docs/reference/project/components/rd-agent.md`), with the decision
in ADR-0044. Also updated where each fact lives: the worker README (how to run it), the
plain-English RD-Agent page, the capability map and `STATUS.md` (generated), and the model
routing calibration table.

## What I am unsure about

- Whether dropping temperature affects research quality over many rounds; format and code checks
  cannot show it (your decision above).
- Codex always adds about 2,600 tokens of built-in tool definitions that no setting removes; they
  were never used, and a call that uses a tool is failed.
- Codex reported 0 reasoning tokens on most calls at effort "medium"; not verified whether that is
  real behaviour or how it is reported.
- The budget is kept per data folder: use one data folder for RD-Agent so the monthly cap is real.
- The plan is filed in the archive rather than registered as live work in the capability map,
  because the map's work-in-progress ceiling admits no new live plan.

## Protected files touched

None. RD-Agent's source, `scripts/codex_bridge.py`, `scripts/handoff.py`, settings, hooks,
workflows, hash-bound sources, guards, oracles and acceptance tests are unchanged.
