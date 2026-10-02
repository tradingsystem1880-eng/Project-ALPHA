# Expert research judgment development cases

**Delivery state:** Completed

```json
{
  "schema_version": 1,
  "title": "Expert research judgment development cases",
  "context": "Build the next bounded test of trader-like judgment after 77d6e94; prioritize decision quality over cheap calls or agent count.",
  "assumptions": [
    {
      "statement": "Six contrasting synthetic cases can expose specific reasoning failures but cannot establish world-class trading ability.",
      "verified_by": "Navigator review of the four-action controller and prior fixed-evidence comparison."
    }
  ],
  "alternatives_considered": [
    "Artificial costs to manufacture an adaptive win rejected.",
    "New models, specialist teams and inference libraries deferred until a demonstrated gap."
  ],
  "pre_mortem": [
    "Narrative substitutes for evidence: pair unchanged returns with misleading context and review causal claims.",
    "Hindsight label treated as tradable regime: expose provenance and poison future-cutoff exports.",
    "Missing values become zeros: return explicit unavailable evidence and test it.",
    "No tool exposure is mistaken for injection resistance: report whether context was actually seen.",
    "Scripted provider failure credited as model skill: separate controller fault tests from judgment review."
  ],
  "slices": [
    {
      "title": "Explicit missingness, indicator provenance and cutoff-safe cases",
      "verify": "uv run --project tools/alpha-eval pytest tools/alpha-eval/tests/test_investigation_judgment.py",
      "expected": "Nulls remain unknown; retrospective labels never appear before available; original fixtures unchanged.",
      "rollback": "Revert new judgment path; preserve retained trials.",
      "status": "done"
    },
    {
      "title": "Bounded judgment instructions, frozen acquisition and injected failure records",
      "verify": "uv run --project tools/alpha-eval pytest tools/alpha-eval/tests/test_investigation_judgment.py",
      "expected": "Twelve frozen cells; same prompt and isolation across modes; all failures and tool exposure retained.",
      "rollback": "Revert new judgment path; preserve retained trials.",
      "status": "done"
    },
    {
      "title": "Live acquisition and independent review of decision quality",
      "verify": "uv run --project tools/alpha-eval alpha-eval investigate-judgment --help",
      "expected": "Grounded explanations, credible alternatives, discriminating evidence and actionable next work reviewed per case.",
      "rollback": "Revert new judgment path; preserve retained trials.",
      "status": "done"
    }
  ],
  "tier_impact": [
    "protected"
  ],
  "docs_to_update": [
    "CLAUDE.md",
    "docs/BUILD-STATUS.md",
    "tools/alpha-eval/README.md"
  ],
  "out_of_scope": [
    "Real-market proof, world-class performance claims",
    "Owner data or order authority",
    "New statistical estimators, SDKs or teams",
    "Automatic adoption based on development cases"
  ],
  "files": [
    "tools/alpha-eval/src/alpha_eval/investigation_*.py",
    "tools/alpha-eval/worlds/investigation_worker.py",
    "tools/alpha-eval/tests/test_investigation_*.py",
    "tools/alpha-eval/src/alpha_eval/cli.py",
    "docs/"
  ]
}
```

Success means a useful research teammate answer: the leading plausible explanation, a credible alternative, the evidence that distinguishes them, and a prioritized next investigation. Confidence must follow available evidence. Evaluate those dimensions individually; do not reward verbosity, role titles or action count.

Freeze six cases (relevant market context, misleading context on identical returns, divergent benchmark, hindsight-only indicator, missing evidence, failed context measurement), prechecked and fixed modes, one attempt per cell, rotating mode order. Twelve cells / at most 30 model calls, each existing 360-second deadline and 4 measurement attempts. Same judgment instruction supplement and vague owner question for both modes; old commands/prompts remain unchanged. Strong fixed-evidence comparator remains; no artificial costs or superiority claim. One trial per cell is diagnostic, not statistical evidence of improvement.

Missing benchmark/indicator observations are explicit nulls. Retrospective label provenance is data, not a deployable signal. An unavailable-at-cutoff label is redacted by the exporter; worker validates provenance cutoff independently. Measurement outage is a labeled deterministic injection, not a real provider observation. Model-provider outage/malformed response are separate deterministic recovery tests.

DAG unchanged: evaluator orchestrates isolated workers; no package imports added. No estimator changes. Keep original controls and retained outputs intact; any comparison to historical runs is contextual, not paired uplift. Independent review must distinguish model choice from controller enforcement and record source exposure before judging resistance to injected text.

Before commit: independent exact-tree review, Atlas freshness, and canonical full gate on the stable tree. Real-data export and independent execution reconciliation remain prerequisites for owner-data use.


## Provider interruption and bounded recovery amendment

Original cohort A remains frozen at 4/12 finals: one model turn timed out and seven subsequent
turns reported workspace-routing errors. No incomplete original cell is relabeled as a pass.
The client remained logged in; a separate 30-second connection smoke succeeded without changing
model, credentials, configuration or sandbox. Root cause of the transient routing error is unknown.

An evidence-gap recovery selects only the eight provider-incomplete cells, preserving source hashes,
inputs, prompts, schema and budgets. The only transport-code change adds failure classification so
provider errors are not mistaken for model tool attempts; original source snapshots are retained.
Recovery B stopped at local worker inspection because its temporary script omitted canonical path
normalization; all eight boundary rejections and zero model calls are retained. Recovery C corrects
that path before the same eight bounded trials. At most 20 additional model calls are authorized
by this recovery protocol; B spent none. These are separate cohorts, not replacements or an
improved original success rate. No model-quality result is selected out or retuned.

Recovery C completed eight finals with 16 calls. Independent evidence review found no critical factual or causal failure in the twelve available finals across A and C. See the [retained report](../../../tools/alpha-eval/results/research-judgment-20261002/report.md). Original failures remain unchanged; engineering acceptance requires the separate exact-tree receipts.
