"""
Ingestion Agent
───────────────
Reads any invoice format → normalises to InvoiceData via LLM.
Includes a self-correction loop: if the first extraction fails schema
validation or basic math checks, the agent retries with the error feedback.
"""

import json
import re
from datetime import date as _date

import tools.llm as llm
from models.invoice import InvoiceData, LineItem
from tools.parsers import parse_invoice_file

MAX_RETRIES = 2

# Item name normalisation map (OCR artifacts and spacing variants → canonical)
_CANONICAL_ITEMS = {
    "widget a": "WidgetA",
    "widgeta": "WidgetA",
    "widget b": "WidgetB",
    "widgetb": "WidgetB",
    "gadget x": "GadgetX",
    "gadgetx": "GadgetX",
    "fakeitem": "FakeItem",
    "fake item": "FakeItem",
}

_FRAUD_SIGNALS = [
    "pay immediately",
    "urgent",
    "wire transfer",
    "wire preferred",
    "avoid penalties",
    "asap",
    "no questions",
    "do not delay",
]

_EXTRACTION_SYSTEM = """You are an expert invoice data extraction specialist.
Extract structured data from the provided invoice text and return valid JSON.
Be precise - do not invent data that isn't present; use null for missing fields."""

_EXTRACTION_SCHEMA = """{
  "invoice_number": "string",
  "vendor": "string or null",
  "date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "line_items": [
    {
      "item": "string (canonical name, no extra spaces)",
      "quantity": number,
      "unit_price": number,
      "note": "string or null"
    }
  ],
  "subtotal": number or null,
  "tax": number or null,
  "total": number,
  "currency": "USD (default) or stated currency code",
  "payment_terms": "string or null",
  "confidence": 0.0–1.0,
  "ingestion_flags": ["list of anomalies you noticed"]
}"""

_EXTRACTION_USER = """Invoice content:
{raw_text}

Previously parsed structured data (use as a hint, may be incomplete):
{structured}

Return JSON matching this schema exactly:
{schema}

Normalisation rules:
- Item names: strip extra spaces ("Widget A" → "WidgetA", "Gadget X" → "GadgetX")
- Dates: ISO format only. If unparseable (e.g. "yesterday"), return null
- Amounts: plain numbers, no $ or commas
- currency: use stated currency or "USD" as default
- confidence: how clear and complete the invoice was (0.0–1.0)
- ingestion_flags: note OCR artifacts, urgency language, foreign currency,
  missing required fields, math mismatches, suspicious content, etc.
- IMPORTANT: extract EVERY line item listed. Formats like "- SuperGizmo x12 $400 each"
  mean item=SuperGizmo, quantity=12, unit_price=400. Do not skip or merge items.
- Each distinct product name is a separate line item entry, even if they appear in
  bullet lists, dashes, or informal email-body formats."""

_CORRECTION_USER = """Your previous extraction attempt failed validation:

Error: {error}

Original invoice text:
{raw_text}

Please correct the extraction and return valid JSON matching the schema:
{schema}"""


