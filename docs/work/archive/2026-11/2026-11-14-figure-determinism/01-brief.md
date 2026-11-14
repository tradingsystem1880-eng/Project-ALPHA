# Hash-bound figures depend only on their inputs

## What the owner wants

From the orchestrating session, 2026-11-14: "Fix it at the root so every hash-bound figure's bytes
are a function of its inputs only, in any process history". A research chart that came out
with different bytes when other tests ran first in the same Python process must not happen again,
and stored evidence must still verify.

## What done looks like

- Every chart ALPHA stores in a run (the research PNG charts and the tear sheet's charts) has the
  same bytes whatever ran earlier in the same process and whatever a local Matplotlib config says.
- A clean process produces exactly the bytes it produced before the fix, so no stored figure and
  no renderer version changes.
- A test renders each figure writer, changes Matplotlib's global state, renders again and
  compares the bytes; the research golden test pins PNG bytes instead of masking their size.

## How they will see it

Nothing visible: internal. The pull request lists the root cause, the tests and which research
approvals need renewing because a file under `packages/alpha-research/src` changed.

## Out of scope

- Font or library differences between machines (for example a Mac with Arial installed); the
  figures stay byte-stable within the locked environment, as documented.
- Any change to what a figure shows, its renderer version, or any approval.
