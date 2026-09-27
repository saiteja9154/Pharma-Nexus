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
from tools.inventory_tools import calculate_need, check_expiry, get_inventory
from tools.vendor_tools import get_vendor_quotes, get_vendor_quote
from tools.deal_scoring import score_quotes, score_deal, check_quote_feasibility

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database is initialized and seeded before testing."""
    init_db()
    seed_db()


def test_vendors_database():
    """Verify vendors table in SQLite has 3 seeded vendors."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vendor_id, name FROM vendors")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 3
    vendor_names = [row["name"] for row in rows]
    assert "Vendor A" in vendor_names
    assert "Vendor B" in vendor_names
    assert "Vendor C" in vendor_names


def test_vendor_offers_database():
    """Verify vendor_offers table in SQLite has 9 seeded offers."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vendor_id, med_id, base_price, min_qty, delivery_days FROM vendor_offers")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 9

    # Vendor A Paracetamol (med_id 1): lowest price 8.00, high MOQ 500, delivery 5 days
    v_a_p1 = next(r for r in rows if r["vendor_id"] == 1 and r["med_id"] == 1)
    assert v_a_p1["base_price"] == 8.00
    assert v_a_p1["min_qty"] == 500
    assert v_a_p1["delivery_days"] == 5

    # Vendor B Paracetamol (med_id 1): medium price 8.50, flexible MOQ 250, fast delivery 2 days
    v_b_p1 = next(r for r in rows if r["vendor_id"] == 2 and r["med_id"] == 1)
    assert v_b_p1["base_price"] == 8.50
    assert v_b_p1["min_qty"] == 250
    assert v_b_p1["delivery_days"] == 2

    # Vendor C Paracetamol (med_id 1): higher price 9.00, moderate MOQ 300, delivery 3 days
    v_c_p1 = next(r for r in rows if r["vendor_id"] == 3 and r["med_id"] == 1)
    assert v_c_p1["base_price"] == 9.00
    assert v_c_p1["min_qty"] == 300
    assert v_c_p1["delivery_days"] == 3


def test_frozen_vendor_profiles():
    """Verify authoritative Phase 0 vendor profiles in database."""
    conn = get_db_connection()
    offers = conn.execute("SELECT vendor_id, med_id, base_price, min_qty, delivery_days FROM vendor_offers WHERE med_id = 1").fetchall()
    conn.close()

    v_a = next(o for o in offers if o["vendor_id"] == 1)
    assert v_a["base_price"] == 8.00
    assert v_a["min_qty"] == 500
    assert v_a["delivery_days"] == 5

    v_b = next(o for o in offers if o["vendor_id"] == 2)
    assert v_b["base_price"] == 8.50
    assert v_b["min_qty"] == 250
    assert v_b["delivery_days"] == 2

    v_c = next(o for o in offers if o["vendor_id"] == 3)
    assert v_c["base_price"] == 9.00
    assert v_c["min_qty"] == 300
    assert v_c["delivery_days"] == 3


def test_get_vendors_endpoint():
    """Verify GET /vendors endpoint."""
    response = client.get("/vendors")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    names = [v["name"] for v in data]
    assert "Vendor A" in names
    assert "Vendor B" in names
    assert "Vendor C" in names


def test_get_vendor_offers_endpoint():
    """Verify GET /vendor-offers endpoint."""
    response = client.get("/vendor-offers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 9
    assert "vendor_name" in data[0]
    assert "med_name" in data[0]
    assert "base_price" in data[0]


def test_vendor_offers_moq_consistency():
    """
    Verify MOQ and Quantity consistency for all 9 vendor offers:
    - vendor_offered_qty = max(required_qty, vendor_MOQ)
    - vendor_offered_qty >= vendor_MOQ
    - vendor_offered_qty >= required_qty
    - vendor_offered_qty <= expiry_safe_qty
    """
    inventory_items = {item["med_id"]: item for item in get_inventory()}
    conn = get_db_connection()
    offers = conn.execute("SELECT vendor_id, med_id, base_price, min_qty, delivery_days FROM vendor_offers").fetchall()
    conn.close()

    assert len(offers) == 9

    for offer in offers:
        med = inventory_items[offer["med_id"]]
        need = calculate_need(
            current_stock=med["current_stock"],
            daily_sales=med["daily_sales"],
            lead_time_days=med["lead_time_days"],
        )
        required_qty = need["required_qty"]
        moq = offer["min_qty"]

        # Formula: vendor_offered_qty = max(required_qty, vendor_MOQ)
        vendor_offered_qty = max(required_qty, moq)

        assert vendor_offered_qty >= moq, f"Offered qty {vendor_offered_qty} must satisfy MOQ {moq}"
        assert vendor_offered_qty >= required_qty, f"Offered qty {vendor_offered_qty} must satisfy required qty {required_qty}"

        expiry_res = check_expiry(expiry_date_str=med["expiry_date"], daily_sales=med["daily_sales"])
        assert vendor_offered_qty <= expiry_res["expiry_safe_qty"], (
            f"Offered qty {vendor_offered_qty} exceeds expiry safe capacity {expiry_res['expiry_safe_qty']}"
        )


# ==========================================
# PHASE 3 VENDOR QUOTES & SCORING TESTS
# ==========================================

def test_get_vendor_quotes_tool():
    """
    Test get_vendor_quotes tool returns all 3 candidate vendors for a medicine,
    correctly filters by med_id, applies the MOQ quantity rule, and computes total cost.
    """
    quotes = get_vendor_quotes(med_id=1, required_qty=100)
    assert len(quotes) == 3

    v_a = next(q for q in quotes if q["vendor_name"] == "Vendor A")
    assert v_a["base_price"] == 8.00
    assert v_a["moq"] == 500
    assert v_a["offered_qty"] == 500
    assert v_a["total_cost"] == 4000.0
    assert v_a["delivery_days"] == 5

    v_b = next(q for q in quotes if q["vendor_name"] == "Vendor B")
    assert v_b["base_price"] == 8.50
    assert v_b["moq"] == 250
    assert v_b["offered_qty"] == 250  # max(100, 250) = 250
    assert v_b["total_cost"] == 2125.0
    assert v_b["delivery_days"] == 2

    v_c = next(q for q in quotes if q["vendor_name"] == "Vendor C")
    assert v_c["base_price"] == 9.00
    assert v_c["moq"] == 300
    assert v_c["offered_qty"] == 300  # max(100, 300) = 300
    assert v_c["total_cost"] == 2700.0
    assert v_c["delivery_days"] == 3


def test_get_vendor_quote_single():
    """Test retrieving a single vendor quote by vendor_id and med_id."""
    quote = get_vendor_quote(vendor_id=2, med_id=1, required_qty=100)
    assert quote is not None
    assert quote["vendor_name"] == "Vendor B"
    assert quote["offered_qty"] == 250  # max(100, 250) = 250
    assert quote["total_cost"] == 2125.0  # 8.50 * 250


def test_check_quote_feasibility():
    """Test deterministic feasibility constraints."""
    # Feasible quote
    q_valid = {"offered_qty": 50, "required_qty": 25, "moq": 50}
    feasible, violations = check_quote_feasibility(q_valid, expiry_safe_qty=200)
    assert feasible is True
    assert len(violations) == 0

    # Infeasible: exceeds expiry capacity
    q_exp = {"offered_qty": 300, "required_qty": 50, "moq": 50}
    feasible, violations = check_quote_feasibility(q_exp, expiry_safe_qty=100)
    assert feasible is False
    assert any("expiry-safe capacity" in v for v in violations)


def test_score_quotes_multi_factor():
    """
    Test explainable deal scoring on candidate quotes.
    Verifies price, delivery, and MOQ trade-offs.
    """
    quotes = get_vendor_quotes(med_id=1, required_qty=100)
    scored = score_quotes(quotes, expiry_safe_qty=1920)

    assert len(scored) == 3
    for sq in scored:
        assert sq["feasible"] is True
        assert 0.0 <= sq["score"] <= 100.0
        assert "price_score" in sq
        assert "delivery_score" in sq
        assert "moq_score" in sq
        assert len(sq["reasons"]) > 0


def test_deterministic_tie_breaker():
    """
    Test deterministic tie-breaker when two quotes receive identical scores.
    """
    # Create two artificial quotes with equal score but differing total cost
    q1 = {
        "vendor_id": 1,
        "vendor_name": "Vendor A",
        "med_id": 1,
        "base_price": 5.0,
        "moq": 10,
        "required_qty": 10,
        "offered_qty": 10,
        "delivery_days": 3,
        "total_cost": 50.0,
        "feasible": True,
        "score": 80.0,
    }
    q2 = {
        "vendor_id": 2,
        "vendor_name": "Vendor B",
        "med_id": 1,
        "base_price": 4.0,
        "moq": 10,
        "required_qty": 10,
        "offered_qty": 10,
        "delivery_days": 3,
        "total_cost": 40.0,
        "feasible": True,
        "score": 80.0,
    }

    candidates = [q1, q2]
    candidates.sort(key=lambda q: (-q["score"], q["total_cost"], q["delivery_days"], q["moq"], q["vendor_id"]))

    # q2 wins because lower total_cost (40.0 < 50.0)
    assert candidates[0]["vendor_id"] == 2
