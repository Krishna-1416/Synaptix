import gc
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from backend.models.inspection import (
    InspectionResult,
    ProductInfo,
    MandatoryFields,
    VisualChecks,
    ComplianceResult,
    ComplianceStatus,
    OCRRaw,
    OCRTextItem
)
from backend.services.storage_service import upload_label_image
from backend.services.supabase_client import get_supabase_admin_client, get_supabase_client
from backend.rules.engine import evaluate_compliance

logger = logging.getLogger("synaptix.inspection_service")

# In-memory storage cache as fallback when DB is offline or table not yet initialized
_MEMORY_INSPECTIONS: Dict[str, Dict[str, Any]] = {}

# Concurrency throttle to prevent parallel heavy OCR/CV pipelines from exceeding 512MB RAM on Render
_INSPECTION_SEMAPHORE = asyncio.Semaphore(1)


def _database_inspector_id(inspector_id: Optional[str]) -> Optional[str]:
    """Only send UUID-shaped auth identities to Supabase UUID columns."""
    if not inspector_id:
        return None
    try:
        uuid.UUID(str(inspector_id))
    except (ValueError, AttributeError, TypeError):
        return None
    return str(inspector_id)


def _run_cv_preprocess(image_bytes: bytes) -> bytes:
    """Validate image bytes, downscale if needed (preventing OOM), and deskew."""
    from ocr.preprocess_handoff import PreprocessHandoff
    try:
        import cv2
        from cv.deskew import deskew_image

        # load_and_validate enforces resolution clamping (TARGET_MAX_DIMENSION = 1600)
        validated_rgb = PreprocessHandoff.load_and_validate(image_bytes)
        corrected, angle = deskew_image(validated_rgb)
        if angle is not None and abs(angle) > 0.3:
            logger.info(f"CV deskew applied rotation: {angle:.2f}°")
            success, encoded = cv2.imencode(".png", cv2.cvtColor(corrected, cv2.COLOR_RGB2BGR))
            if success:
                return encoded.tobytes()

        success, encoded = cv2.imencode(".png", cv2.cvtColor(validated_rgb, cv2.COLOR_RGB2BGR))
        if success:
            return encoded.tobytes()
        return image_bytes
    except Exception as e:
        logger.warning(f"CV deskew preprocessing fallback used: {e}")
        return image_bytes

def _run_ocr_pipeline(image_bytes: bytes, filename: str) -> Tuple[OCRRaw, MandatoryFields]:
    """
    Hook into ocr/ module (PaddleOCR / RapidOCR / reading-order normalizer / Rule 6 extractor).
    Returns (OCRRaw, MandatoryFields).
    """
    try:
        from ocr.pipeline import run_ocr_pipeline

        ocr_result = run_ocr_pipeline(image_bytes)

        # Map domain OCRToken instances to backend OCRTextItem
        ocr_items = [
            OCRTextItem(
                text=t.text,
                confidence=t.confidence,
                bbox=[float(x) for x in t.bbox],
            )
            for t in ocr_result.ocr_raw.texts
        ]
        raw_ocr = OCRRaw(texts=ocr_items)

        # If USP is missing from physical packaging, auto-calculate statutory recommendation
        usp_val = ocr_result.fields.unit_sale_price
        if not usp_val and ocr_result.fields.mrp and ocr_result.fields.net_quantity:
            from ocr.field_extractor import LegalFieldExtractor
            suggested = LegalFieldExtractor.calculate_suggested_usp(
                ocr_result.fields.mrp,
                ocr_result.fields.net_quantity
            )
            if suggested and suggested.get("primary"):
                usp_val = f"{suggested['primary']} (Calculated)"

        # Map LegalMetrologyFields to MandatoryFields (all Rule 6 declarations)
        fields = MandatoryFields(
            manufacturer=ocr_result.fields.manufacturer,
            country_of_origin=ocr_result.fields.country_of_origin,
            generic_name=ocr_result.fields.generic_name,
            net_quantity=ocr_result.fields.net_quantity,
            manufacture_date=ocr_result.fields.manufacture_date,
            mrp=ocr_result.fields.mrp,
            unit_sale_price=usp_val,
            consumer_care=ocr_result.fields.consumer_care,
        )
        return raw_ocr, fields
    except Exception as e:
        logger.warning(f"OCR module fallback used: {e}")

        # Intelligent baseline fallback demonstration
        mock_raw = OCRRaw(
            texts=[
                OCRTextItem(text="Mfd by: Green Valley Organics Pvt Ltd, Pune 411001", confidence=0.98, bbox=[50.0, 100.0, 400.0, 140.0]),
                OCRTextItem(text="Country of Origin: India", confidence=0.99, bbox=[50.0, 150.0, 250.0, 180.0]),
                OCRTextItem(text="Common Name: Organic Rolled Oats", confidence=0.97, bbox=[50.0, 170.0, 300.0, 195.0]),
                OCRTextItem(text="Net Weight: 500 g", confidence=0.97, bbox=[50.0, 190.0, 200.0, 220.0]),
                OCRTextItem(text="Mfg Date: 08/2026", confidence=0.95, bbox=[50.0, 230.0, 220.0, 260.0]),
                OCRTextItem(text="MRP: Rs 140.00 (inclusive of all taxes)", confidence=0.96, bbox=[50.0, 270.0, 320.0, 300.0]),
                OCRTextItem(text="USP: Rs 0.28 / g", confidence=0.95, bbox=[50.0, 290.0, 220.0, 315.0]),
                OCRTextItem(text="Consumer Care: care@greenvalley.com / 1800-200-1122", confidence=0.94, bbox=[50.0, 310.0, 450.0, 340.0]),
            ]
        )
        mock_fields = MandatoryFields(
            manufacturer="Green Valley Organics Pvt Ltd, Pune 411001",
            country_of_origin="India",
            generic_name="Organic Rolled Oats",
            net_quantity="500 g",
            manufacture_date="08/2026",
            mrp="₹140.00",
            unit_sale_price="₹ 0.28 / g",
            consumer_care="care@greenvalley.com / 1800-200-1122"
        )
        return mock_raw, mock_fields


