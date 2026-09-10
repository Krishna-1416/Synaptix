import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
from backend.models.inspection import ComplianceStatus, ComplianceResult

logger = logging.getLogger("synaptix.rules")

DECLARATIONS_PATH = Path(__file__).resolve().parent / "declarations.json"


class RuleEngine:
    def __init__(self, declarations_file: Path = DECLARATIONS_PATH):
        self.rules = self._load_rules(declarations_file)

    def _load_rules(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            logger.warning(f"Rules declarations file not found at {path}")
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("declarations", [])
        except Exception as e:
            logger.error(f"Failed to load rules from {path}: {e}")
            return []

    @staticmethod
    def get_prescribed_min_font_height(net_qty_str: Optional[str]) -> float:
        """
        Determines statutory minimum font height (in mm) under Rule 7 Table 1
        of Legal Metrology (Packaged Commodities) Rules, 2011:
          - Up to 50 g / ml: 1.0 mm
          - Above 50 g / ml up to 200 g / ml: 2.0 mm
          - Above 200 g / ml up to 1 kg / l: 4.0 mm
          - Above 1 kg / l: 6.0 mm
        """
        if not net_qty_str:
            return 1.0
        match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|l|ltr|litres|liter|g|gm|gms|grams?|ml|millilitres?)", str(net_qty_str), re.IGNORECASE)
        if not match:
            return 1.0
        val = float(match.group(1))
        unit = match.group(2).lower()
        if unit in ["kg", "l", "ltr", "litres", "liter"]:
            normalized_val = val * 1000.0
        else:
            normalized_val = val

        if normalized_val <= 50.0:
            return 1.0
        elif normalized_val <= 200.0:
            return 2.0
        elif normalized_val <= 1000.0:
            return 4.0
        else:
            return 6.0

    def evaluate(self, fields: Dict[str, Any], visual_checks: Dict[str, Any] = None) -> ComplianceResult:
        """
        Evaluates declared fields against Legal Metrology (Packaged Commodities) Rules, 2011 (Rule 6, 7, 8, 12).
        """
        violations: List[str] = []
        visual_checks = visual_checks or {}

        # 1. Check Mandatory Declarations (Rule 6)
        for rule in self.rules:
            field_name = rule.get("field")
            label = rule.get("label", field_name)
            is_required = rule.get("required", False)

            value = fields.get(field_name)

            if is_required:
                if not value or str(value).strip().lower() in ["none", "null", "n/a", ""]:
                    violations.append(f"Missing mandatory declaration: {label} (Rule 6).")
                    continue

                val_str = str(value).strip()

                # Format-specific checks
                if field_name == "mrp":
                    # Check for ₹ or Rs or 'MRP' indication
                    if not re.search(r"(₹|rs\.?|inr|mrp|\d+)", val_str, re.IGNORECASE):
                        violations.append("Improper MRP declaration format: Must clearly specify retail price (Rule 6(1)(e)).")

                elif field_name == "unit_sale_price":
                    # Unit Sale Price under Rule 6(1)(m) (e.g. ₹ 0.50/g, Rs 120/kg)
                    if not re.search(r"(?:₹|rs\.?|inr)?\s*\d+(?:\.\d{1,2})?\s*(?:/|per)\s*(?:g|gm|kg|ml|l|ltr|litre|piece|unit|count|item|number|n)\b", val_str, re.IGNORECASE):
                        violations.append("Improper Unit Sale Price format: Must specify price per standard metric unit e.g. ₹/g, ₹/ml, ₹/kg (Rule 6(1)(m)).")

                elif field_name == "net_quantity":
                    # Check for misleading expressions (Rule 12(2))
                    if re.search(r"\b(jumbo|giant|extra|huge|full)\b", val_str, re.IGNORECASE):
                        violations.append("Misleading Net Quantity expression: Exaggerative words like 'Jumbo', 'Extra', or 'Giant' are prohibited (Rule 12(2)).")

                    # Standard units under LM rules: g, kg, ml, l, N, pcs
                    if not re.search(r"\d+\s*(g|kg|gm|gms|ml|l|ltr|litres|liter|n|units|pcs|count)", val_str, re.IGNORECASE):
                        violations.append("Non-compliant Net Quantity unit: Must specify standard metric units (g, kg, ml, l, N) (Rule 12).")

                elif field_name == "manufacture_date":
                    # Check for MM/YYYY, Month YYYY, or date pattern
                    if not re.search(r"(\d{1,2}[/\-\.]\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,]+\d{2,4})", val_str, re.IGNORECASE):
                        violations.append("Improper Date of Manufacture/Packaging: Month and year required (Rule 6(1)(d)).")

                elif field_name == "consumer_care":
                    # Check for phone, email, or contact notice
                    has_phone = bool(re.search(r"(\+?\d[\d\s\-]{8,}\d)", val_str))
                    has_email = bool(re.search(r"[\w\.-]+@[\w\.-]+\.\w+", val_str))
                    has_keyword = bool(re.search(r"(care|helpline|toll[\s\-]?free|contact|feedback)", val_str, re.IGNORECASE))
                    if not (has_phone or has_email or has_keyword):
                        violations.append("Incomplete Consumer Care details: Phone number, email or postal address required (Rule 6(1)(f)).")

        # 2. Check Visual Requirements (Rule 7, 8, 9)
        if visual_checks:
            readability = visual_checks.get("readability")
            if readability and str(readability).upper() in ["POOR", "UNREADABLE", "ILLEGIBLE"]:
                violations.append("Poor declaration readability: Mandatory texts must be prominent and legible (Rule 7 / Rule 9).")

            font_height = visual_checks.get("font_height")
            # Dynamic tiered minimum font height under Rule 7 Table 1
            if font_height is not None:
                prescribed_min_h = self.get_prescribed_min_font_height(fields.get("net_quantity"))
                if font_height < prescribed_min_h:
                    violations.append(
                        f"Font height too small: {font_height:.2f}mm detected (Minimum prescribed height is {prescribed_min_h:.1f}mm for this package quantity under Rule 7 Table 1)."
                    )

            placement = visual_checks.get("placement")
            if placement and any(term in str(placement).upper() for term in ["OUTSIDE", "NON_PDP", "BACK_SEAM", "ILLEGAL_ZONE"]):
                violations.append("Improper declaration placement: Declarations must be positioned on the Principal Display Panel (Rule 8).")

        # Determine overall status
        if not violations:
            status = ComplianceStatus.PASS
        elif any("Missing mandatory declaration" in v for v in violations):
            status = ComplianceStatus.FAIL
        else:
            status = ComplianceStatus.REVIEW

        return ComplianceResult(status=status, violations=violations)


_default_engine = RuleEngine()

def evaluate_compliance(fields: Dict[str, Any], visual_checks: Dict[str, Any] = None) -> ComplianceResult:
    return _default_engine.evaluate(fields, visual_checks)
