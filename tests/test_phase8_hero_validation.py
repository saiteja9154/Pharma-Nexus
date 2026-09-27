"""
Phase 8 Comprehensive Hero Scenario Testing & System Validation Suite.
Validates the complete end-to-end autonomous procurement system:
- Clean baseline database integrity
- Hero Scenario 1 (Paracetamol) complete audit
- Hero Scenario 2 (Cetirizine) complete audit
- Hero Scenario 3 (Azithromycin) complete audit & deterministic ZOPA validation
- Complete decision branches (ACCEPT, REJECT, NO_ORDER, SWITCH_VENDOR, UNRESOLVED)
- Execution safety guards (Invalid validation blocked, non-ACCEPT blocked)
- Duplicate execution idempotency
- Atomic database transaction rollbacks
- Cross-medicine state isolation
- Multi-run reproducibility & determinism
- Full REST API integration flow
"""

import pytest
import sqlite3
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from fastapi.testclient import TestClient
from main import app
from database.db import get_db_connection, init_db
from database.seed import seed_db
from agent.store_agent import StoreAgent, AgentState, AgentActionType
from tools.inventory_tools import calculate_need, check_expiry, get_inventory
from tools.vendor_tools import get_vendor_quotes
from tools.deal_scoring import score_quotes
from tools.purchase_order_tools import create_purchase_order_transaction, get_all_purchase_orders

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_clean_database():
    """Ensure clean baseline seeded database before every test."""
    init_db()
    seed_db()


# ==============================================================================
# SECTION 2: CLEAN BASELINE DATABASE VERIFICATION
# ==============================================================================
def test_clean_baseline_database_state():
    """Verify clean database contains 0 purchase orders, 3 medicines, 3 vendors, 9 offers."""
    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    inv_rows = conn.execute("SELECT med_id, name, current_stock, reorder_point, daily_sales, lead_time_days, expiry_date FROM inventory ORDER BY med_id").fetchall()
    vendor_rows = conn.execute("SELECT vendor_id, name FROM vendors ORDER BY vendor_id").fetchall()
    offer_count = conn.execute("SELECT COUNT(*) FROM vendor_offers").fetchone()[0]
    conn.close()

    assert po_count == 0
    assert len(inv_rows) == 3
    assert len(vendor_rows) == 3
    assert offer_count == 9

    # Verify frozen baseline stock values
    inv_dict = {r["med_id"]: dict(r) for r in inv_rows}
    assert inv_dict[1]["name"] == "Paracetamol" and inv_dict[1]["current_stock"] == 40
    assert inv_dict[2]["name"] == "Cetirizine" and inv_dict[2]["current_stock"] == 25
    assert inv_dict[3]["name"] == "Azithromycin" and inv_dict[3]["current_stock"] == 15


# ==============================================================================
# SECTION 3: HERO SCENARIO 1 — PARACETAMOL
# ==============================================================================
def test_hero_scenario_1_paracetamol():
    """
    Hero Scenario 1: Paracetamol End-to-End Workflow & Execution Audit.
    - Initial Stock: 40 (Reorder: 50) -> Need: 100
    - Selected Vendor: Vendor B (Score: 65.50, Base: $8.50, MOQ: 250, Delivery: 2d)
    - Negotiation: Round 1 offer $7.65 -> Counter $8.07 -> Round 2 counter $7.86 -> Vendor ACCEPT $7.86
    - Validation: PASS all 7 constraints
    - Decision: ACCEPT
    - PO Created: 250 units @ $7.86 = $1965.00
    - Inventory Stock: 40 -> 290
    - Savings: $160.00 (7.53%)
    """
    agent = StoreAgent()
    para_item = next(i for i in get_inventory() if i["med_id"] == 1)
    state = agent.evaluate_medicine(para_item)

    # 1. Need & Expiry
    assert state.required_qty == 100
    assert state.constraints["expiry"]["expiry_safe_qty"] > 250

    # 2. Vendor Selection
    assert state.selected_vendor["vendor_id"] == 2
    assert state.selected_vendor["vendor_name"] == "Vendor B"
    assert state.selected_vendor["moq"] == 250
    assert state.selected_vendor["offered_qty"] == 250
    assert state.selected_vendor["delivery_days"] == 2

    # 3. Negotiation & Agreement
    assert state.negotiation["status"] == "ACCEPTED"
    assert state.best_offer["unit_price"] == 7.86
    assert state.best_offer["quantity"] == 250
    assert state.best_offer["total_cost"] == 1965.00
    assert state.best_offer["savings"] == 160.00
    assert state.best_offer["discount_pct"] == 7.53

    # 4. Phase 5 Validation
    assert state.validation_result["valid"] is True
    assert state.decision == "ACCEPT"

    # 5. Phase 6 Execution
    exec_res = agent.execute_procurement(state)
    assert exec_res["success"] is True
    assert exec_res["inventory_before"] == 40
    assert exec_res["inventory_after"] == 290

    # 6. Database Verification
    conn = get_db_connection()
    po = conn.execute("SELECT * FROM purchase_orders WHERE med_id = 1").fetchone()
    stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()

    assert po is not None
    assert po["vendor_id"] == 2
    assert po["quantity"] == 250
    assert po["unit_price"] == 7.86
    assert po["total_cost"] == 1965.00
    assert po["delivery_days"] == 2
    assert po["status"] == "CREATED"
    assert stock == 290


