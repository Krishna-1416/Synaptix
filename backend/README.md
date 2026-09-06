# backend/ — Backend Engineer

**Stack:** FastAPI (Python 3.10+), Supabase PostgreSQL + Auth, ReportLab, hosted on Render.

## Owns
- `api/` — REST endpoints (`/api/inspect`, `/api/inspections`, `/api/inspections/{id}`, `/api/report/{id}`)
- `services/` — orchestration: calls ocr/, cv/, backend/rules/ in sequence and assembles the shared schema object
- `models/` — Pydantic models + Supabase/Postgres table schemas (mirrors `shared/schemas/inspection_schema.json`)
- Auth (Supabase Auth / RBAC for inspector roles)
- PDF report generation (ReportLab)

## Rule
This is the **only** module the frontend talks to, and the **only** module
that talks to the database and storage. OCR/CV/rules code is imported as
internal Python modules — it never runs as separate services.

## Suggested structure
```
backend/
├── api/            # FastAPI routers
├── services/        # orchestration/business logic
├── models/           # Pydantic + DB models
├── rules/             # Legal & Rules Engineer's folder — see rules/README.md
├── main.py
└── requirements.txt
```

## Day 1 goal
`POST /api/inspect` accepts an image and returns a stub JSON matching
`shared/schemas/inspection_schema.json` (hardcoded values are fine) — this
unblocks the frontend team immediately while OCR/CV/rules are still WIP.
