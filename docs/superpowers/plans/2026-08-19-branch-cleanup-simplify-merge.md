# Branch Cleanup, Simplification, Verification & Merge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Every task begins by loading the repo skill `karpathy-guidelines`** (`.agents/skills/karpathy-guidelines/SKILL.md`); every simplify task also loads `code-simplification` (`.agents/skills/code-simplification/SKILL.md`) and runs the bundled `/simplify` four-lens pass on its own diff before committing; every task ends with `verification-before-completion`. Dispatch **Opus** subagents for the simplify/review tasks (4–9, 15) and **Sonnet** subagents for the mechanical sweeps (12–14).

**Goal:** Reduce everything this branch added on top of `origin/main` (the 39-commit Claude harness + the merged Codex provider/crypto program + docs) to its simplest behavior-preserving form, prove every guardrail and CLI function works, fix docs drift, and land it on `main` through a PR with green CI and a merge commit.

**Architecture:** Behavior-preserving deletion and consolidation only — no new features. The branch's own tests, the full gate stamp, and a recorded baseline of metrics (sub-app list, MCP tool count = 62, deny-rule count = 57, hook events, coverage ≥ 93 %) are the oracle that nothing was lost. Refactor scope is the **branch delta only** (owner decision 2026-08-19); audited pre-existing packages are not touched.

**Tech Stack:** Python 3.12 / `uv` workspace, Typer CLI, pytest, mypy `--strict`, ruff, import-linter; harness = `scripts/gate.py` + `scripts/claude_hooks.py` + `.claude/`; GitHub via `gh`.

**Spec:** The owner request of 2026-08-19 (chat) + `CLAUDE.md` invariants + `docs/operations/claude-code-harness.md`. Findings driving each task come from three read-only audits run 2026-08-19 (harness bloat audit, Codex-delta/docs-drift audit, verification-surface audit); their file:line facts are inlined below so an executor never has to re-derive them.

## Global Constraints

- **Working tree:** `WT=/Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386` on branch `claude/blissful-edison-00b74b` (HEAD `98d8f0d`, clean, 192 commits ahead of `origin/main`, never pushed). The shell cwd resets after every Bash call — **every command starts with `cd "$WT" &&`** (write the absolute path; `$WT` is shorthand in this document). Main checkout `A=/Users/hunternovotny/Desktop/Project-ALPHA` sits on `codex/full-repair-program` (dirty; Task 2 consumes it). Scratchpad `SCRATCH=/private/tmp/claude-501/-Users-hunternovotny-Desktop-Project-ALPHA--claude-worktrees-infallible-kalam-2f15ea/fd3db76f-9c4e-4272-80eb-f3ae8f62c419/scratchpad`.
- **Karpathy rules apply verbatim:** every changed line traces to this plan; no "improving" adjacent code; remove only orphans your own change created; match existing style; if a step turns out to need more than described, stop and say so rather than widening silently.
- **Behavior-preservation oracle:** existing tests pass **unmodified**, except tests whose only subject is code this plan deletes (delete those in the same commit) and the exact test edits this plan names.
- **Protected control-plane writes** (`scripts/gate.py`, `scripts/claude_hooks.py`, `scripts/harness_models.py`, `scripts/codex_bridge.py`, `.claude/settings.json`, `.claude/statusline.py`, `.claude/harness-baseline.json`, `.claude/mutation-baseline.json`, `.mcp.json`, `.semgrep/alpha.yml`, `CLAUDE.md`, `AGENTS.md`, everything under `.claude/{skills,agents,commands,rules}/`, `.github/workflows/`, `tests/bias_guards/`, `tests/oracles/`, `tests/unit/test_claude_harness_*`, `tests/unit/test_claude_md_relocation*`, `tests/unit/test_repo_awareness_drift*`) each need
  `cd "$WT" && uv run python scripts/gate.py ack --reason "<why>" --path <rel>`
  **in its own Bash call immediately before the write. One ack = one write.** Task 6 adds two new files to this list.
- **Commit guard** (`scripts/claude_hooks.py:770-835`): a full-tier stamp for the current tree (`uv run python scripts/gate.py full`, ≈9 min, run in the background and wait for the notification; docs-only commits are waived), a conventional message (`feat|fix|test|build|chore|docs|refactor|ci|style|data(scope): summary`), ≤ 1000 changed non-docs lines per commit, and any risk-tier path (`packages/alpha-{validation,research,backtest}/src/**`, quant-named `packages/*/src` files, `alpha_cli/{_gauntlet,_optim,_seeds,_identity,_surrogate,_synth,_runner}.py`) needs a `/review-gate` APPROVE first. **No edits while a gate is running** (they invalidate the stamp). One green stamp may cover several consecutive commits as long as the tree does not change between them. `git push` also requires a full stamp.
- **Never:** read/edit/render `tests/holdout/`; read `.env`/`.env.*`; print a secret value; `rm -rf` outside `$SCRATCH`; force-push, `--amend`, squash, rebase or history rewrite; `ALPHA_HARNESS_DISABLE=1`; `ALPHA_PAPER_ENABLED`/`ALPHA_IBKR_PAPER_ENABLED`; `alpha paper ibkr-run`; owner-authority verbs (`alpha research approve|reject|decide`, `alpha project override-research-gate|reveal-holdout`, `alpha owner-auth enroll|recover`).
- **Outward-facing steps** (push, PR create, merge, branch/worktree deletion) each get an explicit owner confirmation at execution time (owner decision 2026-08-19: this session executes them, confirming each).
- **Deliberately kept (do not "simplify" these):** `.claude/rules/00-karpathy.md` verbatim mirror of the canonical skill (the always-on mechanism; pinned by `tests/unit/test_claude_md_relocation.py:106-109`); `KARPATHY_BLOCK` injection at SessionStart/PostCompact; the three vendored skills `code-simplification`, `incremental-implementation`, `alpha-research-scientist` (loaded via the Skill tool per `CLAUDE.md`, not agent frontmatter — they are not dead); the 5 thin token wrappers in `gate.py:750-798` (call-site clarity beats 15 lines); the 17 verbatim hook wrapper strings in `settings.json` (JSON cannot factor them; the `[ -f "$h" ] || exit 0` fallback is what lets a `main`-rooted worktree run hook-free); `crypto_data_cmds.py` (3,918 lines, Codex-authored, integration-tested — a structural split is churn, not bloat removal; noted as follow-up in the PR body).

---

## Phase 0 — Baseline and intake

### Task 1: Save the plan and record the baseline oracle

**Files:**
- Create: `docs/superpowers/plans/2026-08-19-branch-cleanup-simplify-merge.md` (copy of this file)
- Create (scratch, not committed): `$SCRATCH/baseline.json`, `$SCRATCH/baseline-doctor.json`, `$SCRATCH/baseline-commands.json`

**Interfaces:**
- Produces: `$SCRATCH/baseline.json` with keys `head`, `stamp_tier`, `stamp_tree_hash`, `subapps` (list), `mcp_tools` (int), `allow`, `deny`, `hook_events` (list), `hook_names` (list), `harness_lines` (map file→lines), `test_count_harness` (int). Task 14 diffs against it.

- [ ] **Step 1: Copy the plan into the repo**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && cp /Users/hunternovotny/.claude/plans/i-have-found-that-shimmying-lynx.md docs/superpowers/plans/2026-08-19-branch-cleanup-simplify-merge.md && git add docs/superpowers/plans/2026-08-19-branch-cleanup-simplify-merge.md && git commit -m "docs(plans): branch cleanup, simplification, verification and merge plan"
```
Expected: commit succeeds without a gate stamp (docs-only waiver in `claude_hooks.docs_only`).

- [ ] **Step 2: Record the baseline**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && S=/private/tmp/claude-501/-Users-hunternovotny-Desktop-Project-ALPHA--claude-worktrees-infallible-kalam-2f15ea/fd3db76f-9c4e-4272-80eb-f3ae8f62c419/scratchpad && uv run alpha info commands --json > "$S/baseline-commands.json" && uv run python scripts/gate.py doctor --json > "$S/baseline-doctor.json"; uv run python - "$S" <<'PY'
import json, subprocess, sys, pathlib
sys.path.insert(0, "scripts"); import gate
S = pathlib.Path(sys.argv[1]); root = pathlib.Path(".")
settings = json.load(open(".claude/settings.json"))
stamp = json.load(open(".claude/state/gate-stamp.json"))
cmds = json.load(open(S / "baseline-commands.json"))  # a list of 172 {"id": "backtest cross-sectional", "args": [...], "options": [...]}
subapps = sorted({c["id"].split()[0] for c in cmds})
command_ids = sorted(c["id"] for c in cmds)
harness = ["scripts/gate.py","scripts/claude_hooks.py","scripts/harness_models.py","scripts/codex_bridge.py",".claude/statusline.py",".claude/settings.json"]
out = {
  "head": subprocess.check_output(["git","rev-parse","HEAD"], text=True).strip(),
  "stamp_tier": stamp["tier"], "stamp_tree_hash": stamp["tree_hash"],
  "subapps": subapps, "command_ids": command_ids,
  "mcp_tools": subprocess.check_output(["grep","-c","@mcp.tool","apps/alpha-mcp/src/alpha_mcp/server.py"], text=True).strip(),
  "allow": len(settings["permissions"]["allow"]), "deny": len(settings["permissions"]["deny"]),
  "hook_events": sorted(settings["hooks"]), "hook_names": list(gate.HOOK_NAMES),
  "harness_lines": {f: sum(1 for _ in open(f)) for f in harness},
  "test_count_harness": subprocess.check_output(["uv","run","pytest","--collect-only","-q","tests/unit/test_claude_harness_gate.py","tests/unit/test_claude_harness_hooks.py","tests/unit/test_claude_harness_hooks_subprocess.py","tests/unit/test_claude_harness_settings.py","tests/unit/test_claude_harness_skills.py","tests/unit/test_claude_harness_codex_bridge.py","tests/unit/test_claude_md_relocation.py","tests/unit/test_repo_awareness_drift.py"], text=True).strip().splitlines()[-1],
}
(S / "baseline.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
PY
```
Expected: `mcp_tools` = `62`, `deny` = `57`, `allow` = `100`, `stamp_tier` = `full`, `command_ids` has 172 entries (launchable commands; `figures` is excluded by design at `info_cmds.py:94`), `subapps` = the 21 launchable sub-apps + `validate` + `report` (23 first tokens). Record whatever it prints — this is the oracle.

---

