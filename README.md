# Synaptix — SIH26034: Automated Legal Metrology Inspection System

Automated packaging-compliance checker: scan a product label → OCR extracts
mandatory declarations → rule engine validates against the Legal Metrology
(Packaged Commodities) Rules, 2011 → compliance report + dashboard.

## Team & Folder Ownership

| Member Role | Folder Owned | Stack |
|---|---|---|
| Legal & Rules Engineer | `backend/rules/`, `shared/schemas/` | JSON Schema, FastAPI |
| OCR Engineer | `ocr/` | PaddleOCR, Tesseract/EasyOCR, OpenCV |
| Computer Vision Engineer | `cv/` | OpenCV |
| Backend Engineer | `backend/api/`, `backend/services/`, `backend/models/` | FastAPI, Supabase, ReportLab |
| Frontend & Product Engineer | `frontend/` | React, Vite, Tailwind, Vercel |

## Golden Rules (read before pushing)
1. **One repository** — everyone works in this monorepo, on their own branch, PR into `main`.
2. **One database** — Supabase PostgreSQL only. Don't spin up local/alt DBs.
3. **One object store** — Supabase Storage only.
4. **One API contract** — the schema in `shared/schemas/` is the source of truth. Propose changes via PR + team sign-off before merging, since it affects everyone downstream.
5. **Frontend isolation** — the frontend calls the FastAPI backend only. It never calls OCR/CV/DB directly.
6. **Never commit secrets** — copy `.env.example` to `.env` locally, keep `.env` out of git.

## End-to-End Flow
```
Camera/Upload → OpenCV preprocessing → PaddleOCR → Structured fields
→ CV visual checks → Legal Metrology rule validation → Compliance result
→ Evidence → PDF report → PostgreSQL history → Dashboard
```

## 7-Day Build Roadmap
See `docs/roadmap.md` for the day-by-day plan and integration milestones.

## Quick Start
1. Clone the repo, `git checkout -b <your-name>/<folder>`.
2. `cp .env.example .env` and fill in your local Supabase keys.
3. Work inside your owned folder; read `shared/schemas/inspection_schema.json` first — every module reads/writes this shape.
4. Open a PR early (Day 1–2) even with a stub, so integration starts immediately.
