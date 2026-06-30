"""
Format-specific parsers that convert raw invoice files into clean intermediate text.
The LLM in the ingestion agent then normalises this text into structured InvoiceData.
"""

import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from io import StringIO


# ── Public entry point ─────────────────────────────────────────────────────────

def parse_invoice_file(path: str) -> dict:
    """
    Detect format and parse into an intermediate dict:
      {
        "format":         str,
        "raw_text":       str,   # clean text for LLM
        "structured":     dict,  # partially parsed (may be empty)
        "parse_warnings": list[str],
      }
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Invoice file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    raw_bytes = open(path, "rb").read()

    # PDF detection (by magic bytes, not just extension)
    if raw_bytes[:4] == b"%PDF" or ext == ".pdf":
        return _parse_pdf(path)

    text = raw_bytes.decode("utf-8", errors="replace")

    if ext == ".json":
        return _parse_json(text, path)
    if ext == ".xml":
        return _parse_xml(text, path)
    if ext == ".csv":
        return _parse_csv(text, path)
    # .txt or unknown — sniff for email headers
    if _looks_like_email(text):
        return _parse_email(text, path)
    return _parse_txt(text, path)


# ── Format detectors ───────────────────────────────────────────────────────────

def _looks_like_email(text: str) -> bool:
    return bool(re.search(r"^(From|To|Subject):\s+", text, re.MULTILINE | re.IGNORECASE))


# ── Individual parsers ─────────────────────────────────────────────────────────

def _parse_json(text: str, path: str) -> dict:
    warnings = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        warnings.append(f"JSON parse error: {e}")
        data = {}

    # Flatten nested vendor dict if present
    if isinstance(data.get("vendor"), dict):
        data["vendor_name"] = data["vendor"].get("name", "")
        data["vendor_address"] = data["vendor"].get("address", "")
        data["vendor"] = data["vendor_name"]

    return {
        "format": "json",
        "raw_text": json.dumps(data, indent=2),
        "structured": data,
        "parse_warnings": warnings,
    }


def _parse_csv(text: str, path: str) -> dict:
    warnings = []
    lines = [l for l in text.strip().splitlines() if l.strip()]

    if not lines:
        return {"format": "csv", "raw_text": text, "structured": {}, "parse_warnings": ["Empty CSV"]}

    first_line = lines[0].lower()

    # Key-value layout: "field,value" (INV-1006)
    if first_line.startswith("field,value"):
        return _parse_csv_kv(text, path)

    # Columnar layout: standard header row (INV-1007, INV-1015)
    return _parse_csv_columnar(text, path)


def _parse_csv_kv(text: str, path: str) -> dict:
    """field,value CSV format (INV-1006)."""
    rows = list(csv.reader(StringIO(text)))
    structured: dict = {"line_items": []}
    warnings = []
    current_item: dict = {}

    for row in rows[1:]:  # skip header
        if len(row) < 2:
            continue
        key, val = row[0].strip().lower(), row[1].strip()
        if not val:
            continue

        if key == "item":
            if current_item.get("item"):
                structured["line_items"].append(current_item)
            current_item = {"item": val}
        elif key == "quantity":
            current_item["quantity"] = _safe_float(val)
        elif key == "unit_price":
            current_item["unit_price"] = _safe_float(val)
        else:
            structured[key] = val

    if current_item.get("item"):
        structured["line_items"].append(current_item)

    return {
        "format": "csv-kv",
        "raw_text": _dict_to_readable(structured),
        "structured": structured,
        "parse_warnings": warnings,
    }


def _parse_csv_columnar(text: str, path: str) -> dict:
    """Standard columnar CSV (INV-1007, INV-1015)."""
    rows = list(csv.reader(StringIO(text)))
    warnings = []

    if not rows:
        return {"format": "csv", "raw_text": text, "structured": {}, "parse_warnings": ["Empty"]}

    header = [h.strip().lower() for h in rows[0]]
    structured: dict = {"line_items": []}
    meta_extracted = False

    for row in rows[1:]:
        if len(row) < len(header):
            row += [""] * (len(header) - len(row))

        rec = dict(zip(header, [c.strip() for c in row]))

        # Summary rows (subtotal/tax/total)
        label = (rec.get("item") or rec.get("") or "").lower()
        if any(k in label for k in ("subtotal", "tax", "total", "shipping")):
            amount_cols = [c for c in ["line total", "amount"] if c in rec]
            if amount_cols:
                val = _safe_float(rec[amount_cols[0]])
                if "subtotal" in label:
                    structured["subtotal"] = val
                elif "tax" in label:
                    structured["tax"] = val
                elif "total" in label and "subtotal" not in label:
                    structured["total"] = val
            continue

        # Meta fields (invoice number, vendor, date) — from first data row
        if not meta_extracted:
            for col in ("invoice number", "invoice_number"):
                if col in rec and rec[col]:
                    structured["invoice_number"] = rec[col]
            for col in ("vendor",):
                if col in rec and rec[col]:
                    structured["vendor"] = rec[col]
            for col in ("date",):
                if col in rec and rec[col]:
                    structured["date"] = rec[col]
            for col in ("due date", "due_date"):
                if col in rec and rec[col]:
                    structured["due_date"] = rec[col]
            meta_extracted = True

        # Line item
        item_col = next((c for c in ("item",) if c in rec and rec[c]), None)
        qty_col = next((c for c in ("qty", "quantity") if c in rec), None)
        price_col = next((c for c in ("unit price", "unit_price") if c in rec), None)

        if item_col and rec.get(item_col):
            line: dict = {"item": rec[item_col]}
            if qty_col:
                line["quantity"] = _safe_float(rec[qty_col])
            if price_col:
                line["unit_price"] = _safe_float(rec[price_col])
            structured["line_items"].append(line)

    return {
        "format": "csv-columnar",
        "raw_text": _dict_to_readable(structured),
        "structured": structured,
        "parse_warnings": warnings,
    }


def _parse_xml(text: str, path: str) -> dict:
    warnings = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        warnings.append(f"XML parse error: {e}")
        return {"format": "xml", "raw_text": text, "structured": {}, "parse_warnings": warnings}

    def tag(node, name):
        el = node.find(name)
        return el.text.strip() if el is not None and el.text else None

    structured: dict = {"line_items": []}

    header = root.find("header") or root
    structured["invoice_number"] = tag(header, "invoice_number")
    structured["vendor"] = tag(header, "vendor")
    structured["date"] = tag(header, "date")
    structured["due_date"] = tag(header, "due_date")
    structured["currency"] = tag(header, "currency")
    structured["payment_terms"] = tag(root, "payment_terms")

    totals = root.find("totals")
    if totals is not None:
        structured["subtotal"] = _safe_float(tag(totals, "subtotal") or "")
        structured["tax"] = _safe_float(tag(totals, "tax_amount") or "")
        structured["total"] = _safe_float(tag(totals, "total") or "")

    for item_el in root.findall(".//item"):
        line: dict = {}
        for key in ("name", "quantity", "unit_price"):
            val = tag(item_el, key)
            if val:
                line["item" if key == "name" else key] = (
                    _safe_float(val) if key in ("quantity", "unit_price") else val
                )
        if line.get("item"):
            structured["line_items"].append(line)

    return {
        "format": "xml",
        "raw_text": _dict_to_readable(structured),
        "structured": structured,
        "parse_warnings": warnings,
    }


def _parse_pdf(path: str) -> dict:
    warnings = []
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages_text = []
            for page in pdf.pages:
                pt = page.extract_text() or ""
                pages_text.append(pt)
        raw_text = "\n".join(pages_text).strip()
    except Exception as e:
        warnings.append(f"PDF extraction error: {e}")
        raw_text = ""

    if not raw_text:
        warnings.append("No text extracted from PDF — may be a scanned image")

    return {
        "format": "pdf",
        "raw_text": raw_text,
        "structured": {},
        "parse_warnings": warnings,
    }


def _parse_email(text: str, path: str) -> dict:
    """Strip email headers and extract invoice body."""
    warnings = []
    lines = text.splitlines()
    body_start = 0

    # Find blank line after headers
    for i, line in enumerate(lines):
        if line.strip() == "":
            body_start = i + 1
            break

    body = "\n".join(lines[body_start:]).strip()

    return {
        "format": "email",
        "raw_text": body,
        "structured": {},
        "parse_warnings": warnings,
    }


def _parse_txt(text: str, path: str) -> dict:
    """Plain text invoice — pass through for LLM normalisation."""
    return {
        "format": "txt",
        "raw_text": text.strip(),
        "structured": {},
        "parse_warnings": [],
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_float(s: str) -> float:
    if not s:
        return 0.0
    cleaned = re.sub(r"[^\d.\-]", "", str(s))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _dict_to_readable(d: dict, indent: int = 0) -> str:
    lines = []
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, list):
            lines.append(f"{prefix}{k}:")
            for item in v:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  - " + ", ".join(f"{ik}: {iv}" for ik, iv in item.items()))
                else:
                    lines.append(f"{prefix}  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            lines.append(_dict_to_readable(v, indent + 1))
        else:
            lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)