### Task 2: Intake the Codex leftovers from checkout A (keep the fix, drop the scripts)

**Files:**
- Modify: `packages/alpha-data/src/alpha_data/quantpad_archive.py` (apply + simplify the uncommitted fix from checkout A)
- Modify: `tests/unit/test_quantpad_archive.py` (append 4 tests)
- Modify: `.gitignore` (add `.quantpad/` next to the `data/` rule at line 34)
- Create: `docs/audit/2026-08-18-quantpad-data-paper-continuation.md` (copied from A, two claims corrected)
- Checkout A cleanup: revert the tracked change, move the 5 untracked scripts + `.quantpad/` to `$SCRATCH/codex-leftovers/`

**Interfaces:**
- Produces: `class _TruncatedStream(DataError)` (module-private) raised by `chunks()` on short/over-long reads; `fetch_quantpad_archive` retries a `_TruncatedStream` twice with `sleep(1.0)`, `sleep(2.0)` then re-raises. `_is_retryable_data_error` (substring matcher) is **not** introduced.

Facts (from the audit): A's diff is +~70/−4 in `fetch_quantpad_archive`: (1) `Content-Length` enforcement — the real fix; a truncated body was previously published as a complete hash-sealed artifact; (2) a chunk `isinstance(bytes)` guard that duplicates `store.publish`'s own check at `quantpad_archive.py:231`; (3) `if not chunk: break` inside `while chunk := reader(...)` — unreachable; (4) `_is_retryable_data_error` substring-matching on its own messages (and on `"response was empty"`, which no message in the module contains — the actual text at `:243` is `"response is empty"`); (5) `_http_error_body/_reason` with `suppress(Exception)` (a silent-except by another name; `CLAUDE.md` forbids). Two new f-strings exceed the 100-column ruff limit.

- [ ] **Step 1: Capture A's working-tree state into the scratchpad (nothing is lost)**

```bash
S=/private/tmp/claude-501/-Users-hunternovotny-Desktop-Project-ALPHA--claude-worktrees-infallible-kalam-2f15ea/fd3db76f-9c4e-4272-80eb-f3ae8f62c419/scratchpad && mkdir -p "$S/codex-leftovers" && cd /Users/hunternovotny/Desktop/Project-ALPHA && git diff -- packages/alpha-data/src/alpha_data/quantpad_archive.py > "$S/codex-leftovers/quantpad_archive.patch" && cp docs/audit/2026-08-18-quantpad-data-paper-continuation.md "$S/codex-leftovers/" && tar czf "$S/codex-leftovers/untracked-scripts-and-quantpad-dir.tgz" scripts/quantpad_complete_data.py scripts/quantpad_completion_summary.py scripts/quantpad_prune_corrupt_manifests.py scripts/run_quantpad_full_completion.sh scripts/run_quantpad_full_completion_until_verified.sh .quantpad && ls -la "$S/codex-leftovers/"
```

