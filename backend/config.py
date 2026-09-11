import os
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in current backend dir or parent root dir
base_dir = Path(__file__).resolve().parent
root_env = base_dir.parent / ".env"
local_env = base_dir / ".env"

if root_env.exists():
    load_dotenv(dotenv_path=root_env)
elif local_env.exists():
    load_dotenv(dotenv_path=local_env)
else:
    load_dotenv()

class Settings:
    PROJECT_NAME: str = "Synaptix - SIH26034 Legal Metrology Inspector"
    API_V1_STR: str = "/api"
    
    # Supabase credentials
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Storage
    SUPABASE_BUCKET_NAME: str = "label-images"
    
    # CORS
    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,*").split(",")
        if origin.strip()
    ]
    CORS_ALLOW_CREDENTIALS: bool = "*" not in CORS_ORIGINS
    
    # Backend port (Render / PaaS injects PORT, fallback to BACKEND_PORT or 8000)
    PORT: int = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "8000")))
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    CORS_ORIGIN_REGEX: str = os.getenv("CORS_ORIGIN_REGEX", r"https://[a-z0-9-]+\.vercel\.app")

settings = Settings()
