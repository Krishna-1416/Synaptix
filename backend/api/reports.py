from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from backend.services.inspection_service import InspectionService
from backend.services.report_service import generate_compliance_pdf

router = APIRouter(prefix="/report", tags=["Reports"])


@router.get(
    "/{inspection_id}",
    summary="Download Legal Metrology Compliance Inspection Certificate (PDF)",
    description="Generates an official PDF certificate with declaration audits, statutory violations, and verification signature blocks."
)
async def download_inspection_report(inspection_id: str):
    inspection = await InspectionService.get_inspection(inspection_id)
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found."
        )

    try:
        pdf_bytes = generate_compliance_pdf(inspection)
        filename = f"Compliance_Certificate_{inspection_id}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed generating PDF compliance certificate: {str(e)}"
        )
