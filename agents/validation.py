"""
Validation Agent
────────────────
Checks extracted InvoiceData against the inventory database and business rules.
Returns a ValidationResult with severity-tagged flags.
Does NOT make approval decisions - that is the Approval Agent's job.
"""

from collections import defaultdict

from models.invoice import InvoiceData, ValidationFlag, ValidationResult
from tools.inventory import check_duplicate, check_item


def run(state: dict) -> dict:
    """LangGraph node: validation."""
    log = []

    if not state.get("invoice_data"):
        return {
            "error": "No invoice data to validate",
            "processing_log": log,
        }

    invoice = InvoiceData.model_validate(state["invoice_data"])
    flags: list[ValidationFlag] = []

    # ── 1. Duplicate detection ─────────────────────────────────────────────────
    dup = check_duplicate(invoice.invoice_number)
    is_duplicate = dup["is_duplicate"]

    if is_duplicate:
        # Check if this is a revision (INV-1004_revised scenario)
        revision = _extract_revision(state.get("invoice_data", {}))
        if revision:
            flags.append(ValidationFlag(
                severity="warning",
                code="DUPLICATE_REVISION",
                message=(
                    f"Revised invoice - original {invoice.invoice_number} "
                    f"processed on {dup['first_seen']} (status: {dup['status']}). "
                    f"Revision: {revision}. Proceeding with caution."
                ),
            ))
            is_duplicate = False  # allow revisions through for human review
        else:
            flags.append(ValidationFlag(
                severity="error",
                code="DUPLICATE_INVOICE",
                message=(
                    f"Invoice {invoice.invoice_number} already processed on "
                    f"{dup['first_seen']} with status '{dup['status']}'. "
                    "Rejecting as duplicate."
                ),
            ))
            log.append(f"[VALIDATE] [FAIL] Duplicate invoice: {invoice.invoice_number}")
            return {
                "validation_result": ValidationResult(
                    passed=False, flags=flags, is_duplicate=True
                ).model_dump(mode="json"),
                "processing_log": log,
            }

    # ── 2. Required field checks ───────────────────────────────────────────────
    if not invoice.vendor or invoice.vendor.strip() == "":
        flags.append(ValidationFlag(
            severity="error",
            code="MISSING_VENDOR",
            message="Invoice has no vendor name",
        ))

    if invoice.due_date is None:
        flags.append(ValidationFlag(
            severity="warning",
            code="MISSING_DUE_DATE",
            message="Invoice is missing a valid due date",
        ))

    if invoice.total <= 0:
        flags.append(ValidationFlag(
            severity="error",
            code="INVALID_TOTAL",
            message=f"Invoice total is non-positive: {invoice.total}",
        ))

    if not invoice.line_items:
        flags.append(ValidationFlag(
            severity="error",
            code="NO_LINE_ITEMS",
            message="Invoice has no line items",
        ))

    # ── 3. Negative or zero quantities ────────────────────────────────────────
    for li in invoice.line_items:
        if li.quantity < 0:
            flags.append(ValidationFlag(
                severity="error",
                code="NEGATIVE_QUANTITY",
                message=f"Item '{li.item}' has negative quantity: {li.quantity}",
                item=li.item,
            ))
        elif li.quantity == 0:
            flags.append(ValidationFlag(
                severity="warning",
                code="ZERO_QUANTITY",
                message=f"Item '{li.item}' has zero quantity",
                item=li.item,
            ))

    # ── 4. Currency check ──────────────────────────────────────────────────────
    if invoice.currency != "USD":
        flags.append(ValidationFlag(
            severity="warning",
            code="FOREIGN_CURRENCY",
            message=f"Invoice is in {invoice.currency}, not USD. Requires manual FX review.",
        ))

    # ── 5. Inventory checks (aggregate per item to catch INV-1013 pattern) ────
    # Aggregate quantities: same item may appear multiple times (bulk orders, discounts)
    aggregated: dict[str, float] = defaultdict(float)
    for li in invoice.line_items:
        if li.quantity > 0:  # skip negative (already flagged)
            aggregated[li.item] += li.quantity

    for item_name, total_qty in aggregated.items():
        result = check_item(item_name, total_qty)

        if result.get("fuzzy_matched"):
            flags.append(ValidationFlag(
                severity="info",
                code="ITEM_NAME_FUZZY_MATCHED",
                message=(
                    f"Item '{item_name}' matched to '{result['item']}' "
                    "via fuzzy name matching (possible OCR/formatting issue)"
                ),
                item=item_name,
            ))

        if result["status"] == "unknown":
            flags.append(ValidationFlag(
                severity="error",
                code="UNKNOWN_ITEM",
                message=f"Item '{item_name}' not found in inventory",
                item=item_name,
            ))
        elif result["status"] == "zero_stock":
            flags.append(ValidationFlag(
                severity="error",
                code="ZERO_STOCK",
                message=(
                    f"Item '{result['item']}' has zero stock in inventory. "
                    "This may indicate a fraudulent or invalid order."
                ),
                item=item_name,
            ))
        elif result["status"] == "exceeds_stock":
            flags.append(ValidationFlag(
                severity="error",
                code="EXCEEDS_STOCK",
                message=(
                    f"Item '{result['item']}': requested {total_qty:.0f} units, "
                    f"only {result['available']} in stock"
                ),
                item=item_name,
            ))
        # "ok" → no flag

    # ── 6. Ingestion-level fraud signals ──────────────────────────────────────
    for ing_flag in invoice.ingestion_flags:
        if "Fraud signal" in ing_flag:
            flags.append(ValidationFlag(
                severity="error",
                code="FRAUD_SIGNAL",
                message=ing_flag,
            ))
        elif "Math mismatch" in ing_flag:
            flags.append(ValidationFlag(
                severity="warning",
                code="MATH_MISMATCH",
                message=ing_flag,
            ))

    # ── 7. Determine overall pass/fail ─────────────────────────────────────────
    errors = [f for f in flags if f.severity == "error"]
    passed = len(errors) == 0

    for f in flags:
        icon = "[FAIL]" if f.severity == "error" else ("[WARN]" if f.severity == "warning" else "[INFO]")
        log.append(f"[VALIDATE] {icon} [{f.code}] {f.message}")

    if passed:
        log.append("[VALIDATE] [OK] All checks passed")
    else:
        log.append(f"[VALIDATE] [FAIL] {len(errors)} error(s) found - invoice will not auto-approve")

    return {
        "validation_result": ValidationResult(
            passed=passed, flags=flags, is_duplicate=is_duplicate
        ).model_dump(mode="json"),
        "processing_log": log,
    }


def _extract_revision(invoice_data: dict) -> str | None:
    """Check for a revision marker in raw invoice data."""
    raw = invoice_data.get("raw_text", "") or ""
    # Look for "revision", "R1", "revised" in raw text
    import re
    match = re.search(r"\b(R\d+|revision[\s:]+\w+|revised)\b", raw, re.IGNORECASE)
    if match:
        return match.group(0)
    # Also check structured fields
    if invoice_data.get("revision"):
        return str(invoice_data["revision"])
    return None
