# backend/rules/ — Legal & Rules Engineer

**Stack:** JSON Schema, Google Sheets (for drafting), FastAPI (for wiring in).

## Owns
- Encoding Legal Metrology (Packaged Commodities) Rules, 2011 — Rule 6 —
  as structured, machine-readable checks
- Regex/format parsers for MRP, Net Quantity, dates
- The compliance decision logic: `fields` (from OCR) → `compliance.status` + `compliance.violations`

## Mandatory fields to encode (Rule 6)
- Manufacturer/Packer name & address
- Country of Origin
- Common/generic name of the commodity
- Net Quantity
- Month & Year of Manufacture
- MRP (inclusive of all taxes)
- Consumer Care details (name, address, phone/email)

## Suggested files
```
rules/
├── declarations.json     # the rule catalogue: field name, required?, regex/format, severity
├── engine.py              # loads declarations.json, evaluates `fields` dict, returns status+violations
└── tests/
    └── test_engine.py     # sample compliant/non-compliant field sets
```

## Day 1–3 goal
`declarations.json` finalized by Day 2 (unblocks OCR normalization target
fields) and `engine.py` returning PASS/FAIL/REVIEW by Day 3.
