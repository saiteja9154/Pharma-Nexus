"""
Unit & Integration Tests for Editable & Creatable ERP Master Data (Phase 10 Extension).
Validates:
- CREATE Inventory (POST /inventory), duplicate rejection, negative validation
- CREATE Vendor (POST /vendors), duplicate rejection
- CREATE Vendor Offer (POST /vendor-offers), duplicate rejection, invalid price/MOQ/delivery rejection
- UPDATE Inventory (PUT /inventory/{med_id}) & SQLite persistence
- UPDATE Vendor Offer (PUT /vendor-offers/{vendor_id}/{med_id}) & SQLite persistence
- Persistence across API calls and database queries
- Store Procurement Agent dynamically discovering and evaluating newly created medicines (e.g. Amoxicillin)
- Store Procurement Agent dynamically discovering and evaluating newly created vendor offers
- PO safety & zero side-effects on master data creation and updates
"""

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
from agent.store_agent import StoreAgent
from tools.inventory_tools import get_inventory, update_inventory_item, add_inventory_item
from tools.vendor_tools import get_vendor_quotes, update_vendor_offer, add_vendor, add_vendor_offer

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_clean_db():
    """Ensure baseline seeded database before each test."""
    init_db()
    seed_db()


# ==============================================================================
# 1. CREATE MEDICINE TESTS
# ==============================================================================
def test_create_medicine_success():
    """Verify POST /inventory successfully creates a new medicine in SQLite."""
    payload = {
        "name": "Amoxicillin 500mg",
        "current_stock": 10,
        "reorder_point": 30,
        "daily_sales": 5,
        "lead_time_days": 3,
        "expiry_date": "2027-01-30",
    }
    response = client.post("/inventory", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["medicine"]["name"] == "Amoxicillin 500mg"
    assert data["medicine"]["med_id"] == 19  # 19th medicine after 1-18
    assert data["medicine"]["current_stock"] == 10
    assert data["medicine"]["reorder_point"] == 30
    assert data["medicine"]["daily_sales"] == 5
    assert data["medicine"]["lead_time_days"] == 3
    assert data["medicine"]["expiry_date"] == "2027-01-30"

    # Verify SQLite directly
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM inventory WHERE name = 'Amoxicillin 500mg'").fetchone()
    conn.close()
    assert row is not None
    assert row["med_id"] == 19
    assert row["current_stock"] == 10


def test_create_medicine_duplicate_rejection():
    """Verify POST /inventory rejects duplicate medicine names."""
    payload = {
        "name": "Paracetamol",  # Already exists in seed
        "current_stock": 10,
        "reorder_point": 30,
        "daily_sales": 5,
        "lead_time_days": 3,
        "expiry_date": "2027-01-30",
    }
    response = client.post("/inventory", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_create_medicine_invalid_values_rejection():
    """Verify POST /inventory rejects negative values or empty names."""
    # Negative stock
    r1 = client.post("/inventory", json={
        "name": "Ibuprofen Extra",
        "current_stock": -5,
        "reorder_point": 20,
        "daily_sales": 5,
        "lead_time_days": 3,
        "expiry_date": "2027-01-30",
    })
    assert r1.status_code == 400

    # Empty name
    r2 = client.post("/inventory", json={
        "name": "   ",
        "current_stock": 10,
        "reorder_point": 20,
        "daily_sales": 5,
        "lead_time_days": 3,
        "expiry_date": "2027-01-30",
    })
    assert r2.status_code == 400

    # Bad date format
    r3 = client.post("/inventory", json={
        "name": "Ibuprofen Extra",
        "current_stock": 10,
        "reorder_point": 20,
        "daily_sales": 5,
        "lead_time_days": 3,
        "expiry_date": "30/01/2027",
    })
    assert r3.status_code == 400


# ==============================================================================
# 2. CREATE VENDOR TESTS
# ==============================================================================
def test_create_vendor_success():
    """Verify POST /vendors successfully creates a new vendor in SQLite."""
    payload = {"name": "Apex Pharma Logistics"}
    response = client.post("/vendors", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["vendor"]["name"] == "Apex Pharma Logistics"
    assert data["vendor"]["vendor_id"] == 7  # 7th vendor after 1-6

    # Verify SQLite directly
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM vendors WHERE name = 'Apex Pharma Logistics'").fetchone()
    conn.close()
    assert row is not None
    assert row["vendor_id"] == 7


def test_create_vendor_duplicate_rejection():
    """Verify POST /vendors rejects duplicate vendor names."""
    payload = {"name": "Vendor A"}  # Already exists
    response = client.post("/vendors", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


# ==============================================================================
# 3. CREATE VENDOR OFFER TESTS
# ==============================================================================
def test_create_vendor_offer_success():
    """Verify POST /vendor-offers successfully registers a new contract offer."""
    # First create a new medicine
    res = client.post("/inventory", json={
        "name": "Doxycycline 100mg",
        "current_stock": 10,
        "reorder_point": 30,
        "daily_sales": 5,
        "lead_time_days": 3,
        "expiry_date": "2027-01-30",
    })
    new_med_id = res.json()["medicine"]["med_id"]

    # Add offer for Doxycycline from Vendor B (vendor_id: 2)
    payload = {
        "vendor_id": 2,
        "med_id": new_med_id,
        "base_price": 5.50,
        "min_qty": 40,
        "delivery_days": 2,
    }
    response = client.post("/vendor-offers", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["offer"]["vendor_id"] == 2
    assert data["offer"]["vendor_name"] == "Vendor B"
    assert data["offer"]["med_id"] == new_med_id
    assert data["offer"]["med_name"] == "Doxycycline 100mg"
    assert data["offer"]["base_price"] == 5.50
    assert data["offer"]["min_qty"] == 40
    assert data["offer"]["delivery_days"] == 2

    # Verify SQLite directly
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM vendor_offers WHERE vendor_id = 2 AND med_id = ?", (new_med_id,)).fetchone()
    conn.close()
    assert row is not None
    assert row["base_price"] == 5.50
    assert row["min_qty"] == 40


def test_create_vendor_offer_duplicate_rejection():
    """Verify POST /vendor-offers rejects duplicate (vendor_id, med_id) offers."""
    payload = {
        "vendor_id": 1,
        "med_id": 1,  # Vendor A Paracetamol offer already exists
        "base_price": 7.50,
        "min_qty": 100,
        "delivery_days": 3,
    }
    response = client.post("/vendor-offers", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_create_vendor_offer_invalid_parameters_rejection():
    """Verify POST /vendor-offers rejects non-positive prices, MOQs, or delivery days."""
    # Zero price
    r1 = client.post("/vendor-offers", json={
        "vendor_id": 1,
        "med_id": 2,
        "base_price": 0.0,
        "min_qty": 50,
        "delivery_days": 2,
    })
    assert r1.status_code == 400

    # Zero MOQ
    r2 = client.post("/vendor-offers", json={
        "vendor_id": 1,
        "med_id": 2,
        "base_price": 5.0,
        "min_qty": 0,
        "delivery_days": 2,
    })
    assert r2.status_code == 400

    # Zero delivery days
    r3 = client.post("/vendor-offers", json={
        "vendor_id": 1,
        "med_id": 2,
        "base_price": 5.0,
        "min_qty": 50,
        "delivery_days": 0,
    })
    assert r3.status_code == 400

    # Non-existent vendor ID
    r4 = client.post("/vendor-offers", json={
        "vendor_id": 999,
        "med_id": 1,
        "base_price": 5.0,
        "min_qty": 50,
        "delivery_days": 2,
    })
    assert r4.status_code == 400


# ==============================================================================
# 4. AGENT DISCOVERY & END-TO-END WITH NEW DATA
# ==============================================================================
def test_agent_discovers_and_processes_newly_added_medicine():
    """
    Verify Store Procurement Agent automatically discovers newly created medicine (Doxycycline),
    evaluates replenishment demand, scores candidate vendor offers, negotiates, validates, and executes.
    """
    # 1. Create Medicine: Doxycycline (stock: 10, reorder: 30, sales: 5, lead: 3 -> coverage: 5d, need: 15u)
    res_med = client.post("/inventory", json={
        "name": "Doxycycline Syrup",
        "current_stock": 10,
        "reorder_point": 30,
        "daily_sales": 5,
        "lead_time_days": 3,
        "expiry_date": "2027-06-30",
    })
    assert res_med.status_code == 201
    new_med_id = res_med.json()["medicine"]["med_id"]

    # 2. Add Vendor Offers for Doxycycline Syrup from Vendor A and Vendor B
    client.post("/vendor-offers", json={
        "vendor_id": 1,
        "med_id": new_med_id,
        "base_price": 6.00,
        "min_qty": 100,
        "delivery_days": 5,
    })
    client.post("/vendor-offers", json={
        "vendor_id": 2,
        "med_id": new_med_id,
        "base_price": 6.50,
        "min_qty": 20,
        "delivery_days": 2,
    })

    # 3. Run StoreAgent
    agent = StoreAgent()
    doxy_item = next(i for i in get_inventory() if i["med_id"] == new_med_id)
    state = agent.evaluate_medicine(doxy_item)

    # Need check (coverage = 3+2 = 5, raw_need = 5*5 = 25, stock = 10 -> required_qty = 15)
    assert state.required_qty == 15
    assert len(state.vendor_quotes) == 2

    # Vendor Selection: Vendor B wins (Score higher due to fast delivery 2d vs 5d, and lower MOQ 20 vs 100)
    assert state.selected_vendor["vendor_id"] == 2
    assert state.selected_vendor["vendor_name"] == "Vendor B"
    assert state.selected_vendor["offered_qty"] == 20

    # Negotiation:
    # Target price = 6.50 * 0.90 = $5.85
    # Vendor B Counter Round 1 = midpoint(5.85, 6.50) = $6.18
    # Agent Counter Round 2 = round((5.85 + 6.18) / 2, 2) = $6.01
    # Vendor B ACCEPT $6.01 (since 6.01 / 6.50 = 0.9246 >= 0.92 floor)
    assert state.negotiation["status"] == "ACCEPTED"
    assert state.best_offer["unit_price"] == 6.01
    assert state.best_offer["quantity"] == 20
    assert state.best_offer["total_cost"] == 120.20

    # Validation: PASS all 7 checks
    assert state.validation_result["valid"] is True
    assert state.decision == "ACCEPT"

    # Execution: PO created & inventory incremented from 10 to 30
    exec_res = agent.execute_procurement(state)
    assert exec_res["success"] is True
    assert exec_res["inventory_before"] == 10
    assert exec_res["inventory_after"] == 30

    # Database state verification
    conn = get_db_connection()
    po = conn.execute("SELECT * FROM purchase_orders WHERE med_id = ?", (new_med_id,)).fetchone()
    stock_after = conn.execute("SELECT current_stock FROM inventory WHERE med_id = ?", (new_med_id,)).fetchone()[0]
    conn.close()

    assert po is not None
    assert po["unit_price"] == 6.01
    assert po["quantity"] == 20
    assert stock_after == 30



# ==============================================================================
# 5. EDIT & PERSISTENCE TESTS
# ==============================================================================
def test_inventory_update_success():
    """Verify PUT /inventory/{med_id} successfully updates medicine in SQLite."""
    payload = {
        "current_stock": 35,
        "reorder_point": 60,
        "daily_sales": 25,
        "lead_time_days": 6,
        "expiry_date": "2027-08-15",
    }
    response = client.put("/inventory/1", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["medicine"]["current_stock"] == 35


def test_vendor_offer_update_success():
    """Verify PUT /vendor-offers/{vendor_id}/{med_id} successfully updates offer in SQLite."""
    payload = {
        "base_price": 7.45,
        "min_qty": 150,
        "delivery_days": 1,
    }
    response = client.put("/vendor-offers/2/1", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["offer"]["base_price"] == 7.45


def test_persistence_after_api_reload():
    """Verify GET endpoints return updated values after PUT updates."""
    client.put("/inventory/2", json={
        "current_stock": 10,
        "reorder_point": 45,
        "daily_sales": 15,
        "lead_time_days": 4,
        "expiry_date": "2027-01-01",
    })
    r_inv = client.get("/inventory")
    cet_inv = next(i for i in r_inv.json() if i["med_id"] == 2)
    assert cet_inv["current_stock"] == 10
    assert cet_inv["reorder_point"] == 45
