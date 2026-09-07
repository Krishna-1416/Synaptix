from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from backend.models.inspection import InspectionResult
from backend.services.inspection_service import InspectionService

router = APIRouter(prefix="", tags=["Inspection"])


@router.post(
    "/inspect",
    response_model=InspectionResult,
    summary="Upload package label image and perform full Legal Metrology compliance inspection",
    description="Processes the image through CV preprocessing, OCR extraction, Rule 6 validation, and persists the result."
)
async def inspect_package_label(
    file: UploadFile = File(..., description="Product label photograph or package scan (JPG/PNG/WEBP)"),
    product_name: Optional[str] = Form(None, description="Optional product name hint"),
    category: Optional[str] = Form("Packaged Commodity", description="Product category (food, beverage, cosmetics, FMCG)")
):
    # Verify content type
    valid_types = ["image/jpeg", "image/png", "image/webp", "image/jpg", "application/octet-stream"]
    if file.content_type and file.content_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.content_type}'. Please upload an image file (JPEG/PNG/WEBP)."
        )

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        result = await InspectionService.process_image_inspection(
            file_bytes=content,
            filename=file.filename or "upload.jpg",
            product_name=product_name,
            product_category=category
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inspection pipeline encountered an error: {str(e)}"
        )
