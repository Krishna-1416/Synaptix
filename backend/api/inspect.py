import asyncio
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from backend.models.inspection import InspectionResult
from backend.models.auth import UserProfile
from backend.services.inspection_service import InspectionService
from backend.api.auth import require_auth

router = APIRouter(prefix="", tags=["Inspection"])
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB production upload limit


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
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded image exceeds the 15 MB size limit.",
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


@router.post(
    "/inspect/batch",
    response_model=list[InspectionResult],
    summary="Upload multiple package label images and perform batch Legal Metrology compliance inspection",
    description=(
        "Processes multiple images in parallel through CV preprocessing, OCR extraction, "
        "rule validation, and persists results to Supabase. "
        "Accepts up to 10 images."
    ),
)
async def inspect_package_labels_batch(
    files: list[UploadFile] = File(..., description="Product label photographs or package scans (up to 10)"),
    product_name: Optional[str] = Form(None, description="Optional product name hint"),
    category: Optional[str] = Form("Packaged Commodity", description="Product category"),
    user: UserProfile = Depends(require_auth),
):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded.",
        )
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch upload exceeds the maximum limit of 10 images.",
        )

    valid_types = ["image/jpeg", "image/png", "image/webp", "image/jpg", "application/octet-stream"]

    file_data = []
    for file in files:
        if file.content_type and file.content_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type '{file.content_type}'. Please upload images (JPEG/PNG/WEBP).",
            )
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One of the uploaded files is empty.",
            )
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="One of the uploaded images exceeds the 15 MB size limit.",
            )
        file_data.append((content, file.filename or "upload.jpg"))

    try:
        results = await asyncio.gather(
            *(
                InspectionService.process_image_inspection(
                    file_bytes=content,
                    filename=filename,
                    product_name=product_name,
                    product_category=category,
                    inspector_id=user.id,
                )
                for content, filename in file_data
            )
        )
        return list(results)

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch inspection pipeline error: {str(e)}",
        )


@router.post(
    "/inspect/multi-angle",
    response_model=InspectionResult,
    summary="Upload multiple panel/angle images of a single package and perform unified Legal Metrology compliance inspection",
    description=(
        "Processes multiple images (e.g. Front PDP, Back Information panel, side panels) of a single packaged commodity, "
        "aggregates OCR tokens across all panels, merges mandatory declarations, and evaluates Legal Metrology rules."
    ),
)
async def inspect_package_multi_angle(
    files: list[UploadFile] = File(..., description="Package panel images (front, back, sides, up to 10)"),
    product_name: Optional[str] = Form(None, description="Optional product name hint"),
    category: Optional[str] = Form("Packaged Commodity", description="Product category"),
    user: UserProfile = Depends(require_auth),
):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded.",
        )
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multi-angle inspection exceeds the maximum limit of 10 images.",
        )

    valid_types = ["image/jpeg", "image/png", "image/webp", "image/jpg", "application/octet-stream"]

    file_data = []
    for file in files:
        if file.content_type and file.content_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type '{file.content_type}'. Please upload images (JPEG/PNG/WEBP).",
            )
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One of the uploaded files is empty.",
            )
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="One of the uploaded images exceeds the 15 MB size limit.",
            )
        file_data.append((content, file.filename or "panel.jpg"))

    try:
        result = await InspectionService.process_multi_angle_inspection(
            images=file_data,
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
            detail=f"Multi-angle inspection pipeline error: {str(e)}",
        )
