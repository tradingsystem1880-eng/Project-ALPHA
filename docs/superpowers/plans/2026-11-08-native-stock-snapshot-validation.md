# Native stock snapshot validation prerequisite

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

Canonical v9 (Library libfile_181ac6079dcc8191b222b76c1f10bf17) W02/T10
requires truthful wrong/missing/changed artifact evidence. T07 cannot be implemented
as cross-owner restart under the current contracts: original PID/retained lock and
outside-pickle guard are required, and consumed invocation cannot be relaunched.

The prior inspector successor ed0b58ee32aa72b25aa5a50fdd281a1748d0cfbb and exports
remain unchanged. Stock finish validates bytes but does not persist a receipt hash:
rule_result is study-only; StockFixtureLaunch requires study=None. Do not borrow that
schema or create new resume/accounting authority. Durable stock binding stays unavailable.

1. Extract the existing exact validator into a bounded byte-snapshot API, retaining one
   contract implementation. The path wrapper reads each fixed artifact once, validates
   and hashes those same immutable bytes, never deserializing a checkpoint. Test bad
   lengths/types/identity and repeated-read/mixed-generation regression.
2. Add current-artifact-only validation to the read-only inspector using its guarded
   directory-FD reads and canonical dispatch identity. Legacy/failed runs without a
   success receipt remain unavailable; incomplete/mismatched success artifacts fail.
   Do not depend on advisory progress to authorize or restore anything.
3. Run new focused synthetic tests/native success journey and independent Codex review.
   Claude is unavailable via existing tool/session; no installation/auth change.

DAG: CLI reuses existing stock fixture contract; no worker/ControlStore/accounting
changes. No market/as-of/statistical changes. Synthetic fixture determinism is unchanged.
No shared generated outputs. README/CLAUDE no_change: this is an explicitly unqualified
operator diagnostic, described in its owned guide; broader shared docs are outside scope.
No full/private gates, transfer, publication or live inference. Frozen predecessor and
successor trees plus exact delta artifacts will be recorded outside the candidate.
