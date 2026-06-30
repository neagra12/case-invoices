"""
Payment Agent
─────────────
If approved: calls mock_payment() and records the transaction.
If rejected: logs the rejection with full reasoning.
"""

from models.invoice import ApprovalResult, InvoiceData, PaymentResult
from tools.inventory import record_invoice
from tools.payment import mock_payment


def run(state: dict) -> dict:
    """LangGraph node: payment."""
    log = []

    invoice = InvoiceData.model_validate(state["invoice_data"])
    approval = ApprovalResult.model_validate(state["approval_result"])

    if approval.approved:
        try:
            result = mock_payment(
                vendor=invoice.vendor,
                amount=invoice.total,
                invoice_number=invoice.invoice_number,
            )
            record_invoice(
                invoice_number=invoice.invoice_number,
                status="paid",
                vendor=invoice.vendor,
                total=invoice.total,
            )
            payment_result = PaymentResult(
                status="paid",
                detail=(
                    f"Payment of {invoice.currency} {invoice.total:,.2f} "
                    f"sent to {invoice.vendor}. "
                    f"Transaction ID: {result.get('transaction_id', 'N/A')}"
                ),
                vendor=invoice.vendor,
                amount=invoice.total,
            )
            log.append(
                f"[PAYMENT] [OK] Paid {invoice.currency} {invoice.total:,.2f} "
                f"to {invoice.vendor} - txn {result.get('transaction_id')}"
            )
        except Exception as e:
            record_invoice(
                invoice_number=invoice.invoice_number,
                status="payment_error",
                vendor=invoice.vendor,
                total=invoice.total,
            )
            payment_result = PaymentResult(
                status="error",
                detail=f"Payment API error: {e}",
                vendor=invoice.vendor,
                amount=invoice.total,
            )
            log.append(f"[PAYMENT] [FAIL] Payment failed: {e}")

    else:
        record_invoice(
            invoice_number=invoice.invoice_number,
            status="rejected",
            vendor=invoice.vendor,
            total=invoice.total,
        )
        payment_result = PaymentResult(
            status="rejected",
            detail=(
                f"Invoice rejected by VP approval.\n"
                f"Reasoning: {approval.reasoning}\n"
                f"Critique: {approval.critique}"
            ),
            vendor=invoice.vendor,
            amount=invoice.total,
        )
        log.append(
            f"[PAYMENT] [FAIL] Rejected - {invoice.invoice_number} ({invoice.vendor})"
        )

    return {
        "payment_result": payment_result.model_dump(mode="json"),
        "processing_log": log,
    }
