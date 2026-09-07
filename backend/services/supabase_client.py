import logging
from typing import Optional
from supabase import create_client, Client
from backend.config import settings

logger = logging.getLogger("synaptix.supabase")

_supabase_client: Optional[Client] = None
_supabase_admin_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Returns standard Supabase client with anon key for user/read operations.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        logger.warning(
            "Supabase URL or ANON Key is missing. Supabase client will run in mock/unconnected mode."
        )
        return None

    try:
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None


def get_supabase_admin_client() -> Optional[Client]:
    """
    Returns Supabase client with service_role key for admin/backend bypass operations (storage, schema ops).
    """
    global _supabase_admin_client
    if _supabase_admin_client is not None:
        return _supabase_admin_client

    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    if not settings.SUPABASE_URL or not key:
        logger.warning(
            "Supabase URL or SERVICE_ROLE Key is missing. Running in mock/unconnected mode."
        )
        return None

    try:
        _supabase_admin_client = create_client(settings.SUPABASE_URL, key)
        return _supabase_admin_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase admin client: {e}")
        return None
