"""
SQLite inventory query tools used by the validation agent.
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "inventory.db")


def _conn() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise RuntimeError(
            f"Database not found at {DB_PATH}. Run `python setup_db.py` first."
        )
    return sqlite3.connect(DB_PATH)


# ── Inventory queries ──────────────────────────────────────────────────────────

def check_item(item: str, quantity: float) -> dict:
    """
    Check a single item against inventory.
    Returns:
      status   : "ok" | "exceeds_stock" | "zero_stock" | "unknown"
      available: int stock level (0 if unknown)
      item     : canonical item name (corrected if fuzzy-matched)
    """
    conn = _conn()
    cursor = conn.cursor()

    # Exact match first
    cursor.execute("SELECT item, stock FROM inventory WHERE item = ?", (item,))
    row = cursor.fetchone()

    if row is None:
        # Fuzzy match: strip spaces, case-insensitive
        cursor.execute("SELECT item, stock FROM inventory")
        all_items = cursor.fetchall()
        conn.close()

        normalised = item.replace(" ", "").lower()
        for db_item, stock in all_items:
            if db_item.replace(" ", "").lower() == normalised:
                # Found via fuzzy match
                if stock == 0:
                    return {"status": "zero_stock", "available": 0, "item": db_item, "fuzzy_matched": True}
                if quantity > stock:
                    return {"status": "exceeds_stock", "available": stock, "item": db_item, "fuzzy_matched": True}
                return {"status": "ok", "available": stock, "item": db_item, "fuzzy_matched": True}

        return {"status": "unknown", "available": 0, "item": item, "fuzzy_matched": False}

    conn.close()
    canonical, stock = row

    if stock == 0:
        return {"status": "zero_stock", "available": 0, "item": canonical, "fuzzy_matched": False}
    if quantity > stock:
        return {"status": "exceeds_stock", "available": stock, "item": canonical, "fuzzy_matched": False}
    return {"status": "ok", "available": stock, "item": canonical, "fuzzy_matched": False}


def get_all_items() -> list[dict]:
    """Return all inventory items."""
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute("SELECT item, stock, unit_price, category FROM inventory")
    rows = cursor.fetchall()
    conn.close()
    return [
        {"item": r[0], "stock": r[1], "unit_price": r[2], "category": r[3]}
        for r in rows
    ]


# ── Duplicate detection ────────────────────────────────────────────────────────

def check_duplicate(invoice_number: str) -> dict:
    """
    Check if this invoice number has been processed before.
    Returns:
      is_duplicate : bool
      first_seen   : ISO timestamp or None
      status       : prior status if duplicate
    """
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT processed_at, status, revision FROM processed_invoices WHERE invoice_number = ? ORDER BY processed_at DESC LIMIT 1",
        (invoice_number,),
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return {"is_duplicate": False, "first_seen": None, "status": None}
    return {"is_duplicate": True, "first_seen": row[0], "status": row[1], "revision": row[2]}


def record_invoice(
    invoice_number: str,
    status: str,
    vendor: Optional[str] = None,
    total: Optional[float] = None,
    revision: Optional[str] = None,
) -> None:
    """Persist a processed invoice for duplicate tracking."""
    conn = _conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO processed_invoices (invoice_number, processed_at, status, vendor, total, revision) VALUES (?, ?, ?, ?, ?, ?)",
        (
            invoice_number,
            datetime.now(timezone.utc).isoformat(),
            status,
            vendor,
            total,
            revision,
        ),
    )
    conn.commit()
    conn.close()
