# Synaptix Project Documentation

This directory contains project documentation, architectural specifications, and the execution roadmap for **Synaptix** (Smart India Hackathon 2025/2026 Problem Statement `SIH26034`).

---

## 7-Day Execution Roadmap

| Day | Primary Work | Integration Milestone |
|---|---|---|
| **1** | Monorepo setup: React/Vite/Tailwind, FastAPI, Supabase, shared JSON schema, Git workflow | Frontend ↔ FastAPI basic connection works |
| **2** | OpenCV preprocessing + PaddleOCR; verify on sample FMCG packages | Frontend upload → FastAPI → OCR → JSON → Frontend |
| **3** | Rule engine + JSON config for MRP/Net Wt/other fields | OCR fields → Rule Engine → compliance result |
| **4** | CV checks: bounding-box overlays, readability, calibrated font-height/placement | CV output joins the common inspection JSON |
| **5** | Supabase Storage + PostgreSQL persistence, auth, inspection history | Full inspection saved and retrievable |
| **6** | Frontend dashboard, report generation, full integration | End-to-end scan → analysis → result → report |
| **7** | Deploy (Vercel + Render), test, rehearse | Stable judge-ready demo — no major new features |

### Non-negotiables
- Vertical slice working by Day 2 (even with stubbed OCR/rules).
- Integrate every day — don't let any module go dark for 2+ days.
- Day 7 is deployment + rehearsal only, not feature work.

---

## System Architecture Overview

- **Frontend (Edge PWA):** React 18, Vite, Tailwind CSS, Service Workers (offline field raid capture).
- **Computer Vision & Preprocessing:** OpenCV 4.x (anti-glare bilateral filtering, perspective deskewing).
- **OCR Engine:** PaddleOCR PP-OCRv4 (DBNet++ text detector + SVTR-LCNet recognizer) with EasyOCR failover.
- **Rule Engine:** Deterministic Rule 6 & Rule 7 statutory compliance auditing under Legal Metrology Rules, 2011.
- **Backend Hub:** FastAPI ASGI async gateway, Supabase PostgreSQL, ReportLab PDF generator.
