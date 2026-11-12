# Pinned native stock worker boundary hardening

This successor starts from the retained910ee456 cumulative offline candidate. It changes
only the two local stock worker files, public synthetic tests and owned documentation.
Upstream RD-Agent484776c211e4fbbeef03e0ec00d6bbee7362a4f4, dependency locks, application
accounting/admission, production commands and UI are unchanged. All results remain
synthetic_only/unqualified; no model request, live study or economic claim is introduced.

## Diagnostic scope and actual interfaces

The original58diagnostics came from applying the controller Python3.12 environment to
standalone workers without their local import directory or pinned upstream source.
Nine missing-import and seven Any-base-class diagnostics were therefore not valid
claims about the actual runtime. Resolving real upstream types also revealed optional
hypothesis/feedback and generic-interface gaps that the unresolved imports hid.

The existing full native stock profile actually selects Python3.11.17 and its installed
RD-Agent dependencies. The lighter workers/rdagent/pyproject.toml conformance environment
is a separate Python3.12 profile; no interpreter constraint or lock is changed here.
Using the actual stock interpreter plus local worker/pinned source import paths gives
51before-diagnostics. The same strict two-file invocation checks the corrected source.
This is a targeted diagnostic, not an expansion of canonical gate targets or a new
admission requirement. Root strict mypy still covers packages/apps/tests independently.

    MYPYPATH=<candidate>/workers/rdagent:<pinned-upstream-source> \
      <existing-controller-mypy> --python-executable <stock-venv>/bin/python \
      --python-version 3.11 --follow-imports=silent \
      workers/rdagent/stock_fixture.py workers/rdagent/stock_fixture_entry.py

No ignores, local upstream stubs, dependency downloads or upstream edits are used.
Scenario, Developer, Experiment, HypothesisGen/Converter/Feedback and Trace annotations
refer directly to the pinned classes. No workspace is instantiated merely to type an
experiment. The trace override preserves the base parameter names and NodeType, including
keyword calls. RDLoop itself remains the exact unmodified upstream class.

## Bounded corrections

- The active ContextVar is explicitly Effects-or-None. A missing guard fails with a
  fixed RuntimeError before charging or component effects, rather than dereferencing None.
- A pure request parser verifies the existing8192byte/closed-field/type/range contract
  before returning a TypedDict. Non-object JSON and unhashable/wrong-type modes fail
  before native settings, environment changes or artifact writes. Existing accepted
  requests, five stages and two fake-model/two fake-tool limits do not change.
- Audit arguments are checked before interpreting argv; metadata exceptions now require
  both the actual executable and exact uname/ldconfig argv. A different executable cannot
  borrow a metadata argv. Credential-name checks normalize both text and byte paths.
  Tests use unopened invented paths and callback arguments, not credential probes or
  unrecognized executable launches.
- The exact loaded RDLoop class and string request-binding marker are verified before
  checkpoint continuation. The dynamic marker remains on that native object; no custom
  loop, second scheduler or resume authority is created.
- Recovered hypothesis and feedback are checked against actual pinned types before
  reading their attributes. Malformed fixture output records failed progress and emits
  no successful trace/receipt. The same guard/counters remain outside native pickle.

Audit names and metadata executable identity still trust os.defpath/PATH and installed
system metadata binaries. They are not executable-content attestation, filesystem or
hostile-code isolation. No OS permissions, network configuration or account access changes.
No CPU/token/dollar enforcement or production worker qualification is implied.

## Identity and evidence

The worker manifest still covers exactly stock_fixture.py, stock_fixture_entry.py and
source_pin.py. All newly referenced runtime code remains inside those hash-bound files;
type-only imports add no unhashed executable helper. source_pin.py and the upstream
source digest stay unchanged. Changed worker bytes necessarily produce a different
manifest and derived launch/code fingerprints; they do not qualify an old approval.
No stored owner binding, history, reservation or allowance is rewritten or replenished.

The explicit old-worker negative uses the actual three-file manifest from910ee456,
14a31445abf42b35165cb4b016bb227f9451f731bd9694938e43ce879d9c209d.
It must fail in the current worker before upstream imports or artifact creation.
Current requests/expectations continue deriving identity from current exact bytes.

The new public test_native_stock_worker_contract.py has four pure entry/audit/loader
checks and three installed-native boundary checks. Real pinned classes test all guarded
callbacks without context and two deliberately malformed native outcomes in fresh
scratch directories. The latter use deterministic operator doubles, make no model call
and must not be described as research execution. The existing native-loop/owner/result/
API/built-browser journeys validate the positive lifecycle with current worker bytes.
The cumulative explicit selection adds this one file to the nine retained native tests;
all run under scripts/run_owned_test.py with existing installed assets and fresh receipt
roots. Private/protected/full gates remain excluded, not replaced by this selection.

The final external manifest binds the exact candidate, before/after diagnostics, checks,
worker/profile hashes, raw synthetic receipts and independent review. Prior candidates,
exports and failure receipts remain preserved. Frontend build bytes can be reused only
where exact unchanged app/package/lock identities prove applicability; the native owner
and served-browser lifecycle must be tested fresh because the worker identity changed.
