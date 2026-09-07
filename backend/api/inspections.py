from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status
from backend.models.inspection import InspectionResult, InspectionListResponse
from backend.services.inspection_service import InspectionService

router = APIRouter(prefix="/inspections", tags=["Inspections Repository"])


@router.get(
    "",
    response_model=InspectionListResponse,
    summary="List past inspection records with filters and pagination"
)
async def list_inspections(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by compliance status: PASS, FAIL, REVIEW"),
    search: Optional[str] = Query(None, description="Search term for product name or inspection ID")
):
    try:
        data = await InspectionService.list_inspections(page=page, limit=limit, status=status, search=search)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query inspections: {str(e)}"
        )


@router.get(
    "/{inspection_id}",
    response_model=InspectionResult,
    summary="Retrieve details of a specific inspection record"
)
async def get_inspection_details(inspection_id: str):
    inspection = await InspectionService.get_inspection(inspection_id)
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )
    return inspection


@router.delete(
    "/{inspection_id}",
    summary="Delete an inspection record"
)
async def delete_inspection(inspection_id: str):
    deleted = await InspectionService.delete_inspection(inspection_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found or could not be deleted."
        )
    return {"status": "success", "message": f"Inspection {inspection_id} removed successfully"}
