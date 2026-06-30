"""
Mock payment API — simulates an external banking integration.
"""

import time
from datetime import datetime, timezone


def mock_payment(vendor: str, amount: float, invoice_number: str = "") -> dict:
    """
    Simulate processing a payment.
    In a real system this would call a banking API.
    Returns {"status": "success", ...}
    """
    # Simulate brief processing time
    time.sleep(0.1)

    label = f"[{invoice_number}] " if invoice_number else ""
    print(f"  [PAID]  {label}Paid ${amount:,.2f} to {vendor}")

    return {
        "status": "success",
        "vendor": vendor,
        "amount": amount,
        "invoice_number": invoice_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transaction_id": f"TXN-{int(time.time() * 1000)}",
    }
