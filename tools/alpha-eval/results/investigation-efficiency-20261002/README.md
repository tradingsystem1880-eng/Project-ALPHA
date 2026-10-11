# Retained investigation efficiency comparison

[Report](report.md) · [Frozen protocol](protocol.json) · [Structured results](comparison.json)

The nine-cell acquisition used the existing Codex gpt-6-astra model at medium effort.
No trial was retried or replaced. Historical Claude and previous Codex results are unchanged.

`evidence.json.gz` retains 277 explicit evidence files and 7 exact source
snapshots verified against the pre-acquisition implementation manifest. It includes exported
panels, manifests, worker preflight, calibration, protocol, reservations, prompts, invocation
configuration, raw model streams, transport usage, all receipts and finals. Client workspace
databases/state are excluded. Verify the archive using `evidence-sha256.txt`.

Model completion is not research-quality acceptance. See the independent review accompanying
this report. Designed controls and single observations do not establish general reliability,
real trading edge, comparative statistical significance or production-workflow performance.
