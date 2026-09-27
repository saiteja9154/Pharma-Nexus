"""
Phase 6 Unit and Integration Tests: Purchase Order Creation & ERP Write-Back Engine.

Covers all 15 mandatory Phase 6 tests:
1. Valid ACCEPT -> PO created in SQLite
2. PO uses final negotiated unit price (not baseline quote)
3. PO total calculation deterministic (unit_price * quantity)
4. Inventory increases by exact PO quantity
5. REJECT -> execution blocked (no PO, no inventory change)
6. NO_ORDER -> execution blocked (no PO, no inventory change)
7. SWITCH_VENDOR -> execution blocked (no PO, no inventory change)
8. UNRESOLVED -> execution blocked (no PO, no inventory change)
9. ACCEPT + invalid validation -> execution blocked
10. Atomic rollback when PO creation fails (no inventory change)
11. Atomic rollback when inventory update fails (no PO created)
12. Duplicate execution prevented (idempotency)
13. PO API endpoint (/purchase-orders and /procurement/execute) returns created PO
14. Inventory update affects only the correct medicine
15. Full execution lifecycle integrity
"""

import pytest
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from fastapi.testclient import TestClient
from main import app
from database.db import get_db_connection, init_db
from database.seed import seed_db
from agent.store_agent import StoreAgent, AgentState, AgentActionType
from tools.purchase_order_tools import create_purchase_order_transaction, get_all_purchase_orders


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database schema is initialized and seeded before each test."""
    init_db()
    seed_db()


client = TestClient(app)


# ==============================================================================
# TEST 1: Valid ACCEPT -> PO created in SQLite
# ==============================================================================
def test_valid_accept_creates_purchase_order():
    """Test 1: StoreAgent evaluating an ACCEPT state creates a PO record in SQLite."""
    agent = StoreAgent()
    item = {
        "med_id": 1,
        "name": "Paracetamol",
        "current_stock": 40,
        "reorder_point": 50,
        "daily_sales": 20,
        "lead_time_days": 5,
        "expiry_date": "2026-12-31",
    }
    state = agent.evaluate_medicine(item)
    assert state.decision == "ACCEPT"
    assert state.validation_result["valid"] is True

    # Execute Phase 6
    exec_res = agent.execute_procurement(state)

    assert exec_res["success"] is True
    assert state.po is not None
    assert state.po["status"] == "CREATED"
    assert state.po["med_id"] == 1
    assert state.po["vendor_id"] == 2
    assert state.po["quantity"] == 250

    # Verify directly in SQLite
    conn = get_db_connection()
    po_row = conn.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (state.po["po_id"],)).fetchone()
    conn.close()

    assert po_row is not None
    assert po_row["med_id"] == 1
    assert po_row["vendor_id"] == 2
    assert po_row["quantity"] == 250
    assert po_row["status"] == "CREATED"


# ==============================================================================
# TEST 2: PO uses final negotiated unit price (not baseline quote)
# ==============================================================================
def test_po_uses_negotiated_unit_price():
    """Test 2: Final PO must reflect negotiated unit price ($7.86), not baseline quote ($8.50)."""
    agent = StoreAgent()
    item = {
        "med_id": 1,
        "name": "Paracetamol",
        "current_stock": 40,
        "reorder_point": 50,
        "daily_sales": 20,
        "lead_time_days": 5,
        "expiry_date": "2026-12-31",
    }
    state = agent.evaluate_medicine(item)
    baseline_price = state.selected_vendor["base_price"]  # $8.50
    negotiated_price = state.best_offer["unit_price"]      # $7.86

    assert baseline_price == 8.50
    assert negotiated_price == 7.86

    exec_res = agent.execute_procurement(state)
    assert exec_res["success"] is True
    assert state.po["unit_price"] == negotiated_price
    assert state.po["unit_price"] != baseline_price

    # Check database
    conn = get_db_connection()
    po_row = conn.execute("SELECT unit_price FROM purchase_orders WHERE po_id = ?", (state.po["po_id"],)).fetchone()
    conn.close()
    assert po_row["unit_price"] == 7.86


# ==============================================================================
# TEST 3: PO total calculation deterministic (unit_price * quantity)
# ==============================================================================
def test_po_total_cost_calculation():
    """Test 3: PO total_cost must equal negotiated_unit_price * final_quantity (7.86 * 250 = 1965.00)."""
    agent = StoreAgent()
    item = {
        "med_id": 1,
        "name": "Paracetamol",
        "current_stock": 40,
        "reorder_point": 50,
        "daily_sales": 20,
        "lead_time_days": 5,
        "expiry_date": "2026-12-31",
    }
    state = agent.evaluate_medicine(item)
    exec_res = agent.execute_procurement(state)

    assert exec_res["success"] is True
    expected_total = round(7.86 * 250, 2)  # 1965.00
    assert state.po["total_cost"] == expected_total
    assert state.po["total_cost"] == 1965.00

    conn = get_db_connection()
    po_row = conn.execute("SELECT total_cost FROM purchase_orders WHERE po_id = ?", (state.po["po_id"],)).fetchone()
    conn.close()
    assert po_row["total_cost"] == 1965.00


# ==============================================================================
# TEST 4: Inventory increases by exact PO quantity
# ==============================================================================
def test_inventory_increases_by_exact_po_quantity():
    """Test 4: Restocking current_stock = inventory_before (40) + ordered_quantity (250) = 290."""
    conn = get_db_connection()
    stock_before = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()
    assert stock_before == 40

    agent = StoreAgent()
    item = {
        "med_id": 1,
        "name": "Paracetamol",
        "current_stock": 40,
        "reorder_point": 50,
        "daily_sales": 20,
        "lead_time_days": 5,
        "expiry_date": "2026-12-31",
    }
    state = agent.evaluate_medicine(item)
    exec_res = agent.execute_procurement(state)

    assert exec_res["success"] is True
    assert exec_res["inventory_before"] == 40
    assert exec_res["inventory_after"] == 290

    conn = get_db_connection()
    stock_after = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()
    assert stock_after == 290


# ==============================================================================
# TEST 5: REJECT -> execution blocked
# ==============================================================================
def test_reject_decision_blocks_execution():
    """Test 5: Decision REJECT must be blocked by execution guard without DB mutations."""
    state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40},
        decision="REJECT",
        validation_result={"valid": False, "reason": "Vendor rejected all proposals"},
        selected_vendor={"vendor_id": 1, "vendor_name": "Vendor A"},
        best_offer=None,
    )
    agent = StoreAgent()
    exec_res = agent.execute_procurement(state)

    assert exec_res["success"] is False
    assert exec_res["error"] == "INVALID_DECISION"

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()

    assert po_count == 0
    assert stock == 40


# ==============================================================================
# TEST 6: NO_ORDER -> execution blocked
# ==============================================================================
def test_no_order_decision_blocks_execution():
    """Test 6: Decision NO_ORDER must be blocked without DB mutations."""
    state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40},
        decision="NO_ORDER",
        validation_result={"valid": False, "reason": "No feasible vendor quote available."},
        selected_vendor=None,
        best_offer=None,
    )
    agent = StoreAgent()
    exec_res = agent.execute_procurement(state)

    assert exec_res["success"] is False
    assert exec_res["error"] == "INVALID_DECISION"

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()

    assert po_count == 0
    assert stock == 40


# ==============================================================================
# TEST 7: SWITCH_VENDOR -> execution blocked
# ==============================================================================
def test_switch_vendor_decision_blocks_execution():
    """Test 7: Decision SWITCH_VENDOR must be blocked without creating PO for old vendor."""
    state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40},
        decision="SWITCH_VENDOR",
        validation_result={"valid": False, "reason": "Deal failed validation, alternative available"},
        selected_vendor={"vendor_id": 2, "vendor_name": "Vendor B"},
        best_offer={"vendor_id": 2, "quantity": 250, "unit_price": 8.08, "status": "UNACCEPTED_COUNTER"},
    )
    agent = StoreAgent()
    exec_res = agent.execute_procurement(state)

    assert exec_res["success"] is False
    assert exec_res["error"] == "INVALID_DECISION"

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()

    assert po_count == 0
    assert stock == 40


# ==============================================================================
# TEST 8: UNRESOLVED -> execution blocked
# ==============================================================================
def test_unresolved_negotiation_blocks_execution():
    """Test 8: Unresolved negotiation state must be blocked from PO execution."""
    state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40},
        decision="NEGOTIATION_UNRESOLVED",
        validation_result={"valid": False, "reason": "Negotiation status is UNRESOLVED"},
        selected_vendor={"vendor_id": 2, "vendor_name": "Vendor B"},
        best_offer={"vendor_id": 2, "quantity": 250, "unit_price": 8.08, "status": "UNACCEPTED_COUNTER"},
    )
    agent = StoreAgent()
    exec_res = agent.execute_procurement(state)

    assert exec_res["success"] is False
    assert exec_res["error"] == "INVALID_DECISION"

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    conn.close()
    assert po_count == 0


# ==============================================================================
# TEST 9: ACCEPT + invalid validation -> execution blocked
# ==============================================================================
def test_accept_with_invalid_validation_is_blocked():
    """Test 9: Critical Guard Test — If decision is ACCEPT but validation_result['valid'] is False, execution MUST be blocked."""
    state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40},
        decision="ACCEPT",
        validation_result={"valid": False, "reason": "Simulated security/business rule constraint bypass attempt"},
        selected_vendor={"vendor_id": 2, "vendor_name": "Vendor B"},
        best_offer={"vendor_id": 2, "quantity": 9999, "unit_price": 0.01, "status": "ACCEPTED"},
    )
    agent = StoreAgent()
    exec_res = agent.execute_procurement(state)

    assert exec_res["success"] is False
    assert exec_res["error"] == "INVALID_VALIDATION"

    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()

    assert po_count == 0
    assert stock == 40


# ==============================================================================
# TEST 10: Atomic rollback when PO creation fails
# ==============================================================================
def test_atomic_rollback_on_po_creation_failure():
    """Test 10: If an error occurs during PO insertion, inventory is untouched and transaction rolled back."""
    conn = get_db_connection()
    stock_before = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    
    # Create temporary SQLite trigger to simulate failure on INSERT purchase_orders
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS simulate_po_insert_failure
        BEFORE INSERT ON purchase_orders
        BEGIN
            SELECT RAISE(ABORT, 'Simulated PO insert failure for atomic rollback test');
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
    conn.execute("DROP TRIGGER IF EXISTS simulate_po_insert_failure;")
    conn.commit()
    conn.close()

    assert po_count == 0
    assert stock_after == stock_before


# ==============================================================================
# TEST 11: Atomic rollback when inventory update fails
# ==============================================================================
def test_atomic_rollback_on_inventory_update_failure():
    """Test 11: If inventory update fails after PO insert, transaction rolls back with 0 POs created."""
    conn = get_db_connection()
    stock_before = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    
    # Create temporary SQLite trigger to simulate failure on UPDATE inventory
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS simulate_inventory_failure
        BEFORE UPDATE ON inventory
        BEGIN
            SELECT RAISE(ABORT, 'Simulated inventory update failure for atomic rollback test');
        END;
    """)
    conn.commit()
    conn.close()

    # Attempt transaction -> Must raise Exception and roll back
    with pytest.raises(Exception):
        create_purchase_order_transaction(
            med_id=1,
            vendor_id=2,
            quantity=250,
            unit_price=7.86,
            total_cost=1965.00,
            delivery_days=2,
        )

    # Verify no PO was saved and stock is unchanged
    conn = get_db_connection()
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock_after = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.execute("DROP TRIGGER IF EXISTS simulate_inventory_failure;")
    conn.commit()
    conn.close()

    assert po_count == 0
    assert stock_after == stock_before


    assert po_count == 0
    assert stock_after == stock_before


