from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from database.db import get_db_connection, init_db
    from database.seed import seed_db
    from agent.store_agent import StoreAgent
    from tools.inventory_tools import (
        get_inventory as fetch_inventory,
        update_inventory_item,
        add_inventory_item,
        get_inventory_item,
        get_inventory_batches,
    )
    from tools.vendor_tools import (
        update_vendor_offer,
        add_vendor,
        update_vendor,
        add_vendor_offer,
    )
    from tools.purchase_order_tools import (
        create_purchase_order_transaction,
        get_all_purchase_orders,
        approve_purchase_order,
        transmit_order_to_supplier,
        cancel_purchase_order,
        receive_goods_transaction,
        get_goods_receipts,
        get_audit_logs,
    )
except ImportError:
    from backend.database.db import get_db_connection, init_db
    from backend.database.seed import seed_db
    from backend.agent.store_agent import StoreAgent
    from backend.tools.inventory_tools import (
        get_inventory as fetch_inventory,
        update_inventory_item,
        add_inventory_item,
        get_inventory_item,
        get_inventory_batches,
    )
    from backend.tools.vendor_tools import (
        update_vendor_offer,
        add_vendor,
        update_vendor,
        add_vendor_offer,
    )
    from backend.tools.purchase_order_tools import (
        create_purchase_order_transaction,
        get_all_purchase_orders,
        approve_purchase_order,
        transmit_order_to_supplier,
        cancel_purchase_order,
        receive_goods_transaction,
        get_goods_receipts,
        get_audit_logs,
    )




@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context to ensure database initialization on startup."""
    init_db()
    # Ensure baseline seed data is populated if inventory is empty
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    conn.close()
    if count == 0:
        seed_db()
    yield


app = FastAPI(
    title="Pharma Nexus ERP API",
    description="Pharma Nexus V2 — Pharma ERP Smart Vendor Restocking & Bargaining API",
    version="4.0.0",
    lifespan=lifespan,
)

# Configure CORS for local Vite frontend
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response Models
class HealthResponse(BaseModel):
    status: str


class EvaluatedMedicine(BaseModel):
    med_id: int
    name: str
    current_stock: int
    reorder_point: int
    daily_sales: int
    lead_time_days: int
    required_qty: int
    procurement_needed: bool
    decision: str
    decision_reason: str
    vendor_quotes: Optional[List[Dict[str, Any]]] = None
    selected_vendor: Optional[Dict[str, Any]] = None
    negotiation: Optional[Dict[str, Any]] = None
    negotiation_history: Optional[List[Dict[str, Any]]] = None
    best_offer: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    savings: Optional[Dict[str, Any]] = None
    po: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    expiry: Optional[Dict[str, Any]] = None
    constraints: Optional[Dict[str, Any]] = None
    state: Optional[Dict[str, Any]] = None


class AgentLogEntry(BaseModel):
    step: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ProcurementStartResponse(BaseModel):
    run_id: Optional[str] = None
    timestamp: Optional[str] = None
    completed_at: Optional[str] = None
    status: str
    medicines_evaluated: int
    procurement_needed_count: int
    selected_vendor_count: Optional[int] = 0
    negotiation_accepted_count: Optional[int] = 0
    deals_validated_count: Optional[int] = 0
    deals_accepted_count: Optional[int] = 0
    total_savings: Optional[float] = 0.0
    medicines: List[EvaluatedMedicine]
    actions: List[Dict[str, Any]]
    logs: List[AgentLogEntry]


class ProcurementExecuteRequest(BaseModel):
    med_id: Optional[int] = None
    medicine_id: Optional[int] = None


class ProcurementExecuteResponse(BaseModel):
    success: bool
    decision: str
    message: Optional[str] = None
    po: Optional[Dict[str, Any]] = None
    inventory: Optional[Dict[str, Any]] = None
    savings: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class InventoryUpdateRequest(BaseModel):
    current_stock: int
    reorder_point: int
    daily_sales: int
    lead_time_days: int
    expiry_date: str


class InventoryCreateRequest(BaseModel):
    name: str
    current_stock: int
    reorder_point: int
    daily_sales: int
    lead_time_days: int
    expiry_date: str


class VendorCreateRequest(BaseModel):
    name: str
    reliability: Optional[float] = 0.95
    contact_email: Optional[str] = None
    payment_terms: Optional[str] = "Net 30"


class VendorUpdateRequest(BaseModel):
    name: str
    reliability: Optional[float] = 0.95
    contact_email: Optional[str] = None
    payment_terms: Optional[str] = "Net 30"


class VendorOfferUpdateRequest(BaseModel):
    base_price: float
    min_qty: int
    delivery_days: int


class VendorOfferCreateRequest(BaseModel):
    vendor_id: int
    med_id: int
    base_price: float
    min_qty: int
    delivery_days: int


class GoodsReceiptRequest(BaseModel):
    received_quantity: int
    batch_number: str
    expiry_date: str
    notes: Optional[str] = None


class POApproveRequest(BaseModel):
    approver: Optional[str] = "Chief Pharmacist"


class POCancelRequest(BaseModel):
    reason: Optional[str] = "Cancelled by user"


class PurchaseOrderCreateRequest(BaseModel):
    medicine_id: Optional[int] = None
    med_id: Optional[int] = None
    vendor_id: int
    quantity: int
    unit_price: float
    total_cost: Optional[float] = None
    delivery_days: Optional[int] = 3
    status: Optional[str] = "PENDING_APPROVAL"
    notes: Optional[str] = None



@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/inventory")
def get_inventory() -> List[Dict[str, Any]]:
    """Retrieve all inventory records from SQLite database using the inventory tool."""
    return fetch_inventory()


@app.get("/inventory/{med_id}")
def get_inventory_item_endpoint(med_id: int):
    """Retrieve details for a single medicine."""
    item = get_inventory_item(med_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Medicine ID {med_id} not found.")
    return item


@app.get("/inventory/{med_id}/batches")
def get_inventory_batches_endpoint(med_id: int):
    """Retrieve recorded batches for a specific medicine."""
    return get_inventory_batches(med_id)


@app.post("/inventory", status_code=201)
def create_inventory_endpoint(payload: InventoryCreateRequest) -> Dict[str, Any]:
    """Create a new medicine in master inventory."""
    try:
        created = add_inventory_item(
            name=payload.name,
            current_stock=payload.current_stock,
            reorder_point=payload.reorder_point,
            daily_sales=payload.daily_sales,
            lead_time_days=payload.lead_time_days,
            expiry_date=payload.expiry_date,
        )
        return {"success": True, "medicine": created}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/inventory/{med_id}")
def update_inventory_endpoint(med_id: int, payload: InventoryUpdateRequest) -> Dict[str, Any]:
    """Update master inventory data for a medicine."""
    try:
        updated = update_inventory_item(
            med_id=med_id,
            current_stock=payload.current_stock,
            reorder_point=payload.reorder_point,
            daily_sales=payload.daily_sales,
            lead_time_days=payload.lead_time_days,
            expiry_date=payload.expiry_date,
        )
        return {"success": True, "medicine": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vendors")
def get_vendors() -> List[Dict[str, Any]]:
    """Retrieve all vendors from SQLite database with reliability and contact terms."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vendor_id, name, COALESCE(reliability, 0.95) AS reliability, contact_email, COALESCE(payment_terms, 'Net 30') AS payment_terms
        FROM vendors
        ORDER BY vendor_id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/vendors/{vendor_id}")
