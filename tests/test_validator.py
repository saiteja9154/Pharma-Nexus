"""
Phase 5 Unit and Integration Tests: Decision & Deal Validation Engine.

Covers all 14 mandatory validation tests:
1. Valid deal -> VALID
2. Quantity below required quantity -> INVALID
3. Quantity below MOQ -> INVALID
4. Quantity above expiry-safe quantity -> INVALID
5. Price violates reservation ceiling -> INVALID
6. Delivery violates configured maximum delivery days -> INVALID
7. Invalid or nonexistent selected vendor -> INVALID
8. UNRESOLVED negotiation cannot become ACCEPT
9. Valid negotiated deal -> ACCEPT
10. Invalid deal with no fallback -> REJECT / NO_ORDER
11. Valid alternative vendor -> SWITCH_VENDOR
12. Savings calculation (baseline_total, negotiated_total, savings, savings_percent)
13. Phase 5 ACCEPT does NOT create a Purchase Order
14. Phase 5 does NOT mutate inventory quantities
"""

import pytest
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from database.db import get_db_connection, init_db
from database.seed import seed_db
from agent.store_agent import StoreAgent, AgentState, AgentActionType
from tools.validator import validate_deal, calculate_deal_savings


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database schema is initialized and seeded before each test."""
    init_db()
    seed_db()


# ==============================================================================
# TEST 1: Valid deal -> VALID
# ==============================================================================
def test_valid_deal_passes_all_checks():
    """Test 1: A deal satisfying all 7 constraints returns valid=True and all checks pass."""
    deal = {
        "vendor_id": 2,
        "vendor_name": "Vendor B",
        "quantity": 250,
        "unit_price": 7.86,
        "initial_price": 8.50,
        "delivery_days": 2,
        "status": "ACCEPTED",
    }
    context = {
        "required_qty": 100,
        "moq": 250,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.50,
        "max_delivery_days": 5,
        "selected_vendor_id": 2,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "ACCEPTED",
    }
    result = validate_deal(deal, context)

    assert result["valid"] is True
    assert len(result["failed_checks"]) == 0
    assert result["checks"]["required_qty"] is True
    assert result["checks"]["moq"] is True
    assert result["checks"]["expiry"] is True
    assert result["checks"]["price"] is True
    assert result["checks"]["delivery"] is True
    assert result["checks"]["vendor"] is True
    assert result["checks"]["negotiation_status"] is True
    assert "satisfies all procurement constraints" in result["reason"]


# ==============================================================================
# TEST 2: Quantity below required quantity -> INVALID
# ==============================================================================
def test_quantity_below_required_qty_fails():
    """Test 2: Negotiated quantity below required quantity fails validation."""
    deal = {
        "vendor_id": 2,
        "quantity": 80,  # Required is 100
        "unit_price": 7.86,
        "delivery_days": 2,
        "status": "ACCEPTED",
    }
    context = {
        "required_qty": 100,
        "moq": 50,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.50,
        "selected_vendor_id": 2,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "ACCEPTED",
    }
    result = validate_deal(deal, context)

    assert result["valid"] is False
    assert "required_qty" in result["failed_checks"]
    assert result["checks"]["required_qty"] is False
    assert "below required quantity" in result["reason"]


# ==============================================================================
# TEST 3: Quantity below MOQ -> INVALID
# ==============================================================================
def test_quantity_below_moq_fails():
    """Test 3: Negotiated quantity below vendor MOQ fails validation."""
    deal = {
        "vendor_id": 1,
        "quantity": 300,  # MOQ is 500
        "unit_price": 7.50,
        "delivery_days": 5,
        "status": "ACCEPTED",
    }
    context = {
        "required_qty": 100,
        "moq": 500,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.00,
        "selected_vendor_id": 1,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "ACCEPTED",
    }
    result = validate_deal(deal, context)

    assert result["valid"] is False
    assert "moq" in result["failed_checks"]
    assert result["checks"]["moq"] is False
    assert "below vendor MOQ" in result["reason"]


# ==============================================================================
# TEST 4: Quantity above expiry-safe quantity -> INVALID
# ==============================================================================
def test_quantity_exceeding_expiry_safe_qty_fails():
    """Test 4: Negotiated quantity exceeding shelf-life safe capacity fails validation."""
    deal = {
        "vendor_id": 2,
        "quantity": 2000,  # Safe limit is 1920
        "unit_price": 7.86,
        "delivery_days": 2,
        "status": "ACCEPTED",
    }
    context = {
        "required_qty": 100,
        "moq": 250,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.50,
        "selected_vendor_id": 2,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "ACCEPTED",
    }
    result = validate_deal(deal, context)

    assert result["valid"] is False
    assert "expiry" in result["failed_checks"]
    assert result["checks"]["expiry"] is False
    assert "exceeds expiry-safe quantity" in result["reason"]


# ==============================================================================
# TEST 5: Price violates reservation/floor -> INVALID
# ==============================================================================
def test_price_violating_reservation_ceiling_fails():
    """Test 5a: Negotiated price above buyer reservation ceiling fails validation."""
    deal = {
        "vendor_id": 2,
        "quantity": 250,
        "unit_price": 9.20,  # Ceiling is 8.50
        "delivery_days": 2,
        "status": "ACCEPTED",
    }
    context = {
        "required_qty": 100,
        "moq": 250,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.50,
        "selected_vendor_id": 2,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "ACCEPTED",
    }
    result = validate_deal(deal, context)

    assert result["valid"] is False
    assert "price" in result["failed_checks"]
    assert result["checks"]["price"] is False
    assert "exceeds reservation ceiling" in result["reason"]


def test_price_violating_vendor_floor_fails():
    """Test 5b: Negotiated price violating vendor reservation/floor price fails validation."""
    # Vendor B base price is 8.50 -> 8% max concession -> Floor is 7.82
    # An offer of 7.50 violates the floor -> INVALID
    invalid_deal = {
        "vendor_id": 2,
        "quantity": 250,
        "unit_price": 7.50,  # Below floor 7.82
        "delivery_days": 2,
        "status": "ACCEPTED",
    }
    context = {
        "required_qty": 100,
        "moq": 250,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.50,
        "vendor_floor_price": 7.82,
        "selected_vendor_id": 2,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "ACCEPTED",
    }
    result_invalid = validate_deal(invalid_deal, context)

    assert result_invalid["valid"] is False
    assert "price" in result_invalid["failed_checks"]
    assert result_invalid["checks"]["price"] is False
    assert "violates vendor reservation/floor price" in result_invalid["reason"]

    # Valid price above floor: 7.86 >= 7.82 -> VALID
    valid_deal = {
        "vendor_id": 2,
        "quantity": 250,
        "unit_price": 7.86,
        "delivery_days": 2,
        "status": "ACCEPTED",
    }
    result_valid = validate_deal(valid_deal, context)
    assert result_valid["valid"] is True
    assert result_valid["checks"]["price"] is True



# ==============================================================================
# TEST 6: Delivery violates configured constraint -> INVALID
# ==============================================================================
def test_delivery_violating_max_sla_fails():
    """Test 6: Delivery timeline exceeding maximum configured days fails validation."""
    deal = {
        "vendor_id": 1,
        "quantity": 500,
        "unit_price": 7.50,
        "delivery_days": 7,  # Configured SLA max is 4 days
        "status": "ACCEPTED",
    }
    context = {
        "required_qty": 100,
        "moq": 500,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.00,
        "max_delivery_days": 4,
        "selected_vendor_id": 1,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "ACCEPTED",
    }
    result = validate_deal(deal, context)

    assert result["valid"] is False
    assert "delivery" in result["failed_checks"]
    assert result["checks"]["delivery"] is False
    assert "exceeds maximum acceptable timeline" in result["reason"]


# ==============================================================================
# TEST 7: Invalid/nonexistent selected vendor -> INVALID
# ==============================================================================
def test_invalid_vendor_mismatch_fails():
    """Test 7: Vendor not in quote candidates or mismatch with selected vendor fails validation."""
    deal = {
        "vendor_id": 99,  # Nonexistent vendor
        "quantity": 250,
        "unit_price": 7.86,
        "delivery_days": 2,
        "status": "ACCEPTED",
    }
    context = {
        "required_qty": 100,
        "moq": 250,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.50,
        "selected_vendor_id": 2,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "ACCEPTED",
    }
    result = validate_deal(deal, context)

    assert result["valid"] is False
    assert "vendor" in result["failed_checks"]
    assert result["checks"]["vendor"] is False


# ==============================================================================
# TEST 8: UNRESOLVED negotiation cannot become ACCEPT
# ==============================================================================
def test_unresolved_negotiation_cannot_become_accept():
    """Test 8: Negotiation status UNRESOLVED must fail validation and cannot be ACCEPT."""
    deal = {
        "vendor_id": 2,
        "quantity": 250,
        "unit_price": 8.08,
        "delivery_days": 2,
        "status": "UNACCEPTED_COUNTER",
    }
    context = {
        "required_qty": 100,
        "moq": 250,
        "expiry_safe_qty": 1920,
        "reservation_price": 8.50,
        "selected_vendor_id": 2,
        "candidate_vendor_ids": [1, 2, 3],
        "negotiation_status": "UNRESOLVED",
    }
    result = validate_deal(deal, context)

    assert result["valid"] is False
    assert "negotiation_status" in result["failed_checks"]
    assert result["checks"]["negotiation_status"] is False
    assert "not ACCEPTED" in result["reason"]


# ==============================================================================
# TEST 9: Valid negotiated deal -> ACCEPT
# ==============================================================================
def test_valid_negotiated_deal_results_in_accept_decision():
    """Test 9: StoreAgent evaluates a valid medicine, negotiates, validates, and sets decision=ACCEPT."""
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
    assert state.validation_result is not None
    assert state.validation_result["valid"] is True
    assert state.savings is not None
    assert state.savings["savings"] > 0
    assert "Ready for PO creation" in state.decision_reason


# ==============================================================================
# TEST 10: Invalid deal with no fallback -> NO_ORDER or REJECT
# ==============================================================================
def test_invalid_deal_no_fallback_results_in_no_order():
    """Test 10: When constraints cannot be satisfied by any vendor, decision is NO_ORDER."""
    agent = StoreAgent()
    item = {
        "med_id": 1,
        "name": "Paracetamol",
        "current_stock": 10,
        "reorder_point": 50,
        "daily_sales": 20,
        "lead_time_days": 5,
        "expiry_date": "2020-01-01",  # Expired -> 0 safe capacity -> 0 feasible vendors
    }
    state = agent.evaluate_medicine(item)

    assert state.decision == "NO_ORDER"
    assert state.validation_result is not None
    assert state.validation_result["valid"] is False
    assert "No vendor satisfies" in state.decision_reason or "No feasible vendor" in state.decision_reason


# ==============================================================================
# TEST 11: Valid alternative vendor -> SWITCH_VENDOR
# ==============================================================================
def test_deal_failure_with_alternative_feasible_vendor_triggers_switch():
    """Test 11: If negotiated deal fails validation but another candidate vendor is feasible, decision is SWITCH_VENDOR."""
    agent = StoreAgent()
    state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40, "reorder_point": 50, "daily_sales": 20, "lead_time_days": 5, "expiry_date": "2026-12-31"},
        required_qty=100,
        constraints={"expiry": {"expiry_safe_qty": 1920}},
        vendor_quotes=[
            {"vendor_id": 1, "vendor_name": "Vendor A", "feasible": True, "score": 70.0},
            {"vendor_id": 2, "vendor_name": "Vendor B", "feasible": True, "score": 85.0},
        ],
        selected_vendor={"vendor_id": 2, "vendor_name": "Vendor B", "base_price": 8.50, "moq": 250, "delivery_days": 2},
        negotiation={"status": "UNRESOLVED"},
        best_offer={
            "vendor_id": 2,
            "vendor_name": "Vendor B",
            "quantity": 250,
            "unit_price": 8.08,
            "delivery_days": 2,
            "status": "UNACCEPTED_COUNTER",
        },
    )

    agent.validate_and_decide(state)

    assert state.decision == "SWITCH_VENDOR"
    assert state.validation_result["valid"] is False
    assert "Alternative feasible vendor" in state.decision_reason
    assert "Vendor A" in state.decision_reason


# ==============================================================================
# TEST 12: Savings calculation
# ==============================================================================
def test_savings_calculation_accuracy():
    """Test 12: Deterministic verification of baseline_total, negotiated_total, savings, savings_percent."""
    # Scenario: 250 units, baseline price $8.50, negotiated price $7.86
    res = calculate_deal_savings(initial_price=8.50, negotiated_price=7.86, quantity=250)

    # 8.50 * 250 = 2125.00
    assert res["baseline_total"] == 2125.00
    # 7.86 * 250 = 1965.00
    assert res["negotiated_total"] == 1965.00
    # 2125.00 - 1965.00 = 160.00
    assert res["savings"] == 160.00
    # (160 / 2125) * 100 = 7.5294... -> 7.53%
    assert res["savings_percent"] == 7.53

    # Zero / negative handling
    zero_res = calculate_deal_savings(initial_price=0.0, negotiated_price=0.0, quantity=0)
    assert zero_res["savings"] == 0.0
    assert zero_res["savings_percent"] == 0.0


# ==============================================================================
# TEST 13 & 14: Phase 5 boundary safety (PO count = 0, Inventory unchanged)
# ==============================================================================
def test_phase5_accept_does_not_create_purchase_order_or_mutate_inventory():
    """Test 13 & 14: Running Phase 5 validation and decision MUST NOT insert POs or update stock."""
    conn = get_db_connection()
    po_count_before = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock_before = conn.execute("SELECT med_id, current_stock FROM inventory ORDER BY med_id").fetchall()
    conn.close()

    assert po_count_before == 0

    # Run complete Phase 5 agent cycle
    agent = StoreAgent()
    result = agent.run()

    # Confirm deals reached ACCEPT
    assert result["deals_accepted_count"] > 0

    # Verify database state after Phase 5
    conn = get_db_connection()
    po_count_after = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    stock_after = conn.execute("SELECT med_id, current_stock FROM inventory ORDER BY med_id").fetchall()
    conn.close()

    # Invariants
    assert po_count_after == 0, f"Purchase orders were created ({po_count_after}), violating Phase 5 boundary!"
    assert [dict(r) for r in stock_after] == [dict(r) for r in stock_before], "Inventory stock was modified!"
