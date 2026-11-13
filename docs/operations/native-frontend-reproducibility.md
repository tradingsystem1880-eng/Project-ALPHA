# Native frontend build reproducibility

Vite preserves symlink paths for dependency resolution (`resolve.preserveSymlinks=true`).
This keeps the shared installed `node_modules` dependency identities beneath each project
root, rather than resolving them into another checkout while application IDs remain local.
Keep one dependency topology and the existing package-lock; do not mix linked alternate
React installations. This setting changes module identity and requires fresh generated SPA.

Bounded synthetic engineering verification: identical 248 non-test production frontend inputs
and the same existing Vite8.1.5/Rolldown1.1.5 dependencies emitted52 byte-identical assets in
fresh top-level and nested locations, with a matching repeat. The existing trailing-whitespace
normalizer was applied unchanged. A browser mounted the new native-result view without page
errors or external requests and handled an unavailable synthetic backend. Source typecheck
passed on the production-only copy. Test sources were deliberately excluded: this is not
full frontend/private qualification, all-app runtime proof or universal cross-platform
reproducibility. Native workers, owner accounting and profile bytes are unchanged.

The previous default realpath configuration produced different declaration/import ordering
at the two locations. Preserving symlink IDs removes the observed variation in this bounded
case; the internal Rolldown ordering mechanism is not proven. No arbitrary textual rewriting
or substantive output normalization is used. Retain the previous candidate and artifacts;
integration must regenerate the SPA from the final assembled source. No inference, provider
or execution authority follows from these build checks.
