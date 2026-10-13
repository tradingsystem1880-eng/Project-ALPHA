# Development loop

Use a focused check while editing, then run final acceptance on the finished tree.
Complete code, documentation, generated contracts and assets before the full gate;
changing them afterward invalidates its evidence.

| Change | Start here |
| --- | --- |
| Python behavior | `uv run pytest -q tests/unit/test_<feature>.py` and its covering integration tests |
| Python imports | `uv run lint-imports` |
| Frontend model | In `apps/alpha-web/frontend`: `npm test -- src/path/model.test.ts` |
| Browser behavior | In that directory: `npm run test:e2e -- e2e/feature.spec.ts` |
| Component readiness | `uv run python scripts/gate.py component NAME` |
| Final acceptance | `uv run python scripts/gate.py full` |

The frontend component runs `npm run build` once, including TypeScript, before
`test:e2e:built`. The standalone `test:e2e` still builds first; use the built-only
command only after a fresh build. API and SPA freshness remain required.

`NAME` is `backend`, `frontend`, `literature`, `qlib`, `atlas` or `eval`.
Focused checks give feedback; they do not confer aggregate acceptance. The `fast`
backend lane excludes platform tests, so control-plane and web changes need their
covering tests explicitly. Keep browser tests serial while their shared store
requires it. Run timing budgets on an idle reference machine under the existing
opt-in policy; functional browser coverage remains required.

Place pure Python behavior in the existing `packages/alpha-*` owner. CLI command
registration belongs in `apps/alpha-cli/src/alpha_cli/*_cmds.py`; reusable application
composition stays in that package. Web/MCP relay supported CLI seams, and frontend
models render Python-authoritative results. Follow the enforced import contracts
before adding a dependency or extracting a module.

Within the CLI, `_crypto_persistence.py` owns exact-byte immutable crypto JSON
writes; typed command wrappers keep document identity and directory selection.
`_control_json.py` owns pure JSON encoding/validation/decoding. `control_store.py`
retains its existing facade names, database transactions, migrations and authority.
Source relocation changes new execution fingerprints intentionally; it never
rewrites historical research evidence or changes document content identities.

Read [the operating manual](../../CLAUDE.md) for mandatory invariants,
[architecture](../ARCHITECTURE.md) for ownership and data flow,
[ADRs](../adr/README.md) for decisions, and [build history](../BUILD-STATUS.md)
for recorded delivery evidence. Plans describe scope; they are not proof of a pass.