def get_vendor_endpoint(vendor_id: int):
    """Retrieve a single vendor with details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT vendor_id, name, reliability, contact_email, payment_terms FROM vendors WHERE vendor_id = ?",
        (vendor_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Vendor ID {vendor_id} not found.")
    return dict(row)


@app.post("/vendors", status_code=201)
def create_vendor_endpoint(payload: VendorCreateRequest) -> Dict[str, Any]:
    """Create a new vendor in master records."""
    try:
        created = add_vendor(
            name=payload.name,
            reliability=payload.reliability if payload.reliability is not None else 0.95,
            contact_email=payload.contact_email,
            payment_terms=payload.payment_terms or "Net 30",
        )
        return {"success": True, "vendor": created}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/vendors/{vendor_id}")
def update_vendor_endpoint(vendor_id: int, payload: VendorUpdateRequest):
    """Update master vendor information."""
    try:
        updated = update_vendor(
            vendor_id=vendor_id,
            name=payload.name,
            reliability=payload.reliability if payload.reliability is not None else 0.95,
            contact_email=payload.contact_email,
            payment_terms=payload.payment_terms or "Net 30",
        )
        return {"success": True, "vendor": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vendor-offers")
def get_vendor_offers() -> List[Dict[str, Any]]:
    """Retrieve all vendor offers with joined vendor and medicine names."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            vo.vendor_id,
            v.name AS vendor_name,
            vo.med_id,
            i.name AS med_name,
            vo.base_price,
            vo.min_qty,
            vo.delivery_days
        FROM vendor_offers vo
        JOIN vendors v ON vo.vendor_id = v.vendor_id
        JOIN inventory i ON vo.med_id = i.med_id
        ORDER BY vo.vendor_id ASC, vo.med_id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/vendor-offers/{vendor_id}/{med_id}")
