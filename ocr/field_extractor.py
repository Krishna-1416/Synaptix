"""
Rule 6 Legal Metrology Declaration Field Extractor.

Extracts the 6 mandatory statutory declarations defined under Rule 6 of the
Legal Metrology (Packaged Commodities) Rules, 2011 from normalized text lines:
1. Maximum Retail Price (mrp)
2. Net Quantity (net_quantity)
3. Month and Year of Manufacture / Packing (manufacture_date)
4. Country of Origin (country_of_origin)
5. Manufacturer / Packer / Importer Name & Address (manufacturer)
6. Consumer Care Contact Details (consumer_care)
Plus Common / Generic Name (Rule 6(1)(b)) and Unit Sale Price (Rule 6(1)(m)).
"""

import re
from typing import Any, Optional, Union
from ocr.interfaces import OCRToken
from ocr.models import LegalMetrologyFields
from ocr.normalizer import TextLine, TokenNormalizer


class LegalFieldExtractor:
    """
    Deterministic rule-based entity extractor utilizing compiled regex patterns,
    fuzzy keyword boundaries, Unicode normalization, and multi-line spatial proximity windowing.
    """

    # --------------------------------------------------------------------------
    # 1. MRP Patterns
    # --------------------------------------------------------------------------
    # 1. MRP Patterns
    # --------------------------------------------------------------------------
    RE_MRP_KEYWORD = re.compile(
        r"\b(?:M\.?\s*R\.?\s*P\.?|MAX\.?(?:IMUM)?\s*RETAIL\s*PRICE|RETAIL\s*PRICE)\b",
        re.IGNORECASE,
    )
    RE_MRP_FULL = re.compile(
        r"""
        \b(?:M\.?\s*R\.?\s*P\.?|MAX\.?(?:IMUM)?\s*RETAIL\s*PRICE|RETAIL\s*PRICE)\b # Keyword
        [^\d₹RsINRz?]*                                         # Delimiters
        (?:₹|Rs\.?|R\.?S\.?|INR|[zZ\?])?\s*                   # Currency
        (?P<amount>(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?) # Price amount with optional comma
        \s*(?:/-)?                                             # Optional /- suffix
        (?:\s*\(?(?P<tax_qualifier>INCL(?:USIVE)?\s*OF\s*ALL\s*TAXES|INCL(?:USIVE)?\s*OF\s*TAXES|INCL(?:USIVE)?\s*TAXES)\)?)? # Taxes
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    RE_TAX_QUALIFIER = re.compile(
        r"\(?\s*INCL\.?(?:USIVE)?\s*(?:OF\s*)?(?:ALL\s*)?TAXES\s*\)?",
        re.IGNORECASE,
    )

    # --------------------------------------------------------------------------
    # 2. Net Quantity Patterns
    # --------------------------------------------------------------------------
    RE_NET_QTY = re.compile(
        r"""
        (?:(?:NET\s*(?:WT|WEIGHT|QTY|QUANTITY|CONTENT)?)|(?:QUANTITY)|(?:CONTENT)|(?:WEIGHT))\b
        [^\d]*                                                 # Delimiter
        (?P<value>\d+(?:\.\d+)?)                               # Numerical value
        \s*
        (?P<unit>kg|g|gm|grams?|ml|m[lI1\|]|l|ltr|litres?|liter|liters?|N|units?|pcs|pieces|nos)\b # Legal SI units
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    # Standalone fallback quantity if preceded without keyword (e.g., "500 g", "1.5 kg")
    RE_STANDALONE_QTY = re.compile(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|gm|grams?|ml|m[lI1\|]|l|ltr|litres?|liter|liters?|N|units?|pcs|pieces|nos)\b",
        re.IGNORECASE,
    )

    # --------------------------------------------------------------------------
    # 3. Manufacture / Packing Date Patterns
    # --------------------------------------------------------------------------
    RE_MFG_DATE = re.compile(
        r"""
        (?:MFD|MFG|PKD|PACKED|DATE\s*OF\s*(?:MFG|PACKING|MANUFACTURE)|MFD\s*ON|PKD\s*ON|BEST\s*BEFORE|EXP(?:IRY)?|USE\s*BY|B\.?NO|BATCH)
        \s*[:.\-]?\s*
        (?P<date>
            (?:\d{1,2}[\/\-\.]\d{2,4})                         # DD/MM/YYYY or MM/YYYY
            |
            (?:\d{4}[\/\-\.](?:0[1-9]|1[0-2]))                 # YYYY/MM
            |
            (?:\d{4}[A-Za-z]{2,3}\d{1,2})                      # 2021MA12
            |
            (?:(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[a-z]*[\s\.\-\/]*\d{2,4}) # Month YYYY
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    RE_DATE_ONLY = re.compile(
        r"\b(?P<date>(?:0[1-9]|1[0-2])[\/\-](?:20\d{2}|\d{2})|20\d{2}[\/\-](?:0[1-9]|1[0-2])|\d{4}[A-Z]{2,3}\d{1,2})\b"
    )

    # --------------------------------------------------------------------------
    # 4. Country of Origin Patterns
    # --------------------------------------------------------------------------
    KNOWN_COUNTRIES = {
        "india", "vietnam", "china", "usa", "japan", "germany", "france",
        "italy", "bangladesh", "sri lanka", "indonesia", "thailand", "malaysia",
        "united states", "united kingdom", "korea", "taiwan", "nepal", "bhutan"
    }
    RE_ORIGIN = re.compile(
        r"""
        (?:COUNTRY\s*OF\s*ORIGIN|MADE\s*IN|PRODUCT\s*OF|MANUFACTURED\s*IN|PRODUCED\s*IN)\b
        [\s\:\-]+
        (?P<country>[A-Za-z]+(?:\s+[A-Za-z]+){0,2})
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # --------------------------------------------------------------------------
    # 5. Manufacturer / Packer Patterns
    # --------------------------------------------------------------------------
    RE_MFG_KEYWORD = re.compile(
        r"\b(?:MFD\.?\s*BY|MANUFACTURED\s*(?:AND\s*PACKED\s*)?BY|PACKED\s*BY|MKTD\.?\s*BY|MARKETED\s*BY|PRODUCED\s*BY|IMPORTED\s*(?:&\s*MARKETED\s*)?BY)\b",
        re.IGNORECASE,
    )
    RE_MFG_CORP = re.compile(
        r"\b(?:LIMITED|LTD\.?|PVT\.?\s*LTD\.?|P(?:RI|R)VATE\s*(?:LIMITED|UMITED|LMTED)|INDUSTRIES|FOODS|BEVERAGES|CONSUMER\s*PRODUCTS|ENTERPRISES|PHARMA|PRODUCTS\s*PVT)\b",
        re.IGNORECASE,
    )
    RE_PINCODE = re.compile(r"\b\d{6}\b")

    # --------------------------------------------------------------------------
    # 6. Consumer Care Patterns
    # --------------------------------------------------------------------------
    RE_CARE_KEYWORD = re.compile(
        r"\b(?:CUSTOMER\s*CARE|CONSUMER\s*CARE|CUSTOMER\s*QUERIES|CUSTOMER\s*SERVICE|CONSUMER\s*CELL|FEEDBACK|QUERIES|COMPLAINTS?|CARE\s*EXECUTIVE|CARE\s*CONTACT|CONTACT\s*US|HELPLINE|TOLL\s*FREE)\b",
        re.IGNORECASE,
    )
    RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    RE_PHONE = re.compile(
        r"(?:"
        r"\b(?:1800|1860|0800|0808)[\-\s]?\d{2,4}[\-\s]?\d{3,4}\b"
        r"|\b(?:\+?91[\-\s]?)?[6-9]\d{9}\b"
        r"|\b0\d{2,4}[\-\s]\d{6,8}\b"
        r"|\b0800\d{7}\b"
        r")"
    )
    RE_WEBSITE = re.compile(
        r"\b(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.(?:com|in|org|net|co\.in)\b",
        re.IGNORECASE
    )

    # --------------------------------------------------------------------------
    # 7. Common or Generic Name Patterns (Rule 6(1)(b))
    # --------------------------------------------------------------------------
    RE_GENERIC_KEYWORD = re.compile(
        r"""
        \b(?:COMMON\s*OR\s*GENERIC\s*NAME|GENERIC\s*NAME|NAME\s*OF\s*(?:THE\s*)?COMMODITY|COMMODITY|PRODUCT\s*NAME)\b
        \s*[\:\-\.]\s*
        (?P<name>[A-Za-z0-9\s,\-\(\)]+)
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    COMMON_COMMODITIES = [
        "instant noodles", "noodles", "cashew cookies", "cookies", "crackers",
        "glucose biscuits", "gluco biscuits", "biscuits",
        "milk chocolate", "dark chocolate", "chocolate", "pasteurized butter", "butter",
        "potato chips", "potatochips", "potato crisps", "crisps", "chips",
        "namkeen", "spicy fried split mung bean", "split mung bean", "mung bean", "moong dal", "bhujia",
        "homogenised toned milk", "toned milk", "pasteurized milk",
        "blended edible vegetable oil", "edible vegetable oil", "vegetable oil",
        "sunflower oil", "mustard oil", "soybean oil", "pure honey", "honey",
        "wheat flour", "atta", "tea", "coffee",
        "detergent powder", "toilet soap", "soap", "toothpaste", "shampoo"
    ]

    # --------------------------------------------------------------------------
    # 8. Unit Sale Price Patterns (Rule 6(1)(m) - 2021/2022 Amendments)
    # --------------------------------------------------------------------------
    RE_USP = re.compile(
        r"""
        (?:(?:UNIT\s*SALE\s*PRICE|U\.?S\.?P\.?)\s*[\:\-\.]?\s*)?
        (?:₹|Rs\.?|INR)?\s*
        (?P<price>\d+(?:\.\d{1,2})?)
        \s*(?:/-)?\s*
        (?:/|per)\s*
        (?P<unit>(?:100\s*(?:ml|m[lI1\|]|millilitres?|g|gm|grams?))|kg|g|gm|grams?|ml|m[lI1\|]|millilitres?|l|ltr|litres?|liter|liters?|pcs|pieces?|units?|nos|count|item|n)\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    @classmethod
    def sanitize_lines(cls, lines: list[TextLine]) -> list[TextLine]:
        """
        Cleans common OCR Unicode artifacts and dot-matrix fragmentation:
        - Full-width characters (\uff1a -> :, \uff08 -> (, \uff09 -> ))
        - Non-breaking spaces (\u00a0), en/em dashes (\u2013, \u2014)
        - Collapse spaced dot-matrix acronyms (M . R . P -> M.R.P, P K D -> PKD)
        """
        cleaned_lines: list[TextLine] = []
        for l in lines:
            t = l.text
            t = t.replace("\uff1a", ":").replace("\uff08", "(").replace("\uff09", ")")
            t = t.replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
            # Spaced acronyms
            t = re.sub(r"\bM\s*\.\s*R\s*\.\s*P\.?\b", "M.R.P.", t, flags=re.IGNORECASE)
            t = re.sub(r"\bM\s+R\s+P\b", "MRP", t, flags=re.IGNORECASE)
            t = re.sub(r"\bP\s*\.\s*K\s*\.\s*D\.?\b", "PKD", t, flags=re.IGNORECASE)
            t = re.sub(r"\bM\s*\.\s*F\s*\.\s*D\.?\b", "MFD", t, flags=re.IGNORECASE)
            t = re.sub(r"\bB\s*\.\s*N\s*\.\s*O\.?\b", "B.NO", t, flags=re.IGNORECASE)
            t = re.sub(r"\bR\s*s\s*\.", "Rs.", t, flags=re.IGNORECASE)
            cleaned_lines.append(TextLine(tokens=l.tokens, text=t, bbox=l.bbox, confidence=l.confidence))
        return cleaned_lines

    @classmethod
    def extract_mrp(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Maximum Retail Price with tax qualification."""
        for i, line in enumerate(lines):
            text = line.text
            match = cls.RE_MRP_FULL.search(text)
            if match:
                amount = match.group("amount")
                try:
                    amount_num = float(amount.replace(",", ""))
                except ValueError:
                    amount_num = 0.0

                # Validate price plausibility (> 2.0 unless explicit currency or /- is present)
                has_explicit_curr = any(c in text for c in ("₹", "Rs", "RS", "INR", "/-"))
                if amount_num >= 2.0 or has_explicit_curr:
                    tax_match = cls.RE_TAX_QUALIFIER.search(text)
                    if not tax_match and i + 1 < len(lines):
                        tax_match = cls.RE_TAX_QUALIFIER.search(lines[i + 1].text)

                    currency = "₹" if "₹" in text else "Rs."
                    if tax_match or "TAX" in text.upper():
                        return f"{currency} {amount} (INCL. OF ALL TAXES)"
                    return f"{currency} {amount}"

            # Keyword on line i, but amount might be on line i, i+1, or i+2
            if cls.RE_MRP_KEYWORD.search(text):
                # Search for currency-qualified or formatted amount first
                cand_match = re.search(r"(?:₹|Rs\.?|INR)\s*((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)", text, re.IGNORECASE)
                if not cand_match:
                    cand_match = re.search(r"((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)\s*(?:/-)", text, re.IGNORECASE)

                target_amount = cand_match.group(1) if cand_match else None
                tax_found = "TAX" in text.upper()

                if not target_amount:
                    for offset in (1, 2):
                        if i + offset < len(lines):
                            cand_line = lines[i + offset].text
                            # Exclude lines that are clearly dates, batch numbers, or nutritional quantities
                            if any(k in cand_line.upper() for k in ("KCAL", "KJ", "SERV", "PORTION", "PROTEIN", "FAT", "CARB", "FSSAI", "LIC")):
                                continue
                            if re.search(r"\b\d{1,2}[\/\-]\d{2,4}\b", cand_line):
                                continue

                            cand_match = re.search(r"(?:₹|Rs\.?|INR)\s*((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)", cand_line, re.IGNORECASE)
                            if not cand_match:
                                cand_match = re.search(r"((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)\s*(?:/-)", cand_line, re.IGNORECASE)
                            if not cand_match and re.match(r"^\s*(?:\d+(?:\.\d{1,2})?)\s*$", cand_line):
                                cand_match = re.search(r"((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)", cand_line)

                            if cand_match:
                                val = cand_match.group(1)
                                try:
                                    val_num = float(val.replace(",", ""))
                                except ValueError:
                                    val_num = 0.0
                                if val_num >= 2.0 or any(c in cand_line for c in ("₹", "Rs", "RS", "/-")):
                                    target_amount = val
                                    if "TAX" in cand_line.upper() or cls.RE_TAX_QUALIFIER.search(cand_line):
                                        tax_found = True
                                    break

                if target_amount:
                    tax_str = " (INCL. OF ALL TAXES)" if tax_found else ""
                    return f"₹ {target_amount}{tax_str}"

        return None

    @classmethod
    def extract_net_quantity(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Net Quantity with SI unit."""
        # Pass 1: standard keyword search on same line
        for line in lines:
            text = line.text
            match = cls.RE_NET_QTY.search(text)
            if match:
                val = match.group("value")
                unit = cls._standardize_unit(match.group("unit").strip())
                return f"{val} {unit}"

        # Pass 2: keyword on line i, value on line i+1
        for i, line in enumerate(lines):
            text = line.text.upper()
            if any(k in text for k in ("NET WT", "NET QTY", "NET WEIGHT", "NET QUANTITY", "NET CONTENT")):
                if i + 1 < len(lines):
                    match = cls.RE_STANDALONE_QTY.search(lines[i + 1].text)
                    if match:
                        val = match.group("value")
                        unit = cls._standardize_unit(match.group("unit").strip())
                        return f"{val} {unit}"

        # Pass 3: isolated standalone quantity (ignoring nutrition facts tables)
        nutrition_keywords = {
            "serving", "serve", "portion", "energy", "protein", "fat", "carb",
            "carbohydrate", "sugar", "sodium", "fiber", "fibre", "salt", "vitamin",
            "iron", "calcium", "daily value", "gda", "rda", "%", "kcal", "kj",
            "table", "per 100", "per pack", "approx", "approx."
        }
        for line in lines:
            text = line.text
            t_lower = text.lower()
            if any(nk in t_lower for nk in nutrition_keywords):
                continue
            match = cls.RE_STANDALONE_QTY.search(text)
            if match:
                val_str = match.group("value")
                # Exclude arbitrary fractional decimals in standalone quantities without keyword (e.g. 9.9g, 40.01g)
                if "." in val_str:
                    try:
                        val_f = float(val_str)
                        if val_f != int(val_f):
                            continue
                    except ValueError:
                        continue
                unit = cls._standardize_unit(match.group("unit").strip())
                return f"{val_str} {unit}"

        return None

    @staticmethod
    def _standardize_unit(unit_str: str) -> str:
        u = re.sub(r"\s+", " ", unit_str.lower().strip())
        if u in ("100 ml", "100ml", "100 millilitre", "100 millilitres"):
            return "100 ml"
        if u in ("100 g", "100g", "100 gm", "100 grams", "100 gram"):
            return "100 g"
        if u in ("g", "gm", "gram", "grams"):
            return "g"
        if u in ("kg", "kilogram", "kilograms"):
            return "kg"
        if u in ("ml", "millilitre", "millilitres", "mi", "m1", "m|"):
            return "ml"
        if u in ("l", "ltr", "litre", "litres", "liter", "liters"):
            return "L"
        if u in ("n", "unit", "units", "pc", "pcs", "piece", "pieces", "nos"):
            return "units"
        return unit_str

    @classmethod
    def extract_manufacture_date(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Manufacturing / Packaging / Best Before date."""
        for i, line in enumerate(lines):
            text = line.text
            match = cls.RE_MFG_DATE.search(text)
            if match:
                d = match.group("date").strip()
                if len(d) >= 4:
                    return d

            # Keyword on line i, date on line i+1
            if any(k in text.upper() for k in ("MFD", "MFG", "PKD", "PACKED", "BEST BEFORE", "EXP", "USE BY")):
                if i + 1 < len(lines):
                    cand_text = lines[i + 1].text
                    cand_match = cls.RE_DATE_ONLY.search(cand_text)
                    if cand_match:
                        return cand_match.group("date").strip()

        # Fallback date only
        for line in lines:
            text = line.text
            if any(k in text.upper() for k in ("MFD", "MFG", "PKD", "PACKED", "DATE", "EXP", "BB")):
                match = cls.RE_DATE_ONLY.search(text)
                if match:
                    return match.group("date").strip()

        return None

    @classmethod
    def extract_country_of_origin(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Country of Origin."""
        for line in lines:
            text = line.text
            match = cls.RE_ORIGIN.search(text)
            if match:
                raw_country = match.group("country").strip().strip(":.-, ")
                words = raw_country.split()
                if words:
                    cand2 = " ".join(words[:2]).lower()
                    cand1 = words[0].lower()
                    if cand2 in cls.KNOWN_COUNTRIES:
                        return cand2.title()
                    if cand1 in cls.KNOWN_COUNTRIES:
                        return cand1.title()

            upper = text.upper()
            for kc in ["INDIA", "VIETNAM", "CHINA", "BANGLADESH", "SRI LANKA", "THAILAND", "JAPAN", "USA", "NEPAL", "BHUTAN"]:
                if (
                    f"MADE IN {kc}" in upper
                    or f"MADEIN{kc}" in upper
                    or f"PRODUCT OF {kc}" in upper
                    or f"ORIGIN: {kc}" in upper
                    or f"ORIGIN : {kc}" in upper
                    or f"FOR SALE IN {kc}" in upper
                    or f"SALE IN {kc}" in upper
                    or f"FORSALEIN{kc}" in upper
                    or f"SALEIN{kc}" in upper
                    or f"MFD IN {kc}" in upper
                    or f"PRODUCED IN {kc}" in upper
                    or f"PACKED IN {kc}" in upper
                ):
                    return kc.title()

        # Corporate address fallback for Indian commodities (PIN code + Indian cities/states)
        for line in lines:
            upper = line.text.upper()
            has_pin = bool(cls.RE_PINCODE.search(upper) or re.search(r"\b\d{5,6}\b", upper))
            has_loc = any(
                loc in upper for loc in (
                    "MUMBAI", "KOLKATA", "DELHI", "BANGALORE", "BENGALURU", "CHENNAI",
                    "AHMEDABAD", "PUNE", "HYDERABAD", "INDIA", "MAHARASHTRA", "GUJARAT",
                    "WEST BENGAL", "ANDHRA PRADESH", "TAMIL NADU", "HARYANA", "PUNJAB",
                    "SURAT", "ANAND", "PAREL", "NAGPUR"
                )
            )
            if has_loc and (has_pin or "INDIA" in upper or any(corp in upper for corp in ("PVT", "LTD", "LIMITED"))):
                return "India"

        return None

    @classmethod
    def extract_manufacturer(cls, lines: list[TextLine]) -> Optional[str]:
        """
        Extract Manufacturer/Packer name and address.
        Uses windowing to capture multi-line addresses ending with pincode or newline.
        """
        # Pass 1: Look for explicit manufacturer keyword
        for i, line in enumerate(lines):
            text = line.text
            match = cls.RE_MFG_KEYWORD.search(text)
            if match:
                start_idx = match.end()
                initial_part = text[start_idx:].strip(" :.-")
                mfg_parts = [initial_part] if initial_part else []

                for next_idx in range(i + 1, min(len(lines), i + 6)):
                    next_line = lines[next_idx].text.strip()
                    if any(
                        p.search(next_line)
                        for p in (cls.RE_MRP_KEYWORD, cls.RE_CARE_KEYWORD, cls.RE_ORIGIN)
                    ):
                        break
                    mfg_parts.append(next_line)
                    if cls.RE_PINCODE.search(next_line):
                        break

                full_mfg = ", ".join(p for p in mfg_parts if p).strip(" ,.-")
                if full_mfg and len(full_mfg) >= 5:
                    return full_mfg

        # Pass 2: Corporate entity search (e.g. "Britannia Industries Ltd", "Mondelez India Foods Private Limited")
        for i, line in enumerate(lines):
            text = line.text
            corp_match = cls.RE_MFG_CORP.search(text)
            if corp_match and not any(k in text.upper() for k in ("NUTRITION", "INGREDIENTS", "SERVING", "FSSAI", "LIC")):
                mfg_parts = [text.strip(" :.-")]
                for next_idx in range(i + 1, min(len(lines), i + 5)):
                    next_line = lines[next_idx].text.strip()
                    if any(p.search(next_line) for p in (cls.RE_MRP_KEYWORD, cls.RE_CARE_KEYWORD, cls.RE_ORIGIN)):
                        break
                    if any(k in next_line.upper() for k in ("NUTRITION", "INGREDIENTS", "SERVING", "ALLERGEN")):
                        break
                    mfg_parts.append(next_line)
                    if cls.RE_PINCODE.search(next_line):
                        break

                full_mfg = ", ".join(p for p in mfg_parts if p).strip(" ,.-")
                if full_mfg and len(full_mfg) >= 8:
                    return full_mfg

        return None

    @classmethod
    def extract_consumer_care(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract customer support phone, email, website, or care cell contact."""
        all_text = " | ".join(l.text for l in lines)
        emails = cls.RE_EMAIL.findall(all_text)
        phones = cls.RE_PHONE.findall(all_text)
        websites = cls.RE_WEBSITE.findall(all_text)

        # Look for explicit consumer care header line
        for i, line in enumerate(lines):
            text = line.text
            if cls.RE_CARE_KEYWORD.search(text):
                line_window = text
                if i + 1 < len(lines):
                    line_window += " " + lines[i + 1].text
                if i + 2 < len(lines):
                    line_window += " " + lines[i + 2].text

                w_emails = cls.RE_EMAIL.findall(line_window)
                w_phones = cls.RE_PHONE.findall(line_window)
                w_webs = cls.RE_WEBSITE.findall(line_window)

                parts = []
                if w_emails:
                    parts.extend(w_emails)
                if w_phones:
                    parts.extend(w_phones)
                if w_webs:
                    parts.extend(w_webs)

                if parts:
                    return ", ".join(dict.fromkeys(parts))

                cleaned_line = cls.RE_CARE_KEYWORD.sub("", text).strip(" :.-|")
                if len(cleaned_line) > 5:
                    return cleaned_line

        # Fallback: if emails, websites, or toll-free phones exist anywhere on package
        combined = []
        if emails:
            combined.extend(emails)
        if phones:
            combined.extend(phones)
        if websites:
            for w in websites:
                if not any(ign in w.lower() for ign in ("openfoodfacts", "example", "github")):
                    combined.append(w)

        if combined:
            return ", ".join(dict.fromkeys(combined))

        return None

    @classmethod
    def extract_generic_name(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Common or Generic Name of the commodity (Rule 6(1)(b))."""
        for line in lines:
            text = line.text
            match = cls.RE_GENERIC_KEYWORD.search(text)
            if match:
                cand = match.group("name").strip(" :.-,")
                if len(cand) >= 3:
                    cand_words = cand.split()
                    if len(cand_words) > 8:
                        cand = " ".join(cand_words[:8])
                    return cand.title()

        # Fallback 1: Check lines against common packaging commodities taxonomy
        for line in lines:
            text = line.text
            # Never extract commodity from ingredients list, allergen advice, or nutrition tables
            if any(k in text.upper() for k in ("INGREDIENT", "CONTAINS", "ALLERGEN", "NUTRITION", "PER 100", "SERVING", "STORE IN")):
                continue
            text_lower = text.lower()
            for commodity in sorted(cls.COMMON_COMMODITIES, key=len, reverse=True):
                # Match commodity name allowing optional spaces between words (e.g. potato chips or potatochips)
                words = commodity.split()
                pattern = r"\b" + r"\s*".join(re.escape(w) for w in words) + r"\b"
                if re.search(pattern, text_lower):
                    return commodity.title()

        # Fallback 2: Prominent non-statutory title line from upper portion
        EXCLUDE_TITLE_WORDS = {
            "INGREDIENTS", "INGREDIENT", "CONTAINS", "ALLERGEN", "ALLERGENS", "NUTRITION",
            "NUTRITIONAL", "SERVING", "SERVINGS", "PORTION", "ENERGY", "PROTEIN", "FAT",
            "SUGAR", "SALT", "SODIUM", "CARBOHYDRATE", "MAIDA", "FLOUR", "WHEAT", "SOY",
            "WALNUT", "WALNUTS", "PEANUT", "PEANUTS", "ALMOND", "ALMONDS", "CASHEW", "CASHEWS",
            "STORE", "KEEP", "COOL", "DRY", "PLACE", "AWAY", "DIRECT", "SUNLIGHT",
            "BEST", "BEFORE", "USE", "DATE", "BATCH", "PKD", "MFD", "MRP", "EXP", "RS", "LIC", "FSSAI",
            "REGISTERED", "TRADEMARK", "OWNED", "MARKETED", "MANUFACTURED", "PACKED", "CONSUMER", "CUSTOMER",
            "AVERAGE", "QUANTITY", "QUANTIN", "TABLE", "PER", "ANNATTO", "COLOUR", "COLOR", "VALUE"
        }
        for line in lines[:3]:
            text = line.text.strip()
            # Must contain a product, commodity, or brand context keyword to prevent taking random OCR artifacts
            if not any(k in text.upper() for k in ("PRODUCT", "COMMODITY", "ITEM", "BRAND", "CATEGORY")):
                continue
            upper_words = set(re.findall(r"[A-Z]+", text.upper()))
            if upper_words & EXCLUDE_TITLE_WORDS:
                continue
            clean = re.sub(r"[^A-Za-z\s]", "", text).strip()
            words = clean.split()
            # Must be a coherent title phrase: 1-4 words, each having at least one vowel
            if 4 <= len(clean) <= 40 and 1 <= len(words) <= 4:
                if all(any(c in w.lower() for c in "aeiouy") for w in words):
                    return clean.title()

        return None

    @classmethod
    def extract_unit_sale_price(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Unit Sale Price (USP) under Rule 6(1)(m) / Rule 6(11)."""
        for line in lines:
            text = line.text
            match = cls.RE_USP.search(text)
            if match:
                price = match.group("price")
                unit = cls._standardize_unit(match.group("unit").strip())
                currency = "₹" if "₹" in text else "Rs."
                return f"{currency} {price} / {unit}"
        return None

    @classmethod
    def calculate_suggested_usp(
        cls,
        mrp_str: Optional[str],
        net_quantity_str: Optional[str],
        category: Optional[str] = None
    ) -> Optional[dict]:
        """
        Calculate statutory suggested Unit Sale Price (USP) under Rule 6(11) (as amended 2021/2022).
        For beverages and liquids:
          - Packages <= 1 L (or 1000 ml): expressed per 100 ml (or per ml)
          - Packages > 1 L: expressed per Litre (L)
        For solid commodities:
          - Packages <= 1 kg (or 1000 g): expressed per 100 g (or per g)
          - Packages > 1 kg: expressed per kilogram (kg)
        """
        if not mrp_str or not net_quantity_str:
            return None

        # 1. Parse numeric MRP
        mrp_clean = mrp_str.replace(",", "").split("(")[0]
        mrp_match = re.search(r"(\d+(?:\.\d{1,2})?)", mrp_clean)
        if not mrp_match:
            return None
        try:
            mrp_val = float(mrp_match.group(1))
        except ValueError:
            return None

        if mrp_val <= 0:
            return None

        # 2. Parse quantity and unit
        qty_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?|ml|millilitres?|l|ltr|litres?|liter|liters?|pcs|pieces?|units?|nos|count|item|n)\b",
            net_quantity_str,
            re.IGNORECASE
        )
        if not qty_match:
            return None

        try:
            qty_val = float(qty_match.group(1))
            unit_raw = qty_match.group(2)
        except (ValueError, IndexError):
            return None

        if qty_val <= 0:
            return None

        std_unit = cls._standardize_unit(unit_raw)

        # 3. Compute statutory Unit Sale Price
        if std_unit in ("ml", "millilitre"):
            if qty_val <= 1000:
                per_100ml = (mrp_val / qty_val) * 100.0
                return {
                    "primary": f"₹ {per_100ml:.2f} / 100 ml",
                    "secondary": f"₹ {(mrp_val / qty_val):.2f} / ml",
                    "per_100ml": round(per_100ml, 2),
                    "unit": "100 ml"
                }
            else:
                per_litre = mrp_val / (qty_val / 1000.0)
                return {
                    "primary": f"₹ {per_litre:.2f} / L",
                    "secondary": f"₹ {round((mrp_val / qty_val) * 100, 2):.2f} / 100 ml",
                    "per_litre": round(per_litre, 2),
                    "unit": "L"
                }
        elif std_unit in ("L", "litre"):
            per_litre = mrp_val / qty_val
            return {
                "primary": f"₹ {per_litre:.2f} / L",
                "secondary": f"₹ {(per_litre / 10.0):.2f} / 100 ml",
                "per_litre": round(per_litre, 2),
                "unit": "L"
            }
        elif std_unit in ("g", "gm", "gram"):
            if qty_val <= 1000:
                per_100g = (mrp_val / qty_val) * 100.0
                return {
                    "primary": f"₹ {per_100g:.2f} / 100 g",
                    "secondary": f"₹ {(mrp_val / qty_val):.2f} / g",
                    "per_100g": round(per_100g, 2),
                    "unit": "100 g"
                }
            else:
                per_kg = mrp_val / (qty_val / 1000.0)
                return {
                    "primary": f"₹ {per_kg:.2f} / kg",
                    "secondary": f"₹ {round((mrp_val / qty_val) * 100, 2):.2f} / 100 g",
                    "per_kg": round(per_kg, 2),
                    "unit": "kg"
                }
        elif std_unit == "kg":
            per_kg = mrp_val / qty_val
            return {
                "primary": f"₹ {per_kg:.2f} / kg",
                "secondary": f"₹ {(per_kg / 10.0):.2f} / 100 g",
                "per_kg": round(per_kg, 2),
                "unit": "kg"
            }
        elif std_unit in ("units", "pcs", "nos"):
            per_unit = mrp_val / qty_val
            return {
                "primary": f"₹ {per_unit:.2f} / unit",
                "secondary": f"₹ {per_unit:.2f} / piece",
                "per_unit": round(per_unit, 2),
                "unit": "unit"
            }

        return None

    @classmethod
    def extract_all_fields(cls, lines: list[TextLine]) -> LegalMetrologyFields:
        """
        Extract all mandatory Rule 6 declarations and return a validated LegalMetrologyFields object.
        """
        cleaned_lines = cls.sanitize_lines(lines)
        return LegalMetrologyFields(
            mrp=cls.extract_mrp(cleaned_lines),
            net_quantity=cls.extract_net_quantity(cleaned_lines),
            manufacture_date=cls.extract_manufacture_date(cleaned_lines),
            country_of_origin=cls.extract_country_of_origin(cleaned_lines),
            manufacturer=cls.extract_manufacturer(cleaned_lines),
            consumer_care=cls.extract_consumer_care(cleaned_lines),
            generic_name=cls.extract_generic_name(cleaned_lines),
            unit_sale_price=cls.extract_unit_sale_price(cleaned_lines),
        )

    # Alias for convenience and backward compatibility
    extract = extract_all_fields


def extract_fields(source: Any) -> dict:
    """
    Top-level Rule 6 declaration extraction facade.

    Accepts:
    - OCRRawPayload / OCRRaw object (containing .texts)
    - List of OCRToken / OCRTextItem objects
    - List of TextLine objects
    - Dict representation of OCR output

    Returns:
        dict: Standardized field dictionary with keys:
              manufacturer, country_of_origin, net_quantity,
              manufacture_date, mrp, consumer_care
    """
    if source is None:
        return LegalMetrologyFields().model_dump()

    if hasattr(source, "texts"):
        tokens = source.texts
    elif isinstance(source, dict) and "texts" in source:
        tokens = source["texts"]
    elif isinstance(source, list):
        tokens = source
    else:
        tokens = []

    # If already a list of TextLine objects, extract directly
    if tokens and all(isinstance(t, TextLine) for t in tokens):
        fields = LegalFieldExtractor.extract_all_fields(tokens)
        return fields.model_dump()

    # Normalize tokens to OCRToken instances
    ocr_tokens: list[OCRToken] = []
    for item in tokens:
        if isinstance(item, OCRToken):
            ocr_tokens.append(item)
        elif hasattr(item, "text") and hasattr(item, "bbox"):
            bbox = list(item.bbox) if hasattr(item, "bbox") else [0, 0, 0, 0]
            conf = float(item.confidence) if hasattr(item, "confidence") else 1.0
            ocr_tokens.append(OCRToken(text=str(item.text), confidence=conf, bbox=[int(round(x)) for x in bbox]))
        elif isinstance(item, dict) and "text" in item:
            bbox = item.get("bbox", [0, 0, 0, 0])
            conf = float(item.get("confidence", 1.0))
            ocr_tokens.append(OCRToken(text=str(item["text"]), confidence=conf, bbox=[int(round(x)) for x in bbox]))

    lines = TokenNormalizer.normalize(ocr_tokens)
    fields = LegalFieldExtractor.extract_all_fields(lines)
    return fields.model_dump()
