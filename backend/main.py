from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from database.db import get_db_connection, init_db
    from database.seed import seed_db
    from agent.store_agent import StoreAgent
    from tools.inventory_tools import get_inventory as fetch_inventory, update_inventory_item, add_inventory_item
    from tools.vendor_tools import update_vendor_offer, add_vendor, add_vendor_offer
except ImportError:
    from backend.database.db import get_db_connection, init_db
    from backend.database.seed import seed_db
    from backend.agent.store_agent import StoreAgent
    from backend.tools.inventory_tools import get_inventory as fetch_inventory, update_inventory_item, add_inventory_item
    from backend.tools.vendor_tools import update_vendor_offer, add_vendor, add_vendor_offer




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



@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/inventory")
def get_inventory() -> List[Dict[str, Any]]:
    """Retrieve all inventory records from SQLite database using the inventory tool."""
    return fetch_inventory()


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
    """Retrieve all vendors from SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vendor_id, name
        FROM vendors
        ORDER BY vendor_id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/vendors", status_code=201)
def create_vendor_endpoint(payload: VendorCreateRequest) -> Dict[str, Any]:
    """Create a new vendor in master records."""
    try:
        created = add_vendor(name=payload.name)
        return {"success": True, "vendor": created}
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
    """Retrieve all purchase orders from SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
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
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


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

