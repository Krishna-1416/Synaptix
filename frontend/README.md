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

For a deployed backend, copy `.env.example` to `.env` and set `VITE_API_BASE_URL` to the API origin, for example `https://api.example.com`.

## Backend connection points

- `POST /api/auth/login` JSON: `email`, `password`
- `POST /api/auth/signup` JSON: `email`, `password`, `full_name`, `role`
- `POST /api/inspect` multipart form: `file`, optional `product_name`, optional `category`
- `GET /api/dashboard/stats`
- `GET /api/inspections?page=1&limit=10&status=PASS&search=rice`
- `GET /api/inspections/{inspection_id}`
- `GET /api/report/{inspection_id}`

When the backend is unreachable, the UI shows a clearly labelled sample-data mode so the screens can be developed before the API is ready.
