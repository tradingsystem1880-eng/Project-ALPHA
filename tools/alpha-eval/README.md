# alpha-eval — ALPHA research capability audit

Measures the platform plus its agent: finding and validating edge, building systems, supporting
trade research, qualifying data, and continuing research across sessions. Scores are diagnostic
engineering evidence, never authority to promote research, trade, or use capital.

## Current execution policy

New trials and judges use **Codex only**, default `gpt-6-astra`, medium effort, concurrency two.
Claude execution is rejected. Historical Claude trajectories, caches, scorecards and published
summaries remain readable and unchanged. Claude-branded repository instructions are not models
and are not removed from the platform.

The continuation plan is
[2026-09-29-codex-benchmark-continuation](../../docs/superpowers/plans/2026-09-29-codex-benchmark-continuation.md).
The [capability audit](../../docs/audit/2026-09-29-codex-capability-audit.md) distinguishes confirmed
findings from disputed judgments and missing evidence.

## Evidence and reproducibility

- Raw streams, sandbox data and model outputs live outside Git under `$ALPHA_EVAL_HOME`
  (default `~/.alpha-bench`). Summaries and the compressed historical hash inventory are in `results/`.
- Run manifests bind platform commit, expanded scenarios, world files, harness, model, effort,
  and client version. Resume rejects incompatible or unmanifested legacy runs.
- A trial collision fails. Explicit retries allocate `attempts/0001`, etc.; originals are retained.
  Reports use the latest completed attempt per slot, with older attempts available for diagnosis.
- Scoring writes `scoring/<revision>/`, never historical scorecards or judge files. Manifests bind
  source trajectories, raw streams, setup evidence, scenarios, scorer, bridge/schema and client.
  Judgment caches include complete prompt, schema, model/effort and trajectory fingerprints.
- A provider/judge failure stops new judge calls. Oversized evidence remains individually ungraded. Partial cards are explicitly named `partial-scorecards*`;
  complete revisions cannot be overwritten. Resume an incomplete revision only with identical inputs.
- `score --reuse-revision <prior>` reuses primary judgments only for identical prompt/schema/model/effort/
  trajectory keys and matching bridge/schema/client identity; the source cache hashes are bound in the
  new revision. Changed normalization requires a new judgment. Deterministic scoring is always rerun.
- Legacy runs lack acquisition-time scenario/world/harness fingerprints and had writable shared
  exports. Their limits remain explicit; rescoring cannot retroactively prove isolation or provenance.
- Historical Codex raw events are replayed into separate normalized artifacts when turn alignment
  is exact. Web searches, file changes and unknown completed event types are retained. Search actions
  without retrieved bodies leave claims unverified, not proven fabricated.

## Isolation

Each new campaign exports a pinned platform commit. Setup, CLI and MCP use that same export.
The export is read-only; trial data is writable. Exports exclude evaluator code, audits, plans,
answer keys, hidden/proposed holdouts, user configuration and owner data.

Codex permission profiles deny owner-home and evaluator files, restrict reads to the platform and
runtime dependencies, and disable command networking. The MCP subprocess runs through the same
profile. Every trial first proves permitted reads/writes, denied evaluator reads and denied export
writes, then initializes MCP and checks required tools. Startup failure blocks the trial. Plugins,
user memory, browser/computer tools and external web search are disabled. A neutral harness message
identifies the offline local data and public CLI without revealing scenario truth.

The profiles are a verified local macOS mechanism, not a portable certification. Do not substitute
`workspace-write` or unrestricted execution if preflight fails. The old read escape remains in
historical evidence, not silently repaired.

## Usage

Run from this directory (the evaluator is a separate uv project):

```bash
uv run pytest -q
uv run alpha-eval list
uv run alpha-eval probe --seeds 40 --out results/<new-name>/layer_a
uv run alpha-eval run --suts codex:gpt-6-astra --ids A04-candles --trials 1 --name <new-run>
uv run alpha-eval run --suts codex:gpt-6-astra --ids A04-candles --trials 1 --name <new-run> --resume
uv run alpha-eval score --name <run> --revision <new-revision>
uv run alpha-eval score --name <run> --revision <incomplete-revision> --resume
uv run alpha-eval report --name <run> --revision <revision> --out results/<new-report>
uv run alpha-eval analyze --name <run> --revision <revision> --out results/<new-analysis>
uv run alpha-eval compare results/<old>/summary.json results/<new>/summary.json
```

