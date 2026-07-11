# Vendored: Kronos

- Upstream: https://github.com/shiyu-coder/Kronos (`master`), MIT License (see `kronos/LICENSE`).
- Files: `kronos/module.py`, `kronos/kronos.py` — upstream `model/module.py`, `model/kronos.py`.
- Patches (the ONLY intentional deviations from upstream):
  1. `kronos.py`: upstream's `sys.path.append("../")` + `from model.module import *` replaced by
     `from .module import *` (relative import; `import sys` dropped as now unused).
  2. Trailing whitespace on otherwise-blank lines may have been stripped in transit.
- Retrieval provenance: fetched 2026-07-11 from `raw.githubusercontent.com` via a text pipeline
  (this build environment blocks direct github access), reassembled from verbatim chunks, then
  verified by `py_compile` + the tiny-random-weights forward-pass test in
  `tests/unit/test_vendored_kronos.py`. Byte-exactness vs a specific upstream commit is NOT
  git-verified — when network access to github.com is available, re-diff against upstream and
  record the commit sha here.
- Upstream commit sha: UNVERIFIED (fill in when github.com is reachable).
- Dependency note: upstream `requirements.txt` pins `einops==0.8.1`, `huggingface_hub==0.33.1`;
  `alpha-forecast` declares `>=` floors instead so the uv workspace resolver stays free.
- Do not edit these files except to sync with upstream; they are excluded from ruff and mypy.