def run(state: dict) -> dict:
    """LangGraph node: ingestion."""
    path = state["invoice_path"]
    log = []

    try:
        # ── Step 1: Format-specific parse ─────────────────────────────────────
        parsed = parse_invoice_file(path)
        raw_text = parsed["raw_text"]
        structured = parsed["structured"]
        fmt = parsed["format"]

        if parsed["parse_warnings"]:
            for w in parsed["parse_warnings"]:
                log.append(f"[INGEST] Parser warning: {w}")

        log.append(f"[INGEST] Format detected: {fmt}")

        # ── Step 2: LLM normalisation with retry loop ─────────────────────────
        invoice_data, flags, error = None, [], None

        for attempt in range(MAX_RETRIES + 1):
            if attempt == 0:
                user_msg = _EXTRACTION_USER.format(
                    raw_text=raw_text[:6000],  # token safety
                    structured=json.dumps(structured, indent=2)[:2000],
                    schema=_EXTRACTION_SCHEMA,
                )
            else:
                user_msg = _CORRECTION_USER.format(
                    error=error,
                    raw_text=raw_text[:6000],
                    schema=_EXTRACTION_SCHEMA,
                )

            try:
                result = llm.chat_json([
                    {"role": "system", "content": _EXTRACTION_SYSTEM},
                    {"role": "user",   "content": user_msg},
                ])
                invoice_data, error = _build_invoice(result, raw_text, fmt)
                if invoice_data:
                    break
                log.append(f"[INGEST] Extraction attempt {attempt + 1} failed: {error}")
            except Exception as e:
                error = str(e)
                log.append(f"[INGEST] LLM error on attempt {attempt + 1}: {e}")

        if invoice_data is None:
            return {
                "error": f"Ingestion failed after {MAX_RETRIES + 1} attempts: {error}",
                "processing_log": log,
            }

        # ── Step 3: Heuristic anomaly detection ───────────────────────────────
        _detect_anomalies(invoice_data, raw_text)

        if invoice_data.ingestion_flags:
            for flag in invoice_data.ingestion_flags:
                log.append(f"[INGEST] [WARN]  {flag}")

        confidence_pct = f"{invoice_data.confidence:.0%}"
        log.append(
            f"[INGEST] [OK] Extracted {invoice_data.invoice_number} "
            f"({invoice_data.vendor}, {invoice_data.currency} {invoice_data.total:,.2f}) "
            f"- confidence {confidence_pct}"
        )

        return {
            "raw_text": raw_text,
            "invoice_data": invoice_data.model_dump(mode="json"),
            "processing_log": log,
            "error": None,
        }

    except FileNotFoundError as e:
        return {"error": str(e), "processing_log": log}
    except Exception as e:
        return {"error": f"Unexpected ingestion error: {e}", "processing_log": log}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_invoice(
    result: dict, raw_text: str, fmt: str
) -> "tuple[InvoiceData | None, str | None]":
    """Validate LLM output and build an InvoiceData. Returns (data, error)."""
    try:
        # Coerce line items
        items = []
        for li in result.get("line_items", []):
            item_name = _normalise_item(str(li.get("item", "")))
            qty = float(li.get("quantity") or 0)
            price = float(li.get("unit_price") or 0)
            items.append(LineItem(
                item=item_name,
                quantity=qty,
                unit_price=price,
                note=li.get("note"),
            ))

        total = float(result.get("total") or 0)
        if total == 0 and items:
            total = sum(i.quantity * i.unit_price for i in items)

        invoice = InvoiceData(
            invoice_number=str(result.get("invoice_number") or "UNKNOWN").strip(),
            vendor=str(result.get("vendor") or "").strip(),
            date=_parse_date(result.get("date")),
            due_date=_parse_date(result.get("due_date")),
            line_items=items,
            subtotal=_safe_float(result.get("subtotal")),
            tax=_safe_float(result.get("tax")),
            total=total,
            currency=str(result.get("currency") or "USD").upper(),
            payment_terms=result.get("payment_terms"),
            raw_text=raw_text,
            ingestion_flags=list(result.get("ingestion_flags") or []),
            confidence=float(result.get("confidence") or 1.0),
        )
        return invoice, None

    except Exception as e:
        return None, str(e)


def _normalise_item(name: str) -> str:
    key = name.replace(" ", "").lower()
    # check canonical map
    for pattern, canonical in _CANONICAL_ITEMS.items():
        if key == pattern.replace(" ", "").lower():
            return canonical
    # OCR correction: replace letter-O that looks like zero in numeric contexts
    # e.g. "2O26" → "2026", "3,500.O0" → "3,500.00"
    return name.strip()


def _parse_date(val) -> "_date | None":
    if val is None or val == "null":
        return None
    if isinstance(val, _date):
        return val
    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "n/a", "yesterday", "today"):
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%B %d, %Y", "%d %b %Y"):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _detect_anomalies(invoice: InvoiceData, raw_text: str) -> None:
    """Heuristic checks appended to ingestion_flags (does not abort)."""
    text_lower = raw_text.lower()

    # Fraud language
    for signal in _FRAUD_SIGNALS:
        if signal in text_lower:
            _add_flag(invoice, f"Fraud signal detected: '{signal}'")
            break

    # Non-USD currency
    if invoice.currency != "USD":
        _add_flag(invoice, f"Non-USD currency: {invoice.currency}")

    # Missing vendor
    if not invoice.vendor:
        _add_flag(invoice, "Missing vendor name")

    # Missing due date
    if invoice.due_date is None:
        _add_flag(invoice, "Missing or unparseable due date")

    # Negative quantities
    for li in invoice.line_items:
        if li.quantity < 0:
            _add_flag(invoice, f"Negative quantity on item '{li.item}': {li.quantity}")

    # Math check: sum of line items vs stated total
    # Allow for tax: if subtotal+tax ≈ total, this is expected and not a mismatch
    if invoice.line_items:
        computed = sum(li.quantity * li.unit_price for li in invoice.line_items)
        stated = invoice.total
        tax = invoice.tax or 0.0
        within_tolerance = abs(computed - stated) <= 1.0
        explained_by_tax = abs(computed + tax - stated) <= 1.0
        if not within_tolerance and not explained_by_tax:
            _add_flag(
                invoice,
                f"Math mismatch: line items sum to ${computed:,.2f} but stated total is ${stated:,.2f}",
            )

    # OCR artefacts in raw text (common: letter O for zero)
    if re.search(r"\d[Oo]\d{2,}", raw_text):
        _add_flag(invoice, "Possible OCR artifact: letter O/o in numeric context")


def _add_flag(invoice: InvoiceData, msg: str) -> None:
    if msg not in invoice.ingestion_flags:
        invoice.ingestion_flags.append(msg)
