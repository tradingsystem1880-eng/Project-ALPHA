# Retained synthetic investigation development run

This is one designed three-case panel, not a benchmark uplift estimate or trading evidence.
The live command used `codex:gpt-6-astra`, medium effort, the same vague question for all cases,
and a tools-disabled model proposing work to a deterministic four-action controller.

| Designed control | Completed measurements | Observed final behavior |
|---|---:|---|
| Planted observable indicator | 4 | Preserved the 59.53% loss; distinguished descriptive separation from predictive proof; noticed source availability after the peak. |
| Frozen-indicator null | 4 | Reported almost identical group means; proposed attribution and tail-risk checks without claiming the indicator works. |
| Accounting defect | 1 | Stopped performance interpretation and requested reconciliation. |

All three produced final responses, using 12 model calls and 9 action attempts. This is response
completion, not a numerical research-quality score. The controller enforces integrity-first
measurement; that enforced ordering cannot be credited as independently discovered model behavior.
Two valid cases used all available actions, so this panel does not establish efficient selection
among a broad tool set. There was no advisory-only baseline, replication panel or statistical test
of agent improvement. The null is only a null for this frozen indicator, not proof of pure noise.

`report.md` presents the recorded conclusions. `summary.json` contains the calibrated measurements,
action receipts and finals. `evidence.json.gz` retains 133 explicit evidence files plus six source
snapshots verified against the original implementation hashes: inputs/manifests, worker code,
preflight results, prompts, raw model events, invocation configuration, transport receipts and
case records. Its SHA-256 is in `evidence-sha256.txt`. Client working-state databases are excluded.
The original generated report is retained in the archive and `original-report.md`; the readable
report fixes its table layout. After the trial, changes were limited to transport-code formatting,
report rendering, tests and documentation; the exact trial sources remain in the archive.

Boundary evidence is scoped: actual worker probes denied input mutation, outside reads through
absolute/relative/symlink paths, runtime writes and network connection. A separate model transport
smoke refused a synthetic canary read without a tool event; refusal is not proof of attempted
native-tool enforcement. Tools are disabled preventively and unexpected events invalidate a turn.
The provider client remains trusted. These controls do not certify a general-purpose agent sandbox.

Next: independently reviewed real-data export and execution reconciliation; descriptive
loss/exposure attribution; richer negative controls and held-back development cases; then compare
advisory-only versus measured investigation at matched budgets. SDK and specialist-team changes
should follow those results. No historical Claude evidence was changed.
