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


# Deterministic realistic ERP seed data: 18 medicines, 6 vendors, 98 vendor offers
MEDICINES = [
    # Hero Medicines (IDs 1, 2, 3) - Values strictly preserved for hero scenarios
    (1, "Paracetamol", 40, 50, 20, 5, "2027-12-31"),
    (2, "Cetirizine", 25, 30, 10, 3, "2027-10-15"),
    (3, "Azithromycin", 15, 20, 5, 4, "2027-11-20"),

    # Expanded Realistic ERP Medicines (IDs 4 to 18)
    (4, "Ibuprofen", 120, 80, 15, 3, "2028-03-31"),          # Healthy stock (120 >= 80) -> NO_PROCUREMENT
    (5, "Amoxicillin", 18, 40, 12, 3, "2027-08-31"),         # Low stock (18 < 40) -> REORDER NEEDED (Need: 42)
    (6, "Omeprazole", 20, 50, 15, 4, "2027-09-30"),          # Low stock (20 < 50) -> REORDER NEEDED (Need: 70)
    (7, "Pantoprazole", 95, 60, 10, 3, "2028-01-15"),        # Healthy stock (95 >= 60) -> NO_PROCUREMENT
    (8, "Metformin", 50, 100, 30, 4, "2028-06-30"),          # High demand, Low stock (50 < 100) -> REORDER NEEDED (Need: 130)
    (9, "Amlodipine", 75, 50, 8, 3, "2027-12-15"),           # Healthy stock (75 >= 50) -> NO_PROCUREMENT
    (10, "Montelukast", 12, 30, 6, 4, "2027-07-20"),         # Low stock (12 < 30) -> REORDER NEEDED (Need: 24)
    (11, "Levocetirizine", 80, 40, 8, 2, "2028-02-28"),      # Healthy stock (80 >= 40) -> NO_PROCUREMENT
    (12, "Diclofenac", 22, 45, 10, 3, "2027-11-30"),         # Low stock (22 < 45) -> REORDER NEEDED (Need: 28)
    (13, "Atorvastatin", 30, 60, 14, 4, "2028-04-30"),       # Low stock (30 < 60) -> REORDER NEEDED (Need: 54)
    (14, "Vitamin B12", 150, 70, 12, 5, "2028-05-15"),       # Healthy stock (150 >= 70) -> NO_PROCUREMENT
    (15, "ORS", 35, 80, 25, 2, "2028-10-31"),                # High demand, Low stock (35 < 80) -> REORDER NEEDED (Need: 65)
    (16, "Famotidine", 60, 40, 6, 3, "2027-08-20"),          # Healthy stock (60 >= 40) -> NO_PROCUREMENT
    (17, "Losartan", 16, 35, 7, 3, "2027-10-31"),            # Low stock (16 < 35) -> REORDER NEEDED (Need: 19)
    (18, "Ciprofloxacin", 10, 25, 5, 4, "2027-09-15"),       # Low stock (10 < 25) -> REORDER NEEDED (Need: 20)
]

VENDORS = [
    (1, "Vendor A"),  # Bulk Pharmaceutical Supplier (Lowest base price, large MOQ, slower delivery)
    (2, "Vendor B"),  # Fast Delivery Supplier (Medium-competitive price, flexible MOQ, fastest delivery)
    (3, "Vendor C"),  # Regional Distributor (Medium/higher price, moderate MOQ, moderate delivery)
    (4, "Vendor D"),  # Generic Medicine Supplier (Competitive generic pricing, medium MOQ, 3-4 day delivery)
    (5, "Vendor E"),  # Hospital Supply Distributor (Higher quality/price, flexible MOQ, reliable delivery)
    (6, "Vendor F"),  # Specialty Pharmaceutical Supplier (Premium pricing, small MOQ, rapid delivery)
]