# ==============================================================================
# SECTION 4: HERO SCENARIO 2 — CETIRIZINE
# ==============================================================================
def test_hero_scenario_2_cetirizine():
    """
    Hero Scenario 2: Cetirizine End-to-End Workflow & Execution Audit.
    - Initial Stock: 25 (Reorder: 30) -> Need: 25
    - Selected Vendor: Vendor B (Score: 74.17, Base: $2.20, MOQ: 30, Delivery: 2d)
    - Negotiation: Round 1 offer $1.98 -> Counter $2.09 -> Round 2 counter $2.04 -> Vendor ACCEPT $2.04
    - Validation: PASS all 7 constraints
    - Decision: ACCEPT
    - PO Created: 30 units @ $2.04 = $61.20
    - Inventory Stock: 25 -> 55
    - Savings: $4.80 (7.27%)
    """
    agent = StoreAgent()
    cet_item = next(i for i in get_inventory() if i["med_id"] == 2)
    state = agent.evaluate_medicine(cet_item)

    # 1. Need & Expiry
    assert state.required_qty == 25
    assert state.constraints["expiry"]["expiry_safe_qty"] >= 30

    # 2. Vendor Selection
    assert state.selected_vendor["vendor_id"] == 2
    assert state.selected_vendor["vendor_name"] == "Vendor B"
    assert state.selected_vendor["moq"] == 30
    assert state.selected_vendor["offered_qty"] == 30

    # 3. Negotiation & Agreement
    assert state.negotiation["status"] == "ACCEPTED"
    assert state.best_offer["unit_price"] == 2.04
    assert state.best_offer["quantity"] == 30
    assert state.best_offer["total_cost"] == 61.20
    assert state.best_offer["savings"] == 4.80
    assert state.best_offer["discount_pct"] == 7.27

    # 4. Phase 5 Validation
    assert state.validation_result["valid"] is True
    assert state.decision == "ACCEPT"

    # 5. Phase 6 Execution
    exec_res = agent.execute_procurement(state)
    assert exec_res["success"] is True
    assert exec_res["inventory_before"] == 25
    assert exec_res["inventory_after"] == 55

    # 6. Database Verification
    conn = get_db_connection()
    po = conn.execute("SELECT * FROM purchase_orders WHERE med_id = 2").fetchone()
    stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 2").fetchone()[0]
    conn.close()

    assert po is not None
    assert po["vendor_id"] == 2
    assert po["quantity"] == 30
    assert po["unit_price"] == 2.04
    assert po["total_cost"] == 61.20
    assert stock == 55


