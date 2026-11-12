# Server-owned native-job result read contract

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
