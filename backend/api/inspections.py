from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status, Depends
from backend.models.inspection import InspectionResult, InspectionListResponse, InspectionUpdateRequest
from backend.services.inspection_service import InspectionService
from backend.models.auth import UserProfile
from backend.api.auth import require_auth

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
    search: Optional[str] = Query(None, description="Search term for product name or inspection ID"),
<<<<<<< HEAD
=======
    inspector_id: Optional[str] = Query(None, description="Filter by inspector user ID"),
>>>>>>> 759c06701767d7ea868c6408f6599d93bc24d382
    user: UserProfile = Depends(require_auth)
):
    try:
        data = await InspectionService.list_inspections(
            page=page,
            limit=limit,
            status=status,
            search=search,
            inspector_id=inspector_id,
            requester_id=user.id,
            is_admin=user.role in {"admin", "administrator"},
        )
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
async def get_inspection_details(inspection_id: str, user: UserProfile = Depends(require_auth)):
    inspection = await InspectionService.get_inspection(
        inspection_id,
        requester_id=user.id,
        is_admin=user.role in {"admin", "administrator"},
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )
    return inspection


@router.patch(
    "/{inspection_id}",
    response_model=InspectionResult,
    summary="Update extracted fields and re-evaluate Legal Metrology compliance (Inspector Override)"
)
async def update_inspection(
    inspection_id: str,
    update_req: InspectionUpdateRequest,
    user: UserProfile = Depends(require_auth)
):
    try:
        updated = await InspectionService.update_inspection_fields(
            inspection_id=inspection_id,
            updated_fields=update_req.fields,
            updated_product=update_req.product,
            requester_id=user.id,
            inspector_id=user.id,
            is_admin=user.role in {"admin", "administrator"},
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inspection '{inspection_id}' not found."
            )
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update inspection: {str(e)}"
        )


@router.delete(
    "/{inspection_id}",
    summary="Delete an inspection record"
)
async def delete_inspection(inspection_id: str, user: UserProfile = Depends(require_auth)):
    deleted = await InspectionService.delete_inspection(
        inspection_id,
        requester_id=user.id,
        is_admin=user.role in {"admin", "administrator"},
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found or could not be deleted."
        )
    return {"status": "success", "message": f"Inspection {inspection_id} removed successfully"}
