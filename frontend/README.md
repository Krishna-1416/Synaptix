# Synaptix Inspector Console

React + Vite frontend for the Synaptix Legal Metrology inspection system.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

The Vite development server proxies `/api` to `http://localhost:8000`. Start the FastAPI app from the repository root in another terminal:

```powershell
uvicorn backend.main:app --reload --port 8000
```

For a deployed backend, set the Vercel project environment variable `VITE_API_BASE_URL` to the API origin, for example `https://api.example.com` (no trailing slash), then redeploy the frontend. The backend deployment must define `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `FRONTEND_URL`, and `CORS_ORIGINS`.

## Backend connection points

- `POST /api/auth/login` JSON: `email`, `password`
- `POST /api/auth/signup` JSON: `email`, `password`, `full_name`, `role`
- `POST /api/inspect` multipart form: `file`, optional `product_name`, optional `category`
- `GET /api/dashboard/stats`
- `GET /api/inspections?page=1&limit=10&status=PASS&search=rice`
- `GET /api/inspections/{inspection_id}`
- `GET /api/report/{inspection_id}`

When the backend is unreachable, the UI shows a clearly labelled sample-data mode so the screens can be developed before the API is ready.

## Field capabilities

- **Live camera capture:** the New inspection screen uses `getUserMedia` with the rear-facing camera preference, a label alignment viewfinder, and a capture button. The captured frame is converted to a JPEG `File` and sent through the same `/api/inspect` multipart request as a picked image.
- **Validation visualizer:** inspection details render `ocr_raw.texts[].bbox` over `image_url` when the backend returns both. The overlay supports normalized coordinates and pixel coordinates, including the schema's `[x, y, width, height]` form, and lists detected or missing declarations below the image.
- **Offline PWA shell:** `manifest.webmanifest`, `sw.js`, and the registration hook make the frontend installable and cache the app shell for field use. API requests still require a reachable backend to run new inspections.
