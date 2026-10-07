# Terminal workflow polish — 2026-09-30

> **Superseded acceptance note (2026-10-05):** pending or failed aggregate results below are historical. The canonical full gate later passed on the frozen shared tree (stamp tree `54b7f96e`, 2026-10-04 13:46 UTC); see `docs/BUILD-STATUS.md`.

Bloomberg-inspired function navigation and information density, using the owner's grey Windows design references. This does not claim Bloomberg feature equivalence or certification.

Delivered: F2 function input covering profile-visible tasks; nested task search with explicit loading, retry and profile filtering; last-task navigation; roving task keyboard focus; compact shared desk toolbar; profile-specific saved dock visibility, width and maximization; comparison grid with distinct pinned canonical symbols; scrolling watchlist with reachable tabs. Layout storage is advisory presentation state and grants no research authority. Archive dataset selection remains separate and is not persisted as a canonical symbol.

Independent reviewer identified retained search text blocking keyboard symbol/run selection and inconsistent duplicate comparison restoration. Controlled search transitions and consistent comparison deduplication resolve those findings. Browser regression types Set symbol, presses Enter, observes an API error, retries and selects a profile-compatible result.

Verification is being refreshed for this exact frontend pass. Earlier backend evidence remains scoped to the prior terminal usability changes; no backend or numerical code changed in this pass. See the terminal usability audit for external archive evidence and provider limitations.


Fresh targeted checks: 3 minimum-viewport browser regressions passed; all 36 page-render/accessibility checks passed across 1280×720, 1440×900 and 1920×1080. Chart and Research screenshots were inspected. On the real owner app at 1280×720 the watchlist tabs end at y=451, exactly inside their panel. Independent source review found no remaining blocker after corrections.

The earlier PDF scratch lint blocker has been cleared by its owner. An initial full-gate attempt passed lint, typing, import and semgrep stages before being stopped to serialize heavy checks. Concurrent browser activity was then discovered in the separate research checkout: its configuration permits reuse of this checkout's port 8802 server. A warning was appended to `/private/tmp/alpha-workflow-report/ui-coordination.md`; no acknowledgement is claimed. Final verification must run after that runner exits. Neither overlapping run proves isolation for the other branch.

The broader initial browser run found only the comparison assertion still addressing its former separate section (198 passed, 3 failed, 4 dependency-blocked). The assertion now checks the shared grid and its targeted workflow passes at all three viewports. Test infrastructure now accepts validated ALPHA_PLAYWRIGHT_PORT, retains refusal to reuse servers, and passes that port to the real backend. Final checks use port 8803, isolating them from concurrent branch tests.

Aggregate backend attempt: 4,738 passed, 2 failed (93.12% coverage). The added manual paragraph exceeded the 6,000-byte core-doc limit and was replaced with a short guide link. The existing delayed ML cancellation test again failed under concurrent full suites; no production cancellation deadline or test expectation was weakened. This remains a load-sensitive validation limitation, not a claimed fix in this UI pass. Final targeted verification and frontend logs: `/tmp/alpha-polish-targeted.log`, `/tmp/alpha-polish-isolated-frontend.log`. Full-repository acceptance is not claimed.
