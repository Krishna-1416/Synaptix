from typing import List, Optional, Any, Dict
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
    packer: Optional[str] = None                 # R6-02
    importer: Optional[str] = None               # R6-03
    country_of_origin: Optional[str] = None      # R6-04
    generic_name: Optional[str] = None           # R6-05
    net_quantity: Optional[str] = None           # R6-07
    manufacture_date: Optional[str] = None       # R6-10
    best_before: Optional[str] = None            # R6-11
    mrp: Optional[str] = None                   # R6-08
    unit_sale_price: Optional[str] = None        # R6-09
    consumer_care: Optional[str] = None          # R6-12
    is_imported: Optional[bool] = None
    is_multi_product: Optional[bool] = None
    is_gm_food: Optional[bool] = None
    is_ecommerce: Optional[bool] = None
    veg_nonveg_mark: Optional[str] = None        # R6-16


class VisualChecks(BaseModel):
    readability: Optional[str] = None
    font_height: Optional[float] = None
    placement: Optional[str] = None
    dpi: Optional[float] = None
    overlay_image: Optional[str] = None


class RuleResult(BaseModel):
    """Per-rule outcome returned to frontend for rule summary cards."""
    rule_id: str
    name: str
    status: str              # "PASS" | "FAIL" | "REVIEW" | "NOT_APPLICABLE"
    reason: Optional[str] = None
    legal_ref: Optional[str] = None


class ComplianceResult(BaseModel):
    status: ComplianceStatus = ComplianceStatus.REVIEW
    violations: List[str] = Field(default_factory=list)
    # Extended fields the frontend reads via inspectionScore() and inspectionConfidence()
    score: Optional[float] = None            # 0.0–1.0  (or 0–100)
    confidence: Optional[float] = None      # 0.0–1.0  (or 0–100)
    rule_results: List[RuleResult] = Field(default_factory=list)


class InspectionResult(BaseModel):
    """
    Shared contract: Matches shared/schemas/inspection_schema.json exactly.
    Extended with rule_results, score, confidence for frontend charts.
    """
    inspection_id: str
    image_id: Optional[str] = None
    image_url: Optional[str] = None
    annotated_image_url: Optional[str] = None
    product: ProductInfo = Field(default_factory=ProductInfo)
    ocr_raw: Optional[OCRRaw] = None
    fields: MandatoryFields = Field(default_factory=MandatoryFields)
    visual_checks: Optional[VisualChecks] = None
    compliance: ComplianceResult = Field(default_factory=ComplianceResult)
    created_at: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: Optional[str] = None


class InspectionUpdateRequest(BaseModel):
    """
    Inspector Override payload: allows updating extracted fields and/or product details.
    """
    fields: Optional[MandatoryFields] = None
    product: Optional[ProductInfo] = None


class InspectionListResponse(BaseModel):
    total: int
    page: int
    limit: int
    data: List[InspectionResult]
