# 7-Day Execution Roadmap

| Day | Primary Work | Integration Milestone |
|---|---|---|
| 1 | Monorepo setup: React/Vite/Tailwind, FastAPI, Supabase, shared JSON schema, Git workflow | Frontend ↔ FastAPI basic connection works |
| 2 | OpenCV preprocessing + PaddleOCR; verify on 10 sample FMCG packages | Frontend upload → FastAPI → OCR → JSON → Frontend |
| 3 | Rule engine + JSON config for MRP/Net Wt/other fields | OCR fields → Rule Engine → compliance result |
| 4 | CV checks: bounding-box overlays, readability, calibrated font-height/placement | CV output joins the common inspection JSON |
| 5 | Supabase Storage + PostgreSQL persistence, auth, inspection history | Full inspection saved and retrievable |
| 6 | Frontend dashboard, report generation, full integration | End-to-end scan → analysis → result → report |
| 7 | Deploy (Vercel + Render), test, rehearse | Stable judge-ready demo — no major new features |

## Non-negotiables
- Vertical slice working by Day 2 (even with stubbed OCR/rules).
- Integrate every day — don't let any module go dark for 2+ days.
- Day 7 is deployment + rehearsal only, not feature work.
