"""
Domain models and schema definitions for the OCR module.
Matches shared/schemas/inspection_schema.json strictly.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from ocr.interfaces import OCRToken


class OCRRawPayload(BaseModel):
    """Corresponds to ocr_raw in shared/schemas/inspection_schema.json."""
    model_config = ConfigDict(frozen=True)
    texts: list[OCRToken] = Field(
        default_factory=list,
        description="List of raw detected text tokens with confidence and bounding boxes",
    )


class LegalMetrologyFields(BaseModel):
    """
    Corresponds to fields in shared/schemas/inspection_schema.json.
    Represents the 6 mandatory declarations under Rule 6 of the Legal Metrology Rules, 2011.
    """
    model_config = ConfigDict(frozen=True)
    manufacturer: Optional[str] = Field(
        default=None,
        description="Name and complete address of the manufacturer, packer, or importer.",
    )
    country_of_origin: Optional[str] = Field(
        default=None,
        description="Country of origin or assembly for imported/packaged commodities.",
    )
    generic_name: Optional[str] = Field(
        default=None,
        description="Common or generic name of the commodity contained in the package (Rule 6(1)(b)).",
    )
    net_quantity: Optional[str] = Field(
        default=None,
        description="Net quantity in standard SI metric units (weight, volume, or count/number).",
    )
    manufacture_date: Optional[str] = Field(
        default=None,
        description="Month and year of manufacture, packing, or pre-packing.",
    )
    mrp: Optional[str] = Field(
        default=None,
        description="Maximum Retail Price inclusive of all taxes.",
    )
    unit_sale_price: Optional[str] = Field(
        default=None,
        description="Unit Sale Price e.g. Rs/g, Rs/ml, Rs/kg (Rule 6(1)(m)).",
    )
    consumer_care: Optional[str] = Field(
        default=None,
        description="Contact details (phone/email/address) of the consumer care cell.",
    )


class OCRTelemetry(BaseModel):
    """Non-functional observability metrics for performance and reliability tracing."""
    model_config = ConfigDict(frozen=True)
    engine_name: str = Field(..., description="Name of the OCR engine used (e.g. PaddleOCR, EasyOCR)")
    inference_latency_ms: float = Field(..., ge=0.0, description="Latency of OCR detection & recognition in ms")
    total_tokens_detected: int = Field(..., ge=0, description="Count of raw text tokens extracted")
    mean_confidence: float = Field(..., ge=0.0, le=1.0, description="Average confidence score across tokens")


class OCRResult(BaseModel):
    """Encapsulates the complete result slice produced by the OCR subsystem."""
    model_config = ConfigDict(frozen=True)
    ocr_raw: OCRRawPayload
    fields: LegalMetrologyFields
    telemetry: Optional[OCRTelemetry] = None
