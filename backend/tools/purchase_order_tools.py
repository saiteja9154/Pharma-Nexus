"""
Purchase Order Tools for Store Procurement Agent (Phase 6).
Provides deterministic, atomic transaction execution to create purchase orders
and write back inventory restocking quantities to the SQLite ERP database.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from database.db import get_db_connection
except ImportError:
    from backend.database.db import get_db_connection


def create_purchase_order_transaction(
    med_id: int,
    vendor_id: int,
    quantity: int,
    unit_price: float,
    total_cost: float,
    delivery_days: int,
    status: str = "CREATED",
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Atomic SQLite Transaction:
      1. Read current inventory stock for med_id.
      2. Insert Purchase Order record into purchase_orders table.
      3. Update inventory current_stock (stock_after = stock_before + quantity).
      4. Commit transaction atomically.
      
    If any error occurs during PO insertion or inventory update, the transaction
    is rolled back completely to prevent partial database mutations.
    
    Returns structured execution result:
      - success (bool)
      - po_id (int)
      - po_number (str)
      - med_id (int)
      - vendor_id (int)
      - quantity (int)
      - unit_price (float)
      - total_cost (float)
      - delivery_days (int)
      - status (str)
      - inventory_before (int)
      - inventory_after (int)
    """
    if quantity <= 0:
        raise ValueError(f"Invalid quantity: {quantity}. Quantity must be a positive integer.")
    if unit_price <= 0:
        raise ValueError(f"Invalid unit price: {unit_price}. Unit price must be positive.")
    if total_cost <= 0:
        raise ValueError(f"Invalid total cost: {total_cost}. Total cost must be positive.")

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()

        # Step 1: Read current inventory
        cursor.execute(
            "SELECT med_id, name, current_stock FROM inventory WHERE med_id = ?",
            (med_id,),
        )
        inv_row = cursor.fetchone()
        if not inv_row:
            raise ValueError(f"Medicine with med_id={med_id} does not exist in inventory.")

        inv_before = inv_row["current_stock"]
        inv_after = inv_before + quantity

        # Step 2: Insert Purchase Order
        cursor.execute(
            """
            INSERT INTO purchase_orders (med_id, vendor_id, quantity, unit_price, total_cost, delivery_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                med_id,
                vendor_id,
                quantity,
                round(float(unit_price), 2),
                round(float(total_cost), 2),
                delivery_days,
                status,
            ),
        )
        po_id = cursor.lastrowid
        po_number = f"PO-#{str(po_id).zfill(4)}"

        # Step 3: Update Inventory current_stock
        cursor.execute(
            """
            UPDATE inventory
            SET current_stock = ?
            WHERE med_id = ?
            """,
            (inv_after, med_id),
        )

        # Step 4: Commit transaction
        conn.commit()

        return {
            "success": True,
            "po_id": po_id,
            "po_number": po_number,
            "med_id": med_id,
            "vendor_id": vendor_id,
            "quantity": quantity,
            "unit_price": round(float(unit_price), 2),
            "total_cost": round(float(total_cost), 2),
            "delivery_days": delivery_days,
            "status": status,
            "inventory_before": inv_before,
            "inventory_after": inv_after,
        }

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_all_purchase_orders(db_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Retrieve all purchase orders with joined medicine and vendor names."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            po.po_id,
            po.med_id,
            i.name AS medicine_name,
            po.vendor_id,
            v.name AS vendor_name,
            po.quantity,
            po.unit_price,
            po.total_cost,
            po.delivery_days,
            po.status
        FROM purchase_orders po
        LEFT JOIN inventory i ON po.med_id = i.med_id
        LEFT JOIN vendors v ON po.vendor_id = v.vendor_id
        ORDER BY po.po_id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
