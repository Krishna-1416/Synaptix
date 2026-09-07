import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List
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

    def evaluate(self, fields: Dict[str, Any], visual_checks: Dict[str, Any] = None) -> ComplianceResult:
        """
        Evaluates declared fields against Legal Metrology (Packaged Commodities) Rules, 2011 (Rule 6 & Rule 7).
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

                # Format specific checks
                val_str = str(value).strip()
                if field_name == "mrp":
                    # Check for ₹ or Rs or 'MRP' indication
                    if not re.search(r"(₹|rs\.?|inr|mrp|\d+)", val_str, re.IGNORECASE):
                        violations.append("Improper MRP declaration format: Must clearly specify retail price (Rule 6(1)(e)).")
                
                elif field_name == "net_quantity":
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

        # 2. Check Visual Requirements (Rule 7)
        if visual_checks:
            readability = visual_checks.get("readability")
            if readability and readability.upper() in ["POOR", "UNREADABLE", "ILLEGIBLE"]:
                violations.append("Poor declaration readability: Mandatory texts must be prominent and legible (Rule 7).")

            font_height = visual_checks.get("font_height")
            # Minimum standard height in mm (typical minimum is 1.0mm - 2.0mm depending on net wt)
            if font_height is not None and font_height < 1.0:
                violations.append(f"Font height too small: {font_height:.2f}mm detected (Minimum prescribed height is 1.0mm under Rule 7).")

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