# ==============================================================================
# SECTION 5, 6, 7: HERO SCENARIO 3 — AZITHROMYCIN (ROOT-CAUSE & RULE CONSISTENCY)
# ==============================================================================
def test_hero_scenario_3_azithromycin_root_cause_analysis():
    """
    Hero Scenario 3: Azithromycin Root-Cause & Deterministic Audit.
    - Initial Stock: 15 (Reorder: 20, daily_sales: 5, lead: 4, safety: 2) -> Need: 15
    - Expiry: 55 days left -> expiry_safe_qty: 275 units
    - Candidate Quotes:
        * Vendor A: Base $12.00, MOQ 50, Delivery 7d -> Total $600.00, Score 51.0
        * Vendor B: Base $14.50, MOQ 20, Delivery 2d -> Total $290.00, Score 66.88 (WINNER)
        * Vendor C: Base $16.00, MOQ 30, Delivery 4d -> Total $480.00, Score 31.0
    - Negotiation with Vendor B:
        * Buyer Target: $13.05 (10% discount), Ceiling: $14.50
        * Vendor Floor: $13.34 (8% max concession)
        * Round 1: Offer $13.05 -> Counter $13.78
        * Round 2: Counter midpoint $13.41 -> Vendor ACCEPT $13.41 (since 13.41 >= 13.34)
    - Validation: All 7 constraints PASS (13.34 <= 13.41 <= 14.50, qty 20 <= 275)
    - Outcome: ACCEPT is 100% deterministic and rule-consistent with frozen seed data.
    """
    agent = StoreAgent()
    azi_item = next(i for i in get_inventory() if i["med_id"] == 3)
    state = agent.evaluate_medicine(azi_item)

    # Need calculation check
    assert state.required_qty == 15

    # Expiry calculation check
    assert state.constraints["expiry"]["expiry_safe_qty"] >= 200
    assert state.constraints["expiry"]["expiry_safe_qty"] >= 20

    # Vendor selection check
    assert state.selected_vendor["vendor_id"] == 2
    assert state.selected_vendor["vendor_name"] == "Vendor B"
    assert state.selected_vendor["offered_qty"] == 20

    # Negotiation check
    assert state.negotiation["status"] == "ACCEPTED"
    assert state.best_offer["unit_price"] == 13.41
    assert state.best_offer["quantity"] == 20
    assert state.best_offer["total_cost"] == 268.20
    assert state.best_offer["savings"] == 21.80
    assert state.best_offer["discount_pct"] == 7.52

    # Validation check
    assert state.validation_result["valid"] is True
    assert state.decision == "ACCEPT"

    # Execution check
    exec_res = agent.execute_procurement(state)
    assert exec_res["success"] is True
    assert exec_res["inventory_before"] == 15
    assert exec_res["inventory_after"] == 35

    # Database state check
    conn = get_db_connection()
    po = conn.execute("SELECT * FROM purchase_orders WHERE med_id = 3").fetchone()
    stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 3").fetchone()[0]
    conn.close()

    assert po is not None
    assert po["vendor_id"] == 2
    assert po["quantity"] == 20
    assert po["unit_price"] == 13.41
    assert po["total_cost"] == 268.20
    assert stock == 35


