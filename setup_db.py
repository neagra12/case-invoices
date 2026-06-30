"""
One-time database initialisation.

Run:  python setup_db.py
Creates inventory.db with inventory and processed_invoices tables.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "inventory.db")


def setup():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── Create tables first ───────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            item        TEXT PRIMARY KEY,
            stock       INTEGER NOT NULL,
            unit_price  REAL,
            category    TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_invoices (
            invoice_number  TEXT NOT NULL,
            processed_at    TEXT NOT NULL,
            status          TEXT NOT NULL,
            vendor          TEXT,
            total           REAL,
            revision        TEXT
        )
    """)

    # ── Seed data (idempotent) ────────────────────────────────────────────────
    cursor.execute("DELETE FROM inventory")
    cursor.execute("DELETE FROM processed_invoices")
    cursor.executemany(
        "INSERT INTO inventory VALUES (?, ?, ?, ?)",
        [
            ("WidgetA",     15,  250.00, "Widget"),
            ("WidgetB",     10,  500.00, "Widget"),
            ("GadgetX",      5,  750.00, "Gadget"),
            ("FakeItem",     0, 1000.00, "Suspicious"),
        ],
    )

    conn.commit()
    conn.close()
    print(f"[OK] Database initialised at {DB_PATH}")
    print("  Inventory:")
    print("    WidgetA  - stock: 15  @ $250")
    print("    WidgetB  - stock: 10  @ $500")
    print("    GadgetX  - stock:  5  @ $750")
    print("    FakeItem - stock:  0  @ $1,000")


if __name__ == "__main__":
    setup()