Omit `--revision` on report/analyze to read legacy scorecards. Analysis defaults to Codex as reference;
`--reference-sut` and `--comparator-sut` select historical comparisons explicitly. Second-pass judging
is opt-in through `--second-judge-tiers`; it uses a separate Codex session and is **same-model review**,
not cross-model validation. Historical Opus/Codex agreement is a separate result.

## What the suite covers

Layer A contains deterministic planted-world platform probes. Layer B contains 41 controlled
scenarios and 37 realistic instances (base requests, hint twins, seed/flaw variants and a positive/null
pair). The existing definitions remain unchanged for historical analysis.

Pass/fail uses deterministic checks, required objectives and evidence-cited verdicts. Rubric means
are supplementary. Missing judges and harness failures are excluded from rates and counted visibly.
Unknown token usage or monetary cost remains unknown. Adaptive diagnostic follow-ups must not be
pooled into fixed-cohort capability rates. Changed suites/scorers/judges do not establish improvement.

Critical findings require trace inspection. In particular, a platform validation PASS is not by itself
proof that a planted positive control is commercially executable; inspect fills, concentration,
sample size and costs. Refusing an untested null is workflow incompletion, not evidence of noise rejection.

## Verification and limitations

`uv run python scripts/gate.py component eval` from the repository root runs lock, install, lint,
format, types and evaluator tests. The canonical aggregate remains `gate.py full`.

Tests cover known-bad scorers, grounded claims, objective citations, preservation, revision collisions,
resume identity, Codex-only execution, normalization, partial traces, failed turns and descendant cleanup.
Historical world-power approximations, legacy overnight/intraday dependence and regex checks remain
limitations; do not turn them into precise scientific power or profitability claims. Platform defects
are follow-up work, not fixed to improve this campaign's scores.

## Workflow V2 diagnostic panel

`scenarios/workflow_v2.yaml` adds separately versioned R06/R08/R19/R20/R21 definitions.
`realdesk_v2` uses XNYS sessions; `bundle_v2` reconciles synthetic daily MTM to trade and
monthly outputs. Legacy catalogs/worlds remain unchanged. R21 distinguishes within-dataset
signal, bounded follow-up value and deployability. Do not pool these with historical scores.

The initial paired panel is five questions (R06-v1, R08-v1, R19-v1, R21 positive/null),
one baseline and one candidate trial each. Completion status is independently adjudicated
from retained execution evidence, separately from rubric credit. Ten trials are diagnostic,
not a powered general capability comparison. See the [active plan](../../docs/superpowers/plans/2026-09-30-research-workflow-completion.md).

## Closed synthetic investigation demo

`uv run --project tools/alpha-eval alpha-eval investigate-demo --out NEW_DIRECTORY`
calibrates three designed controls using physically restricted measurement workers. Add `--live`
to invoke bounded Codex reasoning (default model follows the existing `gpt-6-astra` route).
Outputs are append-only; an existing destination is rejected. No Claude invocation or historical
result mutation occurs. This is an evaluator command, not a public research admission workflow.

The identical vague question is presented for an observable planted indicator, a frozen-indicator
null, and an accounting defect. The null uses the same equity path with an alternating indicator;
it is not evidence that no other explanatory feature exists. These are synthetic panels, not
engine-generated backtests. The positive indicator is deliberately planted; calibration cannot
establish real-world causality or predictive availability.

The lead returns a strict Pydantic proposal. A trusted controller alone dispatches `inspect_run`,
`loss_episodes`, `historical_context`, or `conditional_diagnostic`. It reserves attempts before
execution, counts denials/failures, permits each action once, and allows at most five model calls
including synthesis. Accounting failure blocks further interpretation. A final must cite its
inspection receipt; response completion is distinct from independently reviewed research quality.
No action accepts model-provided paths, code, search parameters or commands.

