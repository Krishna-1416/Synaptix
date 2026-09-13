"""
Synaptix Rule Engine — Legal Metrology (Packaged Commodities) Rules, 2011
Implements R6-01 through R6-17 (Rule 6 mandatory declarations) plus
supporting Rules 7, 8, 9, 10, 11, 12 algorithmic checks.

Each rule returns a RuleResult with status: PASS | FAIL | REVIEW | NOT_APPLICABLE
The overall ComplianceResult aggregates all results and computes:
  - status  : PASS | FAIL | REVIEW
  - score   : ratio of PASS rules out of applicable rules (0.0–1.0)
  - confidence: derived from OCR confidence weighted by rule certainty
  - violations: human-readable failure strings (preserved for frontend compat)
  - rule_results: structured per-rule outcomes for frontend charts/summary
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from backend.models.inspection import (
    ComplianceStatus, ComplianceResult, RuleResult, MandatoryFields, VisualChecks
)

logger = logging.getLogger("synaptix.rules")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COUNTRY_NAMES = {
    "india", "china", "usa", "united states", "united kingdom", "uk", "germany",
    "france", "japan", "south korea", "korea", "bangladesh", "pakistan", "sri lanka",
    "nepal", "bhutan", "thailand", "vietnam", "indonesia", "malaysia", "singapore",
    "canada", "australia", "new zealand", "brazil", "mexico", "italy", "spain",
    "netherlands", "switzerland", "turkey", "russia", "uae", "saudi arabia",
}

_MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DATE_PATTERN = re.compile(
    rf"(\d{{1,2}}[/\-\.]\d{{2,4}}|{_MONTHS}[\s,]+\d{{2,4}}|\d{{2,4}}[/\-\.]\d{{1,2}})",
    re.IGNORECASE,
)
_MRP_PATTERN = re.compile(
    r"(?:mrp|maximum\s+retail\s+price|retail\s+sale\s+price)[^\d₹Rs]*(?:₹|rs\.?|inr)?\s*(\d[\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
_USP_PATTERN = re.compile(
    r"(?:₹|rs\.?|inr)?\s*\d+(?:\.\d{1,2})?\s*(?:/|per)\s*(?:100\s*(?:ml|millilitre|g|gm|grams?)|g|gm|grams?|kg|kilogram|ml|millilitre|l|litre|liter|ltr|piece|unit|count|item|number|n)\b",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(r"(\+?[\d][\d\s\-]{8,}\d)")
_EMAIL_PATTERN = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w{2,}")
_QTY_UNITS = re.compile(
    r"(\d+(?:\.\d+)?)\s*(g|gm|gms|grams?|kg|kilogram|ml|millilitre|l|litre|liter|ltr|n|units?|pcs|count|pieces?)",
    re.IGNORECASE,
)
_MISLEADING_QTY = re.compile(
    r"\b(about|approximately|minimum|not\s+less\s+than|average|jumbo|giant|extra|huge|full)\b",
    re.IGNORECASE,
)
_ADDRESS_PARTS = re.compile(
    r"(?P<pin>\b[1-9]\d{5}\b)"
    r"|(?P<state>andhra\s+pradesh|arunachal\s+pradesh|assam|bihar|chhattisgarh|goa|gujarat|haryana|himachal|"
    r"jharkhand|karnataka|kerala|madhya\s+pradesh|maharashtra|manipur|meghalaya|mizoram|nagaland|odisha|"
    r"punjab|rajasthan|sikkim|tamil\s+nadu|telangana|tripura|uttar\s+pradesh|uttarakhand|west\s+bengal|"
    r"delhi|chandigarh|puducherry|gurgaon|gurugram|noida|mumbai|bangalore|bengaluru|kolkata|chennai|"
    r"hyderabad|pune|ahmedabad|faridabad|ghaziabad|jaipur|indore|lucknow|kanpur|surat|vadodara)\b",
    re.IGNORECASE,
)

_COMMON_GENERIC_COMMODITIES = {
    "noodles", "biscuit", "biscuits", "tea", "coffee", "soap", "rice", "wheat",
    "atta", "maida", "suji", "sugar", "salt", "milk", "bread", "butter", "cheese",
    "oil", "ghee", "chips", "crisps", "snack", "snacks", "cereal", "pasta",
    "juice", "water", "dal", "pulse", "pulses", "flour", "spice", "spices",
    "pickle", "sauce", "ketchup", "jam", "honey", "chocolate", "candy", "cookie", "cookies",
}


def _val(v: Any) -> str:
    """Normalize a field value to a stripped string, returning '' for missing/null."""
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"none", "null", "n/a", "na", "-", ""} else s


def _ok(v: Any) -> bool:
    return bool(_val(v))


def _pass(rule_id: str, name: str, ref: str, reason: str = "") -> RuleResult:
    return RuleResult(rule_id=rule_id, name=name, status="PASS", reason=reason, legal_ref=ref)


def _fail(rule_id: str, name: str, ref: str, reason: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, name=name, status="FAIL", reason=reason, legal_ref=ref)


def _review(rule_id: str, name: str, ref: str, reason: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, name=name, status="REVIEW", reason=reason, legal_ref=ref)


def _na(rule_id: str, name: str, ref: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, name=name, status="NOT_APPLICABLE", legal_ref=ref)


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

def _r6_01(fields: MandatoryFields) -> RuleResult:
    """R6-01 Manufacturer name & address — Rule 6(1)(a), Rule 10."""
    name = "Manufacturer / Packer Name & Address"
    ref = "Rule 6(1)(a), Rule 10"
    val = _val(fields.manufacturer)
    if not val:
        return _fail("R6-01", name, ref, "Manufacturer name & address not detected on label.")
    # Check address completeness (Rule 10): look for at least a city or PIN
    has_address_signal = bool(_ADDRESS_PARTS.search(val)) or any(
        kw in val.lower() for kw in ["road", "street", "nagar", "colony", "pvt", "ltd", "limited", "corp", "corporation", "industries", "works", "sector", "phase", "plot"]
    )
    if not has_address_signal:
        return _review("R6-01", name, ref, f"Manufacturer detected ('{val[:60]}') but address completeness is uncertain — verify street/city/PIN.")
    return _pass("R6-01", name, ref, f"Manufacturer/address declared: {val[:80]}")


def _r6_02(fields: MandatoryFields) -> RuleResult:
    """R6-02 Packer name & address — Rule 6(1)(a). NOT_APPLICABLE when same as manufacturer."""
    name = "Packer Name & Address"
    ref = "Rule 6(1)(a)"
    mfr = _val(fields.manufacturer)
    pkr = _val(fields.packer)
    # If packer field not detected, assume same-entity (NOT_APPLICABLE)
    if not pkr:
        return _na("R6-02", name, ref)
    # If packer differs from manufacturer, validate
    if mfr and pkr.lower() == mfr.lower():
        return _na("R6-02", name, ref)
    has_address = bool(_ADDRESS_PARTS.search(pkr)) or any(
        kw in pkr.lower() for kw in ["road", "nagar", "pvt", "ltd", "colony"]
    )
    if not has_address:
        return _review("R6-02", name, ref, f"Packer '{pkr[:60]}' detected but address is incomplete.")
    return _pass("R6-02", name, ref, f"Packer address declared: {pkr[:80]}")


def _r6_03(fields: MandatoryFields) -> RuleResult:
    """R6-03 Importer name & address — Rule 6(1)(a). Applies only to imported products."""
    name = "Importer Name & Address"
    ref = "Rule 6(1)(a)"
    is_imported = fields.is_imported
    imp = _val(fields.importer)
    # If explicitly not imported
    if is_imported is False:
        return _na("R6-03", name, ref)
    # If explicitly imported
    if is_imported is True:
        if not imp:
            return _fail("R6-03", name, ref, "Product is imported but importer name & address are missing.")
        return _pass("R6-03", name, ref, f"Importer declared: {imp[:80]}")
    # Unknown import status — if importer text found, treat as pass; else NA
    if imp:
        return _pass("R6-03", name, ref, f"Importer declared: {imp[:60]}")
    return _na("R6-03", name, ref)


def _r6_04(fields: MandatoryFields) -> RuleResult:
    """R6-04 Country of origin — Rule 6(1)(aa). Required for imported products."""
    name = "Country of Origin / Manufacture / Assembly"
    ref = "Rule 6(1)(aa)"
    coo = _val(fields.country_of_origin)
    is_imported = fields.is_imported
    if not coo:
        if is_imported is True:
            return _fail("R6-04", name, ref, "Imported product must declare Country of Origin.")
        if is_imported is False:
            return _na("R6-04", name, ref)
        return _review("R6-04", name, ref, "Country of Origin not detected; could not determine if product is imported.")
    # Validate that the declared value looks like a real country name
    coo_lower = coo.lower()
    recognized = any(country in coo_lower for country in _COUNTRY_NAMES)
    if not recognized:
        return _review("R6-04", name, ref, f"'{coo}' may not be a recognized country name — verify manually.")
    return _pass("R6-04", name, ref, f"Country of Origin: {coo}")


def _r6_05(fields: MandatoryFields) -> RuleResult:
    """R6-05 Common / generic name — Rule 6(1)(b)."""
    name = "Common or generic name"
    ref = "Rule 6(1)(b)"
    val = _val(fields.generic_name)
    if not val:
        return _fail("R6-05", name, ref, "Common or generic name not declared on label.")
    # Detect brand-only names (very short single capitalized words are suspect)
    val_clean = val.strip().lower()
    if len(val.split()) == 1 and val[0].isupper() and len(val) < 8 and val_clean not in _COMMON_GENERIC_COMMODITIES:
        return _review("R6-05", name, ref, f"'{val}' appears to be a brand name, not a generic commodity name — verify.")
    return _pass("R6-05", name, ref, f"Generic name declared: {val}")


def _r6_06(fields: MandatoryFields) -> RuleResult:
    """R6-06 Multi-product package — Rule 6(1)(b)."""
    name = "Multi-Product Package Declarations"
    ref = "Rule 6(1)(b)"
    if not fields.is_multi_product:
        return _na("R6-06", name, ref)
    # For multi-product, generic_name should list items
    val = _val(fields.generic_name)
    # Expect at least a list pattern (comma/semicolon separated or numbered items)
    has_list = bool(re.search(r"[,;]|\d+\s*[xX×]\s*\w", val))
    if not has_list:
        return _review("R6-06", name, ref, "Multi-product pack detected but item names/quantities list is not clearly declared.")
    return _pass("R6-06", name, ref, "Multi-product items and quantities declared.")


def _r6_07(fields: MandatoryFields) -> RuleResult:
    """R6-07 Net quantity — Rule 6(1)(c), Rules 11–13."""
    name = "Net Quantity Specification"
    ref = "Rule 6(1)(c), Rule 11, Rule 12"
    val = _val(fields.net_quantity)
    if not val:
        return _fail("R6-07", name, ref, "Net quantity not declared on label.")
    # Misleading qualifiers (Rule 11)
    misleading = _MISLEADING_QTY.search(val)
    if misleading:
        return _review("R6-07", name, ref, f"Misleading Net Quantity expression: qualifier '{misleading.group()}' is prohibited (Rule 11).")
    # Valid unit check (Rule 12)
    if not _QTY_UNITS.search(val):
        return _review("R6-07", name, ref, f"Non-compliant Net Quantity unit: '{val}' must use standard metric units: g, kg, ml, l, or count (Rule 12).")
    return _pass("R6-07", name, ref, f"Net quantity declared: {val}")


def _r6_08(fields: MandatoryFields) -> RuleResult:
    """R6-08 MRP / retail sale price — Rule 6(1)(e)."""
    name = "Maximum Retail Price (MRP)"
    ref = "Rule 6(1)(e)"
    val = _val(fields.mrp)
    if not val:
        return _fail("R6-08", name, ref, "Maximum Retail Price (MRP) not declared on label.")
    # Must contain a numeric value and currency indicator
    has_currency = bool(re.search(r"(₹|rs\.?|inr|mrp)", val, re.IGNORECASE))
    has_number = bool(re.search(r"\d+", val))
    if not (has_currency and has_number):
        return _review("R6-08", name, ref, f"Improper MRP declaration format: '{val}' — must clearly show ₹/Rs. + price.")
    return _pass("R6-08", name, ref, f"MRP declared: {val}")


def _r6_09(fields: MandatoryFields, category: Optional[str] = None) -> RuleResult:
    """R6-09 Unit sale price — Rule 6(11) as amended 2021/2022."""
    name = "Unit Sale Price (USP)"
    ref = "Rule 6(11)"
    raw_val = _val(fields.unit_sale_price)

    # Check if this was an auto-calculated suggestion
    is_calculated = bool(re.search(r"\(calculated\)", raw_val, re.IGNORECASE))
    val = re.sub(r"\(calculated\)", "", raw_val, flags=re.IGNORECASE).strip()

    # Determine if product is liquid / beverage
    is_liquid = False
    net_q = _val(fields.net_quantity).lower()
    if any(u in net_q for u in ["ml", "millilitre", "l", "litre", "ltr"]) or (category and "beverage" in category.lower()):
        is_liquid = True

    # 1. If explicitly declared on packaging (and not auto-calculated)
    if val and not is_calculated:
        if not _USP_PATTERN.search(val):
            return _review(
                "R6-09",
                name,
                ref,
                f"Improper Unit Sale Price format: '{val}'. Required: ₹ [amount] / [unit] (e.g. ₹ 16.00/100ml, ₹ 80/L for beverages; ₹ 0.28/g, ₹ 120/kg for solids)."
            )
        # Check decimal places (must be rounded to nearest 2)
        decimal_match = re.search(r"\d+\.(\d+)", val)
        if decimal_match and len(decimal_match.group(1)) > 2:
            return _review(
                "R6-09",
                name,
                ref,
                f"USP '{val}' has more than 2 decimal places — must be rounded to nearest 2 decimal places under Rule 6(11)."
            )
        return _pass("R6-09", name, ref, f"Unit Sale Price declared: {val}")

    # 2. Derive statutory suggested USP from MRP and Net Quantity under Rule 6(11)
    from ocr.field_extractor import LegalFieldExtractor
    suggested = LegalFieldExtractor.calculate_suggested_usp(fields.mrp, fields.net_quantity, category)
    suggested_str = ""
    if suggested:
        if is_liquid:
            suggested_str = f"{suggested['primary']} (or {suggested.get('secondary', '')})"
        else:
            suggested_str = suggested["primary"]

    # 3. If auto-calculated value was passed
    if is_calculated:
        return _review(
            "R6-09",
            name,
            ref,
            f"USP not printed on beverage label. Auto-calculated statutory expectation under Rule 6(11): {val}. Verify packaging to confirm whether physical declaration was omitted."
        )

    # 4. Value is missing on packaging
    if suggested_str:
        return _fail(
            "R6-09",
            name,
            ref,
            f"Unit Sale Price (USP) not declared on label. Mandatory requirement under Rule 6(11) (statutory expectation: {suggested_str})."
        )

    return _fail(
        "R6-09",
        name,
        ref,
        "Unit Sale Price (USP) not declared. Rule 6(11) requires ₹ per 100ml / L for beverages and liquids, or ₹ per 100g / kg for solid commodities."
    )


def _r6_10(fields: MandatoryFields) -> RuleResult:
    """R6-10 Month/year of manufacture — Rule 6(1)(d)."""
    name = "Month & Year of Manufacture / Packing"
    ref = "Rule 6(1)(d)"
    val = _val(fields.manufacture_date)
    if not val:
        return _fail("R6-10", name, ref, "Month and year of manufacture/packing not declared.")
    if not _DATE_PATTERN.search(val):
        return _fail("R6-10", name, ref, f"Manufacture date '{val}' format is invalid — require MM/YYYY or Month YYYY.")
    # Check it's not confused with an expiry date
    if bool(re.search(r"(best\s+before|expir|use\s+by|bb|ubd)", val, re.IGNORECASE)):
        return _review("R6-10", name, ref, "Detected date may be an expiry/best-before date, not manufacture date — verify.")
    return _pass("R6-10", name, ref, f"Manufacture date declared: {val}")


def _r6_11(fields: MandatoryFields) -> RuleResult:
    """R6-11 Best before / use by — Rule 6(1)(da). Conditional rule."""
    name = "Best Before / Use By Date"
    ref = "Rule 6(1)(da)"
    val = _val(fields.best_before)
    # Rule applies to products that may become unfit after a period
    # If not provided in extracted fields, use heuristic from manufacture_date text
    mfg = _val(fields.manufacture_date)
    bb_in_mfg = bool(re.search(r"(best\s+before|expir|use\s+by|bb|ubd)", mfg, re.IGNORECASE)) if mfg else False

    if not val and not bb_in_mfg:
        return _na("R6-11", name, ref)
    if not val and bb_in_mfg:
        return _review("R6-11", name, ref, "Expiry-related text found in manufacture date field — extract Best Before date separately.")
    if not _DATE_PATTERN.search(val):
        return _fail("R6-11", name, ref, f"Best Before date format invalid: '{val}' — require date, month and year.")
    return _pass("R6-11", name, ref, f"Best Before / Use By declared: {val}")


def _r6_12(fields: MandatoryFields) -> RuleResult:
    """R6-12 Consumer care details — Rule 6(2)."""
    name = "Consumer Care / Helpline Details"
    ref = "Rule 6(2)"
    val = _val(fields.consumer_care)
    if not val:
        return _fail("R6-12", name, ref, "Consumer care details not declared. Must include name, address, phone and email.")
    has_phone = bool(_PHONE_PATTERN.search(val))
    has_email = bool(_EMAIL_PATTERN.search(val))
    if not (has_phone or has_email):
        return _review("R6-12", name, ref, "Consumer care found but missing phone number or email address — verify completeness.")
    return _pass("R6-12", name, ref, f"Consumer care contact details declared: {val[:80]}")


def _r6_13(fields: MandatoryFields, category: Optional[str]) -> RuleResult:
    """R6-13 Dimensions where applicable — Rule 6(1)(f), Rules 12/14–17."""
    name = "Commodity-Specific Dimensions"
    ref = "Rule 6(1)(f), Rules 14–17"
    # Dimensions are relevant for textiles, sheets, containers
    applicable_categories = ["textile", "fabric", "sheet", "container", "household"]
    cat = (category or "").lower()
    if not any(kw in cat for kw in applicable_categories):
        return _na("R6-13", name, ref)
    # Check generic_name or net_quantity for dimension declarations
    val = _val(fields.generic_name) + " " + _val(fields.net_quantity)
    has_dim = bool(re.search(r"\d+\s*(cm|mm|m|metre|meter|inch|in|ft|feet)\b", val, re.IGNORECASE))
    if not has_dim:
        return _review("R6-13", name, ref, f"Category '{category}' may require dimension declaration — verify label.")
    return _pass("R6-13", name, ref, "Dimensions declared where applicable.")


def _r6_14(fields: MandatoryFields, category: Optional[str]) -> RuleResult:
    """R6-14 Commodity-specific declarations gateway — Rule 6(1)(g)."""
    name = "Commodity-Specific Mandatory Declarations"
    ref = "Rule 6(1)(g)"
    # Gateway rule — always PASS if other specific rules are checked
    return _pass("R6-14", name, ref, f"Category '{category or 'General'}' commodity declarations evaluated via applicable sub-rules.")


def _r6_15(fields: MandatoryFields, visual: VisualChecks) -> RuleResult:
    """R6-15 GM marking — Rule 6(7)."""
    name = "Genetically Modified (GM) Marking"
    ref = "Rule 6(7)"
    if not fields.is_gm_food:
        return _na("R6-15", name, ref)
    # Check placement from visual checks
    placement = _val(visual.placement) if visual else ""
    if not placement:
        return _review("R6-15", name, ref, "GM food detected but 'GM' label placement at top-of-PDP could not be verified.")
    if "top" not in placement.lower():
        return _fail("R6-15", name, ref, "'GM' marking must appear at the top of the Principal Display Panel.")
    return _pass("R6-15", name, ref, "'GM' marking present at top of Principal Display Panel.")


def _r6_16(fields: MandatoryFields) -> RuleResult:
    """R6-16 Vegetarian / Non-vegetarian marking — Rule 6(8)."""
    name = "Vegetarian / Non-Vegetarian Symbol"
    ref = "Rule 6(8)"
    mark = _val(fields.veg_nonveg_mark)
    if not mark:
        return _na("R6-16", name, ref)
    mark_lower = mark.lower()
    if any(kw in mark_lower for kw in ["green", "veg", "vegetarian"]):
        return _pass("R6-16", name, ref, "Green (vegetarian) symbol detected.")
    if any(kw in mark_lower for kw in ["red", "brown", "non-veg", "nonveg"]):
        return _pass("R6-16", name, ref, "Red/Brown (non-vegetarian) symbol detected.")
    return _review("R6-16", name, ref, f"Veg/Non-veg mark '{mark}' detected but color/type unclear — verify symbol color.")


def _r6_17(fields: MandatoryFields) -> RuleResult:
    """R6-17 E-commerce declarations — Rule 6(10), Rule 6(10A)."""
    name = "E-Commerce Mandatory Declarations"
    ref = "Rule 6(10), Rule 6(10A)"
    if not fields.is_ecommerce:
        return _na("R6-17", name, ref)
    # E-commerce requires all Rule 6(1) fields except manufacture month/year
    required = [fields.manufacturer, fields.generic_name, fields.net_quantity, fields.mrp, fields.consumer_care]
    missing_count = sum(1 for f in required if not _ok(f))
    if missing_count > 0:
        return _fail("R6-17", name, ref, f"{missing_count} mandatory field(s) missing from e-commerce listing (Rule 6(10)).")
    # For imported product on e-commerce listing, country of origin filter required (from July 2026)
    if fields.is_imported and not _ok(fields.country_of_origin):
        return _fail("R6-17", name, ref, "E-commerce listing of imported product must specify Country of Origin filter (Rule 6(10A), effective July 2026).")
    return _pass("R6-17", name, ref, "E-commerce mandatory declarations verified.")


# Supporting rules

def _rule7(fields: MandatoryFields, visual: VisualChecks) -> RuleResult:
    """Rule 7 — Font size / letter height."""
    name = "Declaration Font Height (Statutory Minimum)"
    ref = "Rule 7, Table 1"
    if not visual or visual.font_height is None:
        return _review("RULE7", name, ref, "Font height could not be measured — manual verification required.")
    qty = _val(fields.net_quantity)
    min_h = _get_min_font_height(qty)
    fh = visual.font_height
    if fh < min_h:
        return _fail("RULE7", name, ref, f"Font height too small: {fh:.2f}mm detected. Minimum prescribed height is {min_h:.1f}mm for this package size (Rule 7 Table 1).")
    return _pass("RULE7", name, ref, f"Font height {fh:.2f}mm meets statutory minimum of {min_h:.1f}mm.")


def _rule8(visual: VisualChecks) -> RuleResult:
    """Rule 8 — Declaration placement on Principal Display Panel."""
    name = "Principal Display Panel Placement"
    ref = "Rule 8"
    if not visual or not visual.placement:
        return _review("RULE8", name, ref, "Placement could not be verified — check declarations are on the Principal Display Panel.")
    placement = visual.placement.upper()
    if any(term in placement for term in ["OUTSIDE", "NON_PDP", "BACK_SEAM", "ILLEGAL_ZONE", "SIDE_SEAM"]):
        return _review("RULE8", name, ref, f"Improper declaration placement: declarations appear outside Principal Display Panel ('{visual.placement}').")
    return _pass("RULE8", name, ref, f"Declarations on Principal Display Panel: {visual.placement}")


def _rule9(visual: VisualChecks) -> RuleResult:
    """Rule 9 — Legibility, prominence, contrast."""
    name = "Declaration Legibility & Prominence"
    ref = "Rule 9"
    if not visual or not visual.readability:
        return _review("RULE9", name, ref, "Readability could not be assessed — manual legibility check required.")
    r = visual.readability.upper()
    if any(term in r for term in ["POOR", "UNREADABLE", "ILLEGIBLE"]):
        return _review("RULE9", name, ref, "Poor declaration readability: declarations are not sufficiently legible/prominent.")
    if any(term in r for term in ["FAIR", "REVIEW", "BORDERLINE"]):
        return _review("RULE9", name, ref, f"Readability assessed as '{visual.readability}' — manual legibility verification recommended.")
    return _pass("RULE9", name, ref, f"Readability: {visual.readability} — declarations are legible and prominent.")


def _get_min_font_height(net_qty_str: Optional[str]) -> float:
    """Rule 7 Table 1 — Tiered minimum font height based on package quantity."""
    if not net_qty_str:
        return 1.0
    m = _QTY_UNITS.search(str(net_qty_str))
    if not m:
        return 1.0
    val = float(m.group(1))
    unit = m.group(2).lower()
    if unit in ("kg", "kilogram", "l", "litre", "liter", "ltr"):
        normalized = val * 1000.0
    else:
        normalized = val
    if normalized <= 50.0:
        return 1.0
    elif normalized <= 200.0:
        return 2.0
    elif normalized <= 1000.0:
        return 4.0
    else:
        return 6.0


# ---------------------------------------------------------------------------
# Main RuleEngine class
# ---------------------------------------------------------------------------

class RuleEngine:
    def evaluate(
        self,
        fields_dict: Dict[str, Any],
        visual_dict: Dict[str, Any] = None,
        ocr_confidences: List[float] = None,
        product_category: Optional[str] = None,
    ) -> ComplianceResult:
        """
        Evaluate all applicable Legal Metrology rules and return a full ComplianceResult.

        Args:
            fields_dict: Extracted mandatory field values (from MandatoryFields.model_dump())
            visual_dict: CV-measured visual checks (from VisualChecks.model_dump())
            ocr_confidences: Per-token OCR confidence values (0.0–1.0)
            product_category: Product category string for conditional rules

        Returns:
            ComplianceResult with status, score, confidence, violations, rule_results
        """
        from backend.models.inspection import MandatoryFields, VisualChecks

        # Re-construct typed objects for cleaner rule access
        try:
            fields = MandatoryFields(**{k: v for k, v in fields_dict.items() if k in MandatoryFields.model_fields})
        except Exception:
            fields = MandatoryFields()
        try:
            visual = VisualChecks(**(visual_dict or {})) if visual_dict else VisualChecks()
        except Exception:
            visual = VisualChecks()

        category = product_category or ""

        # Run all rules
        results: List[RuleResult] = [
            _r6_01(fields),
            _r6_02(fields),
            _r6_03(fields),
            _r6_04(fields),
            _r6_05(fields),
            _r6_06(fields),
            _r6_07(fields),
            _r6_08(fields),
            _r6_09(fields, category),
            _r6_10(fields),
            _r6_11(fields),
            _r6_12(fields),
            _r6_13(fields, category),
            _r6_14(fields, category),
            _r6_15(fields, visual),
            _r6_16(fields),
            _r6_17(fields),
            _rule7(fields, visual),
            _rule8(visual),
            _rule9(visual),
        ]

        # Aggregate
        applicable = [r for r in results if r.status != "NOT_APPLICABLE"]
        passed = [r for r in applicable if r.status == "PASS"]
        failed = [r for r in applicable if r.status == "FAIL"]
        review_rules = [r for r in applicable if r.status == "REVIEW"]

        # Score (0.0–1.0)
        score = round(len(passed) / len(applicable), 4) if applicable else 0.0

        # Violations: flat strings for backward-compat with frontend and test suites
        violations = [
            f"{r.name}: {r.reason}" if r.reason else r.name
            for r in applicable
            if r.status in ("FAIL", "REVIEW")
        ]

        # Confidence: weighted average of OCR confidences, reduced for each REVIEW rule
        if ocr_confidences:
            raw_conf = sum(ocr_confidences) / len(ocr_confidences)
        else:
            raw_conf = 0.90  # conservative default when no OCR data available
        # Reduce confidence slightly per REVIEW rule (uncertainty)
        confidence = round(max(0.0, raw_conf - (len(review_rules) * 0.03)), 4)

        # Overall status
        if failed:
            # Any hard FAIL → overall FAIL
            status = ComplianceStatus.FAIL
        elif review_rules and not failed:
            # Only reviews → REVIEW
            status = ComplianceStatus.REVIEW
        else:
            status = ComplianceStatus.PASS

        return ComplianceResult(
            status=status,
            violations=violations,
            score=score,
            confidence=confidence,
            rule_results=results,
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_engine = RuleEngine()


def evaluate_compliance(
    fields: Dict[str, Any],
    visual_checks: Dict[str, Any] = None,
    ocr_confidences: List[float] = None,
    product_category: Optional[str] = None,
) -> ComplianceResult:
    """Public entry point used by InspectionService."""
    return _default_engine.evaluate(
        fields_dict=fields,
        visual_dict=visual_checks,
        ocr_confidences=ocr_confidences,
        product_category=product_category,
    )
