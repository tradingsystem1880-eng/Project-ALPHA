# Vendored: Kronos

- Upstream: https://github.com/shiyu-coder/Kronos (`master`), MIT License (see `kronos/LICENSE`).
- Files: `kronos/module.py`, `kronos/kronos.py` — upstream `model/module.py`, `model/kronos.py`.
- Patches (the ONLY intentional deviations from upstream):
  1. `kronos.py`: upstream's `sys.path.append("../")` + `from model.module import *` replaced by
     `from .module import *` (relative import; `import sys` dropped as now unused).
  2. Whitespace normalization: upstream `module.py` is CRLF and both files carry some trailing
     whitespace / trailing blank lines; the vendored copies are LF with trailing whitespace
     stripped. No content differences.
- Retrieval provenance: fetched 2026-07-11 from `raw.githubusercontent.com` via a text pipeline
  (that build environment blocked direct github access), reassembled from verbatim chunks, then
  verified by `py_compile` + the tiny-random-weights forward-pass test in
  `tests/unit/test_vendored_kronos.py`.
- Upstream commit sha: `67b630e67f6a18c9e9be918d9b4337c960db1e9a` (master HEAD, verified
  2026-07-14 by cloning github.com/shiyu-coder/Kronos and diffing `model/module.py` +
  `model/kronos.py` against the vendored copies: identical modulo patch 1 and the whitespace
  normalization in patch 2).
- Dependency note: upstream `requirements.txt` pins `einops==0.8.1`, `huggingface_hub==0.33.1`;
  `alpha-forecast` declares `>=` floors instead so the uv workspace resolver stays free.
- Do not edit these files except to sync with upstream; they are excluded from ruff and mypy.