- [ ] **Step 2: Write the failing tests** (append to `tests/unit/test_quantpad_archive.py`; they reuse the module's existing `Response(io.BytesIO)`/`opener` pattern at lines 200-253)

```python
def _response_class(headers: dict[str, str]) -> type[io.BytesIO]:
    class Response(io.BytesIO):
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

        def geturl(self) -> str:
            return "https://api.quantpad.ai/v1/coverage?symbol=AAPL"

    Response.headers = headers  # type: ignore[attr-defined]
    return Response


def test_truncated_stream_fails_loud_after_bounded_retries(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
    Response = _response_class({"Content-Type": "application/json", "Content-Length": "5"})
    calls = 0
    sleeps: list[float] = []

    def opener(*_args: object, **_kwargs: object) -> io.BytesIO:
        nonlocal calls
        calls += 1
        return Response(b"{}")  # 2 bytes delivered, 5 declared

    with pytest.raises(DataError, match="truncated: expected 5 bytes, got 2"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=opener, sleep=sleeps.append
        )
    assert calls == 3
    assert sleeps == [1.0, 2.0]
    assert _store(tmp_path).find_request(request.request_id) is None


def test_over_long_stream_fails_loud(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
    Response = _response_class({"Content-Type": "application/json", "Content-Length": "1"})

    def opener(*_args: object, **_kwargs: object) -> io.BytesIO:
        return Response(b"{}")

    with pytest.raises(DataError, match="longer than declared"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=opener, sleep=lambda _: None
        )


def test_truncated_stream_recovers_on_retry(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")
    Short = _response_class({"Content-Type": "application/json", "Content-Length": "5"})
    Good = _response_class({"Content-Type": "application/json", "Content-Length": "2"})
    calls = 0

    def opener(*_args: object, **_kwargs: object) -> io.BytesIO:
        nonlocal calls
        calls += 1
        return Short(b"{}") if calls == 1 else Good(b"{}")

    result = fetch_quantpad_archive(
        _store(tmp_path), request, api_key="secret", opener=opener, sleep=lambda _: None
    )
    assert calls == 2
    assert result["artifact_bytes"] == 2


def test_server_error_reason_is_surfaced(tmp_path: Path) -> None:
    request = QuantPadArchiveRequestV1(endpoint="coverage", symbol="AAPL", response_format="json")

    def opener(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            "https://api.quantpad.ai/v1/coverage?symbol=AAPL",
            503,
            "unavailable",
            {},
            io.BytesIO(b'{"error": "quota exhausted"}'),
        )

    with pytest.raises(DataError, match=r"reason: quota exhausted"):
        fetch_quantpad_archive(
            _store(tmp_path), request, api_key="secret", opener=opener, sleep=lambda _: None
        )
```
(If `DataError` is not already imported in the test module, add `from alpha_core import DataError`.)

- [ ] **Step 3: Run the new tests — they must fail on the unfixed module**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run pytest tests/unit/test_quantpad_archive.py -q -k "truncated or over_long or reason_is_surfaced" 2>&1 | tail -15
```
Expected: 4 failed (`DataError` not raised for truncation/over-long; no `reason:` in the 503 message).

- [ ] **Step 4: Apply the fix in its simplified form** — edit `quantpad_archive.py` (not the raw patch):

Add after `_BASE_URL` (line 44):
```python
class _TruncatedStream(DataError):
    """Body length disagreed with ``Content-Length``; a bounded retry is allowed."""


def _http_error_reason(exc: urllib.error.HTTPError) -> str:
    """Provider-supplied reason from a 429/5xx body (bounded to 512 chars), else the status."""
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except OSError:
        body = ""
    if not body:
        return str(exc.code)
    try:
        payload = json.loads(body)
    except ValueError:
        return body[:512]
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        return payload["error"]
    return body[:512]
```
Inside the `with opener(...) as response:` block, after the redirect-host check (line ~363) add:
```python
                expected_bytes: int | None = None
                declared = response.headers.get("Content-Length")  # type: ignore[attr-defined]
                if declared is not None:
                    try:
                        expected_bytes = int(declared)
                    except (TypeError, ValueError):
                        expected_bytes = None
```
Replace the `chunks()` generator (line ~384) with:
```python
                def chunks(
                    reader: Callable[[int], bytes] = reader,
                    expected_bytes: int | None = expected_bytes,
                ) -> Iterable[bytes]:
                    downloaded = 0
                    while chunk := reader(1024 * 1024):
                        downloaded += len(chunk)
                        if expected_bytes is not None and downloaded > expected_bytes:
                            raise _TruncatedStream(
                                "QuantPad archive stream is longer than declared bytes "
                                f"({downloaded} > {expected_bytes})"
                            )
                        yield chunk
                    if expected_bytes is not None and downloaded != expected_bytes:
                        raise _TruncatedStream(
                            "QuantPad archive stream is truncated: "
                            f"expected {expected_bytes} bytes, got {downloaded}"
                        )
```
Replace `except DataError: raise` with:
```python
        except _TruncatedStream:
            if attempt == 2:
                raise
            sleep(float(attempt + 1))
        except DataError:
            raise
```
and replace the terminal 429/5xx raise (`if attempt == 2: raise DataError("QuantPad archive request failed; retry the bounded request") from exc`) with:
```python
            if attempt == 2:
                raise DataError(
                    "QuantPad archive request failed; retry the bounded request "
                    f"(reason: {_http_error_reason(exc)})"
                ) from exc
```
Do **not** add `_is_retryable_data_error`, `_http_error_body`, the chunk `isinstance` guard, or `if not chunk: break`. If `suppress` is not otherwise used in the module after this, do not import it. Check the retry loop is `for attempt in range(3)` (the existing structure) so `attempt == 2` is the last try — if the module structures it differently, match that structure rather than this text.

- [ ] **Step 5: Run the module's whole test file, then ruff/mypy on it**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run pytest tests/unit/test_quantpad_archive.py -q 2>&1 | tail -5 && uv run ruff check packages/alpha-data/src/alpha_data/quantpad_archive.py tests/unit/test_quantpad_archive.py && uv run ruff format --check packages/alpha-data/src/alpha_data/quantpad_archive.py tests/unit/test_quantpad_archive.py && uv run mypy packages/alpha-data/src/alpha_data/quantpad_archive.py tests/unit/test_quantpad_archive.py
```
Expected: all tests pass (previous count + 4), ruff clean, mypy clean. If an existing test asserted the old exact 429/5xx message, its `match=` still holds because the prefix is unchanged; if it used equality, that is the one permitted test edit here (append the `(reason: …)` suffix).

- [ ] **Step 6: Bring the audit doc over with its two stale claims corrected, and ignore `.quantpad/`**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && cp /Users/hunternovotny/Desktop/Project-ALPHA/docs/audit/2026-08-18-quantpad-data-paper-continuation.md docs/audit/ && python3 - <<'PY'
import re, pathlib
p = pathlib.Path(".gitignore"); s = p.read_text()
if ".quantpad/" not in s:
    s = s.replace("\ndata/\n", "\ndata/\n.quantpad/\n", 1) if "\ndata/\n" in s else s.rstrip("\n") + "\n.quantpad/\n"
    p.write_text(s)
PY
grep -n "quantpad" .gitignore
```
Then edit `docs/audit/2026-08-18-quantpad-data-paper-continuation.md`: (a) at the "Tests run: 84 passed" line append `— re-run after the Content-Length truncation guard landed on 2026-08-19: <N> passed in tests/unit/test_quantpad_archive.py` with the number from Step 5; (b) at the "a Python sweep" continuity sentence add `(ad-hoc completion scripts, retired 2026-08-19; the truncation guard in alpha_data.quantpad_archive supersedes them)`.

- [ ] **Step 7: Full gate, then commit**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run python scripts/gate.py full
```
(run in background; wait for the notification; expected `[gate:full] PASS — stamp written for current tree.`) then
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run python scripts/gate.py check --tier full && git add packages/alpha-data/src/alpha_data/quantpad_archive.py tests/unit/test_quantpad_archive.py .gitignore docs/audit/2026-08-18-quantpad-data-paper-continuation.md && git commit -m "fix(data): fail loud on truncated QuantPad archive streams

Enforce Content-Length on the streamed body so a short or over-long read can
never be published as a complete hash-sealed artifact; retry a truncated
stream twice (1s/2s) via a typed marker instead of substring-matching error
text; surface the provider's 429/5xx reason. Carries the 2026-08-18 QuantPad
continuation audit record and ignores the .quantpad/ run-log directory."
```

- [ ] **Step 8: Clean checkout A (owner policy: keep code fixes, drop one-off scripts)** — everything was captured in Step 1, so this is reversible from `$SCRATCH`.

```bash
S=/private/tmp/claude-501/-Users-hunternovotny-Desktop-Project-ALPHA--claude-worktrees-infallible-kalam-2f15ea/fd3db76f-9c4e-4272-80eb-f3ae8f62c419/scratchpad && cd /Users/hunternovotny/Desktop/Project-ALPHA && git checkout -- packages/alpha-data/src/alpha_data/quantpad_archive.py && mkdir -p "$S/codex-leftovers/moved" && mv scripts/quantpad_complete_data.py scripts/quantpad_completion_summary.py scripts/quantpad_prune_corrupt_manifests.py scripts/run_quantpad_full_completion.sh scripts/run_quantpad_full_completion_until_verified.sh docs/audit/2026-08-18-quantpad-data-paper-continuation.md .quantpad "$S/codex-leftovers/moved/" && git status --short
```
Expected: `git status --short` prints nothing. **Before running:** check `$S/codex-leftovers/moved/.quantpad/quantpad_run_active.pid` — if the PID it names is alive (`ps -p <pid>`), a Codex completion loop is still running; stop and tell the owner instead of moving its log directory.

---

### Task 3: Salvage the unfinished oracle dedupe, then retire the stale worktrees and the mutation staging leak

**Files:**
- Create: `tests/oracles/_reference/pnl.py`, `tests/oracles/_reference/sampling.py`, `tests/oracles/_reference/tolerances.py` (from the abandoned worktree)
- Modify: `tests/oracles/test_{calibration_known_truth,differential_bailey_ldp,metamorphic_dsr,metamorphic_engine,metamorphic_metrics,metamorphic_pbo,pnl_rederivation}.py` (apply that worktree's hunks — net −75/+36)
- Remove worktrees: `.claude/worktrees/agent-a81d32be7eeb68f6f` (branch `worktree-agent-a81d32be7eeb68f6f`, HEAD `16dcdd0`, an ancestor of ours), `.claude/worktrees/hooks-bind-new-sessions-96d011` (branch `claude/hooks-bind-new-sessions-96d011`, HEAD `1b256b0` = `origin/main`, clean)
- Delete: `$WT/.claude/state/mutation/` (329 MB; `gate.mutate` rebuilds staging from scratch on every run — `gate.py:1534-1535` — and nothing reads it back)

Facts: the agent worktree holds an in-progress refactor of `tests/oracles/` that extracts shared reference helpers (`_reference/{pnl,sampling,tolerances}.py`, 95 new lines) and trims 7 oracle files by −75/+36; its harness-test edits already landed on our tip (5 files byte-identical), and `test_claude_harness_gate.py`/`test_claude_md_relocation.py` differ only because our tip has newer tests. `tests/oracles/**` is protected control plane → one ack per written file. Session worktree `infallible-kalam-2f15ea` is the one this session runs in — leave it.

- [ ] **Step 1: Export the oracle patch and confirm it is only the oracle hunks**

```bash
S=/private/tmp/claude-501/-Users-hunternovotny-Desktop-Project-ALPHA--claude-worktrees-infallible-kalam-2f15ea/fd3db76f-9c4e-4272-80eb-f3ae8f62c419/scratchpad && cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/agent-a81d32be7eeb68f6f && git diff -- tests/oracles > "$S/oracle-dedupe.patch" && cp tests/oracles/_reference/pnl.py tests/oracles/_reference/sampling.py tests/oracles/_reference/tolerances.py "$S/" && git diff --stat -- tests/oracles | tail -1 && wc -l "$S/oracle-dedupe.patch"
```
Expected: `7 files changed, 36 insertions(+), 75 deletions(-)`.

- [ ] **Step 2: Apply on WT — one ack per file (10 files), then the writes**

For each of the 3 new files: `cd "$WT" && uv run python scripts/gate.py ack --reason "oracle reference helpers salvaged from agent-a81d32 worktree (dedupe)" --path tests/oracles/_reference/<name>.py` then write the file with the Write tool (content = `$S/<name>.py`). Then for the 7 modified files, one at a time: ack with the same reason, then `git apply --include=tests/oracles/<file> "$S/oracle-dedupe.patch"`. Afterwards run `uv run python scripts/gate.py audit --digest | grep -A3 LIVE || echo "no armed tokens"` — if `git apply` was not classified as a write and acks are still armed, retire each with `uv run python scripts/gate.py ack --clear` (recorded as `ack_disarmed`, never left LIVE).

- [ ] **Step 3: Verify identical oracle test count and green**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run pytest tests/oracles -q -m "not slow_oracle" 2>&1 | tail -3 && uv run pytest tests/oracles --collect-only -q 2>&1 | tail -1 && git stash -q && uv run pytest tests/oracles --collect-only -q 2>&1 | tail -1 && git stash pop -q && uv run ruff check tests/oracles && uv run mypy tests/oracles
```
Expected: same collected count before/after the stash (dedupe removes helpers, not tests); all pass; ruff+mypy clean.

- [ ] **Step 4: Full gate → commit**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run python scripts/gate.py full
```
(background; wait) then
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run python scripts/gate.py check --tier full && git add tests/oracles && git commit -m "test(oracles): share P&L re-derivation, sampling and tolerance helpers across the oracle suite

Finishes the reference-helper extraction begun in the agent-a81d32 worktree;
numeric tolerances are unchanged, only named once."
```

- [ ] **Step 5: Retire the two stale worktrees and the mutation staging (owner confirmation first — this deletes directories)**

Ask: "Remove worktrees `agent-a81d32be7eeb68f6f` (its only unique content is now committed) and `hooks-bind-new-sessions-96d011` (clean, at origin/main), and delete the 329 MB `.claude/state/mutation/` staging? (y/n)". On yes:
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA && git worktree remove --force .claude/worktrees/agent-a81d32be7eeb68f6f && git worktree remove .claude/worktrees/hooks-bind-new-sessions-96d011 && git branch -D worktree-agent-a81d32be7eeb68f6f claude/hooks-bind-new-sessions-96d011 && git worktree prune && git worktree list && rm -rf /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386/.claude/state/mutation && du -sh /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386/.claude/state
```
(`git branch -D` is not on the deny list — verify with the permission prompt; if denied, leave the branches and note it. `rm -rf` of the git-ignored mutation staging inside our own worktree is the documented owner action at `docs/operations/owner-actions-checklist.md:189-191`; **if the pre-bash guard refuses it, do not route around the guard** (no `find -delete`, no `python -c shutil.rmtree`, never `ALPHA_HARNESS_DISABLE`) — hand the owner the exact command to run and record it as OWNER-ACTION in the Task 12 report.)

---

## Phase 1 — Simplify the harness (behavior-preserving)

### Task 4: `gate.py` — dead code, duplicates, single-source lists, one tree hash

**Files:**
- Modify: `scripts/gate.py` (`semgrep` 1746-1776; `selftest` 1475-1482 + `HARNESS_TEST_GLOBS` 1463-1467 + argparse 1914 + dispatch 2028-2029; `stamp_state`/`stamp_is_valid` 614-624; `build_brief` 1224-1233; `HARNESS_SCRIPTS` 909-914; `doctor` 1034-1035; `mutate` 1663-1712)
- Modify: `scripts/claude_hooks.py` (`_now` 431-432 and its callers 621, 956)
- Modify: `.claude/statusline.py` (`_git` 21-30)
- Modify: `.github/workflows/ci.yml` (line 66 "Harness types")
- Modify: `tests/unit/test_claude_harness_gate.py` (add 3 tests), `tests/unit/test_claude_harness_skills.py` (`_frontmatter` 24-32 → import)
- Modify: `docs/operations/claude-code-harness.md:283` (delete the false `selftest` line — done here so the tree is consistent at commit)

**Interfaces:**
- Produces: `gate.stamp_tier(root: Path) -> str` returning `"full" | "fast" | "none"` (highest tier the fresh stamp satisfies; exactly one `compute_tree_hash` call). `gate.stamp_is_valid(root, tier)` keeps its signature and semantics, now implemented over `stamp_tier`. `gate.HARNESS_SCRIPTS` gains `.claude/statusline.py` and is the single source for the CI mypy step and `doctor`'s presence check.

- [ ] **Step 1: Write the failing tests** (append to `tests/unit/test_claude_harness_gate.py`, class `TestStamps` if present, else module level; ack first: `--path tests/unit/test_claude_harness_gate.py`)

```python
def test_stamp_tier_reports_highest_fresh_tier(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert gate.stamp_tier(repo) == "none"
    gate.write_stamp(repo, "fast", steps=[], duration=0.1)
    assert gate.stamp_tier(repo) == "fast"
    gate.write_stamp(repo, "full", steps=[], duration=0.1)
    assert gate.stamp_tier(repo) == "full"
    (repo / "poke.txt").write_text("x")  # tree changed → stale
    assert gate.stamp_tier(repo) == "none"


def test_stamp_is_valid_hashes_the_tree_once(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gate.write_stamp(repo, "full", steps=[], duration=0.1)
    calls = 0
    real = gate.compute_tree_hash

    def counted(root: Path) -> str:
        nonlocal calls
        calls += 1
        return real(root)

    monkeypatch.setattr(gate, "compute_tree_hash", counted)
    assert gate.stamp_is_valid(repo, "fast") is True
    assert calls == 1


def test_every_gate_subcommand_has_working_help() -> None:
    import argparse

    parser = gate.build_parser()
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert "selftest" not in subparsers.choices
    for name, sub in subparsers.choices.items():
        assert sub.format_help(), name
```
`build_parser()` does not exist yet — extracting the argparse construction from `main()` (`gate.py:1875-1926`) into `def build_parser() -> argparse.ArgumentParser` is the one structural edit in this task; `main()` then does `args = build_parser().parse_args(argv)`. This is what gives `main()` its first test.

Add to `tests/unit/test_claude_harness_hooks.py` (ack first) inside `TestPromptContext` (or module level):
```python
def test_prompt_context_hashes_the_tree_once(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    real = gate.compute_tree_hash

    def counted(root: Path) -> str:
        nonlocal calls
        calls += 1
        return real(root)

    monkeypatch.setattr(gate, "compute_tree_hash", counted)
    code, _ = claude_hooks.hook_prompt_context({"session_id": "s1"}, repo)
    assert code == 0
    assert calls == 1
```

- [ ] **Step 2: Run them — must fail** (`gate.stamp_tier` missing; `build_parser` missing; prompt-context counts 2–3)

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run pytest tests/unit/test_claude_harness_gate.py tests/unit/test_claude_harness_hooks.py -q -k "stamp_tier or hashes_the_tree_once or working_help" 2>&1 | tail -8
```

- [ ] **Step 3: Edit `scripts/gate.py`** (ack: `--path scripts/gate.py`; do all gate.py edits in one Edit-tool pass after the single ack, or ack before each Edit call — one ack per write call)

(a) Stamps — replace `stamp_state`/`stamp_is_valid` (614-624) with:
```python
def stamp_state(root: Path) -> tuple[str, bool]:
    """``(tier, fresh-for-current-tree)``; tier is ``"none"`` when no stamp exists."""
    stamp = read_json(_state_dir(root) / STAMP_FILE)
    if stamp is None:
        return ("none", False)
    return (str(stamp.get("tier")), stamp.get("tree_hash") == compute_tree_hash(root))


def stamp_tier(root: Path) -> str:
    """Highest tier the stamp satisfies for the current tree; ``"none"`` if absent or stale."""
    have, fresh = stamp_state(root)
    return have if fresh and have in TIER_RANK else "none"


def stamp_is_valid(root: Path, tier: str) -> bool:
    return TIER_RANK.get(stamp_tier(root), 0) >= TIER_RANK[tier]
```
(b) `build_brief` (1228-1233): replace the two `stamp_is_valid` calls with one `tier = stamp_tier(root)` and a dict lookup `{"full": "full (valid)", "fast": "fast (valid; full needed to commit)"}.get(tier, "none/stale")`.
(c) `semgrep` (1729-1763): `semgrep_command` filters `p.endswith(".py")`, so the whole-repo call `semgrep_command(root, ["packages","apps","scripts","tests"])` always returns `[]` and the literal fallback always wins. Introduce one module constant and use it in both places:
```python
_SEMGREP_BASE = ("uvx", "semgrep", "--config", str(SEMGREP_RULES), "--metrics=off", "--quiet", "--error")


def semgrep_command(root: Path, paths: list[str]) -> list[str]:
    """``uvx semgrep`` over the given python paths (empty list ⇒ nothing to scan ⇒ ``[]``)."""
    targets = sorted(p for p in paths if p.endswith(".py") and (root / p).is_file())
    return [*_SEMGREP_BASE, *targets] if targets else []
```
and in `semgrep()`: `cmd = [*_SEMGREP_BASE, "packages", "apps", "scripts", "tests"]` for the non-`changed_only` branch. The `--changed` path and the unavailable/ok/fail handling stay byte-identical. `test_semgrep_command_and_scope` (`tests/unit/test_claude_harness_gate.py:975-984`) must pass unmodified.
(d) Delete `HARNESS_TEST_GLOBS` (1463-1467), `selftest` (1475-1482), the `add_parser("selftest")` line and its dispatch branch. Keep `_glob_rel` (used by `determinism`).
(e) `HARNESS_SCRIPTS`: add `".claude/statusline.py"`. In `doctor` (1034-1035) replace the hard-coded three-file presence check with a loop over `HARNESS_SCRIPTS`.
(f) `mutate` (1663-1712): after each module's staging run completes and its result is recorded, add `shutil.rmtree(staging, ignore_errors=True)` (import `shutil` if not already imported) so `.claude/state/mutation/` never accumulates.
(g) Extract `build_parser()` from `main()` exactly as described under Step 1.

- [ ] **Step 4: Edit `scripts/claude_hooks.py`** (ack): delete `_now` (431-432); replace its two call sites with `gate._now()`. In `hook_prompt_context` (1114-1137) replace the two `gate.stamp_is_valid` calls with `tier = gate.stamp_tier(root)` + the mapping `{"full": "full (valid for current tree)", "fast": "fast (valid for current tree; full needed to commit)"}.get(tier, "none/stale — gate required before commit or stop-after-edits")`, and pass `tier` into `_obligations(root, state, tier)`, whose "OWED before stop" branch becomes `if any(_is_source_edit(p) for p in edited) and tier == "none":`. Update `_obligations`' other caller(s) (grep `_obligations(`) to pass `gate.stamp_tier(root)`.

- [ ] **Step 5: Edit `.claude/statusline.py`** (ack): delete the local `_git` (21-30); move `import gate` (currently at :62 inside `main()`, after a `sys.path` insert) to module level after the path insert, and use `gate._git(root, ..., check=False)`; keep the statusline's contract "never raises" by wrapping the call sites that relied on `""` on failure in the existing broad `except` in `main()`. Behaviour must be identical for the rendered line.

- [ ] **Step 6: Edit `.github/workflows/ci.yml:66`** (ack): 
```yaml
      - name: Harness types
        run: uv run mypy --strict $(uv run python -c "import sys; sys.path.insert(0, 'scripts'); import gate; print(' '.join(gate.HARNESS_SCRIPTS))")
```
- [ ] **Step 7: Edit `tests/unit/test_claude_harness_skills.py`** (ack): delete the local `_frontmatter` (24-32) and use `gate._frontmatter` (import `gate` the way the sibling tests do). Edit `docs/operations/claude-code-harness.md`: delete line 283 (`selftest`).

- [ ] **Step 8: Run the harness suites, ruff, mypy on the harness scripts, and doctor**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run pytest tests/unit/test_claude_harness_gate.py tests/unit/test_claude_harness_hooks.py tests/unit/test_claude_harness_hooks_subprocess.py tests/unit/test_claude_harness_settings.py tests/unit/test_claude_harness_skills.py tests/unit/test_claude_harness_codex_bridge.py tests/unit/test_claude_md_relocation.py tests/unit/test_repo_awareness_drift.py -q 2>&1 | tail -3 && uv run ruff check scripts .claude/statusline.py tests/unit && uv run mypy --strict scripts/gate.py scripts/claude_hooks.py scripts/harness_models.py scripts/codex_bridge.py .claude/statusline.py && uv run python scripts/gate.py doctor && python3 .claude/statusline.py < /dev/null | head -2
```
Expected: all pass (baseline count + 4 new); doctor all `ok`; statusline prints its line.

- [ ] **Step 9: Full gate → commit**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run python scripts/gate.py full
```
(background; wait) then
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run python scripts/gate.py check --tier full && git add scripts/gate.py scripts/claude_hooks.py .claude/statusline.py .github/workflows/ci.yml tests/unit/test_claude_harness_gate.py tests/unit/test_claude_harness_hooks.py tests/unit/test_claude_harness_skills.py docs/operations/claude-code-harness.md && git commit -m "refactor(gate): one tree hash per prompt, single-source harness script list, drop dead selftest and semgrep branch

stamp_tier() computes the tree hash once for prompt-context/brief; the CI
mypy step and doctor read gate.HARNESS_SCRIPTS (statusline added, codex_bridge
now type-checked in CI); selftest had no callers; the semgrep directory branch
was unreachable; _now/_git/_frontmatter duplicates collapse onto gate's;
mutate no longer leaks its staging tree; build_parser() gives main() a test."
```

---

### Task 5: `claude_hooks.py` + `settings.json` — write-only telemetry, dead hook event, redundant allows, shared JSON scan

**Files:**
- Modify: `scripts/claude_hooks.py` (`_SESSION_DEFAULTS` 378-388; `record_edit` 405-408; `hook_pre_mcp_guard` 840-846; `hook_instructions_loaded` 950-961; `_HOOKS` 1154-1172; `_rel_path` 439-443; `validate_against_schema` 554-558)
- Modify: `scripts/gate.py` (`HOOK_NAMES` 71-89: remove `"instructions-loaded"`; add `first_json_object` helper next to `read_json`)
- Modify: `scripts/codex_bridge.py` (`_parse_object` 169-178 → use `gate.first_json_object`)
- Modify: `.claude/settings.json` (remove 13 redundant allow entries; remove the `InstructionsLoaded` hook block at 290-300)
- Modify: `tests/unit/test_claude_harness_settings.py` (parametrize row `("InstructionsLoaded","instructions-loaded")` at :97), `tests/unit/test_claude_harness_hooks.py` (asserts at :484 `bash_writes`, :560 `codex_calls`, :678 `instructions_loaded`)
- Regenerate: `.claude/harness-baseline.json` via `gate.py baseline` (pins 57 deny rules and the 11 remaining hook events)
- Modify: `docs/operations/claude-code-harness.md` (the `InstructionsLoaded` row at :91 and the "24 deny rules" at :26)

**Interfaces:**
- Produces: `gate.first_json_object(text: str) -> str | None` — the `find("{")`/`rfind("}")` slice (or `None`), used by `claude_hooks.validate_against_schema` and `codex_bridge._parse_object`.

Facts: `bash_writes` (written `:407-408`) and `codex_calls` (`:843`) have no reader except their tests; `hook_instructions_loaded` writes `state["instructions_loaded"]` that nothing reads (`:950-961`); the `codex_call` **audit event** at `:845` IS read by the digest and retrospective — keep it. Removing a hook event trips `lint_harness` (`gate.py:849-850` "hook event unwired") by design — that is why this task re-baselines with a stated reason. 13 allow entries are subsumed by globs already present: `Bash(python3 scripts/gate.py*)`, `Bash(python3 scripts/codex_bridge.py*)` ⊂ `Bash(python3 *)`; `Bash(uv run python scripts/gate.py*)`, `Bash(uv run python scripts/codex_bridge.py*)`, `Bash(uv run pytest*)`, `Bash(uv run mypy*)`, `Bash(uv run ruff*)`, `Bash(uv run lint-imports*)` ⊂ `Bash(uv run*)`; `Bash(uv lock --check*)` ⊂ `Bash(uv lock*)`; `Bash(git merge-base*)`, `Bash(git merge-tree*)` ⊂ `Bash(git merge*)`; `Bash(git worktree list*)` ⊂ `Bash(git worktree*)`; `Bash(git stash list*)` ⊂ `Bash(git stash*)`. `lint_harness` baselines only deny rules and hook events, so allow removals are invisible to it.

- [ ] **Step 1: Failing test for the shared helper** (ack `tests/unit/test_claude_harness_gate.py`):
```python
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('prefix {"a": 1} suffix', '{"a": 1}'),
        ('```json\n{"a": {"b": 2}}\n```', '{"a": {"b": 2}}'),
        ("no braces here", None),
        ("} {", None),
    ],
)
def test_first_json_object_slices_outermost_braces(text: str, expected: str | None) -> None:
    assert gate.first_json_object(text) == expected
```
Run → fails (`AttributeError`).

- [ ] **Step 2: `gate.py`** (ack): add
```python
def first_json_object(text: str) -> str | None:
    """The outermost ``{...}`` slice of ``text`` (fenced or not), or ``None``."""
    body = text.strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    return body[start : end + 1]
```
and remove `"instructions-loaded"` from `HOOK_NAMES`.

- [ ] **Step 3: `claude_hooks.py`** (ack): (a) delete `hook_instructions_loaded` and its `_HOOKS` row; drop `"instructions_loaded": []`, `"bash_writes": []`, `"codex_calls": 0` from `_SESSION_DEFAULTS`; delete the `bash_writes` append at 407-408 (keep the `via_bash` parameter only if something else uses it — grep; if nothing, drop it and its callers' argument); in `hook_pre_mcp_guard` (840-846) drop the two `state`/`codex_calls` lines but keep `gate.append_audit(root, "codex_call", …)`. (b) In `validate_against_schema` (554-558) replace the manual brace scan with `sliced = gate.first_json_object(body); if sliced is None: return "no JSON object found in the final message"; body = sliced` (keep the fenced-block regex above it — `first_json_object` handles fences too, so delete the regex if the tests still pass without it; otherwise leave it). (c) Fold `_rel_path` (439-443) into `_rel_path_from(root, root, file_path)` **only if** the three call sites never pass a leading-`-` value; verify by reading them; if any could, leave `_rel_path` alone.

- [ ] **Step 4: `codex_bridge.py`** (ack): `_parse_object` becomes
```python
def _parse_object(text: str) -> dict[str, Any] | None:
    body = gate.first_json_object(text)
    if body is None:
        return None
    try:
        obj = json.loads(body)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None
```
- [ ] **Step 5: `.claude/settings.json`** (ack): remove the 13 allow entries listed above and the whole `InstructionsLoaded` hook block. `python3 -c "import json;d=json.load(open('.claude/settings.json'));p=d['permissions'];print(len(p['allow']),len(p['deny']),sorted(d['hooks']))"` → `87 57 [... 11 events, no InstructionsLoaded]`.

- [ ] **Step 6: Tests** (ack each): remove the `("InstructionsLoaded", "instructions-loaded")` row (`test_claude_harness_settings.py:97`); in `test_claude_harness_hooks.py` delete the assertions on `bash_writes` (:484), `codex_calls` (:560) and the `instructions_loaded` test (:678 and its test function) — if a test's only subject was one of these, delete the test.

- [ ] **Step 7: Re-baseline (audited escape, stated reason) and docs**

```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run python scripts/gate.py baseline --reason "pin the 57-rule deny list (33 added since the last baseline) and 11 hook events after retiring the write-only InstructionsLoaded hook" && uv run python scripts/gate.py lint-harness && python3 -c "import json;b=json.load(open('.claude/harness-baseline.json'));print(len(b['deny_rules']),b['hook_events'])"
```
Expected: lint-harness clean; `57 [...]` without `InstructionsLoaded`. Then edit `docs/operations/claude-code-harness.md`: line 26 `24 deny rules` → `57 deny rules`; delete the `InstructionsLoaded` row (:91).

- [ ] **Step 8: Harness suites + doctor, full gate → commit**

Run the Task 4 Step 8 command; expected all green. Then `gate.py full` (background; wait), `check --tier full`, and:
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && git add scripts/gate.py scripts/claude_hooks.py scripts/codex_bridge.py .claude/settings.json .claude/harness-baseline.json tests/unit/test_claude_harness_gate.py tests/unit/test_claude_harness_hooks.py tests/unit/test_claude_harness_settings.py docs/operations/claude-code-harness.md && git commit -m "refactor(hooks): drop write-only session telemetry and the unread InstructionsLoaded hook; share the JSON-object scan; prune 13 subsumed allow globs

bash_writes/codex_calls/instructions_loaded had no reader; the codex_call
audit event (which the digest reads) is unchanged. harness-baseline.json is
re-pinned to the current 57 deny rules and 11 hook events (audited
baseline_written)."
```

---

### Task 6: `gate.py` — extract the two leaf sections into `harness_quant.py` and `harness_awareness.py` (two commits)

**Files:**
- Create: `scripts/harness_quant.py` (from `gate.py` 1485-1839: `stage_mutation_tree`, `staging_only_failures`, `mutation_kill_rate`, `mutation_required`, `mutate`, `write_mutation_baseline`, `semgrep_command`, `semgrep`, `raise_sites`, `uncovered_raise_sites`, `raise_cov`, `determinism`, `_glob_rel` and their private helpers/constants)
- Create: `scripts/harness_awareness.py` (from `gate.py` 1142-1484: `adr_drift`, `open_plan`, `latest_retrospective_watchouts`, `build_brief`, `_brief_cache_key`, `repo_brief`, `_public_symbols`, `build_index`, `write_index`, `plan_front_block`, `plan_check`, `active_plan_scope`, `in_plan_scope`, and their helpers)
- Modify: `scripts/gate.py` (`_PROTECTED_EXACT` 101-115 += the two files; `HARNESS_SCRIPTS` += the two files; `main()` dispatch imports the two modules lazily inside the relevant branches — `gate_steps` is untouched because it already runs `mutate`/`semgrep` as `scripts/gate.py …` subprocesses; `quant_source_modules` stays in the core)
- Modify: `scripts/claude_hooks.py` (`gate.repo_brief`, `gate.active_plan_scope`, `gate.in_plan_scope` → `harness_awareness.…`, importing it next to `import gate`)
- Modify: `tests/unit/test_claude_harness_gate.py` (tests of moved names import from the new modules — mechanical `gate.X` → `harness_quant.X`/`harness_awareness.X`)
- Modify: `.claude/settings.json` (nothing — `Bash(python3 *)`/`Bash(uv run*)` already cover them), `docs/operations/claude-code-harness.md` (component table row for the two files)

Facts (coupling measured by the audit): the quant-rigor block imports only `_env_runner`, `_state_dir`, `read_json`, `write_json_atomic`, `append_audit`, `scoped_changed_paths`, `matches_quant`, `_QUANT_SRC_PREFIXES` from the core and nothing imports into it except `gate_steps` and `main`; the awareness block imports `_git`, `_git_lines`, `compute_tree_hash`, `_state_dir`, `read_json`, `write_json_atomic`, `_now`, `read_audit`, `stamp_tier`, `owner_token_configured`, `ESCAPE_EVENTS`, `DIGEST_DEFAULT_DAYS` and is imported only by `main` and `claude_hooks`. `doctor` is a hub and stays. The flat `import gate` name is load-bearing in ~40 places — **the CLI entry stays `scripts/gate.py`**; only Python-level imports move. Both new files import `gate` (one direction: leaf → core; `gate` imports them **only lazily inside functions**, so there is no import cycle at module load and `import gate` stays stdlib-only and cheap for hooks). Each extraction ≈ 700 changed lines → its own commit under the 1000-line cap.

- [ ] **Step 1 (commit A — quant):** ack `scripts/harness_quant.py`, `scripts/gate.py`, `tests/unit/test_claude_harness_gate.py`, `.github/workflows/nightly.yml` is **untouched** (it calls `scripts/gate.py mutate|semgrep|determinism|raise-cov`, which still dispatch). Create `scripts/harness_quant.py` with the module docstring `"""Quant-rigor sweeps (mutation, semgrep, determinism, raise coverage) — imported lazily by gate.py."""`, `from __future__ import annotations`, `import gate` plus the exact stdlib imports the moved code uses, then the moved code verbatim (references to core names become `gate.<name>`). In `gate.py`: delete the moved block, add the two paths to `_PROTECTED_EXACT` and `HARNESS_SCRIPTS`, and in `main()` write `from harness_quant import mutate` (etc.) inside the matching dispatch branch (module-level `gate` never imports the leaves). Update tests' references. Verify:
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run pytest tests/unit/test_claude_harness_gate.py tests/unit/test_claude_harness_hooks.py -q 2>&1 | tail -2 && uv run mypy --strict scripts/gate.py scripts/harness_quant.py scripts/claude_hooks.py && uv run python scripts/gate.py semgrep --changed && uv run python scripts/gate.py raise-cov | head -3 && python3 -c "import sys,time; sys.path.insert(0,'scripts'); t=time.time(); import gate; print('import gate', round(time.time()-t,3),'s'); assert 'harness_quant' not in sys.modules"
```
Expected: green; `import gate` does not import `harness_quant`. Then `git diff --numstat | awk '{a+=$1;d+=$2} END{print a+d}'` < 1000. Full gate → `check --tier full` → commit `refactor(gate): move the quant-rigor sweeps into scripts/harness_quant.py (lazy import; CLI unchanged)`.

- [ ] **Step 2 (commit B — awareness):** same procedure for `scripts/harness_awareness.py` (`"""Session brief, repo index and plan checks — imported lazily by gate.py and by claude_hooks."""`). `claude_hooks.py` adds `import harness_awareness` beside `import gate` and switches its three call sites. Verify with the same command plus `uv run python scripts/gate.py brief --refresh | head -3 && uv run python scripts/gate.py index >/dev/null && echo index-ok`. Full gate → commit `refactor(gate): move brief/index/plan awareness into scripts/harness_awareness.py (lazy import; CLI unchanged)`. Add the two component rows to `docs/operations/claude-code-harness.md` in commit B.

---

### Task 7: `.claude` prose — retire two undispatched agents and two one-parameter command duplicates

**Files:**
- Delete: `.claude/agents/numerical-verifier.md`, `.claude/agents/docs-drift-checker.md`, `.claude/commands/second-opinion.md`, `.claude/commands/gate-fast.md`
- Modify: `.claude/commands/gate.md` (tier argument), `.claude/commands/codex-review.md` (absorb `--effort`), `.claude/commands/verify-quant.md` (:15-16 delete the `numerical-verifier` sentence)
- Modify: `scripts/claude_hooks.py` (`JSON_AGENT_SCHEMAS` :64 `docs-drift-checker`; `AGENT_BASH_ALLOW` :104 `numerical-verifier`, :108 `docs-drift-checker`; block text :999 `(or /gate-fast)` → `(or /gate fast)`; `_harness_brief` :1029 command list)
- Modify: `scripts/harness_models.py` (delete `DriftFinding`, `DriftFindings` 197-204 — dead once no agent emits them)
- Modify: `tests/unit/test_claude_harness_hooks.py` (`TestAgentBashSandbox` parametrize rows :791 and :809 naming `numerical-verifier`)
- Modify: `docs/operations/claude-code-harness.md` (agent rows :30/:180, command rows :31/:92/:219/:334 for the four removed names), `CLAUDE.md:166-169` (agent + command lists — rewrite to the real remaining sets)

Facts: `numerical-verifier` is optional (`/verify-quant:15`), unschema'd, and duplicates `quant-verifier`'s numeric_spot_checks duty (`harness_models.py:65`, `numerical-verifier.md:35`); `docs-drift-checker` is dispatched by no command and its body runs three pytest files CI already runs; `/second-opinion` = `/codex-review --diff <f> --effort medium`; `/gate-fast` = `/gate` with `fast`. `test_commands_listed_in_harness_doc`/`test_agents_listed_in_harness_doc` iterate the directories, so removals pass; `test_every_agent_preloads_karpathy` iterates too.

- [ ] **Step 1: Delete + edit (ack per write, agents/commands are agent-ackable)**

`git rm .claude/agents/numerical-verifier.md .claude/agents/docs-drift-checker.md .claude/commands/second-opinion.md .claude/commands/gate-fast.md`.
New `.claude/commands/gate.md`:
```markdown
---
description: Run the gate (full tier by default; `fast` = ruff, format, imports, mypy) and stamp on success
argument-hint: [full | fast]
---

Tier is `$ARGUMENTS` if given, else `full`. Run `uv run python scripts/gate.py <tier>`.
`full` mirrors CI (10-minute budget) and is required to commit; `fast` satisfies the Stop guard only.

Report every step's PASS/FAIL verbatim. On failure: show the failing output exactly as printed,
diagnose, fix, and re-run — never soften, summarize away, or work around a failing step. On
success confirm the stamp with `uv run python scripts/gate.py check --tier <tier>`.
```
`.claude/commands/codex-review.md`: change `argument-hint` to `[--uncommitted (default) | --diff <file>] [--effort low|medium|high]` and add after step 1: `For a quick findings-only pass over one file, write `git diff HEAD -- <file>` (or the whole file as a `+`-prefixed diff) to the scratchpad and pass `--diff <scratch> --effort medium`.` Delete lines 15-16 of `verify-quant.md`. In `claude_hooks.py`: remove the two `JSON_AGENT_SCHEMAS`/`AGENT_BASH_ALLOW` rows, change `(or /gate-fast)` → `(or /gate fast)`, and the `_harness_brief` list to `/gate /verify-quant /review-gate /adversarial-review /plan-feature /implement /harness-doctor /codex-review /codex-research /retrospective`. In `harness_models.py` delete `DriftFinding`/`DriftFindings`. In the hooks test remove the two `numerical-verifier` parametrize rows. In `CLAUDE.md:166-169` write: `Subagent team: navigator · test-architect · quant-verifier · invariants-auditor · independent-reviewer · red-team-code · adversarial-reviewer · retrospective · codex-liaison.` and `Commands: /plan-feature /implement /gate [full|fast] /verify-quant /review-gate /adversarial-review /harness-doctor /codex-review /codex-research /retrospective.` Remove the four rows from the harness doc.

- [ ] **Step 2: Verify**
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run pytest tests/unit/test_claude_harness_hooks.py tests/unit/test_claude_harness_settings.py tests/unit/test_claude_harness_skills.py tests/unit/test_repo_awareness_drift.py tests/unit/test_claude_md_relocation.py -q 2>&1 | tail -2 && uv run python scripts/gate.py doctor && grep -rn "numerical-verifier\|docs-drift-checker\|second-opinion\|gate-fast\|DriftFinding" .claude scripts docs CLAUDE.md AGENTS.md tests/unit || echo "no stale references"
```
Expected: green; doctor ok; `no stale references` (the audit journal under `.claude/state/` is git-ignored and may still mention them — that is history, not a reference).

- [ ] **Step 3: Full gate → commit** `chore(claude): fold numerical-verifier into quant-verifier, drop the undispatched docs-drift-checker, merge /second-opinion into /codex-review and /gate-fast into /gate`.

---

### Task 8: Harness tests — remove the duplicated fixtures and helpers

**Files:**
- Modify: `tests/unit/conftest.py` (add the `repo` alias once), `tests/unit/test_claude_harness_gate.py:20-22`, `tests/unit/test_claude_harness_hooks.py:22-24`, `tests/unit/test_claude_harness_hooks_subprocess.py:28-31` (delete the three local `repo` aliases), `tests/unit/test_claude_harness_hooks.py:27-30` + `test_claude_harness_hooks_subprocess.py:47-50` (`_payload` → one helper in `tests/unit/_harness_support.py`), `tests/unit/test_claude_harness_skills.py:113` (rename class `TestKarpathyAlwaysOn` → `TestKarpathyTextIsCanonical` so the name is unique)

- [ ] **Step 1:** Ack each file; make the edits; the `_payload` helper in `_harness_support.py` takes the union signature of the two existing ones (read both; keep every keyword either used).
- [ ] **Step 2:** `uv run pytest tests/unit/test_claude_harness_*.py tests/unit/test_claude_md_relocation.py tests/unit/test_repo_awareness_drift.py -q` → same count as after Task 7; `uv run ruff check tests/unit`.
- [ ] **Step 3:** Full gate → commit `test(harness): one repo fixture alias, one hook payload helper, unique class names`. (May share the Task 7 stamp if the tree is unchanged between the two commits.)

---

## Phase 2 — Codex-merged delta: quality pass (surgical)

### Task 9: Review the Codex-added CLI/data modules for silent failures, duplication and bloat; fix only confirmed findings

**Files (review scope — the branch's added modules only):** `apps/alpha-cli/src/alpha_cli/{provider_cmds,provider_readiness,owner_auth,owner_auth_cmds,ibkr_what_if,paper_acceptance,quantpad_data_cmds,crypto_data_cmds,_crypto_acquisition,_crypto_analysis,_crypto_coverage,research_crypto_binding,research_crypto_data,research_crypto_strategy,research_crypto_runtime,research_crypto_d2,run_context,strategy_candidate,strategy_candidate_cmds,strategy_candidate_runtime}.py`, `packages/alpha-data/src/alpha_data/quantpad_archive.py` and the other files `git diff --name-status origin/main...HEAD -- packages/alpha-data | grep '^A'` lists, `scripts/alpha-with-keychain-provider`.

- [ ] **Step 1: Produce the review diff and dispatch four Opus reviewers in parallel** (superpowers:requesting-code-review + the bundled `/simplify` lenses):
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && S=/private/tmp/claude-501/-Users-hunternovotny-Desktop-Project-ALPHA--claude-worktrees-infallible-kalam-2f15ea/fd3db76f-9c4e-4272-80eb-f3ae8f62c419/scratchpad && git diff origin/main...HEAD --diff-filter=A -- apps/alpha-cli/src/alpha_cli packages/alpha-data/src scripts/alpha-with-keychain-provider > "$S/codex-delta.diff" && wc -l "$S/codex-delta.diff"
```
Agents (each gets the diff path and CLAUDE.md's invariants; if the `engineering:tech-debt` / `engineering:architecture` skills are installed, hand their checklists to the simplification and altitude reviewers respectively): `pr-review-toolkit:silent-failure-hunter` (empty/broad `except`, `suppress(Exception)`, swallowed errors, defaults masking failure); a **reuse** reviewer (re-implementations of `alpha_cli` helpers such as `_runner.load_bars`, `run_store`, `artifact_contract`, `_artifacts.write_run`; pandas outside the sanctioned edges); a **simplification** reviewer (dead code, copy-paste variants, derivable state, unused parameters/imports); an **altitude/invariants** reviewer (look-ahead via `as_of`, determinism seeds from `AlphaSettings.random_seed`/semantic namespaces, typed `DataError` on data gaps/NaN/inf, no live-capital paths, `bias_guard` tests present for every new data adapter — `tests/bias_guards/`).
- [ ] **Step 2: Triage** — for each finding record CONFIRMED / FALSE-POSITIVE / OUT-OF-SCOPE with a one-line reason in `$S/codex-delta-review.md`. Fix every CONFIRMED finding TDD-style (failing test → minimal fix → green), grouped into ≤ 1000-line conventional commits (`fix(cli): …`, `refactor(cli): …`); risk-tier paths need `/review-gate` first (none of the listed modules are risk-tier — verify with `gate.matches_risk` before committing). Do not restructure `crypto_data_cmds.py`.
- [ ] **Step 3: Verify:** `uv run pytest -q -m "not network" tests/unit tests/integration 2>&1 | tail -3` green, `uv run lint-imports`, `uv run mypy packages apps tests`, then full gate → commit(s). Carry `$S/codex-delta-review.md` (counts + skipped-with-reason list) into the PR body in Task 16.

---

## Phase 3 — Docs and CI consistency

### Task 10: CI ⇄ documented gates: close the two asymmetries

**Files:**
- Modify: `.github/workflows/ci.yml` (`qlib-worker` job: add `uv lock --check` before `uv sync --locked`, matching `literature-worker` and `CLAUDE.md:97`)
- Modify: `CLAUDE.md:94` (full-gate one-liner: insert `uv run python scripts/check_openapi_operations.py &&` after the `generate_web_openapi.py --check` step, matching `ci.yml:37-38`), and the same block in `README.md:64-99`
- Verify (no edit unless it fails): `cd apps/alpha-web/frontend && npm run lint -- --deny-warnings` exits 0 with the `oxlint` script

- [ ] **Step 1:** ack `.github/workflows/ci.yml` and `CLAUDE.md`; make the two edits; run `cd "$WT/apps/alpha-web/frontend" && npm run lint -- --deny-warnings; echo "exit=$?"` → `exit=0` (if `oxlint` rejects the flag, change **CLAUDE.md** to the flag oxlint accepts — the doc follows the tool).
- [ ] **Step 2:** `cd "$WT/workers/qlib" && uv lock --check` → passes (so the new CI step is green on first run).
- [ ] **Step 3:** Commit `ci: qlib worker checks its lockfile; document the OpenAPI operations check in the full gate` (CI + CLAUDE.md are non-docs for the guard → needs the current full stamp; if the tree is otherwise unchanged since the last stamp, `check --tier full` still passes; otherwise re-run the gate).

### Task 11: Docs drift sweep

**Files (each item is a quoted, verified stale statement):**
- `README.md:459` "The root-license decision (R-22) … remain[s] pending" → replace with `R-22 is retired under the permanent private/local-only scope (see docs/BUILD-STATUS.md).`
- `README.md:437-438` "Verified owner-presence authentication" under *Not yet built* → delete the item (built: `alpha owner-auth`, ADR-0030) 
- `README.md:433` "Research source-network/download worker …" under *Not yet built* → delete (built: `workers/literature`, ADR-0024)
- `README.md:434` "…or any production empirical D1/D2 runner" → delete (built: `research_d1.py`, `research_d2.py`, ADR-0025/0026)
- `docs/BUILD-STATUS.md:3-6` "Relocated VERBATIM … Zero content changes; the governing current-status paragraph is duplicated in CLAUDE.md" → `Relocated from CLAUDE.md on 2026-08-07; CLAUDE.md keeps only the governing current-status paragraph, which is maintained there and may be newer than the copy below.`
- `CLAUDE.md:134` "The dated implementation narratives below are retained…" → "…are retained in `docs/BUILD-STATUS.md` as historical delivery records"
- `CLAUDE.md:119` "(2026-08-13)" → "(2026-08-19)" and append one sentence: `The harness (ADR-0034) and the Codex provider/crypto program (ADR-0030..0033) merged on 2026-08-19; the branch cleanup plan is docs/superpowers/plans/2026-08-19-branch-cleanup-simplify-merge.md.`
- `CLAUDE.md:159` protected-control-plane list → the full list from `gate._PROTECTED_EXACT`/`_PROTECTED_PREFIXES` (Global Constraints above, plus `scripts/harness_quant.py`, `scripts/harness_awareness.py`)
- `docs/operations/claude-code-harness.md:36` "`--cov=scripts`" → delete that clause (no such step exists); `:132-133` "bound to the exact current tree hash AND the risk-scope diff hash" → "bound to the risk-scope diff hash (`reviewed_diff_hash`)"; `:279-282` doctor claims → remove "orphan tokens" and "executable"; add `scripts/harness_quant.py`/`harness_awareness.py` to the component table (if not done in Task 6)
- `docs/operations/codex-second-model-runbook.md:22` "`scripts/gate.py:902`" → "`scripts/gate.py` (`codex_probe`)"
- `docs/adr/0034-agent-operating-system-v2.md:26-27` headline "require `ALPHA_OWNER_TOKEN`" → "require `ALPHA_OWNER_TOKEN` when the owner token is configured; unset (the owner's 2026-08-19 decision), every escape is agent self-serve and audited — the logbook `gate.py audit --digest` is the control"
- `docs/operations/owner-actions-checklist.md`: refresh the harness command list (no `selftest`, `/gate [full|fast]`), the "329 MB" note (now cleaned; `mutate` no longer leaks), and add the `.quantpad/` ignore + retired completion scripts
- `CHANGELOG.md`: one `## Unreleased` block summarising this PR (harness v2 + Codex program merged; cleanup)

- [ ] **Step 1:** Ack `CLAUDE.md`, `AGENTS.md` (only if touched), and the docs under protected prefixes; edit each item exactly as quoted. 
- [ ] **Step 2:** `uv run pytest tests/unit/test_documentation_truth.py tests/unit/test_claude_md_relocation.py tests/unit/test_repo_awareness_drift.py -q` → green (these pin CLAUDE.md/doc truth). `grep -rn "R-22\|gate-fast\|selftest\|--cov=scripts\|24 deny" README.md CLAUDE.md docs/operations docs/adr/0034* | grep -v BUILD-STATUS` → empty.
- [ ] **Step 3:** Commit `docs: reconcile README/CLAUDE/BUILD-STATUS/harness runbooks with the merged tree` (docs-only → waived stamp; CLAUDE.md is a docs path for the waiver check — if the guard treats it as non-docs, use the current full stamp).

---

## Phase 4 — Verification (all evidence recorded in one dated audit file)

### Task 12: Prove the harness measures work — 21 claimed guardrails + a live permission matrix

**Files:**
- Create: `docs/audit/2026-08-19-harness-and-cli-verification.md` (three sections: A harness measures, B permission matrix, C CLI availability [Task 13], D gates [Task 14])

- [ ] **Step 1: Determine which `settings.json` governs this session** — `ls -la /Users/hunternovotny/Desktop/Project-ALPHA/.claude/settings.json 2>&1; diff -q /Users/hunternovotny/Desktop/Project-ALPHA/.claude/settings.json "$WT/.claude/settings.json"; echo "CLAUDE_PROJECT_DIR=$CLAUDE_PROJECT_DIR"`. Record the answer verbatim. If checkout A has a stale untracked copy that Claude Code loads for `.claude/worktrees/*` sessions, say so in the report — the live matrix then reflects the tracked file only after Task 16 puts checkout A on `main`.
- [ ] **Step 2: Run the mechanical checks and paste verbatim** (all read-only):
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run python scripts/gate.py doctor; uv run python scripts/gate.py lint-harness; uv run python scripts/gate.py check --tier full; uv run python scripts/gate.py audit --verify; uv run python scripts/gate.py audit --digest | head -40; uv run python scripts/gate.py brief | head -5; python3 .claude/statusline.py < /dev/null; uv run pytest tests/unit/test_claude_harness_gate.py tests/unit/test_claude_harness_hooks.py tests/unit/test_claude_harness_hooks_subprocess.py tests/unit/test_claude_harness_settings.py tests/unit/test_claude_harness_skills.py tests/unit/test_claude_harness_codex_bridge.py tests/unit/test_claude_md_relocation.py tests/unit/test_repo_awareness_drift.py -q 2>&1 | tail -2; python3 scripts/codex_bridge.py probe
```
- [ ] **Step 3: Exercise the guardrails that must BLOCK (each must fail; record the exact refusal text):** (1) `Read` `tests/holdout/README.md` → pre-read-guard block; (2) `Edit` `.claude/settings.json` without an ack → pre-edit-guard block; (3) `git commit --allow-empty -m "feat: probe"` after `touch probe.py && git add probe.py` with **no** stamp (edit a byte first so the stamp is stale) → commit-guard block, then `git rm --cached probe.py && rm probe.py`; (4) `rm -rf /tmp/never-exists-alpha-probe` → pre-bash-guard refusal (outside scratchpad); (5) `uv run alpha research approve nonexistent` → permission deny; (6) `security find-generic-password -w -s project-alpha-tiingo` → permission deny; (7) `git push --force` → deny; (8) `git commit --amend --no-edit` → deny. Also the three CI block-smoke payloads via `python3 scripts/claude_hooks.py pre-bash-guard`/`pre-edit-guard`/`gate.py attest --kind review` exactly as in `ci.yml:67-79` → each exits non-zero.
- [ ] **Step 4: Exercise 8 ALLOW commands (must run without a permission prompt):** `git status`, `git log -1`, `git diff --stat`, `find . -maxdepth 1 -name '*.md'`, `du -sh .`, `security find-generic-password -s project-alpha-tiingo` (metadata only — never `-w`), `uv run python scripts/gate.py doctor`, `uv run alpha info`. Record ALLOWED / PROMPTED / BLOCKED per command exactly as observed. **If anything is PROMPTED or BLOCKED, write that down; do not claim the allowlist works.**
- [ ] **Step 5: Positive checks:** `gate.py ack --reason "verification probe" --path .claude/rules/docs.md` then `gate.py ack --clear` → journal shows `ack_disarmed`; `gate.py audit --digest` lists it; commit → `gate.py brief` shows the new HEAD (brief keyed on git position, `d52ec30`); `gate.py check` (default fast tier) prints `tier fast`; a `main`-rooted worktree (`/Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/infallible-kalam-2f15ea`) has `ls .claude/settings.json scripts/claude_hooks.py` → missing (harness travels with the branch until merge).
- [ ] **Step 6:** Write sections A and B of the audit doc as a table: `# | measure | command | expected | observed | PASS/FAIL`.

### Task 13: Prove every CLI function is available (Sonnet sweep; no network beyond local IB gateway/keychain launcher; no paper flags)

- [ ] **Step 1: Every sub-app and root command answers `--help` (exit 0):**
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && for c in data crypto-data backtest forecast optim paper propfirm provider quantpad-data info options owner-auth risk screener research figures project evidence ml monte-carlo suite strategy-candidate validate report; do uv run alpha $c --help >/dev/null 2>&1 && echo "OK   alpha $c" || echo "FAIL alpha $c"; done
```
Then every launchable leaf command (172 ids such as `backtest cross-sectional`):
```bash
cd /Users/hunternovotny/Desktop/Project-ALPHA/.claude/worktrees/claude-quantitative-finance-improvements-fa7386 && uv run alpha info commands --json | python3 -c "import json,sys; [print(c['id']) for c in json.load(sys.stdin)]" | while read -r id; do uv run alpha $id --help >/dev/null 2>&1 && echo "OK   alpha $id" || echo "FAIL alpha $id"; done | sort | tee /private/tmp/claude-501/-Users-hunternovotny-Desktop-Project-ALPHA--claude-worktrees-infallible-kalam-2f15ea/fd3db76f-9c4e-4272-80eb-f3ae8f62c419/scratchpad/cli-help-sweep.txt | grep -c '^OK'
```
Expected: `172` and zero `FAIL` lines. Compare `command_ids`/`subapps` to `$SCRATCH/baseline.json` — identical sets.
- [ ] **Step 2: Projections:** `uv run alpha info`, `uv run alpha info strategies --json`, `info providers --json` (12 providers), `info system --json`, `uv run alpha data symbols --json`, `uv run alpha data snapshots --json`, `uv run alpha paper readiness --json` (expect `paper_passed: false`, all 22 requirements unevidenced — that is the honest state), `uv run alpha paper ibkr-preflight SPY.ARCA --asset-class etf` (expect `IBKR Paper preflight OK … gateway: loopback:4002, paper, read-only … clients: data=20, exec=21`; if 4002 is not listening — `lsof -iTCP -sTCP:LISTEN -nP | grep ':4002'` — record "gateway down, preflight skipped").
- [ ] **Step 3: Provider checks through the canonical launcher** (each injects its keychain item into one child process; never `-w` yourself): `scripts/alpha-with-keychain-provider tiingo check`, `quantpad check`, `coingecko check`, `finnhub quote` (the launcher refuses `finnhub check` by design — record that); `uv run alpha provider check ibkr --json` **only** with the owner's env recipe from the IBKR verification (`set -a; . ./.env 2>/dev/null; set +a; export ALPHA_IBKR_PAPER_ACCOUNT="$(security find-generic-password -w -s project-alpha-ibkr-paper-account)"` — this exact string is the owner's documented recipe; if the permission layer denies it, record DENIED and skip; never echo the variable). Expected fields: `verification_state`, `gateway_reachable`, `permissions`, `granted_capabilities` — record verbatim; a missing keychain item is a recorded MISSING, not a failure of this plan.
- [ ] **Step 4: MCP + web:** `uv run pytest tests/integration/test_research_mcp.py -q -k "tool" 2>&1 | tail -2` (62-tool pin), `grep -c "@mcp.tool" apps/alpha-mcp/src/alpha_mcp/server.py` = 62; `uv run pytest tests/integration -q -k "healthz or web_app" 2>&1 | tail -2`.
- [ ] **Step 5:** Append section C to the audit doc (table per command: `command | exit | note`).

### Task 14: Every gate green, recorded

- [ ] **Step 1 (Python full gate, background):** `cd "$WT" && uv run python scripts/gate.py full` → all 13 steps PASS; then `uv run lint-imports` (14 contracts kept), `uv run pytest -m bias_guard -q` (≥ 31 files), `uv run alpha info`.
- [ ] **Step 2 (frontend gate, background, ~15 min):** `cd "$WT/apps/alpha-web/frontend" && npm ci && npm run lint -- --deny-warnings && npm run test:coverage && npm run generate:api && npx playwright install chromium && npm run test:e2e && cd "$WT" && git status --porcelain apps/alpha-web/src/alpha_web/static/app apps/alpha-web/frontend/src/api/generated.ts` → empty (assets and generated TS unchanged).
- [ ] **Step 3 (workers):** `cd "$WT/workers/literature" && uv lock --check && uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q -m "not network"`; `cd "$WT/workers/qlib" && uv lock --check && uv sync --locked && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q`.
- [ ] **Step 4 (harness sweeps):** `uv run python scripts/gate.py determinism`, `gate.py semgrep`, `gate.py doctor`, `gate.py lint-harness`, `gate.py audit --verify`.
- [ ] **Step 5 (baseline diff):** re-run the Task 1 Step 2 recorder into `$SCRATCH/final.json` and diff: `subapps` identical, `mcp_tools` 62, `deny` 57, `hook_events` = baseline minus `InstructionsLoaded`, `harness_lines` lower for `gate.py`/`claude_hooks.py`/`settings.json`, `test_count_harness` ≥ baseline − (deleted-dead-code tests) + new tests — list every difference and its cause.
- [ ] **Step 6:** Append section D (each gate: command, duration, result, first line of output on failure — there must be none). Commit `docs(audit): harness, permission, CLI-availability and gate verification record for the cleanup PR` (docs-only).

---

## Phase 5 — Finish

### Task 15: Independent review of the whole branch diff, then the final gate

- [ ] **Step 1:** superpowers:requesting-code-review — dispatch `pr-review-toolkit:code-reviewer` and `pr-review-toolkit:code-simplifier` (Opus) on `git diff origin/main...HEAD` restricted to the files this plan touched (`git log --name-only --format= <first-cleanup-commit>..HEAD | sort -u`), plus `pr-review-toolkit:comment-analyzer` on the docs. Also `/review-gate` if any risk-tier path was touched in Task 9 (verify with `for f in $(git diff --name-only origin/main...HEAD); do uv run python -c "import sys; sys.path.insert(0,'scripts'); import gate; print('$f') if gate.matches_risk('$f') else None"; done`).
- [ ] **Step 2:** Fix CONFIRMED findings (TDD), skip with reason otherwise; record in `$SCRATCH/final-review.md`.
- [ ] **Step 3:** Final `gate.py full` → PASS; `git status --porcelain` empty; `git log --oneline origin/main..HEAD | wc -l` recorded.

### Task 16: Push → PR → CI green → merge (merge commit) → post-merge cleanup

Facts: remote `origin` = `https://github.com/tradingsystem1880-eng/Project-ALPHA.git`; `gh` is authenticated as `tradingsystem1880-eng`; default branch `main`; **no branch protection**; history uses GitHub merge commits (`Merge pull request #N from tradingsystem1880-eng/<branch>`); no PR template/CODEOWNERS; neither `claude/blissful-edison-00b74b` nor `codex/full-repair-program` exists on the remote.

- [ ] **Step 1 — confirm, then push:** Ask the owner: "Push `claude/blissful-edison-00b74b` (N commits, never pushed) to origin? (y/n)". On yes: `cd "$WT" && uv run python scripts/gate.py check --tier full && git push -u origin claude/blissful-edison-00b74b` (the pre-bash guard requires the full stamp for push — it is fresh from Task 15).
- [ ] **Step 2 — confirm, then open the PR:** Show the owner the title and body first. Title: `feat: harness v2, provider/crypto program, and branch cleanup (ADR-0030..0034)`. Body sections: *What* (one paragraph: Codex provider/crypto/paper-acceptance/owner-auth program + Claude Code harness v2 + this cleanup); *Cleanup summary* (numbers from `$SCRATCH/final.json` vs `baseline.json`: lines removed per harness file, allow 100→87, agents 11→9, commands 12→10, hook events 12→11, deny 57 pinned, MCP 62 unchanged); *Verification* (link `docs/audit/2026-08-19-harness-and-cli-verification.md`; every gate green); *Review* (Task 9 + Task 15 counts and skipped-with-reason list); *Follow-ups* (`crypto_data_cmds.py` split; `_crypto_analysis.py`/`_crypto_coverage.py` lack dedicated unit files; paper readiness stays `paper_passed: false` by design; IB Gateway binds `*:4002` — restrict in IB settings); *ADRs* 0030–0034; footer `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. On yes: `gh pr create --base main --head claude/blissful-edison-00b74b --title "…" --body-file "$SCRATCH/pr-body.md"`.
- [ ] **Step 3 — watch CI:** `gh pr checks <num> --watch` (5 jobs: check, harness, frontend, qlib-worker, literature-worker). If any job fails: fix on the branch (normal TDD + gate + commit + push, no amend), never `--admin`/skip.
- [ ] **Step 4 — confirm, then merge:** "CI is green on PR #<num>. Merge into main with a merge commit? (y/n)". On yes: `gh pr merge <num> --merge --subject "Merge pull request #<num> from tradingsystem1880-eng/claude/blissful-edison-00b74b"` (matches the repo's merge style; **no** `--squash`, **no** `--rebase`, **no** `--delete-branch` until Step 5 confirms).
- [ ] **Step 5 — post-merge (confirm each):** `cd /Users/hunternovotny/Desktop/Project-ALPHA && git fetch origin && git checkout main && git pull --ff-only` (checkout A leaves `codex/full-repair-program`; `.claude/settings.json` etc. are now tracked there — `ls .claude/settings.json scripts/claude_hooks.py`); ask before `git branch -d codex/full-repair-program` (fully contained in main after merge — `git branch --merged main | grep codex/full-repair-program`) and before `gh pr view <num> --json state` + `git push origin --delete claude/blissful-edison-00b74b` (optional; the worktree `fa7386` can then be removed with `git worktree remove` — ask). Run `uv run python scripts/gate.py doctor` from checkout A on `main` → ok (harness now on main). 
- [ ] **Step 6 — memory:** update `/Users/hunternovotny/.claude/projects/-Users-hunternovotny-Desktop-Project-ALPHA/memory/project-harness-v2.md` (merged to main via PR #<num> on the merge date; `gate.py` split; `/gate [full|fast]`) and `MEMORY.md` index line; add a `project-branch-cleanup-2026-08-19.md` note only if there is a non-derivable fact (e.g. the owner's scope decisions: branch-delta only, keep-fixes-drop-scripts, session executes push/PR/merge with confirmation).

---

## Verification (end-to-end acceptance for the whole plan)

1. `docs/audit/2026-08-19-harness-and-cli-verification.md` exists with sections A–D, every row PASS or explicitly recorded as MISSING/DENIED/SKIPPED with reason — never a silent gap.
2. `$SCRATCH/final.json` vs `baseline.json`: same 22 sub-apps + `validate`/`report`; MCP 62; deny 57; hook events 11 (`InstructionsLoaded` gone, by decision); `gate.py` ≤ ~1,300 lines; `claude_hooks.py` and `settings.json` smaller; harness test count not lower except for deleted-dead-code tests (listed).
3. Every guardrail probe in Task 12 Step 3 still blocks; every allow probe in Step 4 is recorded honestly.
4. `gh pr checks` all green; PR merged with a merge commit; checkout A on `main` with the harness present and `gate.py doctor` ok.
5. No secret value appears in any committed file: `git grep -nE "eyJ[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|[a-f0-9]{40}" -- ':!uv.lock' ':!*.lock' ':!*/generated.ts' ':!*/openapi.json' ':!apps/alpha-web/src/alpha_web/static/*'` returns only hashes that are content digests (manifest/receipt hashes), never a credential; the pasted Finnhub key appears nowhere (`git grep -c <first 6 chars of the key>` → nothing — the executor knows the prefix from the owner's message and must not paste the key itself into any file or command history beyond this grep).

## Out of scope (stated so it is not silently done)

Refactoring audited pre-existing packages; splitting `crypto_data_cmds.py`; unit tests for Codex modules that are integration-covered (listed as follow-ups); rotating the exposed Finnhub key (owner declined 2026-08-19); enabling paper flags or running any IBKR order; extending Touch ID owner presence to the harness escapes; changing the 93 % coverage floor, the 14 import contracts, or any deny rule.
