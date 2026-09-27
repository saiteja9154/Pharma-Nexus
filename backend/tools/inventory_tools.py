"""
Inventory Tools for Store Procurement Agent (Phase 2).
Provides deterministic, read-only tools to observe stock levels,
calculate required procurement quantities, and evaluate expiry constraints.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from database.db import get_db_connection
except ImportError:
    from backend.database.db import get_db_connection

# Centralized deterministic safety buffer (Phase 0 / Phase 2 specification)
DEFAULT_SAFETY_DAYS = 2


def get_inventory(db_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """
    Read-only tool: Retrieve all inventory items from the SQLite database.
    
    Returns structured records containing:
      - med_id (int)
      - name (str)
      - current_stock (int)
      - reorder_point (int)
      - daily_sales (int)
      - lead_time_days (int)
      - expiry_date (str)
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            med_id,
            name,
            current_stock,
            reorder_point,
            daily_sales,
            lead_time_days,
            expiry_date
        FROM inventory
        ORDER BY med_id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def calculate_need(
    current_stock: int,
    daily_sales: int,
    lead_time_days: int,
    safety_days: int = DEFAULT_SAFETY_DAYS
) -> Dict[str, int]:
    """
    Deterministic tool: Calculate required procurement quantity using frozen Phase 0 formula.
    
    Formula:
      coverage_days = lead_time_days + safety_days
      raw_need = daily_sales * coverage_days
      required_qty = max(raw_need - current_stock, 0)
    """
    coverage_days = lead_time_days + safety_days
    raw_need = daily_sales * coverage_days
    required_qty = max(raw_need - current_stock, 0)

    return {
        "required_qty": int(required_qty),
        "coverage_days": int(coverage_days),
        "raw_need": int(raw_need),
        "safety_days": int(safety_days),
    }


def check_expiry(
    expiry_date_str: str,
    daily_sales: int,
    reference_date: Optional[date] = None,
    lead_time_days: int = 0
) -> Dict[str, Any]:
    """
    Deterministic tool: Check expiry constraint for a medicine.
    
    Calculates:
      - expiry_days_left: days from reference_date to expiry_date
      - expiry_safe_qty: daily_sales * expiry_days_left (maximum units sellable before expiry)
      - expiry_risk: boolean flag indicating if stock expires before delivery or within 30 days
    """
    ref_date = reference_date if reference_date is not None else date.today()

    try:
        exp_date = datetime.strptime(str(expiry_date_str).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {
            "expiry_days_left": 0,
            "expiry_safe_qty": 0,
            "expiry_risk": True,
            "error": f"Invalid expiry date format: '{expiry_date_str}'. Expected YYYY-MM-DD.",
        }

    days_left = (exp_date - ref_date).days

    if days_left <= 0:
        return {
            "expiry_days_left": days_left,
            "expiry_safe_qty": 0,
            "expiry_risk": True,
        }

    expiry_safe_qty = daily_sales * days_left
    # Expiry risk is flagged if expiring within 30 days or within the supplier lead time
    expiry_risk = days_left < 30 or days_left <= lead_time_days

    return {
        "expiry_days_left": days_left,
        "expiry_safe_qty": int(expiry_safe_qty),
        "expiry_risk": bool(expiry_risk),
    }


def update_inventory_item(
    med_id: int,
    current_stock: int,
    reorder_point: int,
    daily_sales: int,
    lead_time_days: int,
    expiry_date: str,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Update master data for a medicine in the SQLite inventory table.
    
    Validations:
      - current_stock >= 0
      - reorder_point >= 0
      - daily_sales >= 0
      - lead_time_days >= 0
      - expiry_date must be valid YYYY-MM-DD
      - med_id must exist in database
    """
    if current_stock < 0:
        raise ValueError("current_stock cannot be negative.")
    if reorder_point < 0:
        raise ValueError("reorder_point cannot be negative.")
    if daily_sales < 0:
        raise ValueError("daily_sales cannot be negative.")
    if lead_time_days < 0:
        raise ValueError("lead_time_days cannot be negative.")

    expiry_str = str(expiry_date).strip()
    try:
        datetime.strptime(expiry_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid expiry_date format: '{expiry_date}'. Expected YYYY-MM-DD.")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check existence
    cursor.execute("SELECT med_id, name FROM inventory WHERE med_id = ?", (med_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Medicine with med_id={med_id} does not exist.")

    med_name = row["name"]

    cursor.execute(
        """
        UPDATE inventory
        SET current_stock = ?,
            reorder_point = ?,
            daily_sales = ?,
            lead_time_days = ?,
            expiry_date = ?
        WHERE med_id = ?
        """,
        (current_stock, reorder_point, daily_sales, lead_time_days, expiry_str, med_id),
    )
    conn.commit()
    conn.close()

    return {
        "med_id": med_id,
        "name": med_name,
        "current_stock": current_stock,
        "reorder_point": reorder_point,
        "daily_sales": daily_sales,
        "lead_time_days": lead_time_days,
        "expiry_date": expiry_str,
    }


def add_inventory_item(
    name: str,
    current_stock: int,
    reorder_point: int,
    daily_sales: int,
    lead_time_days: int,
    expiry_date: str,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Insert a new medicine into the SQLite inventory table.
    
    Validations:
      - name must not be empty
      - name must be unique (case-insensitive)
      - current_stock >= 0
      - reorder_point >= 0
      - daily_sales >= 0
      - lead_time_days >= 0
      - expiry_date must be valid YYYY-MM-DD
    """
    clean_name = str(name).strip()
    if not clean_name:
        raise ValueError("Medicine name cannot be empty.")

    if current_stock < 0:
        raise ValueError("current_stock cannot be negative.")
    if reorder_point < 0:
        raise ValueError("reorder_point cannot be negative.")
    if daily_sales < 0:
        raise ValueError("daily_sales cannot be negative.")
    if lead_time_days < 0:
        raise ValueError("lead_time_days cannot be negative.")

    expiry_str = str(expiry_date).strip()
    try:
        datetime.strptime(expiry_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid expiry_date format: '{expiry_date}'. Expected YYYY-MM-DD.")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check for unique medicine name
    cursor.execute("SELECT med_id FROM inventory WHERE LOWER(name) = LOWER(?)", (clean_name,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        raise ValueError(f"Medicine with name '{clean_name}' already exists in inventory (ID: #{existing['med_id']}).")

    cursor.execute(
        """
        INSERT INTO inventory (name, current_stock, reorder_point, daily_sales, lead_time_days, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (clean_name, current_stock, reorder_point, daily_sales, lead_time_days, expiry_str),
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "med_id": new_id,
        "name": clean_name,
        "current_stock": current_stock,
        "reorder_point": reorder_point,
        "daily_sales": daily_sales,
        "lead_time_days": lead_time_days,
        "expiry_date": expiry_str,
    }


