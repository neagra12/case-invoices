"""
Approval Agent
──────────────
Two-stage LLM reasoning with self-critique loop.

Stage 1: LLM analyses the invoice + validation flags → initial decision
Stage 2: LLM critiques its own decision → may revise

Rule: invoices over $10,000 always go through the full LLM loop.
      Clean invoices under $10,000 may be auto-approved.
"""

import json

import tools.llm as llm
from models.invoice import ApprovalResult, InvoiceData, ValidationResult

HIGH_VALUE_THRESHOLD = 10_000.0

_SYSTEM = """You are a VP of Finance at Acme Corp, a PE-backed manufacturing firm.
You are responsible for approving vendor invoices before payment.
You are analytically rigorous, skeptical of anomalies, but fair to legitimate vendors.
Always return valid JSON."""

_ANALYSIS_PROMPT = """Review this invoice and its validation findings, then decide whether to approve or reject.

── Invoice ──────────────────────────────────────────────────────
Invoice Number : {invoice_number}
Vendor         : {vendor}
Amount         : {currency} {total}
Date           : {date}
Due Date       : {due_date}
Payment Terms  : {payment_terms}
Items          :
{items_summary}

── Validation Findings ──────────────────────────────────────────
{validation_summary}

── Context ──────────────────────────────────────────────────────
High-value flag (>$10,000): {high_value}
Ingestion confidence      : {confidence}%
Ingestion anomalies       : {ingestion_flags}

── Instructions ─────────────────────────────────────────────────
Return JSON:
{{
  "approved": true or false,
  "reasoning": "Detailed reasoning. Address each validation flag explicitly.",
  "risk_level": "low" | "medium" | "high",
  "key_concerns": ["list of specific concerns, if any"]
}}"""

_CRITIQUE_PROMPT = """You previously reviewed invoice {invoice_number} and made this decision:

Decision  : {decision}
Risk Level: {risk_level}
Reasoning : {reasoning}
Concerns  : {concerns}

Now critique your own decision rigorously:
- If you APPROVED: Are you being too lenient? Could any flag indicate fraud or error?
  Consider: what's the cost if this is fraudulent or wrong?
- If you REJECTED: Are you being too strict? Could there be a legitimate business reason
  for each flag? Consider: what's the cost to vendor relationships of a wrong rejection?

Return JSON:
{{
  "critique": "Your self-critique (2-4 sentences)",
  "final_approved": true or false,
  "final_reasoning": "Updated reasoning if your decision changed, otherwise restate why you're confident"
}}"""


