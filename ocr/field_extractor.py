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
"""

import re
from typing import Optional
from ocr.models import LegalMetrologyFields
from ocr.normalizer import TextLine, TokenNormalizer


class LegalFieldExtractor:
    """
    Deterministic rule-based entity extractor utilizing compiled regex patterns,
    keyword boundaries, and multi-line spatial proximity windowing.
    """

    # --------------------------------------------------------------------------
    # 1. MRP Patterns
    # --------------------------------------------------------------------------
    RE_MRP_KEYWORD = re.compile(
        r"(?:M\.?\s*R\.?\s*P\.?|MAX(?:IMUM)?\s*RETAIL\s*PRICE)",
        re.IGNORECASE,
    )
    RE_MRP_FULL = re.compile(
        r"""
        (?:M\.?\s*R\.?\s*P\.?|MAX(?:IMUM)?\s*RETAIL\s*PRICE)   # Keyword
        [^\d₹Rs]*                                              # Delimiters
        (?:₹|Rs\.?|INR)?\s*                                    # Currency
        (?P<amount>\d+(?:\.\d{1,2})?)                          # Price amount
        \s*(?:/-)?                                             # Optional /- suffix
        (?:\s*\(?(?P<tax_qualifier>INCL(?:USIVE)?\s*OF\s*ALL\s*TAXES|INCL(?:USIVE)?\s*OF\s*TAXES)\)?)? # Taxes
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    RE_TAX_QUALIFIER = re.compile(
        r"\(?\s*INCL\.?(?:USIVE)?\s*OF\s*(?:ALL\s*)?TAXES\s*\)?",
        re.IGNORECASE,
    )

    # --------------------------------------------------------------------------
    # 2. Net Quantity Patterns
    # --------------------------------------------------------------------------
    RE_NET_QTY = re.compile(
        r"""
        (?:(?:NET\s*(?:WT|WEIGHT|QTY|QUANTITY|CONTENT)?)|(?:QUANTITY)|(?:CONTENT))\b
        [^\d]*                                                 # Delimiter
        (?P<value>\d+(?:\.\d+)?)                               # Numerical value
        \s*
        (?P<unit>kg|g|gm|grams?|ml|l|ltr|litres?|N|units?|pcs|pieces|nos)\b # Legal SI units
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    # Standalone fallback quantity if preceded without keyword (e.g., "500 g", "1.5 kg")
    RE_STANDALONE_QTY = re.compile(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|gm|grams?|ml|l|ltr|litres?|N|units?|pcs|pieces|nos)\b",
        re.IGNORECASE,
    )

    # --------------------------------------------------------------------------
    # 3. Manufacture / Packing Date Patterns
    # --------------------------------------------------------------------------
    RE_MFG_DATE = re.compile(
        r"""
        (?:MFD|MFG|PKD|PACKED|DATE\s*OF\s*(?:MFG|PACKING|MANUFACTURE)|MFD\s*ON|PKD\s*ON)\b
        [^\w\d]*
        (?P<date>
            (?:\d{1,2}[\/\-\.]\d{2,4})                         # DD/MM/YYYY or MM/YYYY
            |
            (?:(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[a-z]*[\s\.\-\/]*\d{2,4}) # Month YYYY
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    RE_DATE_ONLY = re.compile(
        r"\b(?P<date>(?:0[1-9]|1[0-2])[\/\-](?:20\d{2}|\d{2}))\b" # MM/YYYY or MM/YY
    )

    # --------------------------------------------------------------------------
    # 4. Country of Origin Patterns
    # --------------------------------------------------------------------------
    RE_ORIGIN = re.compile(
        r"""
        (?:COUNTRY\s*OF\s*ORIGIN|MADE\s*IN|PRODUCT\s*OF|MANUFACTURED\s*IN)\b
        [\s\:\-]+
        (?P<country>[A-Za-z\s]{2,25})
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # --------------------------------------------------------------------------
    # 5. Manufacturer / Packer Patterns
    # --------------------------------------------------------------------------
    RE_MFG_KEYWORD = re.compile(
        r"\b(?:MFD\.?\s*BY|MANUFACTURED\s*(?:AND\s*PACKED\s*)?BY|PACKED\s*BY|MKTD\.?\s*BY|MARKETED\s*BY|PRODUCED\s*BY|IMPORTED\s*BY)\b",
        re.IGNORECASE,
    )
    RE_PINCODE = re.compile(r"\b\d{6}\b")

    # --------------------------------------------------------------------------
    # 6. Consumer Care Patterns
    # --------------------------------------------------------------------------
    RE_CARE_KEYWORD = re.compile(
        r"\b(?:CUSTOMER\s*CARE|CONSUMER\s*CARE|FEEDBACK|QUERIES|COMPLAINTS?|CARE\s*EXECUTIVE|CONTACT\s*US)\b",
        re.IGNORECASE,
    )
    RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    RE_PHONE = re.compile(
        r"(?:(?:(?:\+?91[\-\s]?)?|0)?(?:1800|1860)[\-\s]?\d{3}[\-\s]?\d{3,4}|\b\d{10}\b|\b\d{3,5}[\-\s]\d{6,8}\b)"
    )

    @classmethod
    def extract_mrp(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Maximum Retail Price with tax qualification."""
        for i, line in enumerate(lines):
            text = line.text
            match = cls.RE_MRP_FULL.search(text)
            if match:
                amount = match.group("amount")
                # Look for tax qualifier in current line or next line
                tax_match = cls.RE_TAX_QUALIFIER.search(text)
                if not tax_match and i + 1 < len(lines):
                    tax_match = cls.RE_TAX_QUALIFIER.search(lines[i + 1].text)

                currency = "₹" if "₹" in text else "Rs."
                if tax_match or "TAX" in text.upper():
                    return f"{currency} {amount} (INCL. OF ALL TAXES)"
                return f"{currency} {amount}"

            # Fallback if keyword detected but regex missed
            if cls.RE_MRP_KEYWORD.search(text):
                digit_match = re.search(r"(?:₹|Rs\.?|INR)?\s*(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE)
                if digit_match:
                    amount = digit_match.group(1)
                    tax_match = cls.RE_TAX_QUALIFIER.search(text)
                    if not tax_match and i + 1 < len(lines):
                        tax_match = cls.RE_TAX_QUALIFIER.search(lines[i + 1].text)
                    tax = " (INCL. OF ALL TAXES)" if (tax_match or "TAX" in text.upper()) else ""
                    currency = "₹" if "₹" in text else "Rs."
                    return f"{currency} {amount}{tax}"

        return None

    @classmethod
    def extract_net_quantity(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Net Quantity with SI unit."""
        for line in lines:
            text = line.text
            match = cls.RE_NET_QTY.search(text)
            if match:
                val = match.group("value")
                unit = match.group("unit").strip()
                # Standardize unit representation
                unit_clean = cls._standardize_unit(unit)
                return f"{val} {unit_clean}"

        # Secondary search for isolated declarations (e.g. "NET WT 500g")
        for line in lines:
            text = line.text
            if "NET" in text.upper() or "QTY" in text.upper() or "WEIGHT" in text.upper():
                match = cls.RE_STANDALONE_QTY.search(text)
                if match:
                    val = match.group("value")
                    unit = cls._standardize_unit(match.group("unit"))
                    return f"{val} {unit}"

        return None

    @staticmethod
    def _standardize_unit(unit_str: str) -> str:
        u = unit_str.lower()
        if u in ("g", "gm", "gram", "grams"):
            return "g"
        if u in ("kg", "kilogram", "kilograms"):
            return "kg"
        if u in ("ml", "millilitre", "millilitres"):
            return "ml"
        if u in ("l", "ltr", "litre", "litres"):
            return "l"
        if u in ("n", "unit", "units", "pc", "pcs", "piece", "pieces", "nos"):
            return "units"
        return unit_str

    @classmethod
    def extract_manufacture_date(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract Manufacturing / Packaging date in MM/YYYY format."""
        for line in lines:
            text = line.text
            match = cls.RE_MFG_DATE.search(text)
            if match:
                return match.group("date").strip()

        # Secondary search if keyword is in line
        for line in lines:
            text = line.text
            if any(k in text.upper() for k in ("MFD", "MFG", "PKD", "PACKED", "DATE")):
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
                country = match.group("country").strip().strip(":.-, ")
                # Capitalize nicely
                return country.title() if country.isupper() else country

            # Explicit check for common "Made in India"
            if "MADE IN INDIA" in text.upper():
                return "India"
            if "PRODUCT OF INDIA" in text.upper():
                return "India"

        return None

    @classmethod
    def extract_manufacturer(cls, lines: list[TextLine]) -> Optional[str]:
        """
        Extract Manufacturer/Packer name and address.
        Uses windowing to capture multi-line addresses ending with pincode or newline.
        """
        for i, line in enumerate(lines):
            text = line.text
            match = cls.RE_MFG_KEYWORD.search(text)
            if match:
                # Capture text after the keyword on the same line
                start_idx = match.end()
                initial_part = text[start_idx:].strip(" :.-")
                mfg_parts = [initial_part] if initial_part else []

                # Lookahead to subsequent lines for address continuation
                for next_idx in range(i + 1, min(len(lines), i + 4)):
                    next_line = lines[next_idx].text.strip()
                    # Stop if next line starts with another major declaration
                    if any(
                        p.search(next_line)
                        for p in (cls.RE_MRP_KEYWORD, cls.RE_CARE_KEYWORD, cls.RE_ORIGIN)
                    ):
                        break
                    mfg_parts.append(next_line)
                    # If we found a 6-digit Indian PIN code, address block is usually complete
                    if cls.RE_PINCODE.search(next_line):
                        break

                full_mfg = ", ".join(p for p in mfg_parts if p).strip(" ,.-")
                if full_mfg and len(full_mfg) >= 5:
                    return full_mfg

        return None

    @classmethod
    def extract_consumer_care(cls, lines: list[TextLine]) -> Optional[str]:
        """Extract customer support phone, email, or care cell contact."""
        care_contacts: list[str] = []

        # Find emails and phones globally across tokens
        all_text = " | ".join(l.text for l in lines)
        emails = cls.RE_EMAIL.findall(all_text)
        phones = cls.RE_PHONE.findall(all_text)

        # Look for explicit consumer care header line
        for i, line in enumerate(lines):
            text = line.text
            if cls.RE_CARE_KEYWORD.search(text):
                # Check for email / phone in this line or subsequent line
                line_window = text
                if i + 1 < len(lines):
                    line_window += " " + lines[i + 1].text

                w_emails = cls.RE_EMAIL.findall(line_window)
                w_phones = cls.RE_PHONE.findall(line_window)

                parts = []
                if w_emails:
                    parts.extend(w_emails)
                if w_phones:
                    parts.extend(w_phones)

                if parts:
                    return ", ".join(dict.fromkeys(parts)) # Deduplicate preserving order
                
                # If no phone/email found, return the cleaned line itself
                cleaned_line = cls.RE_CARE_KEYWORD.sub("", text).strip(" :.-|")
                if len(cleaned_line) > 5:
                    return cleaned_line

        # Fallback: if emails or toll-free phones exist anywhere on package
        if emails or phones:
            combined = emails + phones
            return ", ".join(dict.fromkeys(combined))

        return None

    @classmethod
    def extract_all_fields(cls, lines: list[TextLine]) -> LegalMetrologyFields:
        """
        Extract all six Rule 6 declarations and return a validated LegalMetrologyFields object.
        """
        return LegalMetrologyFields(
            mrp=cls.extract_mrp(lines),
            net_quantity=cls.extract_net_quantity(lines),
            manufacture_date=cls.extract_manufacture_date(lines),
            country_of_origin=cls.extract_country_of_origin(lines),
            manufacturer=cls.extract_manufacturer(lines),
            consumer_care=cls.extract_consumer_care(lines),
        )
