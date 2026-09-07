import os
import uuid
import logging
from pathlib import Path
from typing import Tuple, Optional
from backend.services.supabase_client import get_supabase_admin_client
from backend.config import settings

logger = logging.getLogger("synaptix.storage")

# Local fallback storage directory if Supabase bucket isn't reachable
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def upload_label_image(file_bytes: bytes, original_filename: str) -> Tuple[str, str]:
    """
    Uploads label image to Supabase Storage bucket 'label-images'.
    Falls back to local file storage if Supabase credentials are not provided or error occurs.
    
    Returns:
        Tuple[image_id, public_image_url]
    """
    ext = Path(original_filename).suffix or ".jpg"
    image_id = f"IMG-{uuid.uuid4().hex[:8].upper()}"
    filename = f"{image_id}{ext}"
    
    admin_client = get_supabase_admin_client()
    
    if admin_client:
        try:
            # Upload to Supabase Storage
            bucket = settings.SUPABASE_BUCKET_NAME
            # Path inside bucket
            storage_path = f"labels/{filename}"
            
            # Content-type detection
            content_type = "image/jpeg"
            if ext.lower() in [".png"]:
                content_type = "image/png"
            elif ext.lower() in [".webp"]:
                content_type = "image/webp"

            res = admin_client.storage.from_(bucket).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            
            public_url = admin_client.storage.from_(bucket).get_public_url(storage_path)
            logger.info(f"Uploaded {filename} to Supabase bucket '{bucket}'. URL: {public_url}")
            return image_id, public_url
        except Exception as e:
            logger.warning(f"Supabase storage upload failed ({e}). Falling back to local storage.")

    # Local fallback
    local_path = UPLOAD_DIR / filename
    with open(local_path, "wb") as f:
        f.write(file_bytes)
        
    local_url = f"/api/uploads/{filename}"
    logger.info(f"Saved image locally at {local_path}")
    return image_id, local_url
