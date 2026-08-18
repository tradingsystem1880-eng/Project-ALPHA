---
description: Quick Codex Spark pass over one file or diff - findings only, no fixes, no gate weight
argument-hint: <path/to/file.py | diff file>
---

Target: $ARGUMENTS

A fast, low-ceremony second look; findings only. Not a substitute for
/review-gate or /verify-quant.

1. If the target is a source file, write `git diff HEAD -- <file>` (or, when
   the file is unchanged, the whole file as a `+`-prefixed diff) to the
   scratchpad; if it is already a diff file, use it as is.
2. Dispatch `codex-liaison` with `review --diff <scratch file> --effort medium`.
3. Relay the findings labeled **second opinion (Codex, untrusted)**, or the
   one-line unavailability reason. Do not fix anything from this command;
   carry findings into the normal TDD loop.
