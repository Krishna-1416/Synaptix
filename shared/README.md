# shared/ — Everyone (coordinate before changing)

## Owns
- `schemas/inspection_schema.json` — the one integration contract every
  module reads/writes. OCR writes `fields`, CV writes `visual_checks`,
  the rule engine writes `compliance`, the backend persists the whole
  object, the frontend reads it.

## Rule
Changes here affect all six people. Propose changes in a PR, get a quick
thumbs-up from whoever owns the affected section, then merge — don't
push breaking changes to this folder solo.