# ==============================================================================
# SECTION 9: COMPLETE STATE MACHINE DECISION BRANCHES
# ==============================================================================
def test_decision_branches_state_machine():
    """
    Verify all 5 decision branches:
    1. ACCEPT: PO count += 1, stock increases
    2. REJECT: PO count = 0, stock unchanged
    3. NO_ORDER: PO count = 0, stock unchanged
    4. SWITCH_VENDOR: PO count = 0, stock unchanged
    5. UNRESOLVED: PO count = 0, stock unchanged
    """
    agent = StoreAgent()

    # 1. ACCEPT branch
    accept_state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40},
        decision="ACCEPT",
        validation_result={"valid": True, "reason": "All checks passed"},
        selected_vendor={"vendor_id": 2, "vendor_name": "Vendor B", "delivery_days": 2},
        best_offer={"vendor_id": 2, "quantity": 250, "unit_price": 7.86, "delivery_days": 2, "status": "ACCEPTED"},
    )
    res_accept = agent.execute_procurement(accept_state)
    assert res_accept["success"] is True
    assert res_accept["inventory_after"] == 290

    # 2. REJECT branch
    reject_state = AgentState(
        medicine={"med_id": 2, "name": "Cetirizine"},
        inventory={"current_stock": 25},
        decision="REJECT",
        validation_result={"valid": False, "reason": "Vendor rejected proposals"},
        selected_vendor={"vendor_id": 1, "vendor_name": "Vendor A"},
        best_offer=None,
    )
    res_reject = agent.execute_procurement(reject_state)
    assert res_reject["success"] is False
    assert res_reject["error"] == "INVALID_DECISION"

    # 3. NO_ORDER branch
    no_order_state = AgentState(
        medicine={"med_id": 3, "name": "Azithromycin"},
        inventory={"current_stock": 15},
        decision="NO_ORDER",
        validation_result={"valid": False, "reason": "No feasible supplier"},
        selected_vendor=None,
        best_offer=None,
    )
    res_no_order = agent.execute_procurement(no_order_state)
    assert res_no_order["success"] is False
    assert res_no_order["error"] == "INVALID_DECISION"

    # 4. SWITCH_VENDOR branch
    switch_state = AgentState(
        medicine={"med_id": 2, "name": "Cetirizine"},
        inventory={"current_stock": 25},
        decision="SWITCH_VENDOR",
        validation_result={"valid": False, "reason": "Deal failed validation, switch available"},
        selected_vendor={"vendor_id": 2, "vendor_name": "Vendor B"},
        best_offer={"vendor_id": 2, "quantity": 30, "unit_price": 2.04, "status": "UNACCEPTED_COUNTER"},
    )
    res_switch = agent.execute_procurement(switch_state)
    assert res_switch["success"] is False
    assert res_switch["error"] == "INVALID_DECISION"

    # 5. UNRESOLVED branch
    unresolved_state = AgentState(
        medicine={"med_id": 3, "name": "Azithromycin"},
        inventory={"current_stock": 15},
        decision="NEGOTIATION_UNRESOLVED",
        validation_result={"valid": False, "reason": "Bargaining rounds expired without agreement"},
        selected_vendor={"vendor_id": 2, "vendor_name": "Vendor B"},
        best_offer={"vendor_id": 2, "quantity": 20, "unit_price": 13.41, "status": "UNACCEPTED_COUNTER"},
    )
    res_unres = agent.execute_procurement(unresolved_state)
    assert res_unres["success"] is False
    assert res_unres["error"] == "INVALID_DECISION"

    # Verify database PO count is exactly 1 (only from ACCEPT) and Cetirizine/Azithromycin stocks untouched
    conn = get_db_connection()
    total_pos = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    cet_stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 2").fetchone()[0]
    azi_stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 3").fetchone()[0]
    conn.close()

    assert total_pos == 1
    assert cet_stock == 25
    assert azi_stock == 15


# ==============================================================================
# SECTION 10, 11, 12, 13: EXECUTION SAFETY, DUPLICATES, ROLLBACK, ISOLATION
# ==============================================================================
def test_execution_guard_invalid_validation_blocked():
    """Security guard: ACCEPT with invalid validation MUST be rejected."""
    state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40},
        decision="ACCEPT",
        validation_result={"valid": False, "reason": "Simulated bypass attempt"},
        selected_vendor={"vendor_id": 2, "vendor_name": "Vendor B"},
        best_offer={"vendor_id": 2, "quantity": 250, "unit_price": 7.86, "status": "ACCEPTED"},
    )
    agent = StoreAgent()
    res = agent.execute_procurement(state)

    assert res["success"] is False
    assert res["error"] == "INVALID_VALIDATION"

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    conn.close()
    assert po_count == 0


def test_duplicate_execution_safety():
    """Executing an accepted deal twice must not duplicate PO or increase inventory twice."""
    agent = StoreAgent()
    para_item = next(i for i in get_inventory() if i["med_id"] == 1)
    state = agent.evaluate_medicine(para_item)

    res1 = agent.execute_procurement(state)
    assert res1["success"] is True

    res2 = agent.execute_procurement(state)
    assert res2["success"] is False
    assert res2["error"] == "DUPLICATE_EXECUTION"

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()

    assert po_count == 1
    assert stock == 290


def test_transaction_rollback_po_failure():
    """Simulating PO insertion failure rolls back transaction completely."""
    conn = get_db_connection()
    stock_before = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS test_fail_po
        BEFORE INSERT ON purchase_orders
        BEGIN
            SELECT RAISE(ABORT, 'Simulated PO insert trigger failure');
        END;
    """)
    conn.commit()
    conn.close()

    with pytest.raises(Exception):
        create_purchase_order_transaction(
            med_id=1,
            vendor_id=2,
            quantity=250,
            unit_price=7.86,
            total_cost=1965.00,
            delivery_days=2,
        )

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock_after = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.execute("DROP TRIGGER IF EXISTS test_fail_po;")
    conn.commit()
    conn.close()

    assert po_count == 0
    assert stock_after == stock_before


def test_transaction_rollback_inventory_failure():
    """Simulating inventory update failure rolls back transaction completely."""
    conn = get_db_connection()
    stock_before = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS test_fail_inv
        BEFORE UPDATE ON inventory
        BEGIN
            SELECT RAISE(ABORT, 'Simulated inventory update trigger failure');
        END;
    """)
    conn.commit()
    conn.close()

    with pytest.raises(Exception):
        create_purchase_order_transaction(
            med_id=1,
            vendor_id=2,
            quantity=250,
            unit_price=7.86,
            total_cost=1965.00,
            delivery_days=2,
        )

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock_after = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.execute("DROP TRIGGER IF EXISTS test_fail_inv;")
    conn.commit()
    conn.close()

    assert po_count == 0
    assert stock_after == stock_before