def get_vendor_offer_endpoint(vendor_id: int, med_id: int):
    """Retrieve a single contract offer."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            vo.vendor_id,
            v.name AS vendor_name,
            vo.med_id,
            i.name AS med_name,
            vo.base_price,
            vo.min_qty,
            vo.delivery_days
        FROM vendor_offers vo
        JOIN vendors v ON vo.vendor_id = v.vendor_id
        JOIN inventory i ON vo.med_id = i.med_id
        WHERE vo.vendor_id = ? AND vo.med_id = ?
        """,
        (vendor_id, med_id),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Vendor offer not found for vendor {vendor_id} and medicine {med_id}.")
    return dict(row)


@app.post("/vendor-offers", status_code=201)
def create_vendor_offer_endpoint(payload: VendorOfferCreateRequest) -> Dict[str, Any]:
    """Create a new contract offer for a vendor and medicine."""
    try:
        created = add_vendor_offer(
            vendor_id=payload.vendor_id,
            med_id=payload.med_id,
            base_price=payload.base_price,
            min_qty=payload.min_qty,
            delivery_days=payload.delivery_days,
        )
        return {"success": True, "offer": created}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/vendor-offers/{vendor_id}/{med_id}")
def update_vendor_offer_endpoint(vendor_id: int, med_id: int, payload: VendorOfferUpdateRequest) -> Dict[str, Any]:
    """Update master contract offer data for a vendor and medicine."""
    try:
        updated = update_vendor_offer(
            vendor_id=vendor_id,
            med_id=med_id,
            base_price=payload.base_price,
            min_qty=payload.min_qty,
            delivery_days=payload.delivery_days,
        )
        return {"success": True, "offer": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/purchase-orders")
def get_purchase_orders() -> List[Dict[str, Any]]:
    """Retrieve all purchase orders from SQLite database with status and receipt progress."""
    return get_all_purchase_orders()


@app.post("/purchase-orders", status_code=201)
def create_purchase_order_endpoint(payload: PurchaseOrderCreateRequest) -> Dict[str, Any]:
    """Create a new purchase order with safe lifecycle status."""
    med_id = payload.medicine_id or payload.med_id
    if not med_id:
        raise HTTPException(status_code=400, detail="medicine_id or med_id is required.")
    total_cost = payload.total_cost or round(payload.unit_price * payload.quantity, 2)
    try:
        po = create_purchase_order_transaction(
            med_id=med_id,
            vendor_id=payload.vendor_id,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            total_cost=total_cost,
            delivery_days=payload.delivery_days or 3,
            status=payload.status or "PENDING_APPROVAL",
            notes=payload.notes,
        )
        return {"success": True, "purchase_order": po}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/purchase-orders/{po_id}")
def get_single_purchase_order(po_id: int):
    """Retrieve details and receipt history for a single purchase order."""
    orders = get_all_purchase_orders()
    for o in orders:
        if o["po_id"] == po_id:
            receipts = get_goods_receipts(po_id=po_id)
            return {**o, "receipts": receipts}
    raise HTTPException(status_code=404, detail=f"Purchase order PO-#{po_id:04d} not found.")


@app.post("/purchase-orders/{po_id}/approve")
def approve_purchase_order_endpoint(po_id: int, payload: Optional[POApproveRequest] = None):
    """Approve a purchase order (PENDING_APPROVAL -> APPROVED)."""
    approver = payload.approver if payload else "Chief Pharmacist"
    try:
        return approve_purchase_order(po_id=po_id, approver_name=approver)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/purchase-orders/{po_id}/order")
def order_purchase_order_endpoint(po_id: int):
    """Dispatch an approved purchase order to supplier (APPROVED -> ORDERED)."""
    try:
        return transmit_order_to_supplier(po_id=po_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/purchase-orders/{po_id}/cancel")
def cancel_purchase_order_endpoint(po_id: int, payload: Optional[POCancelRequest] = None):
    """Cancel an active purchase order."""
    reason = payload.reason if payload else "Cancelled by user"
    try:
        return cancel_purchase_order(po_id=po_id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/purchase-orders/{po_id}/receive")
def receive_purchase_order_goods_endpoint(po_id: int, payload: GoodsReceiptRequest):
    """
    Record verified goods receipt, increment inventory stock, assign batch, and update PO status.
    """
    try:
        return receive_goods_transaction(
            po_id=po_id,
            received_quantity=payload.received_quantity,
            batch_number=payload.batch_number,
            expiry_date=payload.expiry_date,
            discrepancy_notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/goods-receipts")
def get_goods_receipts_endpoint(po_id: Optional[int] = None):
    """Retrieve goods receipt history."""
    return get_goods_receipts(po_id=po_id)


@app.get("/audit-logs")
def get_audit_logs_endpoint(entity_type: Optional[str] = None, limit: int = 100):
    """Retrieve audit log history."""
    return get_audit_logs(entity_type=entity_type, limit=limit)


@app.post("/procurement/start", response_model=ProcurementStartResponse)
def trigger_procurement():
    """
    Phase 4 & 5 StoreAgent evaluation endpoint.
    Runs autonomous Observe -> Reason -> Calculate Need -> Expiry Check ->
    Get Quotes -> Multi-factor Score -> Select Vendor -> Adaptive Bargaining -> Deal Validation.
    Read-only with respect to inventory and purchase orders.
    """
    agent = StoreAgent()
    result = agent.run()
    return result


@app.post("/negotiation/run", response_model=ProcurementStartResponse)
@app.post("/procurement/negotiate", response_model=ProcurementStartResponse)
def trigger_negotiation():
    """
    Dedicated Negotiation execution endpoint.
    Performs fresh SQLite inventory read, candidate quote discovery, vendor selection,
    and executes multi-round bargaining protocol & deal validation.
    """
    agent = StoreAgent()
    result = agent.run()
    return result


@app.get("/procurement/status")
@app.get("/agent/status")
def get_agent_status():
    """Get current agent readiness status and database summary."""
    conn = get_db_connection()
    cursor = conn.cursor()
    inv_count = cursor.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    vendor_count = cursor.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
    po_count = cursor.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    conn.close()
    return {
        "status": "ready",
        "inventory_count": inv_count,
        "vendor_count": vendor_count,
        "purchase_orders_count": po_count,
    }


@app.post("/database/seed")
@app.post("/database/reset")
def reset_database_endpoint():
    """Reset SQLite database to deterministic Phase 1 baseline seed data."""
    seed_db()
    return {"success": True, "message": "Database reset and seeded successfully."}


@app.post("/procurement/execute", response_model=ProcurementExecuteResponse)
def execute_procurement_endpoint(request: Optional[ProcurementExecuteRequest] = None):
    """
    Phase 6 ERP Write-Back execution endpoint.
    Runs StoreAgent autonomous procurement -> validates ACCEPT decision ->
    executes atomic SQLite transaction -> creates Purchase Order -> updates Inventory stock.
    """
    target_med_id = None
    if request:
        target_med_id = request.medicine_id or request.med_id

    agent = StoreAgent()
    result = agent.run(target_med_id=target_med_id)

    if target_med_id:
        state = agent.states.get(target_med_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Medicine ID {target_med_id} not found in inventory.")

        exec_res = agent.execute_procurement(state)
        if not exec_res.get("success"):
            return {
                "success": False,
                "decision": state.decision or "UNKNOWN",
                "message": exec_res.get("message") or exec_res.get("error"),
                "po": None,
                "inventory": None,
                "savings": None,
                "execution_result": None,
                "error": exec_res.get("error"),
            }

        return {
            "success": True,
            "decision": state.decision,
            "message": f"Purchase Order created and inventory updated for {state.medicine.get('name')}.",
            "po": state.po,
            "inventory": {
                "before": exec_res.get("inventory_before"),
                "after": exec_res.get("inventory_after"),
            },
            "savings": state.savings,
            "execution_result": exec_res.get("execution_result"),
        }
    else:
        executed_pos = []
        last_exec = None
        for state in agent.states.values():
            if state.decision == "ACCEPT" and state.validation_result and state.validation_result.get("valid"):
                exec_res = agent.execute_procurement(state)
                if exec_res.get("success"):
                    executed_pos.append(state.po)
                    last_exec = exec_res

        if not executed_pos:
            return {
                "success": False,
                "decision": "NO_ORDERS_EXECUTED",
                "message": "No accepted and validated deals found for execution.",
                "po": None,
                "inventory": None,
                "savings": None,
                "execution_result": None,
                "error": "NO_ELIGIBLE_DEALS",
            }

        return {
            "success": True,
            "decision": "ACCEPT",
            "message": f"Successfully created {len(executed_pos)} purchase orders in ERP.",
            "po": executed_pos[0] if len(executed_pos) == 1 else None,
            "inventory": {
                "before": last_exec.get("inventory_before") if last_exec else None,
                "after": last_exec.get("inventory_after") if last_exec else None,
            } if last_exec else None,
            "savings": None,
            "execution_result": {"executed_count": len(executed_pos), "pos": executed_pos},
        }

