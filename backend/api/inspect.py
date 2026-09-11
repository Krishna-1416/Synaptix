from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from backend.models.inspection import InspectionResult
from backend.models.auth import UserProfile
from backend.services.inspection_service import InspectionService
from backend.api.auth import require_auth

router = APIRouter(prefix="", tags=["Inspection"])


@router.post(
    "/inspect",
    response_model=InspectionResult,
    summary="Upload package label image and perform full Legal Metrology compliance inspection",
    description=(
        "Processes the image through CV preprocessing, OCR extraction, "
        "R6-01–R6-17 rule validation, Rules 7-12 visual checks, "
        "and persists the result to Supabase. "
        "Returns compliance.rule_results[], compliance.score (0–1) and "
        "compliance.confidence (0–1) for frontend charts."
    ),
)
async def inspect_package_label(
    file: UploadFile = File(..., description="Product label photograph or package scan (JPG/PNG/WEBP)"),
    product_name: Optional[str] = Form(None, description="Optional product name hint"),
    category: Optional[str] = Form("Packaged Commodity", description="Product category"),
    user: UserProfile = Depends(require_auth),
):
    valid_types = ["image/jpeg", "image/png", "image/webp", "image/jpg", "application/octet-stream"]
    if file.content_type and file.content_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.content_type}'. Please upload an image (JPEG/PNG/WEBP).",
        )

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        result = await InspectionService.process_image_inspection(
            file_bytes=content,
            filename=file.filename or "upload.jpg",
            product_name=product_name,
            product_category=category,
            inspector_id=user.id,
        )
        return result

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inspection pipeline error: {str(e)}",
        )
