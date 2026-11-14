# One real RD-Agent loop, end to end

**Delivery state:** Completed — the loop ran end to end once on real crypto bars; its backtest step ran but measured nothing about the idea (see `04-verify.md`); done when its pull request merges.
**Build class:** small — documents only; the run itself used no repository code change.

Filed straight into the archive, as the gateway task was: the work-in-progress ceiling admits no
new live plan, and the work was finished in one sitting.

## For the owner

- RD-Agent ran its whole research loop once, for real, on the 15 coins of Binance daily bars on
  the Dell: an AI model (through the Codex route) proposed four simple factors, wrote their code,
  RD-Agent's checks accepted it, Qlib trained a model and backtested it, and the AI judged the
  result. 27 model calls, about 4.5 minutes.
- The backtest step was hollow: RD-Agent's built-in model settings are tuned for 300 Chinese
  stocks; on 15 coins the model learned nothing (it gave every coin the same score every day), so
  the backtest numbers are noise and the AI's "improved" verdict rests on that noise.
- Nothing here is evidence. Next steps and what each needs from you are in `05-handoff.md`.

```json
{
  "schema_version": 1,
  "title": "One real RD-Agent loop, end to end",
  "context": "The owner's first goal after the clean-up is one real RD-Agent loop through the Codex route; the previous attempt stopped at the Qlib backtest step on made-up data.",
  "assumptions": [
    {"statement": "RD-Agent's QlibFactorRunner runs qrun in its upstream Docker image (local_qlib, built from rdagent/scenarios/qlib/docker/Dockerfile) when MODEL_CoSTEER_env_type=docker, mounting a Qlib data folder at /root/.qlib.", "verified_by": "reading rdagent/utils/env.py and scenarios/qlib/experiment/workspace.py at the pinned source, then the run's docker execution logs"},
    {"statement": "The factor templates hard-code provider_uri ~/.qlib/qlib_data/cn_data, market csi300, benchmark SH000300, TopkDropout topk 50, LightGBM with lambda_l1 205.7 and lambda_l2 581.0, and ann_scaler 252.", "verified_by": "reading scenarios/qlib/experiment/factor_template/*.yaml"},
    {"statement": "The factor coder executes generated code with FACTOR_CoSTEER_python_bin, but its runtime probe asks conda for the environment's PATH.", "verified_by": "reading components/coder/factor_coder/config.py and utils/env.py CondaConf"}
  ],
  "alternatives_considered": [
    "Qlib's public Chinese-stock dataset (the data RD-Agent's templates are tuned for): would give a non-degenerate backtest but is not the owner's crypto data and needs a further download; not taken in this session.",
    "Editing RD-Agent's templates for crypto (topk, LightGBM penalties, annualisation): forbidden, RD-Agent is pinned and unmodified.",
    "A trimmed Qlib image instead of the upstream Dockerfile: more work and a second image to trust; the upstream image was built as-is."
  ],
  "pre_mortem": [
    "The backtest runs but means nothing: checked the predictions directly; they were constant, so the result is reported as uninformative.",
    "Data names lie: the template's Chinese names (csi300, SH000300, cn_data) are aliases for crypto data; written down in the run's ALIASES.md and here.",
    "Budget overrun: gateway caps left at 60 calls and 10 USD; the run used 27 calls and 0 USD."
  ],
  "slices": [
    {"title": "Runtime: pinned RD-Agent install with the stock runtime; upstream Qlib image built", "verify": "bash scripts/setup_rdagent.sh --with-stock-runtime; docker image inspect local_qlib:latest", "expected": "source digest and stock identity print; image present", "rollback": "remove .alpha/state/runtime and the image", "status": "done"},
    {"title": "Real data: 15 Binance coins re-hashed and converted to Qlib's format with Qlib's dump_bin", "verify": "qlib-build-receipt.json and logs/qlib-data.sha256 in the run folder", "expected": "43,181 bars, no gaps, BTC closes match to float32 precision", "rollback": "delete the run folder", "status": "done"},
    {"title": "One FactorRDLoop iteration through the gateway", "verify": "work/log in the run folder and gateway calls.jsonl", "expected": "all five steps executed, under 60 calls", "rollback": "none needed", "status": "done"},
    {"title": "Roadmap, component page and this task folder", "verify": "uv run python scripts/gate.py check", "expected": "All checks passed", "rollback": "revert the document changes", "status": "done"}
  ],
  "tier_impact": ["none"],
  "docs_to_update": ["docs/roadmap/rd-agent-in-alpha.md", "docs/reference/project/components/rd-agent.md"],
  "out_of_scope": ["RD-Agent source and templates", "workers/rdagent code", "scripts/setup_rdagent.sh", "research guards", "the paid route", "admission or promotion of any result"],
  "files": [
    "docs/work/archive/2026-11/2026-11-14-rdagent-first-real-loop/",
    "docs/roadmap/rd-agent-in-alpha.md",
    "docs/reference/project/components/rd-agent.md"
  ]
}
```

## Read first

| Read | Section | When |
|---|---|---|
| [worker invariants](../../../../reference/invariants/workers.md) | RD-Agent worker | always |
| [RD-Agent component](../../../../reference/project/components/rd-agent.md) | — | always |
| [ADR-0044](../../../../adr/0044-rdagent-model-gateway.md) | — | the model connection |

## Slices

As in the JSON block. The run lives outside every git tree, in
`/home/hunta/alpha-clean-base/runs/2026-11-14-rdagent-first-real-loop/`; nothing in the
repository changed except documents.

## Test plan

No code changed. The run is checked by its own records: RD-Agent's logs, the gateway's call
records and budget, the Qlib data receipt and hashes, and a direct look at the model's
predictions. The gate (`scripts/gate.py check`) covers the documents.

## Look-ahead, determinism and import impact

No ALPHA package changed. The run read ALPHA's data store read-only. Qlib's label is
`Ref($close,-2)/Ref($close,-1)-1` and its backtest trades at the next day's close, not ALPHA's
next open. Model answers are not deterministic; the backtest with constant scores was not
deterministic either (two identical baseline runs gave different returns), see `04-verify.md`.