Inputs contain only cutoff-permitted synthetic rows and bounded source records. Parent hashes
remain evaluator-side. Measurement workers have read-only input/code access, a minimized environment
and no network access. Actual preflight probes test reads, denied input mutation, absolute/relative/
symlink escapes and network connection denial. Model decisions use an empty workspace, host skills
and configuration disabled, auxiliary tools disabled, explicit deny/read permissions, and no MCP.
Raw events are retained; unexpected tool events invalidate the turn. A model canary refusal is
only evidence of no observed disclosure, not a substitute for worker enforcement probes.

Conditional summaries freeze indicator t against equity return t→t+1 and report counts/means,
without significance or uncertainty estimates. Context is dated untrusted synthetic text, never
instructions or proof of cause. All exposed periods remain observed retrospective evidence.
`summary.json`, per-action receipts, raw model events, invocation settings, code/input hashes and
`report.md` preserve what actually happened. There is no baseline comparison or general AI-uplift
claim in this development panel. Real-data exports, predictive confirmation, broader recovery,
agent-team/SDK ablations and outcome benchmarks remain later work.

Configuration reference used for this adapter:
[OpenAI Codex configuration](https://developers.openai.com/codex/config-reference) and
[permissions](https://developers.openai.com/codex/permissions), verified against installed CLI help
and the retained transport smoke. Provider transport remains trusted; model tools and measurement
workers have separate restrictions.


### Investigation efficiency comparison

`alpha-eval investigate-compare --out NEW_DIR` performs isolated synthetic calibration and
writes the frozen nine-cell protocol. Add `--live` to acquire all nine Codex trials. It compares
the unchanged legacy adaptive policy with pre-model inspection plus compact JSON, and a
fixed-evidence advisory synthesis. The latter collects all permitted measurements before one
model call, stopping collection on integrity failure. It is a synthetic comparator, not the
production `diagnostic suggest` workflow. The default demo remains unchanged.

All automatic measurements consume the four-action budget. The same panel hashes, worker, model
and isolation are used across arms; mode order rotates across cases. Full receipts are preserved
losslessly. `comparison-protocol.json` precedes inference; `comparison.json` includes every trial,
including failures. Usage totals are unknown when any call lacks valid usage; cached tokens are
a subset of input, never an additional charge estimate. Trial elapsed time includes measurements
and provider setup/model calls but excludes shared preflight/calibration. Calibration
measurements are reported separately. No billing dollars or statistical uplift are inferred.

See the [efficiency plan](../../docs/superpowers/plans/2026-10-02-investigation-efficiency.md).

[Retained nine-trial results](results/investigation-efficiency-20261002/report.md) show lower
measured usage for prechecked and fixed policies, with an independent qualitative evidence
review. The small designed panel does not establish general agent reliability; defaults remain
unchanged and richer selection tests precede any team/runtime expansion.


### Research judgment cases

`alpha-eval investigate-judgment --out NEW_DIR` prepares six isolated synthetic cases and
freezes a 12-cell protocol. Add `--live` for prechecked versus fixed Codex trials (at most 30
model calls). The same optional judgment guidance asks both modes for a leading explanation,
a credible alternative, discriminating evidence and prioritized next work. It is not a
production assistant integration or a claim of expert trading competence. Old commands and
default prompts remain unchanged.

Cases contrast relevant and misleading context, strategy losses against a rising benchmark,
post-outcome labels, missing benchmark/indicator data, and an injected context measurement outage.
The last is a deterministic test fault, not an observed provider incident. Null data remain
unavailable, never fabricated zero returns. Indicator provenance is exposed; labels unavailable
at the export cutoff are redacted and independently checked by the worker. The numerical
estimators are unchanged. Source inventory titles are untrusted metadata, not conclusions.

Review actual source exposure before crediting resistance to injected instructions. Failure to
retrieve a source is not successful handling of its text. Automatic accounting enforcement is
separate from model judgment. The fixed mode still supplies all available measurements; no
artificial cost handicap is added to manufacture an adaptive advantage.

[Judgment plan](../../docs/superpowers/plans/2026-10-02-research-judgment-cases.md) defines the
case-specific expectations outside model inputs. Completion, engineering verification and
research-quality review are separate. Real execution reconciliation and data export remain
prerequisites for using owner trading evidence.

Transport receipts now include `failure_kind`, distinguishing provider errors, malformed events,
unexpected tool events and timeouts. The shared stream `stop` field retains its legacy generic
callback-stop label; it must not by itself be interpreted as evidence of a model tool attempt.
