# ADR-0030: Require fresh Touch ID for Workstation research authority

**Status:** Accepted
**Date:** 2026-08-13
**Deciders:** Project ALPHA owner and AI build agents

## Context

The private Workstation can present research evidence and proposals, but an ordinary browser click
does not establish that the local owner reviewed the exact artifact and consequence. A caller-
provided actor string is not authentication. Keeping every decision in a separate CLI also made the
guided owner journey unnecessarily opaque. The browser needs a narrow owner-presence mechanism
without acquiring the CLI's general authority or creating any broker, order, holdout, paper-entry,
risk-override, or research-gate-override path.

WebAuthn platform credentials provide origin-bound public-key authentication and user verification.
For local development, the canonical relying-party origin is `http://localhost:8801`; the server may
bind its socket to loopback, but requests made to `127.0.0.1` redirect before enrollment or action.

## Decision

- Pin `webauthn==3.0.0` in `alpha-cli`; it is the sole registration/assertion verifier. The browser
  performs only the standard WebAuthn ceremony and never supplies an owner actor.
- Enrollment begins only with `alpha owner-auth enroll --reason ...`. The trusted CLI issues a
  five-minute fragment-token URL. Replacement uses `alpha owner-auth recover --reason ...` and
  appends the recovery reason; the browser cannot initiate or weaken recovery.
- Add an exact, additive schema-v3 control-store migration under the existing writer lock and exact
  V2 backup discipline. Store verified public credentials, one-time challenges, append-only
  credential events, and append-only owner-action receipts. Historical records are not rewritten.
- Require a new 60-second, single-use assertion with `userVerification=required`, exact origin and
  RP ID, and a strictly increasing signature counter for every Workstation owner action.
- Bind each challenge to a closed action type, project, immutable artifact hash, authoritative case
  revision, consequence summary, reason, and canonical payload hash. Recheck case revision and
  payload before consuming the assertion. Consume and receipt authorization before executing the
  server-built closed CLI command so parallel replay can never execute twice.
- Permit only source-claim screen/reject/revise, source-pack freeze, exploration
  approve/reject/revise, D1 launch, confirmation approve/reject, exact D2 launch, and final research
  disposition. MCP and generic jobs receive no owner-auth capability. Trusted CLI recovery remains
  available and does not make a browser assertion reusable.

## Consequences

- Guided mode can perform explicit owner research decisions without copying opaque IDs, while
  Advanced mode grants no added authority.
- Expired, replayed, cross-origin, wrong-action, counter-regressed, state-stale, or payload-modified
  ceremonies fail closed. A failed executor consumes its authorization, requiring fresh owner
  presence for a retry; this favors at-most-once authority over convenience.
- Credential material stays in the control store and browser authenticator. The server derives the
  actor from the verified credential. Neither MCP nor generic command execution can impersonate it.
- The permanent exclusions above require a new ADR and explicit owner decision before they can ever
  be added; this record does not authorize them.
