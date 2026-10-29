# Synthetic native lifecycle foundation

Status: local implementation; no native activation or release qualification.

Baseline: qualified admission tree `93a85ff21874589f4d673a1849e684e5df9ab9e4`
on `e635e6cb5bc7b9fa688dc524998d7fe1ff8eebdc`.

1. Add protected typed lifecycle events and transactional claim/failure closure in the existing
   ControlStore. Guard native ownership against generic mutation and stale reconciliation.
   Verify with explicitly named public store tests and disposable synthetic databases.
2. Add one detached trusted owner for fixed synthetic payloads, using DurableJobLease and an
   inherited lock. Reconnect only observes/cancels; owner loss remains quarantined.
   Verify controller/owner death, cancellation, timeout and process-group cleanup fixtures.
3. Review exact changes independently; correct defects; run explicit-path typing/lint and public
   regression tests. Preserve failed receipts. No full gate, commits or publication in this slice.

Package DAG is unchanged: CLI composes control and process lifecycle. No analytical package gains
persistence or execution authority. No market data, statistical estimator or seed changes.

Normal process exit is pending scientific admission, never a successful D1 attempt. Reservations
remain charged in full. Cleanup covers the POSIX process group only. Real-native activation still
requires physical worker isolation, containment, effect enforcement, executable qualification,
scientific artifact admission and a compatible-writer cutover. No schema/open migration is added.

## Adversarial continuation

Start from preserved lifecycle tree `0daaa28c1f956a8f68ba6ad673fbb2197ba13676`.
Use `test_native_fixture_adversarial.py` plus the existing explicit public fixture files;
preserve red receipts, fix only demonstrated lifecycle defects, then independently review.

- Share one cleanup result across lease cancellation/failure and owner completion. Freeze issued
  observations; incomplete/interrupted cleanup cannot become clean evidence on retry.
- Refuse dispatch after terminal no-spawn completion or after launch preparation uses the deadline.
- Keep known escaped descendants in fully charged quarantine; original-group exit is insufficient.
- Exercise both cancellation/completion transaction orders, duplicate calls, abrupt owner death
  before commit, suspended-owner expiry, and blocked publication without reclaiming capacity.

Blocked journal publication can postpone process termination. The tests record that limitation;
they qualify conservative accounting, not independent deadline enforcement or OS containment.

## Journal-independent cleanup continuation

Baseline: preserved adversarial tree `af2e9ee4bf1d062fd070581f27aa4011cc35c306`.

1. Preserve the measured blocked-publication failure, then arm the existing lease safety thread
   immediately at retained Popen, before post-spawn verification or publication. Its callbacks
   perform no SQLite work; heartbeat reporting stays on the owner thread. Verify stalled start,
   heartbeat and actual SQLite writer cases through explicit public synthetic tests.
2. Bind a private per-job cancel-only Unix datagram endpoint before dispatch. Socket delivery is
   no authority/cleanup receipt. The trusted owner journals received cancellation intent with
   its observations in the existing transaction before terminalization. Verify client death,
   both writer orders, malformed/stale requests, failures and races. Never signal persisted PIDs.
3. Run the complete explicit public lifecycle/regression selection and scoped typing/lint; have
   a fresh independent comprehensive reviewer audit the whole delta and actual test receipts.
   Resolve material findings before final identity. No aggregate gate, dependency/schema change,
   native activation, private data access, permissions changes, commit or publication.

Publication may lag physical execution and cleanup. Journal event times are publication times;
they are not exact execution timestamps or metered resource usage. Persistence failures leave
capacity/full charges occupied until verified observations can be recorded. This supersedes the
earlier blocked-journal cleanup limitation for the measured supported fixture profile, without
claiming hard OS timing, arbitrary-descendant containment, or owner-death recovery.

The independent comprehensive audit blocked the first passing candidate on a competing-reap
race: owner/lease polling and TERM-grace cleanup could release the leader before a later numeric
group signal. Correction: native owner/lease observation uses Linux waitid(WNOWAIT), serialized
with one cleanup attempt. Retain the child through TERM/grace/final KILL, then reap; subsequent
group checks are nondestructive. Already-lost wait ownership or post-reap group persistence
leaves charged quarantine, with no retry. Deterministic before-first-signal and TERM-to-KILL
regressions preserve the red evidence. No default non-native lease behavior is changed.

The follow-up audit reproduced normal-exit misclassification while start/heartbeat publication
stayed blocked beyond the deadline. The native observer now completes physical cleanup for an
observed exit on the safety loop, after checking pending stop/deadline requests, without journal
work. Its normal result therefore survives later reporting delays. The detached entry establishes
default SIGCHLD before claims/effects; other dispositions are denied by the host profile. Internal
in-process fixtures require the trusted default/no-auto-reaping profile and exclusive wait ownership;
concurrent outside waitpid or signal-disposition mutation is unsupported. No sigaction ABI shim,
kernel privilege, new dependency, or wider process-containment claim is introduced.