def test_cross_medicine_isolation():
    """Executing PO for Cetirizine (med_id: 2) must not modify Paracetamol or Azithromycin stock."""
    res = client.post("/procurement/execute", json={"medicine_id": 2})
    assert res.status_code == 200

    conn = get_db_connection()
    para_stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    cet_stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 2").fetchone()[0]
    azi_stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 3").fetchone()[0]
    conn.close()

    assert para_stock == 40  # Untouched
    assert cet_stock == 55   # 25 + 30
    assert azi_stock == 15   # Untouched


# ==============================================================================
# SECTION 14 & 15: REPRODUCIBILITY & API FLOW
# ==============================================================================
def test_reproducibility_deterministic_outcomes():
    """Running full evaluation 3 times from fresh seed state yields identical decisions, prices, and quantities."""
    for _ in range(3):
        init_db()
        seed_db()
        agent = StoreAgent()
        res = agent.run()

        assert res["medicines_evaluated"] == 3
        assert res["deals_accepted_count"] == 3

        med1 = next(m for m in res["medicines"] if m["med_id"] == 1)
        med2 = next(m for m in res["medicines"] if m["med_id"] == 2)
        med3 = next(m for m in res["medicines"] if m["med_id"] == 3)

        assert med1["decision"] == "ACCEPT" and med1["best_offer"]["unit_price"] == 7.86 and med1["best_offer"]["quantity"] == 250
        assert med2["decision"] == "ACCEPT" and med2["best_offer"]["unit_price"] == 2.04 and med2["best_offer"]["quantity"] == 30
        assert med3["decision"] == "ACCEPT" and med3["best_offer"]["unit_price"] == 13.41 and med3["best_offer"]["quantity"] == 20


def test_full_rest_api_flow():
    """Verify all REST API endpoints: GET /inventory, /vendors, /vendor-offers, /purchase-orders, POST /procurement/start, /procurement/execute."""
    # 1. GET /inventory
    r_inv = client.get("/inventory")
    assert r_inv.status_code == 200
    assert len(r_inv.json()) == 3

    # 2. GET /vendors
    r_v = client.get("/vendors")
    assert r_v.status_code == 200
    assert len(r_v.json()) == 3

    # 3. GET /vendor-offers
    r_vo = client.get("/vendor-offers")
    assert r_vo.status_code == 200
    assert len(r_vo.json()) == 9

    # 4. GET /purchase-orders (initially 0)
    r_po0 = client.get("/purchase-orders")
    assert r_po0.status_code == 200
    assert len(r_po0.json()) == 0

    # 5. POST /procurement/start
    r_start = client.post("/procurement/start")
    assert r_start.status_code == 200
    start_data = r_start.json()
    assert start_data["status"] == "completed"
    assert len(start_data["medicines"]) == 3

    # 6. POST /procurement/execute for all medicines
    for med_id in [1, 2, 3]:
        r_exec = client.post("/procurement/execute", json={"medicine_id": med_id})
        assert r_exec.status_code == 200
        exec_data = r_exec.json()
        assert exec_data["success"] is True
        assert exec_data["decision"] == "ACCEPT"

    # 7. GET /purchase-orders (now contains 3 committed POs)
    r_po3 = client.get("/purchase-orders")
    assert r_po3.status_code == 200
    orders = r_po3.json()
    assert len(orders) == 3

    # Total spend verification: 1965.00 + 61.20 + 268.20 = 2294.40
    total_spend = sum(o["total_cost"] for o in orders)
    assert round(total_spend, 2) == 2294.40