# ==============================================================================
# TEST 12: Duplicate execution prevented (Idempotency)
# ==============================================================================
def test_duplicate_execution_prevented():
    """Test 12: Executing the same accepted procurement twice must only create 1 PO and update stock once."""
    agent = StoreAgent()
    item = {
        "med_id": 1,
        "name": "Paracetamol",
        "current_stock": 40,
        "reorder_point": 50,
        "daily_sales": 20,
        "lead_time_days": 5,
        "expiry_date": "2026-12-31",
    }
    state = agent.evaluate_medicine(item)

    # First execution -> Success
    res1 = agent.execute_procurement(state)
    assert res1["success"] is True
    po_id_1 = state.po["po_id"]

    conn = get_db_connection()
    po_count_1 = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock_1 = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()

    assert po_count_1 == 1
    assert stock_1 == 290

    # Second execution on same state -> Blocked
    res2 = agent.execute_procurement(state)
    assert res2["success"] is False
    assert res2["error"] == "DUPLICATE_EXECUTION"

    conn = get_db_connection()
    po_count_2 = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock_2 = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    conn.close()

    assert po_count_2 == 1
    assert stock_2 == 290


# ==============================================================================
# TEST 13: PO API returns created PO
# ==============================================================================
def test_purchase_order_api_lifecycle():
    """Test 13: POST /procurement/execute creates PO, and GET /purchase-orders returns it."""
    # Execute procurement via API endpoint
    res = client.post("/procurement/execute", json={"medicine_id": 1})
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["decision"] == "ACCEPT"
    assert data["po"]["medicine_name"] == "Paracetamol"
    assert data["po"]["quantity"] == 250
    assert data["po"]["unit_price"] == 7.86
    assert data["po"]["total_cost"] == 1965.00
    assert data["inventory"]["before"] == 40
    assert data["inventory"]["after"] == 290

    # Query GET /purchase-orders
    po_res = client.get("/purchase-orders")
    assert po_res.status_code == 200
    orders = po_res.json()

    assert len(orders) >= 1
    created_po = orders[0]
    assert created_po["medicine_name"] == "Paracetamol"
    assert created_po["vendor_name"] == "Vendor B"
    assert created_po["quantity"] == 250
    assert created_po["unit_price"] == 7.86
    assert created_po["total_cost"] == 1965.00
    assert created_po["status"] == "CREATED"


