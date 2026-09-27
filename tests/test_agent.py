import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from main import app
from database.db import get_db_connection, init_db
from database.seed import seed_db
from agent.store_agent import StoreAgent, AgentState, AgentActionType
from tools.inventory_tools import calculate_need, check_expiry
from tools.negotiation_tools import (
    vendor_respond,
    generate_agent_negotiation_action,
    calculate_target_price,
    calculate_reservation_price,
    MAX_NEGOTIATION_ROUNDS,
)
from tools.validator import validate_negotiation_action

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database schema is initialized and seeded before each test."""
    init_db()
    seed_db()


def test_health_endpoint():
    """Verify GET /health returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_purchase_orders_endpoint():
    """Verify GET /purchase-orders returns status 200 and a list."""
    response = client.get("/purchase-orders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_all_tables_exist():
    """Verify that all required Phase 1 tables exist in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row["name"] for row in cursor.fetchall()]
    conn.close()

    assert "inventory" in tables
    assert "vendors" in tables
    assert "vendor_offers" in tables
    assert "purchase_orders" in tables


# ==========================================
# PHASE 2 & 3 AGENT TESTS
# ==========================================

def test_low_stock_triggers_procurement_and_vendor_selection():
    """
    Given current_stock < reorder_point:
    - decision must be PROCUREMENT_REQUIRED
    - vendor_quotes must be retrieved and scored
    - one feasible vendor must be selected
    - negotiation must complete with best_offer
    """
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

    assert state.decision in ["PROCUREMENT_REQUIRED", "READY_FOR_VALIDATION", "ACCEPT"]
    assert state.required_qty == 100
    assert len(state.vendor_quotes) == 3
    assert state.selected_vendor is not None
    assert "vendor_name" in state.selected_vendor
    assert state.selected_vendor["score"] > 0
    assert state.best_offer is not None
    assert len(state.negotiation_history) > 0


def test_adequate_stock_no_procurement():
    """
    Given current_stock >= reorder_point:
    - decision must be NO_PROCUREMENT
    - required_qty must be 0
    - selected_vendor must be None
    - negotiation must be empty
    """
    agent = StoreAgent()
    item = {
        "med_id": 102,
        "name": "Ibuprofen",
        "current_stock": 80,
        "reorder_point": 50,
        "daily_sales": 10,
        "lead_time_days": 3,
        "expiry_date": "2027-01-01",
    }
    state = agent.evaluate_medicine(item)

    assert state.decision == "NO_PROCUREMENT"
    assert "at or above reorder point" in state.decision_reason
    assert state.required_qty == 0
    assert state.selected_vendor is None
    assert state.vendor_quotes == []
    assert state.negotiation_history == []
    assert state.best_offer is None


def test_agent_state_structure_phase4():
    """
    Verify AgentState schema and Phase 4 negotiation field population.
    """
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

    # Populated fields
    assert isinstance(state.medicine, dict)
    assert state.medicine["med_id"] == 1
    assert state.medicine["name"] == "Paracetamol"
    assert isinstance(state.inventory, dict)
    assert state.inventory["current_stock"] == 40
    assert state.required_qty == 100
    assert isinstance(state.constraints, dict)
    assert isinstance(state.vendor_quotes, list)
    assert len(state.vendor_quotes) == 3
    assert state.selected_vendor is not None
    assert isinstance(state.negotiation, dict)
    assert state.negotiation["status"] == "ACCEPTED"
    assert isinstance(state.negotiation_history, list)
    assert len(state.negotiation_history) >= 2
    assert state.best_offer is not None
    assert state.best_offer["unit_price"] <= state.selected_vendor["base_price"]
    assert state.decision in ["PROCUREMENT_REQUIRED", "READY_FOR_VALIDATION", "ACCEPT"]
    assert state.decision_reason is not None
    assert state.validation_result is not None
    assert state.validation_result["valid"] is True
    assert state.savings is not None

    # Phase 6+ placeholders remain None
    assert state.po is None


def test_procurement_start_endpoint_phase4():
    """
    Verify POST /procurement/start executes Phase 4 StoreAgent and returns negotiation results.
    """
    response = client.post("/procurement/start")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["medicines_evaluated"] == 3
    assert data["procurement_needed_count"] == 3
    assert data["selected_vendor_count"] == 3
    assert data["negotiation_accepted_count"] == 3
    assert len(data["medicines"]) == 3
    assert len(data["logs"]) > 0

    for med in data["medicines"]:
        assert med["procurement_needed"] is True
        assert len(med["vendor_quotes"]) == 3
        assert med["selected_vendor"] is not None
        assert med["negotiation"] is not None
        assert med["negotiation"]["status"] == "ACCEPTED"
        assert len(med["negotiation_history"]) >= 2
        assert med["best_offer"] is not None
        assert "savings" in med["best_offer"]
        assert "unit_price" in med["best_offer"]


def test_no_feasible_vendor_handling():
    """
    Verify agent gracefully handles scenario where all vendor quotes are infeasible.
    """
    agent = StoreAgent()
    # Medicine with expiry date that yields 0 safe capacity
    item = {
        "med_id": 1,
        "name": "Paracetamol",
        "current_stock": 10,
        "reorder_point": 50,
        "daily_sales": 20,
        "lead_time_days": 5,
        "expiry_date": "2020-01-01",  # Expired -> expiry_safe_qty = 0
    }
    state = agent.evaluate_medicine(item)

    assert state.selected_vendor is None
    assert state.decision in ["NO_FEASIBLE_VENDOR", "NO_ORDER"]
    assert ("No feasible vendor" in state.decision_reason or "No vendor satisfies" in state.decision_reason)
    assert state.best_offer is None


def test_agent_actions_trace():
    """
    Verify agent produces structured action history containing OBSERVE, CALCULATE, CHECK_EXPIRY, GET_QUOTES, SELECT_VENDOR, OFFER/COUNTER.
    """
    agent = StoreAgent()
    result = agent.run()

    action_types = [a["action"] for a in result["actions"]]
    assert AgentActionType.OBSERVE_INVENTORY.value in action_types
    assert AgentActionType.CALCULATE_NEED.value in action_types
    assert AgentActionType.CHECK_EXPIRY.value in action_types
    assert AgentActionType.GET_QUOTES.value in action_types
    assert AgentActionType.SELECT_VENDOR.value in action_types
    assert (AgentActionType.OFFER.value in action_types or AgentActionType.COUNTER.value in action_types)


def test_no_side_effects_on_db():
    """
    Verify that running procurement execution does NOT modify database state:
    - Zero purchase orders created
    - Inventory stock remains strictly unchanged
    - Vendor offers remain unchanged
    """
    conn = get_db_connection()
    stock_before = conn.execute("SELECT med_id, current_stock FROM inventory ORDER BY med_id").fetchall()
    po_count_before = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    offers_before = conn.execute("SELECT COUNT(*) FROM vendor_offers").fetchone()[0]
    conn.close()

    # Trigger StoreAgent via API
    response = client.post("/procurement/start")
    assert response.status_code == 200

    # Also run StoreAgent directly
    agent = StoreAgent()
    agent.run()

    # Verify state after execution
    conn = get_db_connection()
    stock_after = conn.execute("SELECT med_id, current_stock FROM inventory ORDER BY med_id").fetchall()
    po_count_after = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    offers_after = conn.execute("SELECT COUNT(*) FROM vendor_offers").fetchone()[0]
    conn.close()

    assert po_count_after == po_count_before == 0
    assert offers_after == offers_before == 9
    assert [dict(r) for r in stock_after] == [dict(r) for r in stock_before]


# ==========================================
# PHASE 4 ADAPTIVE NEGOTIATION TESTS
# ==========================================

def test_vendor_response_accept():
    """Test 1: Vendor accepts offer when price is within quick-accept tolerance (>= 95%)."""
    resp = vendor_respond(vendor_id=2, offered_price=8.10, quantity=250, base_price=8.50, round_num=1)
    assert resp["action"] == "ACCEPT"
    assert resp["price"] == 8.10


def test_vendor_response_counter():
    """Test 2: Vendor counters when price is in negotiation range (e.g. 90% of base)."""
    resp = vendor_respond(vendor_id=2, offered_price=7.65, quantity=250, base_price=8.50, round_num=1)
    assert resp["action"] == "COUNTER"
    assert 7.65 < resp["price"] < 8.50  # Midpoint concession ($8.08)


def test_vendor_response_reject():
    """Test 3: Vendor rejects deep lowball offers outside discount policy."""
    resp = vendor_respond(vendor_id=2, offered_price=4.50, quantity=250, base_price=8.50, round_num=1)
    assert resp["action"] == "REJECT"


def test_agent_adaptation_on_vendor_counter():
    """Test 4: Agent observes vendor counter and adapts next action to midpoint."""
    # Round 1: Agent opens at target $7.65 (10% discount from $8.50)
    ctx_r1 = {
        "round": 1,
        "vendor_id": 2,
        "med_name": "Paracetamol",
        "quantity": 250,
        "target_price": 7.65,
        "reservation_price": 8.50,
    }
    proposal_r1 = generate_agent_negotiation_action(ctx_r1)
    assert proposal_r1["action"] == "OFFER"
    assert proposal_r1["price"] == 7.65

    # Vendor counters at $8.08
    v_resp = {"action": "COUNTER", "price": 8.08}

    # Round 2: Agent adapts to midpoint between target ($7.65) and counter ($8.08) -> $7.86 / $7.87
    ctx_r2 = {
        "round": 2,
        "vendor_id": 2,
        "med_name": "Paracetamol",
        "quantity": 250,
        "target_price": 7.65,
        "reservation_price": 8.50,
        "last_vendor_response": v_resp,
    }
    proposal_r2 = generate_agent_negotiation_action(ctx_r2)
    assert proposal_r2["action"] == "COUNTER"
    assert proposal_r2["price"] == 7.86 or proposal_r2["price"] == 7.87
    assert "Adapting counter" in proposal_r2["reason"]


def test_max_negotiation_rounds_enforced():
    """Test 5: Verify negotiation completes within MAX_NEGOTIATION_ROUNDS (2)."""
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

    assert state.negotiation["round"] <= MAX_NEGOTIATION_ROUNDS
    assert state.negotiation["status"] in ["ACCEPTED", "REJECTED", "UNRESOLVED"]


def test_negotiation_history_recording():
    """Test 6: Every turn is recorded chronologically with speaker, action, and price."""
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

    history = state.negotiation_history
    assert len(history) >= 2

    # Check alternating turns: STORE_AGENT -> VENDOR
    assert history[0]["speaker"] == "STORE_AGENT"
    assert history[1]["speaker"] == "VENDOR"

    for turn in history:
        assert "round" in turn
        assert "speaker" in turn
        assert "action" in turn
        assert "price" in turn
        assert "message" in turn


def test_best_offer_tracking():
    """Test 7: Successful negotiation populates state.best_offer with verified unit price, savings, and total cost."""
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

    assert state.best_offer is not None
    bo = state.best_offer
    assert bo["vendor_id"] == 2
    assert bo["vendor_name"] == "Vendor B"
    assert bo["quantity"] == 250  # Must respect Vendor B MOQ 250
    assert bo["unit_price"] < bo["initial_price"]
    assert bo["savings"] > 0
    assert bo["total_cost"] == round(bo["unit_price"] * bo["quantity"], 2)


def test_action_validation_blocks_invalid_proposals():
    """Test 8: Action validator blocks invalid prices, excessive amounts, MOQ violations, and malformed inputs."""
    ctx = {
        "vendor_id": 2,
        "reservation_price": 8.50,
        "max_rounds": 2,
        "moq": 250,
        "required_qty": 100,
        "expiry_safe_qty": 1920,
    }

    # Case 1: Negative price
    valid, err = validate_negotiation_action({"action": "OFFER", "price": -5.0, "quantity": 250, "vendor_id": 2}, ctx)
    assert valid is False
    assert "positive number" in err

    # Case 2: Price above reservation ceiling
    valid, err = validate_negotiation_action({"action": "OFFER", "price": 10.50, "quantity": 250, "vendor_id": 2}, ctx)
    assert valid is False
    assert "exceeds buyer reservation" in err

    # Case 3: Unsupported action
    valid, err = validate_negotiation_action({"action": "INVALID_ACTION", "price": 7.65}, ctx)
    assert valid is False
    assert "Unsupported" in err

    # Case 4: Quantity below MOQ
    valid, err = validate_negotiation_action({"action": "OFFER", "price": 7.65, "quantity": 100, "vendor_id": 2}, ctx)
    assert valid is False
    assert "violates vendor MOQ" in err

    # Case 5: Quantity exceeding expiry-safe capacity
    valid, err = validate_negotiation_action({"action": "OFFER", "price": 7.65, "quantity": 3000, "vendor_id": 2}, ctx)
    assert valid is False
    assert "exceeds expiry-safe capacity" in err

    # Case 6: Valid proposal
    valid, err = validate_negotiation_action({"action": "OFFER", "price": 7.65, "quantity": 250, "vendor_id": 2, "round": 1}, ctx)
    assert valid is True
    assert err is None


def test_moq_quantity_flow_invariance():
    """Test A: Verify quantity invariant: vendor_moq <= final_qty <= expiry_safe_qty."""
    agent = StoreAgent()
    # Paracetamol: required_qty = 100, Vendor B MOQ = 250
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

    assert state.required_qty == 100
    assert state.selected_vendor["moq"] == 250
    assert state.selected_vendor["offered_qty"] == 250
    assert state.best_offer["quantity"] == 250
    assert state.best_offer["quantity"] >= state.selected_vendor["moq"]
    assert state.best_offer["quantity"] >= state.required_qty
    assert state.best_offer["quantity"] <= 1920  # expiry_safe_qty


def test_vendor_counter_is_not_auto_accepted():
    """Test B: Vendor COUNTER in Round 2 terminates with UNRESOLVED status (not auto-accepted)."""
    # Simulate a tight vendor that counters at 96% in round 2 when buyer proposes 90%
    agent = StoreAgent()
    # Mock a state where selected vendor is Vendor A (which counters if buyer proposes 90%)
    state = AgentState(
        medicine={"med_id": 1, "name": "Paracetamol"},
        inventory={"current_stock": 40, "reorder_point": 50, "daily_sales": 20, "lead_time_days": 5, "expiry_date": "2026-12-31"},
        required_qty=100,
        constraints={"expiry": {"expiry_safe_qty": 1920}},
        selected_vendor={
            "vendor_id": 1,  # Vendor A
            "vendor_name": "Vendor A",
            "base_price": 8.00,
            "moq": 500,
            "offered_qty": 500,
            "delivery_days": 5,
        },
    )
    # If agent offers target (90% = $7.20), Vendor A in round 1 counters at $7.68 (96%).
    # In round 2, agent adapts to midpoint ($7.20 + $7.68)/2 = $7.44 (ratio = 0.93 < 0.96).
    # Vendor A responds with COUNTER ($7.68).
    result_state = agent.negotiate_with_vendor(state)

    assert result_state.negotiation["status"] == "UNRESOLVED"
    assert result_state.negotiation["final_status"] == "UNRESOLVED"
    assert result_state.decision == "NEGOTIATION_UNRESOLVED"
    assert result_state.best_offer is not None
    assert result_state.best_offer["status"] == "UNACCEPTED_COUNTER"


def test_explicit_acceptance_flow():
    """Test C: Vendor ACCEPT in Round 2 results in ACCEPTED status and agreed best offer."""
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

    assert state.negotiation["status"] == "ACCEPTED"
    assert state.decision in ["READY_FOR_VALIDATION", "ACCEPT"]
    assert state.best_offer["status"] == "ACCEPTED"
    assert state.best_offer["quantity"] == 250
    assert state.best_offer["unit_price"] in [7.86, 7.87]
    assert state.best_offer["savings"] > 0