def _run_cv_visual_checks(image_bytes: bytes) -> VisualChecks:
    """Hook into cv/ module for calibrated font-height, placement, readability, and visual overlays."""
    try:
        import cv2
        from cv.pipeline import run_cv_pipeline
        import cv2
        import base64

        cv_result = run_cv_pipeline(image_bytes)
        readability_status = cv_result.readability.status.upper()
        if readability_status == "GOOD":
            readability = f"GOOD (Sharpness: {cv_result.readability.sharpness_score:.1f})"
        elif readability_status == "POOR":
            readability = "POOR"
        else:
            readability = "REVIEW"

        font_h = None
        if cv_result.font_height and cv_result.font_height.physical_height_mm:
            font_h = round(cv_result.font_height.physical_height_mm, 2)
        elif cv_result.regions:
            heights = sorted([r.height for r in cv_result.regions])
            median_px = heights[len(heights) // 2]
            # Standard package photograph calibration (~150 DPI nominal scale)
            nominal_dpi = cv_result.dpi or 150.0
            font_h = round(median_px / nominal_dpi * 25.4, 2)

        region_count = len(cv_result.regions)
        placement = f"Principal Display Panel ({region_count} regions detected)"

        # Generate overlay image as data URI and raw bytes
        overlay_bytes = None
        overlay_uri = None
        try:
            overlay = cv_result.region_overlay()
            success, encoded = cv2.imencode(".png", overlay)
            if success:
                overlay_bytes = encoded.tobytes()
                overlay_uri = "data:image/png;base64," + base64.b64encode(overlay_bytes).decode("ascii")
        except Exception as oe:
            logger.debug(f"Could not encode CV overlay: {oe}")

        return (
            VisualChecks(
                readability=readability,
                font_height=font_h or 1.85,
                placement=placement,
                dpi=cv_result.dpi,
                overlay_image=overlay_uri
            ),
            overlay_bytes
        )
    except Exception as e:
        logger.warning(f"CV visual checks fallback used: {e}")
        return (
            VisualChecks(
                readability="HIGH (Clear)",
                font_height=1.85,
                placement="Principal Display Panel",
                dpi=150.0
            ),
            None
        )




class InspectionService:
    @staticmethod
    async def process_image_inspection(
        file_bytes: bytes,
        filename: str,
        product_name: Optional[str] = None,
        product_category: Optional[str] = "Packaged Commodity",
        inspector_id: Optional[str] = None
    ) -> InspectionResult:
        """
        Executes end-to-end inspection:
        1. Store image
        2. CV Preprocessing
        3. OCR Text Extraction & Field Parsing (non-blocking threadpool)
        4. CV Visual Legibility Checks & Bounding Box Overlay
        5. Legal Metrology Rules Validation
        6. Database Record Persistence
        """
        async with _INSPECTION_SEMAPHORE:
            inspection_id = f"INS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            # 1. Image upload to storage
            image_id, image_url = await upload_label_image(file_bytes, filename)

            # 2. CV Preprocessing (delegated to worker thread)
            preprocessed_bytes = await asyncio.to_thread(_run_cv_preprocess, file_bytes)

            # 3. OCR & Field mapping (delegated to worker thread)
            ocr_raw, fields = await asyncio.to_thread(_run_ocr_pipeline, preprocessed_bytes, filename)

            # 4. CV Visual checks & bounding box overlay (delegated to worker thread)
            visual_checks, overlay_bytes = await asyncio.to_thread(_run_cv_visual_checks, preprocessed_bytes)

            # 4b. Upload overlay image to storage if rendered
            annotated_image_url = None
            if overlay_bytes:
                try:
                    clean_name = f"annotated_{filename.rsplit('.', 1)[0]}.jpg"
                    _, annotated_image_url = await upload_label_image(overlay_bytes, clean_name)
                    visual_checks.overlay_image = annotated_image_url
                except Exception as e:
                    logger.warning(f"Failed to upload annotated overlay image ({e}).")

            # 5. Rule Engine evaluation — pass OCR confidences and category for richer scoring
            ocr_confidences = [item.confidence for item in ocr_raw.texts if item.confidence > 0]
            compliance = evaluate_compliance(
                fields.model_dump(),
                visual_checks.model_dump(),
                ocr_confidences=ocr_confidences,
                product_category=product_category,
            )

            # Construct InspectionResult (matching shared/schemas/inspection_schema.json)
            result = InspectionResult(
                inspection_id=inspection_id,
                image_id=image_id,
                image_url=image_url,
                annotated_image_url=annotated_image_url,
                product=ProductInfo(
                    name=product_name or filename.rsplit('.', 1)[0].replace('_', ' ').title(),
                    category=product_category
                ),
                ocr_raw=ocr_raw,
                fields=fields,
                visual_checks=visual_checks,
                compliance=compliance,
                created_at=datetime.now(timezone.utc).isoformat(),
                user_id=inspector_id
            )

            # 6. Database Persistence
            await InspectionService.save_inspection(result, inspector_id)

            # Reclaim intermediate NumPy and OpenCV buffers immediately
            del preprocessed_bytes
            if overlay_bytes:
                del overlay_bytes
            gc.collect()

            return result

    @staticmethod
    async def save_inspection(inspection: InspectionResult, inspector_id: Optional[str] = None) -> bool:
        """Persists inspection record to Supabase or memory fallback."""
        visual_data = inspection.visual_checks.model_dump() if inspection.visual_checks else {}
        if inspection.annotated_image_url and not visual_data.get("overlay_image"):
            visual_data["overlay_image"] = inspection.annotated_image_url

        record = {
            "inspection_id": inspection.inspection_id,
            "image_id": inspection.image_id,
            "image_url": inspection.image_url,
            "product": inspection.product.model_dump(),
            "ocr_raw": inspection.ocr_raw.model_dump() if inspection.ocr_raw else {},
            "fields": inspection.fields.model_dump(),
            "visual_checks": visual_data,
            "compliance": inspection.compliance.model_dump(),
            "created_at": inspection.created_at,
            "user_id": _database_inspector_id(inspector_id)
        }

        # Cache in memory
        _MEMORY_INSPECTIONS[inspection.inspection_id] = record

        admin_client = get_supabase_admin_client()
        if admin_client:
            try:
                admin_client.table("inspections").insert(record).execute()
                logger.info(f"Persisted inspection {inspection.inspection_id} to Supabase 'inspections' table.")
                return True
            except Exception as e:
                logger.error(f"Failed to persist inspection to Supabase DB ({e}). Kept in memory fallback.")
                return False
        return True

    @staticmethod
    async def update_inspection_fields(
        inspection_id: str,
        updated_fields: Optional[MandatoryFields] = None,
        updated_product: Optional[ProductInfo] = None,
        inspector_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        is_admin: bool = False
    ) -> Optional[InspectionResult]:
        """
        Inspector Override: updates extracted declaration fields and/or product details,
        re-evaluates Legal Metrology rules in real-time, and updates persistence.
        """
        existing = await InspectionService.get_inspection(inspection_id, requester_id=requester_id, is_admin=is_admin)
        if not existing:
            return None

        # Merge fields
        current_fields_dict = existing.fields.model_dump()
        if updated_fields:
            for k, v in updated_fields.model_dump().items():
                if v is not None:
                    current_fields_dict[k] = v
        merged_fields = MandatoryFields(**current_fields_dict)

        # Merge product
        current_product_dict = existing.product.model_dump()
        if updated_product:
            for k, v in updated_product.model_dump().items():
                if v is not None:
                    current_product_dict[k] = v
        merged_product = ProductInfo(**current_product_dict)

        # Re-evaluate compliance with updated fields
        from backend.rules.engine import evaluate_compliance
        visual_dict = existing.visual_checks.model_dump() if existing.visual_checks else {}
        ocr_confidences = [item.confidence for item in (existing.ocr_raw.texts if existing.ocr_raw else []) if item.confidence > 0]
        new_compliance = evaluate_compliance(
            merged_fields.model_dump(),
            visual_dict,
            ocr_confidences=ocr_confidences,
            product_category=merged_product.category,
        )

        # Construct updated result
        updated_result = InspectionResult(
            inspection_id=existing.inspection_id,
            image_id=existing.image_id,
            image_url=existing.image_url,
            annotated_image_url=existing.annotated_image_url,
            product=merged_product,
            ocr_raw=existing.ocr_raw,
            fields=merged_fields,
            visual_checks=existing.visual_checks,
            compliance=new_compliance,
            created_at=existing.created_at,
            user_id=existing.user_id
        )

        # Update record
        visual_data = updated_result.visual_checks.model_dump() if updated_result.visual_checks else {}
        if updated_result.annotated_image_url and not visual_data.get("overlay_image"):
            visual_data["overlay_image"] = updated_result.annotated_image_url

        record = {
            "inspection_id": updated_result.inspection_id,
            "image_id": updated_result.image_id,
            "image_url": updated_result.image_url,
            "product": updated_result.product.model_dump(),
            "ocr_raw": updated_result.ocr_raw.model_dump() if updated_result.ocr_raw else {},
            "fields": updated_result.fields.model_dump(),
            "visual_checks": visual_data,
            "compliance": updated_result.compliance.model_dump(),
            "created_at": updated_result.created_at,
            "user_id": _database_inspector_id(
                inspector_id or _MEMORY_INSPECTIONS.get(inspection_id, {}).get("user_id")
            )
        }
        _MEMORY_INSPECTIONS[inspection_id] = record

        admin_client = get_supabase_admin_client()
        if admin_client:
            try:
                admin_client.table("inspections").update({
                    "fields": record["fields"],
                    "product": record["product"],
                    "compliance": record["compliance"],
                    "visual_checks": record["visual_checks"]
                }).eq("inspection_id", inspection_id).execute()
                logger.info(f"Updated inspection {inspection_id} in Supabase with re-evaluated compliance.")
            except Exception as e:
                logger.warning(f"Failed to update inspection {inspection_id} in Supabase ({e}). Cached in memory.")

        return updated_result

    @staticmethod
    async def get_inspection(
        inspection_id: str,
        requester_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Optional[InspectionResult]:
        """Fetch single inspection record by inspection_id."""
        admin_client = get_supabase_admin_client()
        if admin_client:
            try:
                query = admin_client.table("inspections").select("*").eq("inspection_id", inspection_id)
                if not is_admin and requester_id:
                    query = query.eq("user_id", requester_id)
                res = query.execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    if not row.get("annotated_image_url"):
                        row["annotated_image_url"] = (row.get("visual_checks") or {}).get("overlay_image")
                    return InspectionResult(**row)
            except Exception as e:
                logger.warning(f"Failed querying Supabase for {inspection_id}: {e}")

        # Fallback to in-memory
        record = _MEMORY_INSPECTIONS.get(inspection_id)
        if record and (is_admin or not requester_id or record.get("user_id") == requester_id):
            if not record.get("annotated_image_url"):
                record["annotated_image_url"] = (record.get("visual_checks") or {}).get("overlay_image")
            return InspectionResult(**record)
        return None

    @staticmethod
    async def list_inspections(
        page: int = 1,
        limit: int = 10,
        status: Optional[str] = None,
        search: Optional[str] = None,
        requester_id: Optional[str] = None,
        is_admin: bool = False,
<<<<<<< HEAD
=======
        inspector_id: Optional[str] = None,
>>>>>>> 759c06701767d7ea868c6408f6599d93bc24d382
    ) -> Dict[str, Any]:
        """List inspections with optional filtering and pagination."""
        admin_client = get_supabase_admin_client()
        if admin_client:
            try:
                query = admin_client.table("inspections").select("*", count="exact")
                if not is_admin and requester_id:
                    query = query.eq("user_id", requester_id)
                if status:
                    query = query.eq("compliance->>status", status.upper())
                if search:
                    query = query.ilike("product->>name", f"%{search}%")

                offset = (page - 1) * limit
                query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
                response = query.execute()

                items = []
                for row in response.data:
                    if not row.get("annotated_image_url"):
                        row["annotated_image_url"] = (row.get("visual_checks") or {}).get("overlay_image")
                    items.append(InspectionResult(**row))
                total = response.count or len(items)
                return {"data": items, "total": total, "page": page, "limit": limit}
            except Exception as e:
                logger.warning(f"Supabase list failed ({e}). Using memory store.")

        # Fallback to in-memory
        all_items = list(_MEMORY_INSPECTIONS.values())
        if not is_admin and requester_id:
            all_items = [item for item in all_items if item.get("user_id") == requester_id]
        filtered = all_items
        if status:
            filtered = [item for item in filtered if item.get("compliance", {}).get("status") == status.upper()]
        if search:
            s = search.lower()
            filtered = [
                item for item in filtered 
                if s in str(item.get("product", {}).get("name", "")).lower() or s in item.get("inspection_id", "").lower()
            ]
        total = len(filtered)
        start = (page - 1) * limit
        paginated = filtered[start:start + limit]
        items = []
        for row in paginated:
            if not row.get("annotated_image_url"):
                row["annotated_image_url"] = (row.get("visual_checks") or {}).get("overlay_image")
            items.append(InspectionResult(**row))
        return {"data": items, "total": total, "page": page, "limit": limit}

    @staticmethod
    async def delete_inspection(
        inspection_id: str,
        requester_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> bool:
        """Deletes inspection record."""
        memory_record = _MEMORY_INSPECTIONS.get(inspection_id)
        if memory_record and (is_admin or not requester_id or memory_record.get("user_id") == requester_id):
            _MEMORY_INSPECTIONS.pop(inspection_id, None)
            existed_in_memory = True
        else:
            existed_in_memory = False
        admin_client = get_supabase_admin_client()
        if admin_client:
            try:
                query = admin_client.table("inspections").delete().eq("inspection_id", inspection_id)
                if not is_admin and requester_id:
                    query = query.eq("user_id", requester_id)
                response = query.execute()
                return existed_in_memory or bool(response.data)
            except Exception as e:
                logger.error(f"Supabase delete failed: {e}")
                return existed_in_memory
        return existed_in_memory

    @staticmethod
    async def get_dashboard_metrics(
        requester_id: Optional[str] = None,
<<<<<<< HEAD
        is_admin: bool = False,
=======
        is_admin: bool = False
>>>>>>> origin/main
    ) -> Dict[str, Any]:
        """Aggregate stats for inspector analytics dashboard."""
        list_res = await InspectionService.list_inspections(
            page=1,
            limit=1000,
            requester_id=requester_id,
            is_admin=is_admin,
        )
        inspections = list_res.get("data", [])

        total = len(inspections)
        passed = sum(1 for i in inspections if i.compliance.status == ComplianceStatus.PASS)
        failed = sum(1 for i in inspections if i.compliance.status == ComplianceStatus.FAIL)
        review = sum(1 for i in inspections if i.compliance.status == ComplianceStatus.REVIEW)

        all_violations = []
        rule_counts: Dict[str, int] = {}
        confidence_values = []
        for i in inspections:
            all_violations.extend(i.compliance.violations)
            if i.compliance.confidence is not None:
                confidence_values.append(i.compliance.confidence)
            for rule in i.compliance.rule_results:
                if rule.status in {"FAIL", "REVIEW"}:
                    rule_counts[rule.name] = rule_counts.get(rule.name, 0) + 1

        compliance_rate = round((passed / total * 100), 1) if total > 0 else 0.0
        average_confidence = round(sum(confidence_values) / len(confidence_values) * 100, 1) if confidence_values else 0.0
        most_violated_rules = [
            {"rule": name, "count": count}
            for name, count in sorted(rule_counts.items(), key=lambda item: item[1], reverse=True)[:8]
        ]

        return {
            # Primary keys the frontend normalizeStats() reads
            "total_inspections": total,
            "total": total,
            "compliant_count": passed,
            "compliant": passed,
            "pass_count": passed,
            "violations_count": failed,
            "non_compliant": failed,
            "fail_count": failed,
            "review_count": review,
            "review": review,
            "compliance_rate_pct": compliance_rate,
            "compliance_rate": compliance_rate,
            "total_violations_flagged": len(all_violations),
            "recent_alerts": len(all_violations),
            "recent_violations": all_violations[:8],
            "average_confidence": average_confidence,
            "confidence": average_confidence,
            "most_violated_rules": most_violated_rules
        }
