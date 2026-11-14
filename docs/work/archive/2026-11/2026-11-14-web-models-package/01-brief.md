# The web API models as a package

## What the owner wants

From the clean-up milestone "agent-sized code": "apps/alpha-web/src/alpha_web/api/models.py (3,407
lines) split into a package of coherent modules behind unchanged import names; the generated
OpenAPI document must be byte-identical before and after (there is a freshness check; prove it)."

In one sentence: the same models, the same API contract, in files an agent can hold.

## What done looks like

- `alpha_web.api.models` is a package of area modules, none near the 1,500-line limit; every old
  import still works.
- The OpenAPI document generated after the change is byte-identical to the one before, shown by
  the freshness check and a hash.

## How they will see it

Nothing visible: internal. The Workstation and its API behave exactly as before.

## Out of scope

The frontend, `openapi.json`, `generated.ts`, any model's fields or validation.
