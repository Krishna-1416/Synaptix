# frontend/ — Frontend & Product Engineer

**Stack:** React + Vite (PWA), Tailwind CSS, deployed on Vercel.

## Owns
- Camera capture / image upload screen (mobile-responsive, PWA-installable)
- Validation visualizer (bounding boxes over detected fields, pass/fail highlight)
- Inspector dashboard (past inspections, filters, search)
- History view + PDF/report download

## Rule
Talks **only** to the FastAPI backend (`VITE_API_BASE_URL`). Never calls
OCR, CV, or Supabase directly from the client.

## Suggested structure
```
frontend/
├── src/
│   ├── pages/        # Scan, Dashboard, History, InspectionDetail
│   ├── components/   # UploadCard, BBoxOverlay, ComplianceBadge, ReportButton
│   ├── api/          # thin fetch wrapper around backend endpoints
│   └── App.jsx
├── public/
├── index.html
├── vite.config.js
└── package.json
```

## Day 1 goal
Basic screen that POSTs an image to `/api/inspect` and renders the raw JSON
response — proves the frontend↔backend wire is live before anything else
is built.
