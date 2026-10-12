"""
Unit and Integration Tests for Real-World Procurement Agent Upgrade (Stages 1-6).

Covers:
1. Inventory need formulas (demand, lead time, safety stock, outstanding POs, near-expiry spoilage).
2. Deal scoring with configurable weights, supplier reliability, and trade-off rationale.
3. Supplier Gateway & negotiation behavior profiles with simulated labels.
4. Purchase Order safe lifecycle (DRAFT -> PENDING_APPROVAL -> APPROVED -> ORDERED -> PARTIALLY_RECEIVED -> RECEIVED).
5. Safe inventory invariant: stock NEVER increments on PO creation; increments ONLY on verified physical goods receipt.
6. Partial and complete goods receiving with batch tracking and discrepancy calculation.
7. Duplicate receipt prevention.
8. Atomic rollback on goods receipt error.
9. StoreAgent duplicate order suppression across repeated runs with active POs.
10. Vendor master data CRUD, reliability updates, and audit trail logging.
"""

import pytest
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from fastapi.testclient import TestClient
from main import app
from database.db import get_db_connection, init_db
from database.seed import seed_db
from agent.store_agent import StoreAgent
from tools.inventory_tools import calculate_need, check_expiry, get_inventory_item, get_inventory_batches
from tools.deal_scoring import score_quotes
from tools.supplier_gateway import SimulatedSupplierGateway
from tools.negotiation_tools import vendor_respond, calculate_target_price
from tools.purchase_order_tools import (
    create_purchase_order_transaction,
    approve_purchase_order,
    transmit_order_to_supplier,
    cancel_purchase_order,
    receive_goods_transaction,
    get_purchase_order_by_id,
    get_outstanding_po_qty,
    get_goods_receipts,
    get_audit_logs,
)
from tools.vendor_tools import get_vendor_by_id, update_vendor, get_vendor_offer


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database schema is initialized and seeded before each test."""
    init_db()
    seed_db()


client = TestClient(app)


# ==============================================================================
# 1. INVENTORY NEED CALCULATION FORMULAS & SPOILAGE AUDIT
# ==============================================================================

def test_need_calculation_formulas_and_explanation():
    """Verify standard demand, lead time, and safety stock formula with explainability."""
    result = calculate_need(
        current_stock=20,
        daily_sales=10,
        lead_time_days=5,
        safety_days=7,
        reorder_point=50,
    )

    # Lead time demand = 10 * 5 = 50
    assert result["lead_time_demand"] == 50
    # Safety stock = 10 * 7 = 70
    assert result["safety_stock"] == 70
    # Target stock = 50 + 70 = 120
    assert result["target_stock"] == 120
    # Required qty = 120 - 20 = 100
    assert result["required_qty"] == 100
    assert result["needs_reorder"] is True
    assert "Deficit: 100 units" in result["explanation"]


def test_need_calculation_accounts_for_outstanding_pos():
    """Verify that incoming on-order purchase orders prevent unnecessary duplicate reorders."""
    # Deficit without PO would be: target (120) - stock (20) = 100 units needed.
    # Case A: Outstanding PO of 40 units exists, but net stock (60) > reorder_point (50)
    result_covered = calculate_need(
        current_stock=20,
        daily_sales=10,
        lead_time_days=5,
        safety_days=7,
        outstanding_po_qty=40,
        reorder_point=50,
    )
    assert result_covered["net_available"] == 60
    assert result_covered["needs_reorder"] is False
    assert result_covered["required_qty"] == 0
    assert "Procurement already active or stock adequate" in result_covered["explanation"]

    # Case B: Outstanding PO of 10 units exists, net stock (30) <= reorder_point (50)
    result_partial = calculate_need(
        current_stock=20,
        daily_sales=10,
        lead_time_days=5,
        safety_days=7,
        outstanding_po_qty=10,
        reorder_point=50,
    )
    assert result_partial["net_available"] == 30
    assert result_partial["needs_reorder"] is True
    # Target 120 - net 30 = 90 units
    assert result_partial["required_qty"] == 90


def test_near_expiry_spoilage_and_consumption_estimate():
    """Verify expiry risk detects shelf-life constraints and calculates spoilage units."""
    # Current stock 100 units, but expiring in 10 days with daily sales of 2
    # Consumption capacity = 2 * 10 = 20 units. Spoilage risk = 100 - 20 = 80 units!
    expiry_res = check_expiry(days_left=10, daily_sales=2, lead_time_days=5, current_stock=100)
    assert expiry_res["expiry_risk"] is True
    assert expiry_res["estimated_consumption_before_expiry"] == 20
    assert expiry_res["spoilage_risk_units"] == 80


# ==============================================================================
# 2. DEAL SCORING WITH SUPPLIER RELIABILITY & CONFIGURABLE WEIGHTS
# ==============================================================================

def test_deal_scoring_with_reliability_and_custom_weights():
    """Verify multi-factor deal scoring incorporates supplier reliability with explainable breakdown."""
    quotes = [
        {
            "vendor_id": 1,
            "vendor_name": "Reliable Vendor",
            "base_price": 10.0,
            "delivery_days": 2,
            "moq": 50,
            "offered_qty": 100,
            "required_qty": 100,
            "reliability": 0.98,
        },
        {
            "vendor_id": 2,
            "vendor_name": "Cheaper but Less Reliable Vendor",
            "base_price": 9.0,
            "delivery_days": 3,
            "moq": 50,
            "offered_qty": 100,
            "required_qty": 100,
            "reliability": 0.85,
        },
    ]

    # Custom weights prioritizing reliability
    scored = score_quotes(
        quotes=quotes,
        weights={"price": 0.30, "delivery": 0.20, "moq": 0.10, "reliability": 0.40},
    )

    assert len(scored) == 2
    v1 = next(q for q in scored if q["vendor_id"] == 1)
    v2 = next(q for q in scored if q["vendor_id"] == 2)

    assert v1["reliability_score"] == 0.98
    assert v2["reliability_score"] == 0.85
    assert v1["score_breakdown"]["reliability"] == 98.0
    assert v2["score_breakdown"]["reliability"] == 85.0
    assert len(v1["reasons"]) > 0


# ==============================================================================
# 3. SUPPLIER GATEWAY & NEGOTIATION PROFILES (LABELED SIMULATION)
# ==============================================================================

def test_simulated_supplier_gateway_negotiation_profile():
    """Verify simulated negotiation returns labeled simulation flags and honors vendor profiles."""
    gateway = SimulatedSupplierGateway()

    # Vendor 2 (Vendor B - Flexible Profile)
    result = gateway.negotiate_terms(
        vendor_id=2,
        vendor_name="Vendor B",
        medicine_name="Paracetamol",
        quantity=250,
        initial_price=8.50,
        target_discount_pct=0.10,
    )

    assert result["is_simulated"] is True
    assert result["simulation_notice"] == "Simulated negotiation based on vendor profile behavioral model (Demo Mode)."
    assert result["status"] == "AGREED"
    assert len(result["turns"]) == 4  # 2 rounds * 2 turns
    # Best offer unit price should match the accepted deal (7.86)
    assert result["best_offer"]["unit_price"] == pytest.approx(7.86, rel=1e-2)


def test_supplier_negotiation_unresolved_when_target_too_aggressive():
    """Verify negotiation can result in UNRESOLVED/REJECT when agent discount exceeds vendor threshold."""
    gateway = SimulatedSupplierGateway()

    # Vendor 4 (Vendor D - Firm Profile, tolerance is small)
    # Requesting a 35% discount (unrealistically aggressive)
    result = gateway.negotiate_terms(
        vendor_id=4,
        vendor_name="Vendor D",
        medicine_name="Test Medicine",
        quantity=100,
        initial_price=10.00,
        target_discount_pct=0.35,
    )

    assert result["is_simulated"] is True
    # Firm vendor will counter minimally and not accept a 35% cut
    assert result["status"] in ("UNRESOLVED", "REJECTED")


# ==============================================================================
# 4. PURCHASE ORDER SAFE LIFECYCLE & INVENTORY INVARIANT
# ==============================================================================

def test_safe_lifecycle_inventory_invariant():
    """
    Critical Invariant:
    Creating a purchase order MUST NOT increase available inventory.
    Inventory increments ONLY upon explicit physical goods receipt.
    """
    med_id = 1
    initial_stock = get_inventory_item(med_id)["current_stock"]

    # 1. Create PO in PENDING_APPROVAL status
    po = create_purchase_order_transaction(
        medicine_id=med_id,
        vendor_id=2,
        quantity=100,
        unit_price=7.86,
        status="PENDING_APPROVAL",
    )
    po_id = po["po_id"]
    assert po["status"] == "PENDING_APPROVAL"

    # Verify inventory was NOT touched
    stock_after_create = get_inventory_item(med_id)["current_stock"]
    assert stock_after_create == initial_stock

    # 2. Approve PO
    approved_po = approve_purchase_order(po_id)
    assert approved_po["status"] == "APPROVED"

    # Verify inventory still unchanged
    stock_after_approve = get_inventory_item(med_id)["current_stock"]
    assert stock_after_approve == initial_stock

    # 3. Transmit/Dispatch PO to supplier
    ordered_po = transmit_order_to_supplier(po_id)
    assert ordered_po["status"] == "ORDERED"

    # Verify inventory still unchanged
    stock_after_order = get_inventory_item(med_id)["current_stock"]
    assert stock_after_order == initial_stock

    # 4. Receive physical goods
    receipt = receive_goods_transaction(
        po_id=po_id,
        received_quantity=100,
        batch_number="BATCH-TEST-INV-01",
        expiry_date="2027-12-31",
        notes="Inspected and verified good condition",
    )

    assert receipt["status"] == "RECEIVED"
    assert receipt["inventory"]["before"] == initial_stock
    assert receipt["inventory"]["after"] == initial_stock + 100

    # Verify inventory table is now incremented by exactly 100
    final_stock = get_inventory_item(med_id)["current_stock"]
    assert final_stock == initial_stock + 100


def test_partial_and_complete_goods_receipt():
    """Verify partial receiving splits and final receipt completes PO lifecycle."""
    med_id = 2
    initial_stock = get_inventory_item(med_id)["current_stock"]

    # Create & advance PO to ORDERED
    po = create_purchase_order_transaction(
        medicine_id=med_id,
        vendor_id=2,
        quantity=60,
        unit_price=2.04,
        status="ORDERED",
    )
    po_id = po["po_id"]

    # Partial receipt 1: 25 units
    res1 = receive_goods_transaction(
        po_id=po_id,
        received_quantity=25,
        batch_number="BATCH-PART-01",
        expiry_date="2027-06-30",
    )
    assert res1["status"] == "PARTIALLY_RECEIVED"
    assert res1["received_quantity"] == 25
    assert get_inventory_item(med_id)["current_stock"] == initial_stock + 25

    # Partial receipt 2: remaining 35 units
    res2 = receive_goods_transaction(
        po_id=po_id,
        received_quantity=35,
        batch_number="BATCH-PART-02",
        expiry_date="2027-06-30",
    )
    assert res2["status"] == "RECEIVED"
    assert res2["received_quantity"] == 35
    assert res2["total_received"] == 60
    assert get_inventory_item(med_id)["current_stock"] == initial_stock + 60

    # Batches recorded in inventory_batches
    batches = get_inventory_batches(med_id)
    batch_nums = [b["batch_number"] for b in batches]
    assert "BATCH-PART-01" in batch_nums
    assert "BATCH-PART-02" in batch_nums


def test_duplicate_receipt_prevention():
    """Verify receiving on an already fully received PO raises ValueError."""
    med_id = 3
    po = create_purchase_order_transaction(
        medicine_id=med_id,
        vendor_id=2,
        quantity=20,
        unit_price=13.41,
        status="ORDERED",
    )
    po_id = po["po_id"]

    # Fully receive
    receive_goods_transaction(po_id=po_id, received_quantity=20)

    # Attempting to receive again on fully received PO must be rejected
    with pytest.raises(ValueError, match="already.*RECEIVED|fully received"):
        receive_goods_transaction(po_id=po_id, received_quantity=10)


def test_over_receipt_prevention():
    """Verify attempting to receive more units than ordered is rejected."""
    med_id = 1
    po = create_purchase_order_transaction(
        medicine_id=med_id,
        vendor_id=2,
        quantity=50,
        unit_price=7.86,
        status="ORDERED",
    )
    po_id = po["po_id"]

    with pytest.raises(ValueError, match="exceeds remaining outstanding quantity"):
        receive_goods_transaction(po_id=po_id, received_quantity=60)


def test_po_cancellation_lifecycle():
    """Verify purchase orders in pre-delivery state can be cancelled cleanly."""
    po = create_purchase_order_transaction(
        medicine_id=1,
        vendor_id=1,
        quantity=30,
        unit_price=8.50,
        status="PENDING_APPROVAL",
    )
    po_id = po["po_id"]

    cancelled = cancel_purchase_order(po_id, reason="Budget freeze")
    assert cancelled["status"] == "CANCELLED"
    assert "Budget freeze" in cancelled.get("notes", "")

    # Cannot receive on a CANCELLED PO
    with pytest.raises(ValueError, match="Cannot receive goods for PO-"):
        receive_goods_transaction(po_id=po_id, received_quantity=30)


# ==============================================================================
# 5. ATOMIC ROLLBACK ON RECEIPT FAILURE
# ==============================================================================

def test_atomic_rollback_on_receipt_failure():
    """Verify database transaction rollbacks if batch insertion or stock update fails."""
    med_id = 1
    initial_stock = get_inventory_item(med_id)["current_stock"]

    po = create_purchase_order_transaction(
        medicine_id=med_id,
        vendor_id=2,
        quantity=40,
        unit_price=7.86,
        status="ORDERED",
    )
    po_id = po["po_id"]

    # Simulate an error by mocking log_audit to fail inside the transaction
    with patch("tools.purchase_order_tools.log_audit", side_effect=RuntimeError("Simulated audit write crash")):
        with pytest.raises(RuntimeError):
            receive_goods_transaction(po_id=po_id, received_quantity=40)

    # Verify inventory is untouched
    current_stock = get_inventory_item(med_id)["current_stock"]
    assert current_stock == initial_stock


# ==============================================================================
# 6. STORE AGENT DUPLICATE ORDER SUPPRESSION ACROSS REPEATED RUNS
# ==============================================================================

def test_agent_repeated_run_suppresses_duplicate_orders():
    """Verify repeated agent execution detects active on-order POs and avoids duplicate orders."""
    agent = StoreAgent()

    # Paracetamol (Med #1) starts at 40 units (reorder point 50)
    # Run 1: Agent evaluates and recommends procurement
    med1_item = get_inventory_item(1)
    eval1 = agent.evaluate_medicine(med1_item)
    assert eval1.required_qty == 100
    assert eval1.best_offer["quantity"] == 250
    assert eval1.decision == "ACCEPT"

    # Now create an active PO in ORDERED status covering the deficit
    create_purchase_order_transaction(
        medicine_id=1,
        vendor_id=2,
        quantity=250,
        unit_price=7.86,
        status="ORDERED",
    )

    # Run 2: Fresh database evaluation with active PO
    eval2 = agent.evaluate_medicine(med1_item)
    assert eval2.required_qty == 0
    assert eval2.decision in ("NO_ORDER", "NO_PROCUREMENT")
    assert "Procurement already active" in eval2.decision_reason


# ==============================================================================
# 7. VENDOR MASTER DATA & AUDIT TRAIL LOGGING
# ==============================================================================

def test_vendor_master_data_update_and_offers():
    """Verify vendor contact info, reliability rating, and payment terms can be updated."""
    updated = update_vendor(
        vendor_id=1,
        name="Vendor A Pharma Corp",
        reliability=0.99,
        contact_email="orders@vendora-pharma.com",
        payment_terms="Net 45",
    )
    assert updated["name"] == "Vendor A Pharma Corp"
    assert updated["reliability"] == 0.99
    assert updated["contact_email"] == "orders@vendora-pharma.com"
    assert updated["payment_terms"] == "Net 45"

    # Verify retrieved from DB
    vendor = get_vendor_by_id(1)
    assert vendor["reliability"] == 0.99
    assert vendor["contact_email"] == "orders@vendora-pharma.com"


def test_audit_trail_and_goods_receipts_logging():
    """Verify all PO lifecycle mutations are logged chronologically in audit_log and goods_receipts."""
    po = create_purchase_order_transaction(
        medicine_id=1,
        vendor_id=2,
        quantity=50,
        unit_price=7.86,
        status="PENDING_APPROVAL",
    )
    po_id = po["po_id"]
    approve_purchase_order(po_id)
    transmit_order_to_supplier(po_id)
    receive_goods_transaction(
        po_id=po_id,
        received_quantity=50,
        batch_number="BATCH-AUDIT-01",
        expiry_date="2028-01-01",
    )

    # Verify audit logs
    logs = get_audit_logs(entity_type="PURCHASE_ORDER", entity_id=po_id)
    actions = [log["action"] for log in logs]
    assert "CREATE_PO" in actions
    assert "APPROVE_PO" in actions
    assert "DISPATCH_ORDER" in actions
    assert "RECEIVE_GOODS" in actions

    # Verify goods receipt entry
    receipts = get_goods_receipts(po_id=po_id)
    assert len(receipts) == 1
    assert receipts[0]["batch_number"] == "BATCH-AUDIT-01"
    assert receipts[0]["received_qty"] == 50


# ==============================================================================
# 8. FASTAPI REST ENDPOINTS FOR STAGE 4 LIFECYCLE
# ==============================================================================

def test_fastapi_po_lifecycle_endpoints():
    """Verify FastAPI endpoints for approve, order, cancel, receive, and batches."""
    # 1. Create a PO
    create_res = client.post(
        "/purchase-orders",
        json={"medicine_id": 1, "vendor_id": 2, "quantity": 30, "unit_price": 7.86, "status": "PENDING_APPROVAL"},
    )
    assert create_res.status_code == 201
    po_data = create_res.json()["purchase_order"]
    po_id = po_data["po_id"]

    # 2. Approve via API
    app_res = client.post(f"/purchase-orders/{po_id}/approve")
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"

    # 3. Transmit to supplier via API
    ord_res = client.post(f"/purchase-orders/{po_id}/order")
    assert ord_res.status_code == 200
    assert ord_res.json()["status"] == "ORDERED"

    # 4. Receive goods via API
    rec_res = client.post(
        f"/purchase-orders/{po_id}/receive",
        json={
            "received_quantity": 30,
            "batch_number": "BATCH-API-01",
            "expiry_date": "2027-10-10",
            "notes": "Verified through REST API",
        },
    )
    assert rec_res.status_code == 200
    assert rec_res.json()["status"] == "RECEIVED"

    # 5. Fetch batches via API
    batch_res = client.get("/inventory/1/batches")
    assert batch_res.status_code == 200
    batches = batch_res.json()
    assert any(b["batch_number"] == "BATCH-API-01" for b in batches)

    # 6. Fetch goods receipts via API
    gr_res = client.get("/goods-receipts")
    assert gr_res.status_code == 200
    assert any(gr["po_id"] == po_id for gr in gr_res.json())

    # 7. Fetch audit logs via API
    audit_res = client.get("/audit-logs")
    assert audit_res.status_code == 200
    assert len(audit_res.json()) > 0
