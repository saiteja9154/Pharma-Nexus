import sqlite3
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
for p in (str(BASE_DIR), str(BACKEND_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from database.db import get_db_connection, init_db, DEFAULT_DB_PATH
except ImportError:
    from backend.database.db import get_db_connection, init_db, DEFAULT_DB_PATH


# Deterministic seed data for Phase 1
MEDICINES = [
    (1, "Paracetamol", 40, 50, 20, 5, "2026-12-31"),
    (2, "Cetirizine", 25, 30, 10, 3, "2026-10-15"),
    (3, "Azithromycin", 15, 20, 5, 4, "2026-11-20"),
]

VENDORS = [
    (1, "Vendor A"),
    (2, "Vendor B"),
    (3, "Vendor C"),
]

# Vendor A: Lowest base price, High MOQ, Slower delivery
# Vendor B: Medium price, More flexible MOQ, Faster delivery
# Vendor C: Higher price, Moderate MOQ, Moderate delivery
VENDOR_OFFERS = [
    # Vendor A (vendor_id: 1)
    (1, 1, 8.00, 500, 5),
    (1, 2, 1.80, 100, 7),
    (1, 3, 12.00, 50, 7),
    # Vendor B (vendor_id: 2)
    (2, 1, 8.50, 250, 2),
    (2, 2, 2.20, 30, 2),
    (2, 3, 14.50, 20, 2),
    # Vendor C (vendor_id: 3)
    (3, 1, 9.00, 300, 3),
    (3, 2, 2.60, 50, 4),
    (3, 3, 16.00, 30, 4),
]


def seed_db(db_path: Optional[Path | str] = None) -> None:
    """Seed the database with deterministic Phase 1 data."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Clear existing tables to ensure clean baseline on re-seeding
    cursor.execute("DELETE FROM purchase_orders;")
    cursor.execute("DELETE FROM vendor_offers;")
    cursor.execute("DELETE FROM inventory;")
    cursor.execute("DELETE FROM vendors;")


    # Insert medicines (deterministic and idempotent)
    cursor.executemany(
        """
        INSERT OR REPLACE INTO inventory (med_id, name, current_stock, reorder_point, daily_sales, lead_time_days, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        MEDICINES,
    )


    # Insert vendors
    cursor.executemany(
        """
        INSERT OR REPLACE INTO vendors (vendor_id, name)
        VALUES (?, ?)
        """,
        VENDORS,
    )

    # Insert vendor offers
    cursor.executemany(
        """
        INSERT OR REPLACE INTO vendor_offers (vendor_id, med_id, base_price, min_qty, delivery_days)
        VALUES (?, ?, ?, ?, ?)
        """,
        VENDOR_OFFERS,
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed_db()
    print("Database seeded successfully with 3 medicines, 3 vendors, and 9 vendor offers.")
