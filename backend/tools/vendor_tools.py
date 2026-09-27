"""
Vendor Tools for Store Procurement Agent (Phase 3 Foundation).
Provides deterministic tools to query vendor offerings, calculate quote quantities
based on MOQ rules, and evaluate total commitment costs.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from database.db import get_db_connection
except ImportError:
    from backend.database.db import get_db_connection


def get_vendor_quotes(
    med_id: int,
    required_qty: int,
    db_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve all candidate vendor quotes for a specific medicine.
    
    Enforces the frozen MOQ quantity rule:
      vendor_offered_qty = max(required_qty, vendor_MOQ)
      total_cost = base_price * vendor_offered_qty
    
    Returns structured quote records for StoreAgent decision making.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            vo.vendor_id,
            v.name AS vendor_name,
            vo.med_id,
            i.name AS med_name,
            vo.base_price,
            vo.min_qty AS moq,
            vo.delivery_days
        FROM vendor_offers vo
        JOIN vendors v ON vo.vendor_id = v.vendor_id
        JOIN inventory i ON vo.med_id = i.med_id
        WHERE vo.med_id = ?
        ORDER BY vo.vendor_id ASC
        """,
        (med_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    quotes: List[Dict[str, Any]] = []
    for row in rows:
        moq = int(row["moq"])
        base_price = float(row["base_price"])
        # Quantity Rule: offered_qty = max(required_qty, MOQ)
        offered_qty = max(required_qty, moq)
        total_cost = round(base_price * offered_qty, 2)

        quotes.append(
            {
                "vendor_id": row["vendor_id"],
                "vendor_name": row["vendor_name"],
                "med_id": row["med_id"],
                "med_name": row["med_name"],
                "base_price": base_price,
                "moq": moq,
                "required_qty": required_qty,
                "offered_qty": offered_qty,
                "delivery_days": int(row["delivery_days"]),
                "total_cost": total_cost,
            }
        )

    return quotes


def get_vendor_quote(
    vendor_id: int,
    med_id: int,
    required_qty: int,
    db_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve quote from a single specific vendor for a medicine."""
    quotes = get_vendor_quotes(med_id, required_qty, db_path)
    for q in quotes:
        if q["vendor_id"] == vendor_id:
            return q
    return None


def update_vendor_offer(
    vendor_id: int,
    med_id: int,
    base_price: float,
    min_qty: int,
    delivery_days: int,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Update master data for a vendor offer in the SQLite vendor_offers table.
    
    Validations:
      - base_price > 0
      - min_qty > 0
      - delivery_days >= 0
      - (vendor_id, med_id) must exist in vendor_offers
    """
    if base_price <= 0:
        raise ValueError("base_price must be greater than 0.")
    if min_qty <= 0:
        raise ValueError("min_qty (MOQ) must be greater than 0.")
    if delivery_days < 0:
        raise ValueError("delivery_days cannot be negative.")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check existence and fetch names
    cursor.execute(
        """
        SELECT 
            vo.vendor_id,
            v.name AS vendor_name,
            vo.med_id,
            i.name AS med_name
        FROM vendor_offers vo
        JOIN vendors v ON vo.vendor_id = v.vendor_id
        JOIN inventory i ON vo.med_id = i.med_id
        WHERE vo.vendor_id = ? AND vo.med_id = ?
        """,
        (vendor_id, med_id),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Vendor offer for vendor_id={vendor_id} and med_id={med_id} does not exist.")

    vendor_name = row["vendor_name"]
    med_name = row["med_name"]

    cursor.execute(
        """
        UPDATE vendor_offers
        SET base_price = ?,
            min_qty = ?,
            delivery_days = ?
        WHERE vendor_id = ? AND med_id = ?
        """,
        (round(float(base_price), 2), int(min_qty), int(delivery_days), vendor_id, med_id),
    )
    conn.commit()
    conn.close()

    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "med_id": med_id,
        "med_name": med_name,
        "base_price": round(float(base_price), 2),
        "min_qty": int(min_qty),
        "delivery_days": int(delivery_days),
    }


def add_vendor(
    name: str,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Insert a new vendor into the SQLite vendors table.
    
    Validations:
      - name must not be empty
      - name must be unique (case-insensitive)
    """
    clean_name = str(name).strip()
    if not clean_name:
        raise ValueError("Vendor name cannot be empty.")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Unique check
    cursor.execute("SELECT vendor_id FROM vendors WHERE LOWER(name) = LOWER(?)", (clean_name,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        raise ValueError(f"Vendor with name '{clean_name}' already exists (ID: #{existing['vendor_id']}).")

    cursor.execute("INSERT INTO vendors (name) VALUES (?)", (clean_name,))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "vendor_id": new_id,
        "name": clean_name,
    }


def add_vendor_offer(
    vendor_id: int,
    med_id: int,
    base_price: float,
    min_qty: int,
    delivery_days: int,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Insert a new vendor contract offer into the SQLite vendor_offers table.
    
    Validations:
      - base_price > 0
      - min_qty > 0
      - delivery_days >= 0 (or > 0)
      - vendor_id must exist in vendors table
      - med_id must exist in inventory table
      - (vendor_id, med_id) must be unique in vendor_offers table
    """
    if base_price <= 0:
        raise ValueError("base_price must be greater than 0.")
    if min_qty <= 0:
        raise ValueError("min_qty (MOQ) must be greater than 0.")
    if delivery_days <= 0:
        raise ValueError("delivery_days must be greater than 0.")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Check vendor existence
    cursor.execute("SELECT vendor_id, name FROM vendors WHERE vendor_id = ?", (vendor_id,))
    v_row = cursor.fetchone()
    if not v_row:
        conn.close()
        raise ValueError(f"Vendor with vendor_id={vendor_id} does not exist.")
    vendor_name = v_row["name"]

    # 2. Check medicine existence
    cursor.execute("SELECT med_id, name FROM inventory WHERE med_id = ?", (med_id,))
    m_row = cursor.fetchone()
    if not m_row:
        conn.close()
        raise ValueError(f"Medicine with med_id={med_id} does not exist in inventory.")
    med_name = m_row["name"]

    # 3. Check duplicate offer
    cursor.execute(
        "SELECT vendor_id FROM vendor_offers WHERE vendor_id = ? AND med_id = ?",
        (vendor_id, med_id),
    )
    if cursor.fetchone():
        conn.close()
        raise ValueError(f"Contract offer from '{vendor_name}' for '{med_name}' already exists.")

    # 4. Insert offer
    cursor.execute(
        """
        INSERT INTO vendor_offers (vendor_id, med_id, base_price, min_qty, delivery_days)
        VALUES (?, ?, ?, ?, ?)
        """,
        (vendor_id, med_id, round(float(base_price), 2), int(min_qty), int(delivery_days)),
    )
    conn.commit()
    conn.close()

    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "med_id": med_id,
        "med_name": med_name,
        "base_price": round(float(base_price), 2),
        "min_qty": int(min_qty),
        "delivery_days": int(delivery_days),
    }


