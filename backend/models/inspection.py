from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum


class ComplianceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


class ProductInfo(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None


class OCRTextItem(BaseModel):
    text: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bbox: List[float] = Field(default_factory=list, description="[x1, y1, x2, y2] or [x, y, w, h]")


class OCRRaw(BaseModel):
    texts: List[OCRTextItem] = Field(default_factory=list)


class MandatoryFields(BaseModel):
    manufacturer: Optional[str] = None
    country_of_origin: Optional[str] = None
    net_quantity: Optional[str] = None
    manufacture_date: Optional[str] = None
    mrp: Optional[str] = None
    consumer_care: Optional[str] = None


class VisualChecks(BaseModel):
    readability: Optional[str] = None
    font_height: Optional[float] = None
    placement: Optional[str] = None
    dpi: Optional[float] = None
    overlay_image: Optional[str] = None


class ComplianceResult(BaseModel):
    status: ComplianceStatus = ComplianceStatus.REVIEW
    violations: List[str] = Field(default_factory=list)


class InspectionResult(BaseModel):
    """
    Shared contract: Matches shared/schemas/inspection_schema.json exactly.
    """
    inspection_id: str
    image_id: Optional[str] = None
    image_url: Optional[str] = None
    product: ProductInfo = Field(default_factory=ProductInfo)
    ocr_raw: Optional[OCRRaw] = None
    fields: MandatoryFields = Field(default_factory=MandatoryFields)
    visual_checks: Optional[VisualChecks] = None
    compliance: ComplianceResult = Field(default_factory=ComplianceResult)
    created_at: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InspectionListResponse(BaseModel):
    total: int
    page: int
    limit: int
    data: List[InspectionResult]