VENDOR_OFFERS = [
    # =========================================================================
    # 1. PARACETAMOL (med_id: 1) — Hero data preserved
    # =========================================================================
    (1, 1, 8.00, 500, 5),   # Vendor A (Hero)
    (2, 1, 8.50, 250, 2),   # Vendor B (Hero Winner)
    (3, 1, 9.00, 300, 3),   # Vendor C (Hero)
    (4, 1, 8.20, 400, 4),   # Vendor D
    (5, 1, 9.20, 200, 3),   # Vendor E
    (6, 1, 9.80, 100, 2),   # Vendor F

    # =========================================================================
    # 2. CETIRIZINE (med_id: 2) — Hero data preserved
    # =========================================================================
    (1, 2, 1.80, 100, 7),   # Vendor A (Hero)
    (2, 2, 2.20, 30, 2),    # Vendor B (Hero Winner)
    (3, 2, 2.60, 50, 4),    # Vendor C (Hero)
    (4, 2, 2.00, 80, 5),    # Vendor D
    (5, 2, 2.40, 40, 3),    # Vendor E
    (6, 2, 2.80, 20, 2),    # Vendor F

    # =========================================================================
    # 3. AZITHROMYCIN (med_id: 3) — Hero data preserved
    # =========================================================================
    (1, 3, 12.00, 50, 7),   # Vendor A (Hero)
    (2, 3, 14.50, 20, 2),   # Vendor B (Hero Winner)
    (3, 3, 16.00, 30, 4),   # Vendor C (Hero)
    (4, 3, 13.00, 40, 5),   # Vendor D
    (5, 3, 15.00, 25, 3),   # Vendor E
    (6, 3, 17.50, 15, 2),   # Vendor F

    # =========================================================================
    # 4. IBUPROFEN (med_id: 4)
    # =========================================================================
    (1, 4, 3.50, 200, 5),   # Vendor A
    (2, 4, 4.00, 100, 2),   # Vendor B
    (3, 4, 4.20, 150, 3),   # Vendor C
    (4, 4, 3.70, 180, 4),   # Vendor D
    (5, 4, 4.50, 80, 2),    # Vendor E

    # =========================================================================
    # 5. AMOXICILLIN (med_id: 5)
    # =========================================================================
    (1, 5, 5.00, 100, 5),   # Vendor A
    (2, 5, 5.80, 40, 2),    # Vendor B
    (3, 5, 6.20, 60, 3),    # Vendor C
    (4, 5, 5.20, 50, 3),    # Vendor D
    (5, 5, 6.00, 30, 2),    # Vendor E
    (6, 5, 6.80, 20, 1),    # Vendor F

    # =========================================================================
    # 6. OMEPRAZOLE (med_id: 6)
    # =========================================================================
    (1, 6, 4.20, 150, 6),   # Vendor A
    (2, 6, 4.80, 70, 2),    # Vendor B
    (3, 6, 5.20, 100, 3),   # Vendor C
    (4, 6, 4.50, 80, 3),    # Vendor D
    (5, 6, 5.00, 50, 2),    # Vendor E

    # =========================================================================
    # 7. PANTOPRAZOLE (med_id: 7)
    # =========================================================================
    (1, 7, 5.50, 120, 5),   # Vendor A
    (2, 7, 6.20, 50, 2),    # Vendor B
    (3, 7, 6.60, 80, 4),    # Vendor C
    (4, 7, 5.80, 60, 3),    # Vendor D
    (5, 7, 6.40, 40, 2),    # Vendor E

    # =========================================================================
    # 8. METFORMIN (med_id: 8)
    # =========================================================================
    (1, 8, 2.10, 300, 5),   # Vendor A
    (2, 8, 2.60, 150, 2),   # Vendor B
    (3, 8, 2.80, 200, 3),   # Vendor C
    (4, 8, 2.30, 200, 3),   # Vendor D
    (5, 8, 2.90, 100, 2),   # Vendor E

    # =========================================================================
    # 9. AMLODIPINE (med_id: 9)
    # =========================================================================
    (1, 9, 1.80, 150, 5),   # Vendor A
    (2, 9, 2.30, 60, 2),    # Vendor B
    (3, 9, 2.50, 80, 3),    # Vendor C
    (4, 9, 2.00, 100, 4),   # Vendor D
    (6, 9, 2.70, 30, 1),    # Vendor F

    # =========================================================================
    # 10. MONTELUKAST (med_id: 10)
    # =========================================================================
    (1, 10, 8.50, 80, 6),   # Vendor A
    (2, 10, 9.80, 25, 2),   # Vendor B
    (3, 10, 10.50, 40, 3),  # Vendor C
    (4, 10, 9.00, 50, 4),   # Vendor D
    (5, 10, 10.20, 30, 2),  # Vendor E
    (6, 10, 11.50, 20, 1),  # Vendor F

    # =========================================================================
    # 11. LEVOCETIRIZINE (med_id: 11)
    # =========================================================================
    (1, 11, 2.50, 120, 5),  # Vendor A
    (2, 11, 3.10, 40, 2),   # Vendor B
    (3, 11, 3.40, 60, 3),   # Vendor C
    (4, 11, 2.80, 80, 4),   # Vendor D
    (5, 11, 3.30, 50, 2),   # Vendor E

    # =========================================================================
    # 12. DICLOFENAC (med_id: 12)
    # =========================================================================
    (1, 12, 3.00, 100, 5),  # Vendor A
    (2, 12, 3.70, 30, 2),   # Vendor B
    (3, 12, 4.00, 50, 3),   # Vendor C
    (4, 12, 3.30, 50, 3),   # Vendor D
    (5, 12, 3.90, 40, 2),   # Vendor E

    # =========================================================================
    # 13. ATORVASTATIN (med_id: 13)
    # =========================================================================
    (1, 13, 6.00, 150, 5),  # Vendor A
    (2, 13, 7.20, 60, 2),   # Vendor B
    (3, 13, 7.80, 80, 3),   # Vendor C
    (4, 13, 6.50, 80, 3),   # Vendor D
    (5, 13, 7.50, 50, 2),   # Vendor E
    (6, 13, 8.40, 30, 1),   # Vendor F

    # =========================================================================
    # 14. VITAMIN B12 (med_id: 14)
    # =========================================================================
    (1, 14, 4.00, 200, 6),  # Vendor A
    (2, 14, 4.80, 80, 2),   # Vendor B
    (3, 14, 5.20, 100, 3),  # Vendor C
    (4, 14, 4.40, 120, 4),  # Vendor D
    (5, 14, 5.00, 60, 2),   # Vendor E

    # =========================================================================
    # 15. ORS (med_id: 15)
    # =========================================================================
    (1, 15, 1.20, 200, 5),  # Vendor A
    (2, 15, 1.60, 80, 2),   # Vendor B
    (3, 15, 1.80, 100, 3),  # Vendor C
    (4, 15, 1.35, 120, 3),  # Vendor D
    (5, 15, 1.70, 60, 2),   # Vendor E

    # =========================================================================
    # 16. FAMOTIDINE (med_id: 16)
    # =========================================================================
    (1, 16, 2.80, 100, 5),  # Vendor A
    (2, 16, 3.40, 40, 2),   # Vendor B
    (3, 16, 3.80, 60, 3),   # Vendor C
    (4, 16, 3.10, 60, 3),   # Vendor D
    (5, 16, 3.60, 40, 2),   # Vendor E

    # =========================================================================
    # 17. LOSARTAN (med_id: 17)
    # =========================================================================
    (1, 17, 4.50, 80, 5),   # Vendor A
    (2, 17, 5.40, 25, 2),   # Vendor B
    (3, 17, 5.90, 40, 3),   # Vendor C
    (4, 17, 4.80, 40, 3),   # Vendor D
    (5, 17, 5.60, 30, 2),   # Vendor E
    (6, 17, 6.30, 15, 1),   # Vendor F

    # =========================================================================
    # 18. CIPROFLOXACIN (med_id: 18)
    # =========================================================================
    (1, 18, 7.00, 60, 5),   # Vendor A
    (2, 18, 8.40, 20, 2),   # Vendor B
    (3, 18, 9.00, 30, 3),   # Vendor C
    (4, 18, 7.60, 35, 4),   # Vendor D
    (5, 18, 8.70, 25, 2),   # Vendor E
    (6, 18, 9.80, 15, 1),   # Vendor F
]


def seed_db(db_path: Optional[Path | str] = None) -> None:
    """Seed the database with deterministic Phase 1 & Expanded ERP data."""
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
    print(f"Database seeded successfully with {len(MEDICINES)} medicines, {len(VENDORS)} vendors, and {len(VENDOR_OFFERS)} vendor offers.")