def run(state: dict) -> dict:
    """LangGraph node: approval."""
    log = []

    invoice = InvoiceData.model_validate(state["invoice_data"])
    validation = ValidationResult.model_validate(state["validation_result"])

    requires_scrutiny = invoice.total >= HIGH_VALUE_THRESHOLD
    has_errors = not validation.passed
    has_fraud = any(f.code == "FRAUD_SIGNAL" for f in validation.flags)

    # ── Fast-path: auto-approve clean, low-value invoices ─────────────────────
    if not has_errors and not requires_scrutiny and not has_fraud:
        result = ApprovalResult(
            approved=True,
            requires_scrutiny=False,
            reasoning=(
                f"Invoice passes all validation checks. "
                f"Amount ({invoice.currency} {invoice.total:,.2f}) is below the $10,000 scrutiny threshold. "
                "Auto-approved."
            ),
            critique="N/A - auto-approved, no scrutiny required.",
            final_decision="APPROVED",
        )
        log.append("[APPROVE] [OK] Auto-approved (clean, low-value invoice)")
        return {
            "approval_result": result.model_dump(mode="json"),
            "processing_log": log,
        }

    # ── Full LLM reasoning loop ────────────────────────────────────────────────
    if requires_scrutiny:
        log.append(f"[APPROVE] [HIGH]  High-value invoice (${invoice.total:,.2f}) - enhanced scrutiny active")

    items_summary = _format_items(invoice)
    validation_summary = _format_validation(validation)
    ingestion_flags = "; ".join(invoice.ingestion_flags) or "None"

    analysis_msg = _ANALYSIS_PROMPT.format(
        invoice_number=invoice.invoice_number,
        vendor=invoice.vendor or "(unknown)",
        currency=invoice.currency,
        total=f"{invoice.total:,.2f}",
        date=str(invoice.date or "N/A"),
        due_date=str(invoice.due_date or "N/A"),
        payment_terms=invoice.payment_terms or "N/A",
        items_summary=items_summary,
        validation_summary=validation_summary,
        high_value="YES - requires extra scrutiny" if requires_scrutiny else "No",
        confidence=f"{invoice.confidence * 100:.0f}",
        ingestion_flags=ingestion_flags,
    )

    try:
        analysis = llm.chat_json([
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": analysis_msg},
        ])
    except Exception as e:
        log.append(f"[APPROVE] LLM error during analysis: {e}")
        return {"error": f"Approval agent LLM error: {e}", "processing_log": log}

    initial_approved = bool(analysis.get("approved", False))
    reasoning = str(analysis.get("reasoning", ""))
    risk_level = str(analysis.get("risk_level", "medium"))
    concerns = analysis.get("key_concerns", [])

    log.append(f"[APPROVE] Initial decision: {'APPROVED' if initial_approved else 'REJECTED'} (risk: {risk_level})")

    # ── Self-critique loop ─────────────────────────────────────────────────────
    critique_msg = _CRITIQUE_PROMPT.format(
        invoice_number=invoice.invoice_number,
        decision="APPROVED" if initial_approved else "REJECTED",
        risk_level=risk_level,
        reasoning=reasoning,
        concerns=json.dumps(concerns),
    )

    try:
        critique = llm.chat_json([
            {"role": "system",    "content": _SYSTEM},
            {"role": "user",      "content": analysis_msg},
            {"role": "assistant", "content": json.dumps(analysis)},
            {"role": "user",      "content": critique_msg},
        ])
    except Exception as e:
        log.append(f"[APPROVE] LLM error during critique: {e} - using initial decision")
        critique = {
            "critique": "Critique unavailable due to LLM error.",
            "final_approved": initial_approved,
            "final_reasoning": reasoning,
        }

    final_approved = bool(critique.get("final_approved", initial_approved))
    final_reasoning = str(critique.get("final_reasoning", reasoning))
    critique_text = str(critique.get("critique", ""))

    if final_approved != initial_approved:
        log.append(
            f"[APPROVE] [REVISED] Decision revised after critique: "
            f"{'APPROVED' if final_approved else 'REJECTED'}"
        )
    else:
        log.append(
            f"[APPROVE] Decision confirmed: {'[OK] APPROVED' if final_approved else '[FAIL] REJECTED'}"
        )

    result = ApprovalResult(
        approved=final_approved,
        requires_scrutiny=requires_scrutiny,
        reasoning=final_reasoning,
        critique=critique_text,
        final_decision="APPROVED" if final_approved else "REJECTED",
    )

    return {
        "approval_result": result.model_dump(mode="json"),
        "processing_log": log,
    }


# ── Formatters ─────────────────────────────────────────────────────────────────

def _format_items(invoice: InvoiceData) -> str:
    lines = []
    for li in invoice.line_items:
        note = f" [{li.note}]" if li.note else ""
        lines.append(
            f"  • {li.item}: qty {li.quantity} × ${li.unit_price:,.2f} = ${li.quantity * li.unit_price:,.2f}{note}"
        )
    return "\n".join(lines) or "  (none)"


def _format_validation(vr: ValidationResult) -> str:
    if not vr.flags:
        return "  [OK] No issues found"
    lines = []
    for f in vr.flags:
        icon = "[FAIL]" if f.severity == "error" else ("[WARN]" if f.severity == "warning" else "[INFO]")
        lines.append(f"  {icon} [{f.severity.upper()}] {f.message}")
    return "\n".join(lines)
