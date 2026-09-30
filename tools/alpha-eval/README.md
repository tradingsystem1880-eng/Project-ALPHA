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
