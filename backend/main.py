import sys
from pathlib import Path

# Ensure project root is in sys.path so 'backend', 'ocr', 'cv', and 'shared' are importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse

from backend.config import settings
from backend.services.supabase_client import get_supabase_client, get_supabase_admin_client
from backend.api.inspect import router as inspect_router
from backend.api.inspections import router as inspections_router
from backend.api.reports import router as reports_router
from backend.api.dashboard import router as dashboard_router
from backend.api.auth import router as auth_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Automated packaging-compliance checker under Legal Metrology (Packaged Commodities) Rules, 2011. "
        "Scans product labels, detects mandatory declarations (Rule 6), performs visual readability checks (Rule 7), "
        "identifies violations, generates official PDF certificates, and powers the inspector dashboard."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else [],
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local uploads directory for image fallback serving
upload_dir = Path(__file__).resolve().parent / "uploads"
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

# Register API Routers under /api
app.include_router(inspect_router, prefix=settings.API_V1_STR)
app.include_router(inspections_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root access directly to interactive documentation."""
    return RedirectResponse(url="/docs")


@app.get("/api/health", tags=["System"])
def health_check():
    """System health check endpoint verifying database connectivity."""
    db_status = "connected" if get_supabase_admin_client() is not None else "mock_mode"
    return {
        "status": "healthy",
        "system": "Synaptix SIH26034",
        "database": db_status,
        "docs": "/docs"
    }


@app.get("/health", tags=["System"])
def public_health_check():
    """Deployment health endpoint for Render and external uptime checks."""
    return health_check()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "path": request.url.path
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
        app_dir=str(PROJECT_ROOT)
    )
