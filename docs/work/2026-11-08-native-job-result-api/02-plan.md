# Server-owned native-job result read contract

**Delivery state:** Implemented – qualification pending — code only in uncommitted candidate a631e8e7; never merged or gated

```json
{
  "schema_version": 1,
  "title": "Server-owned native-job result read contract",
  "context": "W04 prerequisite for W02/T10 receiver-backed results: a read-only GET for native job results, mounted with a minimal shared router change and no canonical run publication or link. Front block added 2026-11-13 during the plan status pass; every field restates this plan's own text. Implementation slices are marked done because the named code and tests exist in candidate a631e8e7; review slices stay pending unless the text records a review.",
  "assumptions": [
    {
      "statement": "The parent explicitly authorizes the minimal shared router mount in app.py.",
      "verified_by": "Plan text: 'Parent explicitly authorizes minimal shared router mount'."
    },
    {
      "statement": "API profiles are trusted, stable local deployment assets with engineering-default preflight bounds.",
      "verified_by": "Plan section 'Engineering defaults (NOT canonical admission/budget policy)'."
    }
  ],
  "alternatives_considered": [
    "A direct-reader draft that imported native CLI business modules into alpha_web; rejected because it crossed the web platform import DAG, replaced by the CLI-backed boundary."
  ],
  "pre_mortem": [
    "Reading native business modules directly from alpha_web breaks the platform import DAG (found and corrected in source check).",
    "An exited read-CLI leader can leave descendants holding pipes (found in independent review; fixed with retained-child observation and terminate_and_reap)."
  ],
  "slices": [
    {
      "title": "Dedicated AlphaSettings subclass and bounded read preflight",
      "verify": "Focused checks of configuration defaults and preflight bounds",
      "expected": "Profile fields default to None; no inference from clients, snapshots or credentials; fixed existing native-result CLI semantics only",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "apps/alpha-web/src/alpha_web/_native_results.py"
      ],
      "status": "done"
    },
    {
      "title": "Mount GET /api/native-jobs/{job_id}/result",
      "verify": "Typed completed/invalid/unavailable responses; HTTP 200 for domain availability, ApiErrorV1/422 for invalid syntax",
      "expected": "UUID-only identity, query/body rejected before evidence access, parsed receipt/result only when completed",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "apps/alpha-web/src/alpha_web/api/native_results.py",
        "apps/alpha-web/src/alpha_web/api/native_result_models.py",
        "apps/alpha-web/src/alpha_web/app.py"
      ],
      "status": "done"
    },
    {
      "title": "Fresh synthetic mounted-request tests and independent review",
      "verify": "test_native_result_api.py with TestClient(create_app()) over a fresh synthetic native job; independent source/security review",
      "expected": "Wrong job/profile, corruption, missing proof, late cancel, traversal and unconfigured cases fail closed; no launch, owner-record writes or credential exposure",
      "rollback": "Not stated in the original plan text; revert this slice's candidate changes.",
      "files": [
        "tests/unit/test_native_result_api.py",
        "docs/operations/native-result-api.md"
      ],
      "status": "done"
    }
  ],
  "tier_impact": [
    "none"
  ],
  "docs_to_update": [
    "docs/operations/native-result-api.md"
  ],
  "out_of_scope": [
    "ControlStore, accounting/schema/policy, dispatch/guard/worker semantics and security settings.",
    "Global frontend, Qlib results, saved inspector, paper and science edits.",
    "Public server deployment, inference and canonical run publication.",
    "Broad/full or private gates, publication, transfers and installs.",
    "Shared generated outputs and shared README/CLAUDE documentation."
  ]
}
```

W04 prerequisite for W02/T10 receiver-backed results; canonical v9 Library
libfile_181ac6079dcc8191b222b76c1f10bf17. Preserve1ef50df4c6df48edf5790d5698064431731e306b.
Parent explicitly authorizes minimal shared router mount; no canonical run publication/link.

Owned paths: new alpha_web/_native_results.py, api/native_results.py and
api/native_result_models.py; new public test_native_result_api.py and dedicated API guide.
Shared app.py only adds native_results_api import after ml_api and include after jobs_api.
Existing paper/research/source-reader registrations stay intact; absent paper successor is
not reconstructed. Exact mount hunk relayed in commentary; no cross-thread send tool exists.

1. Server deployment config uses dedicated AlphaSettings subclass, same ALPHA_ env/.env
   mechanism. Existing data_dir plus native_result_source/runtime/mode, all profilefields
   defaultNone. No inference from clients/snapshots/environment credentials. Dedicated
   bounded read preflight, then the fixed existing native-result CLI semantics only. No direct transitive imports
   of business/engine modules into alpha_web; preserve the existing platform DAG.
2. Mount GET /api/native-jobs/{job_id}/result. Only UUID identity; reject any query/nonempty
   body before evidence access. Typed completed/invalid/unavailable response with parsed
   receipt/result only completed, hash provenance, resumeFalse/scientificnot_admitted.
   Domain availability uses HTTP200; invalid syntax/selectors use existing ApiErrorV1/422.
3. Actual fresh synthetic nativejob→ownerreceipt→freshprocess TestClient(create_app())
   mounted request. Test wrongjob/profile/corruption/missingproof/latecancel, traversal,
   forbidden selectors/invalidstate and defaultunconfigured behavior. Assert no launch,
   ownerrecord writes, APIcredential exposure. Focused checks + independent source/security
   Codex review if no existing authorized Claude; no installs/auth changes.

Engineering defaults (NOT canonical admission/budget policy): API profiles are trusted
stable local deployment assets, source scan max4096entries/2048files/32MiB, Python64MiB,
lock1MiB, pyvenv64KiB; response128KiB. Existing exact artifact/control readcaps stay reused.
These are preflight bounds, not OS-level isolation or atomic filesystem guarantees. Source
profile pin/fingerprint/currentidentity must still match existing canonical records.

No ControlStore, accounting/schema/policy, dispatch/guard/worker semantics, securitysettings,
runID, globalfrontend/QlibResults/savedinspector/paper/science edits. Read-only GET uses
existing Workstation local access/error middleware. No public server deployment, inference,
protected/private/broadgates, transfers or publication. README/CLAUDE no_change: unqualified
native fixture API documented in owned guide; shared docs outside this isolated slice.

Source check found that the first direct-reader draft crossed the existing web platform
import DAG through native CLI business modules. Corrected before delivery to the normal
CLI-backed boundary with bounded stdout/stderr/time and typed exit/state validation.
The scoped import contract is checked unchanged via a temporary exact contract copy
(with an identifier added solely because the repository's unnamed contracts make the
tool's --contract filter raise KeyError). No repository contract/ignore list is weakened.

Independent review found an exited read-CLI leader could leave descendants holding pipes.
Replaced transport cleanup with existing durable_lease retained-child observation and
terminate_and_reap, keeping PID ownership through final group signal. Added exitedleader
regressions for open/closed descendant pipes; no new native owner or resume authority.
