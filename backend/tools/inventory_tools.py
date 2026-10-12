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
    safety_days: int = DEFAULT_SAFETY_DAYS,
    outstanding_po_qty: int = 0,
    expiry_days_left: Optional[int] = None,
    reorder_point: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Deterministic procurement decision tool:
      coverage_days = lead_time_days + safety_days
      raw_need = daily_sales * coverage_days
      
      Batch & Expiry Accounting:
      If stock is expiring before replenishment, units sellable before expiry = daily_sales * max(0, expiry_days_left).
      Any current_stock beyond sellable units will spoil before dispensing:
      unusable_stock = max(0, current_stock - (daily_sales * max(0, expiry_days_left))) if expiry_days_left is not None else 0
      usable_current_stock = max(0, current_stock - unusable_stock)
      
      On-Order PO Accounting:
      outstanding_po_qty represents active POs already in transit/approval.
      effective_inventory = usable_current_stock + outstanding_po_qty
      
      Reorder Trigger:
      If reorder_point is provided:
        needs_reorder = effective_inventory <= reorder_point
        required_qty = max(raw_need - effective_inventory, 0) if needs_reorder else 0
      Else:
        required_qty = max(raw_need - effective_inventory, 0)
        needs_reorder = required_qty > 0
    """
    coverage_days = lead_time_days + safety_days
    raw_need = daily_sales * coverage_days
    lead_time_demand = daily_sales * lead_time_days
    safety_stock = daily_sales * safety_days

    unusable_stock = 0
    if expiry_days_left is not None:
        if expiry_days_left < 0:
            unusable_stock = current_stock
        else:
            sellable = daily_sales * expiry_days_left
            if current_stock > sellable:
                unusable_stock = current_stock - sellable

    usable_current_stock = max(0, current_stock - unusable_stock)
    effective_inventory = usable_current_stock + outstanding_po_qty

    if reorder_point is not None:
        needs_reorder = effective_inventory <= reorder_point
        required_qty = max(raw_need - effective_inventory, 0) if needs_reorder else 0
    else:
        required_qty = max(raw_need - effective_inventory, 0)
        needs_reorder = required_qty > 0

    if not needs_reorder:
        explanation = (
            f"Net inventory ({effective_inventory} = stock {current_stock} + POs {outstanding_po_qty}) "
            f"is above replenishment threshold ({reorder_point if reorder_point is not None else raw_need}). "
            f"Procurement already active or stock adequate; 0 units needed."
        )
    else:
        explanation = (
            f"Demand: {daily_sales}/day across {coverage_days}d coverage ({lead_time_days}d lead + {safety_days}d safety buffer) "
            f"= {raw_need} units target. Current stock: {current_stock} (usable: {usable_current_stock}) + "
            f"incoming POs: {outstanding_po_qty} = effective stock: {effective_inventory} units. "
            f"Deficit: {required_qty} units required."
        )

    return {
        "required_qty": int(required_qty),
        "coverage_days": int(coverage_days),
        "raw_need": int(raw_need),
        "lead_time_demand": int(lead_time_demand),
        "safety_stock": int(safety_stock),
        "target_stock": int(raw_need),
        "reorder_point": int(reorder_point) if reorder_point is not None else None,
        "safety_days": int(safety_days),
        "current_stock": int(current_stock),
        "outstanding_po_qty": int(outstanding_po_qty),
        "usable_current_stock": int(usable_current_stock),
        "unusable_stock": int(unusable_stock),
        "spoilage_risk_units": int(unusable_stock),
        "effective_inventory": int(effective_inventory),
        "net_available": int(effective_inventory),
        "needs_reorder": bool(needs_reorder),
        "explanation": explanation,
    }


def check_expiry(
    expiry_date_str: Optional[str] = None,
    daily_sales: int = 1,
    reference_date: Optional[date] = None,
    lead_time_days: int = 0,
    current_stock: Optional[int] = None,
    days_left: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Deterministic tool: Check expiry constraint and shelf-life capacity for a medicine.
    
    Calculates:
      - expiry_days_left: days from reference_date to expiry_date
      - expiry_safe_qty: daily_sales * expiry_days_left (maximum units sellable before expiry)
      - expiry_risk: boolean flag indicating if stock expires before delivery or within 30 days
      - estimated_consumption_before_expiry: daily_sales * max(0, days_left)
      - spoilage_risk_units: units at risk of expiring if current_stock exceeds consumption
    """
    ref_date = reference_date if reference_date is not None else date.today()

    if days_left is not None:
        computed_days = int(days_left)
    elif expiry_date_str:
        try:
            exp_date = datetime.strptime(str(expiry_date_str).strip(), "%Y-%m-%d").date()
            computed_days = (exp_date - ref_date).days
        except (ValueError, TypeError):
            return {
                "expiry_days_left": 0,
                "expiry_safe_qty": 0,
                "expiry_risk": True,
                "estimated_consumption_before_expiry": 0,
                "spoilage_risk_units": current_stock or 0,
                "error": f"Invalid expiry date format: '{expiry_date_str}'. Expected YYYY-MM-DD.",
                "explanation": "Invalid expiry date format. Urgent inspection required.",
            }
    else:
        computed_days = 999

    days_left = computed_days

    if days_left <= 0:
        return {
            "expiry_days_left": days_left,
            "expiry_safe_qty": 0,
            "expiry_risk": True,
            "estimated_consumption_before_expiry": 0,
            "spoilage_risk_units": current_stock or 0,
            "explanation": f"Batch expired ({abs(days_left)} days ago). Urgent write-off required.",
        }

    expiry_safe_qty = daily_sales * days_left
    expiry_risk = days_left < 30 or days_left <= lead_time_days
    estimated_consumption = daily_sales * days_left
    spoilage_units = max(0, (current_stock - estimated_consumption)) if current_stock is not None else 0

    explanation = (
        f"{days_left} days until expiry. Dispensing capacity: {expiry_safe_qty} units "
        f"at {daily_sales}/day. Expiry risk: {'HIGH' if expiry_risk else 'LOW'}."
    )

    return {
        "expiry_days_left": days_left,
        "expiry_safe_qty": int(expiry_safe_qty),
        "expiry_risk": bool(expiry_risk),
        "estimated_consumption_before_expiry": int(estimated_consumption),
        "spoilage_risk_units": int(spoilage_units),
        "explanation": explanation,
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


def get_inventory_item(med_id: int, db_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single medicine record from SQLite inventory table."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT med_id, name, current_stock, reorder_point, daily_sales, lead_time_days, expiry_date
        FROM inventory
        WHERE med_id = ?
        """,
        (med_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_inventory_batches(med_id: int, db_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Retrieve all recorded batches for a specific medicine."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT batch_id, med_id, batch_number, quantity, expiry_date, received_at
        FROM inventory_batches
        WHERE med_id = ?
        ORDER BY expiry_date ASC
        """,
        (med_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]



