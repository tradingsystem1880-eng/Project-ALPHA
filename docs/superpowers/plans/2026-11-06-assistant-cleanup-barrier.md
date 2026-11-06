# Assistant cleanup before lock release

```json
{
  "schema_version": 1,
  "title": "Assistant cleanup before lock release",
  "context": "The native-upstream documentation aggregate exposed a watchdog failure: the inherited lock became available while the model child still had state R. Self-directed group SIGKILL sends a signal but supplies no completion barrier.",
  "assumptions": [{"statement":"Assistant launches a trusted command in an isolated process group; model tools remain disabled", "verified_by":"assistant_runtime.py and assistant_worker.py"}],
  "alternatives_considered": ["Do not weaken the immediate post-lock assertion or retry a failing aggregate until green", "Keep the watchdog alive outside the model group and wait for cleanup", "Existing durable_lease retained-leader helper is Linux-only and cannot follow communicate after it has reaped a child"],
  "pre_mortem": ["Moving the model group without changing caller cancellation leaves an orphan", "Reaping the group leader before the final destructive signal permits PID reuse", "A repeated cancellation interrupts cleanup", "Orphan zombies block group disappearance without a functioning reaper"],
  "slices": [
    {"title":"Watchdog cleanup barrier", "verify":"Synthetic ordering, parent death, deadline and descendant tests", "expected":"Signal owned model group before reaping; retain lock until cleanup completes", "rollback":"Revert lifecycle change as a unit", "status":"done"},
    {"title":"Caller cancellation and qualification", "verify":"Runtime cancellation regressions, public aggregate and required independent review", "expected":"Caller requests watchdog shutdown and waits; all prior docs evidence remains history", "rollback":"Revert caller and watchdog together", "status":"in_progress"}
  ],
  "tier_impact": ["protected"],
  "docs_to_update": [".claude/rules/alpha-cli.md", "docs/BUILD-STATUS.md", "README.md"],
  "out_of_scope": ["Model calls or spending", "Trading authority", "Detached malicious process containment", "Private test source", "Changing gate or coverage requirements"],
  "files": ["apps/alpha-cli/src/alpha_cli/assistant_worker.py", "apps/alpha-cli/src/alpha_cli/assistant_runtime.py", "tests/unit/test_assistant_cleanup.py", "tests/unit/test_assistant_boundaries.py", "tests/unit/test_assistant_service.py", "tests/unit/test_gate_process_supervisor.py"]
}
```

No DAG, statistical, data-clock or seed changes. A pending kill is not proof of
termination ([kill semantics](https://man7.org/linux/man-pages/man2/kill.2.html));
the caller must wait for completion ([Python subprocess](https://docs.python.org/3.12/library/subprocess.html)).
The original ten documentation paths do not match the formal review scope. This
repair's required manual update does, so assess the final path set independently;
do not inherit another candidate's private-suite exception.