# ==============================================================================
# TEST 14: Inventory update affects only the correct medicine
# ==============================================================================
def test_inventory_update_affects_only_target_medicine():
    """Test 14: Executing PO for Paracetamol (med_id: 1) must NOT modify Cetirizine (med_id: 2) or Azithromycin (med_id: 3)."""
    conn = get_db_connection()
    cet_before = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 2").fetchone()[0]
    azi_before = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 3").fetchone()[0]
    conn.close()

    assert cet_before == 25
    assert azi_before == 15

    # Execute Paracetamol only
    res = client.post("/procurement/execute", json={"medicine_id": 1})
    assert res.status_code == 200

    conn = get_db_connection()
    para_after = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 1").fetchone()[0]
    cet_after = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 2").fetchone()[0]
    azi_after = conn.execute("SELECT current_stock FROM inventory WHERE med_id = 3").fetchone()[0]
    conn.close()

    assert para_after == 290  # 40 + 250
    assert cet_after == 25   # Untouched
    assert azi_after == 15   # Untouched


# ==============================================================================
# TEST 15: Full execution lifecycle integrity (Cetirizine & Azithromycin)
# ==============================================================================
def test_full_execution_lifecycle_all_hero_medicines():
    """Test 15: Fresh database execution for Cetirizine and Azithromycin reaches correct PO and stock amounts."""
    # Seed fresh DB
    init_db()
    seed_db()

    # Cetirizine: stock 25, req 30, vendor 2 (Vendor B), base 2.20, negotiated 2.04, total 61.20, stock_after 55
    res_cet = client.post("/procurement/execute", json={"medicine_id": 2})
    assert res_cet.status_code == 200
    cet_data = res_cet.json()
    assert cet_data["success"] is True
    assert cet_data["po"]["quantity"] == 30
    assert cet_data["po"]["unit_price"] == 2.04
    assert cet_data["po"]["total_cost"] == 61.20
    assert cet_data["inventory"]["before"] == 25
    assert cet_data["inventory"]["after"] == 55

    # Azithromycin: stock 15, req 20, vendor 2 (Vendor B), base 14.50, negotiated 13.41, total 268.20, stock_after 35
    res_azi = client.post("/procurement/execute", json={"medicine_id": 3})
    assert res_azi.status_code == 200
    azi_data = res_azi.json()
    assert azi_data["success"] is True
    assert azi_data["po"]["quantity"] == 20
    assert azi_data["po"]["unit_price"] == 13.41
    assert azi_data["po"]["total_cost"] == 268.20
    assert azi_data["inventory"]["before"] == 15
    assert azi_data["inventory"]["after"] == 35

    # Check total purchase orders in database
    conn = get_db_connection()
    total_pos = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    conn.close()
    assert total_pos == 2
