from fastapi import APIRouter, HTTPException, status, Depends
from backend.services.inspection_service import InspectionService
from backend.models.auth import UserProfile
from backend.api.auth import require_auth

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])


@router.get(
    "/stats",
    summary="Get aggregated compliance statistics and metrics for enforcement officers",
    description="Returns total inspection counts, compliance rate, violations breakdown, and recent alerts."
)
async def get_dashboard_statistics(user: UserProfile = Depends(require_auth)):
    try:
        is_admin = user.role in {"admin", "administrator"}
        metrics = await InspectionService.get_dashboard_metrics(
            requester_id=user.id,
            is_admin=is_admin
        )
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate dashboard statistics: {str(e)}"
        )

