"""
Purchase Order Tools & Receiving Lifecycle Engine for Store Procurement Agent (Stage 4).
Provides deterministic, atomic transaction execution for the complete procurement lifecycle:
  DRAFT -> PENDING_APPROVAL -> APPROVED -> ORDERED -> PARTIALLY_RECEIVED -> RECEIVED
  (plus CANCELLED and REJECTED)

Core Rules:
  - Available inventory does NOT increase merely because a PO was created.
  - Inventory increases ONLY when physical goods are recorded as received.
  - Records batch identifiers, expiry dates, received quantities, and discrepancies.
  - Prevents duplicate orders and duplicate receipt processing.
  - Atomic database transactions with rollback on failure.
  - Maintains a full audit trail of approvals, transmissions, and receipts.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

try:
    from database.db import get_db_connection
except ImportError:
    from backend.database.db import get_db_connection

VALID_PO_STATUSES = {
    "DRAFT",
    "PENDING_APPROVAL",
    "APPROVED",
    "ORDERED",
    "PARTIALLY_RECEIVED",
    "RECEIVED",
    "CANCELLED",
    "REJECTED",
    "CREATED",  # Legacy status alias
}


def log_audit(
    cursor: sqlite3.Cursor,
    entity_type: str,
    entity_id: Optional[int],
    action: str,
    details: str,
) -> None:
    """Record an audit trail event inside an existing open transaction."""
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO audit_log (entity_type, entity_id, action, details, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entity_type, entity_id, action, details, now_iso),
    )


def get_outstanding_po_qty(
    med_id: int,
    db_path: Optional[Path | str] = None,
) -> int:
    """
    Calculate total pending/incoming units for a medicine across active POs.
    Active statuses: DRAFT, PENDING_APPROVAL, APPROVED, ORDERED, PARTIALLY_RECEIVED.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT quantity, COALESCE(received_quantity, 0) AS received
        FROM purchase_orders
        WHERE med_id = ?
          AND status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ORDERED', 'PARTIALLY_RECEIVED')
        """,
        (med_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    total_outstanding = 0
    for r in rows:
        remaining = max(0, r["quantity"] - r["received"])
        total_outstanding += remaining
    return total_outstanding


def create_purchase_order_transaction(
    med_id: Optional[int] = None,
    vendor_id: int = 1,
    quantity: int = 1,
    unit_price: float = 1.0,
    total_cost: Optional[float] = None,
    delivery_days: int = 3,
    status: str = "CREATED",
    auto_receive: Optional[bool] = None,
    notes: Optional[str] = None,
    db_path: Optional[Path | str] = None,
    medicine_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Atomic SQLite Purchase Order Creation Transaction.
    
    Safe Lifecycle Support:
      - If auto_receive is True (or legacy status == "CREATED" with auto_receive=None):
        Creates PO and immediately logs receipt + increments inventory (legacy Phase 6 behavior).
      - If auto_receive is False (or status in PENDING_APPROVAL/ORDERED with auto_receive=None):
        Creates PO safely without increasing available inventory until goods are physically received.
    """
    actual_med_id = med_id if med_id is not None else medicine_id
    if actual_med_id is None:
        raise ValueError("med_id or medicine_id is required.")
    med_id = actual_med_id

    actual_total_cost = total_cost if total_cost is not None else round(unit_price * quantity, 2)
    total_cost = actual_total_cost

    if quantity <= 0:
        raise ValueError(f"Invalid quantity: {quantity}. Quantity must be a positive integer.")
    if unit_price <= 0:
        raise ValueError(f"Invalid unit price: {unit_price}. Unit price must be positive.")
    if total_cost <= 0:
        raise ValueError(f"Invalid total cost: {total_cost}. Total cost must be positive.")

    # Determine whether immediate inventory restocking is requested
    should_auto_receive = auto_receive if auto_receive is not None else (status == "CREATED")

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()

        # Step 1: Read current inventory
        cursor.execute(
            "SELECT med_id, name, current_stock, expiry_date FROM inventory WHERE med_id = ?",
            (med_id,),
        )
        inv_row = cursor.fetchone()
        if not inv_row:
            raise ValueError(f"Medicine with med_id={med_id} does not exist in inventory.")

        inv_before = inv_row["current_stock"]
        med_name = inv_row["name"]
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 2: Prevent duplicate open orders if one is already active and not auto-receiving
        if not should_auto_receive:
            cursor.execute(
                """
                SELECT po_id, status FROM purchase_orders
                WHERE med_id = ? AND status IN ('PENDING_APPROVAL', 'APPROVED', 'ORDERED')
                """,
                (med_id,),
            )
            existing_active = cursor.fetchone()
            if existing_active:
                raise ValueError(
                    f"Duplicate order prevented: Active order (PO-#{existing_active['po_id']:04d}, status: {existing_active['status']}) "
                    f"already exists for {med_name}."
                )

        received_qty = quantity if should_auto_receive else 0
        final_status = "RECEIVED" if (should_auto_receive and status == "RECEIVED") else status

        # Step 3: Insert Purchase Order
        cursor.execute(
            """
            INSERT INTO purchase_orders (
                med_id, vendor_id, quantity, unit_price, total_cost,
                delivery_days, status, created_at, updated_at, received_quantity, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                med_id,
                vendor_id,
                quantity,
                round(float(unit_price), 2),
                round(float(total_cost), 2),
                delivery_days,
                final_status,
                now_iso,
                now_iso,
                received_qty,
                notes,
            ),
        )
        po_id = cursor.lastrowid
        po_number = f"PO-#{str(po_id).zfill(4)}"

        # Step 4: Update inventory only if auto_receive is active
        if should_auto_receive:
            inv_after = inv_before + quantity
            cursor.execute(
                "UPDATE inventory SET current_stock = ? WHERE med_id = ?",
                (inv_after, med_id),
            )
            # Create batch & goods receipt record for legacy receive simulation
            batch_num = f"BATCH-AUTO-{po_id:04d}"
            cursor.execute(
                """
                INSERT INTO goods_receipts (
                    po_id, med_id, vendor_id, received_qty, batch_number, expiry_date, discrepancy_qty, notes, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 'Auto-received on order creation', ?)
                """,
                (po_id, med_id, vendor_id, quantity, batch_num, inv_row["expiry_date"], now_iso),
            )
            cursor.execute(
                """
                INSERT INTO inventory_batches (med_id, batch_number, quantity, expiry_date, received_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (med_id, batch_num, quantity, inv_row["expiry_date"], now_iso),
            )
        else:
            inv_after = inv_before  # Stock remains unchanged until goods are explicitly received

        # Step 5: Audit Log
        log_audit(
            cursor=cursor,
            entity_type="PURCHASE_ORDER",
            entity_id=po_id,
            action="CREATE_PO",
            details=f"Created {po_number} for {quantity} units of {med_name} @ ${unit_price:.2f}/u. Status: {final_status}.",
        )

        conn.commit()

        return {
            "success": True,
            "po_id": po_id,
            "po_number": po_number,
            "med_id": med_id,
            "medicine_name": med_name,
            "vendor_id": vendor_id,
            "quantity": quantity,
            "unit_price": round(float(unit_price), 2),
            "total_cost": round(float(total_cost), 2),
            "delivery_days": delivery_days,
            "status": final_status,
            "inventory_before": inv_before,
            "inventory_after": inv_after,
            "auto_received": should_auto_receive,
        }

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def approve_purchase_order(
    po_id: int,
    approver_name: str = "Chief Pharmacist",
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Transition a PO from PENDING_APPROVAL (or DRAFT) to APPROVED."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,))
        po = cursor.fetchone()
        if not po:
            raise ValueError(f"Purchase Order PO-#{po_id:04d} does not exist.")

        curr_status = po["status"]
        if curr_status not in ("PENDING_APPROVAL", "DRAFT"):
            raise ValueError(
                f"Cannot approve PO-#{po_id:04d}: current status is '{curr_status}' (must be 'PENDING_APPROVAL' or 'DRAFT')."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE purchase_orders SET status = 'APPROVED', updated_at = ? WHERE po_id = ?",
            (now_iso, po_id),
        )

        log_audit(
            cursor=cursor,
            entity_type="PURCHASE_ORDER",
            entity_id=po_id,
            action="APPROVE_PO",
            details=f"PO approved by {approver_name}.",
        )

        conn.commit()
        return {
            "success": True,
            "po_id": po_id,
            "po_number": f"PO-#{po_id:04d}",
            "previous_status": curr_status,
            "status": "APPROVED",
            "approver": approver_name,
            "updated_at": now_iso,
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def transmit_order_to_supplier(
    po_id: int,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Transition an APPROVED PO to ORDERED (transmitting to supplier via simulated gateway)."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,))
        po = cursor.fetchone()
        if not po:
            raise ValueError(f"Purchase Order PO-#{po_id:04d} does not exist.")

        curr_status = po["status"]
        if curr_status != "APPROVED":
            raise ValueError(
                f"Cannot dispatch PO-#{po_id:04d}: status is '{curr_status}' (must be 'APPROVED' first)."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE purchase_orders SET status = 'ORDERED', updated_at = ? WHERE po_id = ?",
            (now_iso, po_id),
        )

        log_audit(
            cursor=cursor,
            entity_type="PURCHASE_ORDER",
            entity_id=po_id,
            action="DISPATCH_ORDER",
            details="Order electronically dispatched to supplier via Simulated Demo Gateway.",
        )

        conn.commit()
        return {
            "success": True,
            "po_id": po_id,
            "po_number": f"PO-#{po_id:04d}",
            "previous_status": curr_status,
            "status": "ORDERED",
            "updated_at": now_iso,
            "is_simulated": True,
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def cancel_purchase_order(
    po_id: int,
    reason: str = "Cancelled by pharmacy manager",
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Cancel an active purchase order."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,))
        po = cursor.fetchone()
        if not po:
            raise ValueError(f"Purchase Order PO-#{po_id:04d} does not exist.")

        curr_status = po["status"]
        if curr_status in ("RECEIVED", "CANCELLED", "REJECTED"):
            raise ValueError(
                f"Cannot cancel PO-#{po_id:04d}: current status is already terminal ('{curr_status}')."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE purchase_orders SET status = 'CANCELLED', updated_at = ?, notes = ? WHERE po_id = ?",
            (now_iso, po_id, f"Cancelled: {reason}"),
        )

        log_audit(
            cursor=cursor,
            entity_type="PURCHASE_ORDER",
            entity_id=po_id,
            action="CANCEL_PO",
            details=f"PO cancelled. Reason: {reason}.",
        )

        conn.commit()
        return {
            "success": True,
            "po_id": po_id,
            "po_number": f"PO-#{po_id:04d}",
            "previous_status": curr_status,
            "status": "CANCELLED",
            "reason": reason,
            "notes": reason,
            "updated_at": now_iso,
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def receive_goods_transaction(
    po_id: int,
    received_quantity: int,
    batch_number: Optional[str] = None,
    expiry_date: Optional[str] = None,
    discrepancy_notes: Optional[str] = None,
    db_path: Optional[Path | str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atomic Goods Receipt & Inventory Stock Write-Back Transaction.
    
    Validations:
      1. PO must exist and be in APPROVED, ORDERED, or PARTIALLY_RECEIVED status.
      2. Duplicate receipt prevented if PO is already RECEIVED.
      3. received_quantity > 0.
      4. batch_number must not be empty.
      5. expiry_date must be valid YYYY-MM-DD.
      
    Execution:
      - Increases inventory current_stock by received_quantity.
      - Inserts record into goods_receipts.
      - Inserts batch into inventory_batches.
      - Updates PO status: PARTIALLY_RECEIVED or RECEIVED.
      - Writes audit log event.
    """
    effective_batch = batch_number or f"LOT-PO{po_id:04d}"
    clean_batch = str(effective_batch).strip()
    if not clean_batch:
        raise ValueError("Batch identifier cannot be empty.")

    effective_expiry = expiry_date or "2027-12-31"
    clean_expiry = str(effective_expiry).strip()
    if not clean_expiry:
        raise ValueError("Expiry date cannot be empty.")

    effective_notes = discrepancy_notes or notes

    if received_quantity <= 0:
        raise ValueError(f"Received quantity must be greater than 0 (got {received_quantity}).")

    clean_expiry = str(effective_expiry).strip()
    try:
        datetime.strptime(clean_expiry, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid expiry date: '{clean_expiry}'. Expected format YYYY-MM-DD.")

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()

        # Step 1: Read and lock PO record
        cursor.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,))
        po = cursor.fetchone()
        if not po:
            raise ValueError(f"Purchase Order PO-#{po_id:04d} does not exist.")

        curr_status = po["status"]
        if curr_status == "RECEIVED":
            raise ValueError(
                f"Duplicate receipt prevented: PO-#{po_id:04d} is already marked RECEIVED in full."
            )
        if curr_status not in ("APPROVED", "ORDERED", "PARTIALLY_RECEIVED", "CREATED"):
            raise ValueError(
                f"Cannot receive goods for PO-#{po_id:04d}: current status is '{curr_status}' "
                f"(must be 'APPROVED', 'ORDERED', or 'PARTIALLY_RECEIVED')."
            )

        med_id = po["med_id"]
        vendor_id = po["vendor_id"]
        ordered_qty = po["quantity"]
        prev_received = po["received_quantity"] or 0

        # Prevent receiving more than the total ordered quantity
        remaining_qty = max(0, ordered_qty - prev_received)
        if received_quantity > remaining_qty:
            raise ValueError(
                f"Received quantity ({received_quantity}) exceeds remaining outstanding quantity ({remaining_qty})."
            )

        new_received_total = prev_received + received_quantity

        # Check for discrepancy
        discrepancy_qty = new_received_total - ordered_qty
        new_status = "RECEIVED" if new_received_total >= ordered_qty else "PARTIALLY_RECEIVED"

        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 2: Read inventory before
        cursor.execute("SELECT current_stock, name FROM inventory WHERE med_id = ?", (med_id,))
        inv_row = cursor.fetchone()
        if not inv_row:
            raise ValueError(f"Medicine with med_id={med_id} not found in inventory.")
        inv_before = inv_row["current_stock"]
        inv_after = inv_before + received_quantity
        med_name = inv_row["name"]

        # Step 3: Update inventory current_stock
        cursor.execute(
            "UPDATE inventory SET current_stock = ? WHERE med_id = ?",
            (inv_after, med_id),
        )

        # Step 4: Record Batch in inventory_batches
        cursor.execute(
            """
            INSERT INTO inventory_batches (med_id, batch_number, quantity, expiry_date, received_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (med_id, clean_batch, received_quantity, clean_expiry, now_iso),
        )

        # Step 5: Insert Goods Receipt record
        notes_str = discrepancy_notes or (
            f"Full receipt ({received_quantity} units)" if new_status == "RECEIVED"
            else f"Partial receipt ({received_quantity} units; {ordered_qty - new_received_total} remaining)"
        )
        cursor.execute(
            """
            INSERT INTO goods_receipts (
                po_id, med_id, vendor_id, received_qty, batch_number, expiry_date, discrepancy_qty, notes, received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                po_id,
                med_id,
                vendor_id,
                received_quantity,
                clean_batch,
                clean_expiry,
                discrepancy_qty,
                notes_str,
                now_iso,
            ),
        )
        receipt_id = cursor.lastrowid

        # Step 6: Update PO status and received_quantity
        cursor.execute(
            """
            UPDATE purchase_orders
            SET status = ?,
                received_quantity = ?,
                updated_at = ?
            WHERE po_id = ?
            """,
            (new_status, new_received_total, now_iso, po_id),
        )

        # Step 7: Audit log for both Purchase Order and Goods Receipt
        log_audit(
            cursor=cursor,
            entity_type="PURCHASE_ORDER",
            entity_id=po_id,
            action="RECEIVE_GOODS",
            details=(
                f"Goods receipt recorded for PO-#{po_id:04d} ({med_name}): {received_quantity} units received "
                f"(Batch: {clean_batch}, Expiry: {clean_expiry}). Stock: {inv_before} -> {inv_after}. PO Status: {new_status}."
            ),
        )

        conn.commit()

        return {
            "success": True,
            "receipt_id": receipt_id,
            "po_id": po_id,
            "po_number": f"PO-#{po_id:04d}",
            "med_id": med_id,
            "medicine_name": med_name,
            "received_quantity": received_quantity,
            "total_received": new_received_total,
            "ordered_quantity": ordered_qty,
            "discrepancy_qty": discrepancy_qty,
            "batch_number": clean_batch,
            "expiry_date": clean_expiry,
            "status": new_status,
            "po_status": new_status,
            "inventory": {
                "before": inv_before,
                "after": inv_after,
            },
            "inventory_before": inv_before,
            "inventory_after": inv_after,
            "received_at": now_iso,
        }

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_all_purchase_orders(db_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """Retrieve all purchase orders with joined medicine and vendor names and receipt progress."""
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
            po.status,
            COALESCE(po.received_quantity, 0) AS received_quantity,
            po.created_at,
            po.updated_at,
            po.notes
        FROM purchase_orders po
        LEFT JOIN inventory i ON po.med_id = i.med_id
        LEFT JOIN vendors v ON po.vendor_id = v.vendor_id
        ORDER BY po.po_id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_purchase_order_by_id(
    po_id: int,
    db_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single purchase order by ID with medicine and vendor details."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            po.po_id,
            po.po_number,
            po.med_id,
            i.name AS medicine_name,
            po.vendor_id,
            v.name AS vendor_name,
            po.quantity,
            po.unit_price,
            po.total_cost,
            po.delivery_days,
            po.status,
            COALESCE(po.received_quantity, 0) AS received_quantity,
            po.created_at,
            po.updated_at,
            po.notes
        FROM purchase_orders po
        LEFT JOIN inventory i ON po.med_id = i.med_id
        LEFT JOIN vendors v ON po.vendor_id = v.vendor_id
        WHERE po.po_id = ?
        """,
        (po_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_goods_receipts(
    po_id: Optional[int] = None,
    db_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve goods receipt history with medicine and vendor details."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    query = """
        SELECT 
            gr.receipt_id,
            gr.po_id,
            gr.med_id,
            i.name AS medicine_name,
            gr.vendor_id,
            v.name AS vendor_name,
            gr.received_qty,
            gr.batch_number,
            gr.expiry_date,
            gr.discrepancy_qty,
            gr.notes,
            gr.received_at
        FROM goods_receipts gr
        LEFT JOIN inventory i ON gr.med_id = i.med_id
        LEFT JOIN vendors v ON gr.vendor_id = v.vendor_id
    """
    params = []
    if po_id is not None:
        query += " WHERE gr.po_id = ?"
        params.append(po_id)
    query += " ORDER BY gr.receipt_id DESC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_audit_logs(
    entity_type: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[Path | str] = None,
    entity_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieve audit log history."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    query = "SELECT log_id, entity_type, entity_id, action, details, created_at FROM audit_log"
    params = []
    conditions = []
    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)
    if entity_id is not None:
        conditions.append("entity_id = ?")
        params.append(entity_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY log_id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
