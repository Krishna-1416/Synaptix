from fastapi import APIRouter, HTTPException, status
from backend.services.inspection_service import InspectionService

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])


@router.get(
    "/stats",
    summary="Get aggregated compliance statistics and metrics for enforcement officers",
    description="Returns total inspection counts, compliance rate, violations breakdown, and recent alerts."
)
async def get_dashboard_statistics():
    try:
        metrics = await InspectionService.get_dashboard_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate dashboard statistics: {str(e)}"
        )
