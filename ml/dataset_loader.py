"""
Dataset manifest ingestion, audit, and ground-truth declaration loader.

Strictly distinguishes between:
A. Product metadata (name, category, barcode, dimensions)
B. Available ground-truth declarations (manufacturer, net quantity, etc.)
C. Raw OCR text (currently absent from manifest)
D. Bounding-box annotations (currently absent from manifest)

Rule: Missing declarations must remain None/null. Never invent or hallucinate labels.
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ml.schemas import STANDARD_FIELD_NAMES


# Regular expressions for safe, conservative extraction of ground truth from visible_declarations
RE_EXPLICIT_QTY = re.compile(
    r"(?:Net\s*(?:Weight|Qty|Quantity)?\s*[:e\s]+)?(\d+(?:\.\d+)?\s*(?:g|gm|kg|ml|l|ltr|pcs|units?))\b",
    re.IGNORECASE,
)
RE_COMPANY_INDICATORS = re.compile(
    r"\b(?:Ltd|Limited|Pvt\.?\s*Ltd|Private\s*Limited|Industries|Enterprises|Foods|Holdings|Products|GCMMF)\b",
    re.IGNORECASE,
)


@dataclass
class SourceInfo:
    """Provenance and file locations for a sample."""
    file: str
    back_file_alias: Optional[str] = None
    source_url: Optional[str] = None
    original_path: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "back_file_alias": self.back_file_alias,
            "source_url": self.source_url,
            "original_path": self.original_path,
        }


@dataclass
class GroundTruthDeclarations:
    """
    Verified Rule 6 statutory ground-truth values.
    Unannotated or missing fields are strictly None.
    """
    manufacturer: Optional[str] = None
    country_of_origin: Optional[str] = None
    generic_name: Optional[str] = None
    net_quantity: Optional[str] = None
    manufacture_date: Optional[str] = None
    mrp: Optional[str] = None
    unit_sale_price: Optional[str] = None
    consumer_care: Optional[str] = None

    def to_dict(self) -> dict[str, Optional[str]]:
        return {
            "manufacturer": self.manufacturer,
            "country_of_origin": self.country_of_origin,
            "generic_name": self.generic_name,
            "net_quantity": self.net_quantity,
            "manufacture_date": self.manufacture_date,
            "mrp": self.mrp,
            "unit_sale_price": self.unit_sale_price,
            "consumer_care": self.consumer_care,
        }

    def get_annotated_fields(self) -> dict[str, str]:
        """Return only fields that have non-null ground-truth values."""
        return {k: v for k, v in self.to_dict().items() if v is not None}


@dataclass
class DatasetRecord:
    """
    Individual sample record from the manifest.

    Clearly delineates:
    - Product Metadata
    - Source/Image Info
    - Available Ground-Truth Declarations
    - OCR Text (null in manifest)
    - Bounding Box Annotations (empty in manifest)
    """
    index: int
    product_name: str
    category: str
    barcode: Optional[str] = None
    dimensions: Optional[str] = None
    size_kb: Optional[float] = None
    source_info: SourceInfo = field(default_factory=lambda: SourceInfo(file=""))
    ground_truth: GroundTruthDeclarations = field(default_factory=GroundTruthDeclarations)
    visible_declarations_raw: list[str] = field(default_factory=list)

    # ML annotations (explicitly separated to prevent false assumptions)
    ocr_text: Optional[str] = None
    bbox_annotations: list[dict[str, Any]] = field(default_factory=list)

    # Direct property accessors required by specification
    @property
    def manufacturer(self) -> Optional[str]:
        return self.ground_truth.manufacturer

    @property
    def country_of_origin(self) -> Optional[str]:
        return self.ground_truth.country_of_origin

    @property
    def generic_name(self) -> Optional[str]:
        return self.ground_truth.generic_name

    @property
    def net_quantity(self) -> Optional[str]:
        return self.ground_truth.net_quantity

    @property
    def manufacture_date(self) -> Optional[str]:
        return self.ground_truth.manufacture_date

    @property
    def mrp(self) -> Optional[str]:
        return self.ground_truth.mrp

    @property
    def unit_sale_price(self) -> Optional[str]:
        return self.ground_truth.unit_sale_price

    @property
    def consumer_care(self) -> Optional[str]:
        return self.ground_truth.consumer_care

    def has_ground_truth(self, field_name: str) -> bool:
        """Check if a specific field has verified ground truth."""
        return getattr(self.ground_truth, field_name, None) is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "product_name": self.product_name,
            "category": self.category,
            "barcode": self.barcode,
            "dimensions": self.dimensions,
            "size_kb": self.size_kb,
            "source_info": self.source_info.to_dict(),
            "ground_truth": self.ground_truth.to_dict(),
            "visible_declarations_raw": list(self.visible_declarations_raw),
            "ocr_text": self.ocr_text,
            "bbox_annotations": list(self.bbox_annotations),
        }


@dataclass
class DatasetAuditSummary:
    """Quantitative audit of dataset composition, completeness, and missing annotations."""
    total_records: int
    field_support_counts: dict[str, int]
    records_with_any_ground_truth: int
    records_with_complete_declarations: int
    has_ocr_transcriptions: bool
    has_bounding_boxes: bool
    is_complete_training_set: bool
    missing_annotations: dict[str, int]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "field_support_counts": dict(self.field_support_counts),
            "records_with_any_ground_truth": self.records_with_any_ground_truth,
            "records_with_complete_declarations": self.records_with_complete_declarations,
            "has_ocr_transcriptions": self.has_ocr_transcriptions,
            "has_bounding_boxes": self.has_bounding_boxes,
            "is_complete_training_set": self.is_complete_training_set,
            "missing_annotations": dict(self.missing_annotations),
            "notes": list(self.notes),
        }


def _parse_ground_truth(visible_declarations: list[str], product_name: str) -> GroundTruthDeclarations:
    """
    Carefully parses available ground-truth declarations from raw strings.
    Adheres strictly to the principle of never inventing or guessing values.
    """
    mfg: Optional[str] = None
    net_qty: Optional[str] = None
    generic_name: Optional[str] = None

    for decl in visible_declarations:
        decl_clean = decl.strip()
        decl_lower = decl_clean.lower()

        # 1. Net Quantity: Only accept if a numerical quantity and unit are explicitly present
        # Ignore mere labels like "Net Quantity" or "Net Weight / Quantity"
        if not net_qty:
            qty_match = RE_EXPLICIT_QTY.search(decl_clean)
            if qty_match:
                net_qty = qty_match.group(1).strip()

        # 2. Manufacturer: Look for specific company names and entity indicators
        if not mfg:
            if RE_COMPANY_INDICATORS.search(decl_clean):
                # Filter out lines that are just regulatory or nutritional references
                if not any(k in decl_lower for k in ("fssai", "nutrition", "ingredient", "table", "profile")):
                    mfg = decl_clean

        # 3. Generic Name: Explicit statutory commodity descriptions
        if not generic_name:
            if any(k in decl_lower for k in (
                "blended edible vegetable oil",
                "toned milk",
                "pasteurized butter",
                "noodles",
                "biscuits",
                "potato chips",
                "chocolate",
            )):
                generic_name = decl_clean

    # Fallback for generic name if present in product name
    if not generic_name:
        for common in ("Noodles", "Butter", "Biscuits", "Chips", "Oil", "Milk"):
            if common.lower() in product_name.lower():
                generic_name = common
                break

    # Note: MRP, manufacture_date, country_of_origin, and consumer_care contact details
    # are completely absent from the manifest and are strictly left as None.
    return GroundTruthDeclarations(
        manufacturer=mfg,
        country_of_origin=None,
        generic_name=generic_name,
        net_quantity=net_qty,
        manufacture_date=None,
        mrp=None,
        unit_sale_price=None,
        consumer_care=None,
    )


def load_samples_manifest(manifest_path: Optional[Union[str, Path]] = None) -> list[DatasetRecord]:
    """
    Loads and parses sample_data/real_samples/samples_manifest.json.

    Args:
        manifest_path: Optional Path or string path to the manifest. If None, resolves
                       relative to the project root.

    Returns:
        list[DatasetRecord]: List of parsed dataset records.
    """
    if manifest_path is None:
        # Resolve path relative to this file: ml/ -> root -> sample_data/real_samples/samples_manifest.json
        project_root = Path(__file__).resolve().parent.parent
        manifest_path = project_root / "sample_data" / "real_samples" / "samples_manifest.json"
    else:
        manifest_path = Path(manifest_path)

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found at: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    if not isinstance(raw_items, list):
        raise ValueError(f"Expected list of records in manifest, got {type(raw_items).__name__}")

    records: list[DatasetRecord] = []
    for item in raw_items:
        visible_decls = item.get("visible_declarations", [])
        product_name = str(item.get("product_name", "Unknown Product"))
        panel_cat = str(item.get("panel_category", "Packaged Commodity"))

        source_info = SourceInfo(
            file=str(item.get("file", "")),
            back_file_alias=item.get("back_file_alias"),
            source_url=item.get("source_url"),
            original_path=item.get("path"),
        )

        ground_truth = _parse_ground_truth(visible_decls, product_name)

        record = DatasetRecord(
            index=int(item.get("index", len(records) + 1)),
            product_name=product_name,
            category=panel_cat,
            barcode=item.get("barcode"),
            dimensions=item.get("dimensions"),
            size_kb=float(item.get("size_kb")) if item.get("size_kb") is not None else None,
            source_info=source_info,
            ground_truth=ground_truth,
            visible_declarations_raw=visible_decls,
            ocr_text=None,
            bbox_annotations=[],
        )
        records.append(record)

    return records


def audit_dataset(records: list[DatasetRecord]) -> DatasetAuditSummary:
    """
    Performs a thorough audit of available records and reports ground-truth coverage.
    """
    total = len(records)
    support_counts: dict[str, int] = {fn: 0 for fn in STANDARD_FIELD_NAMES}
    records_with_any = 0
    records_with_complete = 0

    for rec in records:
        has_any = False
        all_present = True
        for fn in STANDARD_FIELD_NAMES:
            val = getattr(rec.ground_truth, fn, None)
            if val is not None:
                support_counts[fn] += 1
                has_any = True
            else:
                all_present = False

        if has_any:
            records_with_any += 1
        if all_present:
            records_with_complete += 1

    missing_counts = {fn: total - support_counts[fn] for fn in STANDARD_FIELD_NAMES}

    notes = [
        "Manifest serves as a sample inventory, not an annotated ML training dataset.",
        "Bounding-box coordinates for text tokens are 100% missing.",
        "Raw OCR transcribed text is 100% missing from manifest records.",
        f"MRP ground truth is present in 0/{total} records.",
        f"Manufacture Date ground truth is present in 0/{total} records.",
        f"Country of Origin ground truth is present in 0/{total} records.",
        f"Unit Sale Price ground truth is present in 0/{total} records.",
        f"Consumer Care contact details are present in 0/{total} records.",
    ]

    return DatasetAuditSummary(
        total_records=total,
        field_support_counts=support_counts,
        records_with_any_ground_truth=records_with_any,
        records_with_complete_declarations=records_with_complete,
        has_ocr_transcriptions=False,
        has_bounding_boxes=False,
        is_complete_training_set=False,
        missing_annotations=missing_counts,
        notes=notes,
    )
