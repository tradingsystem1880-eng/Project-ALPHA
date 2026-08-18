# Hidden holdout seed

These are the initial `@pytest.mark.holdout` behaviour tests over the gauntlet gates, the
DSR/PBO thresholds and the t+1-open execution convention. They are staged here (an
unprotected path) because the authoring agent must never read or edit `tests/holdout/` — the
harness denies Read/Edit/Write/shell-writes there unless the owner token is present.

Owner, once, to activate them:

```bash
git mv tests/holdout_seed tests/holdout
```

After the move: CI and `gate.py full` run them (they are ordinary tests under `tests/`), the
commit guard blocks on a failure like any other test, `independent-reviewer` may read them,
and this README can be deleted. Add new holdout tests directly under `tests/holdout/`
yourself; an agent that proposes one stages it under `tests/holdout_seed/` again.
