from datetime import date, timedelta
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
from tools.inventory_tools import get_inventory, calculate_need, check_expiry, DEFAULT_SAFETY_DAYS

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database is initialized and seeded before testing."""
    init_db()
    seed_db()


def test_inventory_database():
    """Verify inventory table in SQLite has 18 seeded medicines."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT med_id, name, current_stock, reorder_point, daily_sales, lead_time_days, expiry_date FROM inventory")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 18
    med_names = [row["name"] for row in rows]
    assert "Paracetamol" in med_names
    assert "Cetirizine" in med_names
    assert "Azithromycin" in med_names
    assert "Amoxicillin" in med_names
    assert "Metformin" in med_names

    # Check Paracetamol specifically
    para = next(r for r in rows if r["name"] == "Paracetamol")
    assert para["current_stock"] == 40
    assert para["reorder_point"] == 50
    assert para["daily_sales"] == 20
    assert para["lead_time_days"] == 5


def test_get_inventory_endpoint():
    """Verify GET /inventory returns seeded medicines."""
    response = client.get("/inventory")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 18

    names = [item["name"] for item in data]
    assert "Paracetamol" in names
    assert "Cetirizine" in names
    assert "Azithromycin" in names


def test_get_inventory_tool():
    """Verify get_inventory tool reads directly from SQLite and returns structured records."""
    items = get_inventory()
    assert len(items) == 18
    for item in items:
        assert "med_id" in item
        assert "name" in item
        assert "current_stock" in item
        assert "reorder_point" in item
        assert "daily_sales" in item
        assert "lead_time_days" in item
        assert "expiry_date" in item


def test_calculate_need_formula():
    """
    Test 3: Required Quantity formula verification
    coverage_days = lead_time_days + safety_days
    raw_need = daily_sales * coverage_days
    required_qty = max(raw_need - current_stock, 0)
    """
    # Case 1: Paracetamol (lead=5, safety=2 -> coverage=7, sales=20 -> raw_need=140, stock=40 -> req=100)
    res = calculate_need(current_stock=40, daily_sales=20, lead_time_days=5, safety_days=2)
    assert res["coverage_days"] == 7
    assert res["raw_need"] == 140
    assert res["safety_days"] == 2
    assert res["required_qty"] == 100

    # Case 2: Cetirizine (lead=3, safety=2 -> coverage=5, sales=10 -> raw_need=50, stock=25 -> req=25)
    res = calculate_need(current_stock=25, daily_sales=10, lead_time_days=3, safety_days=2)
    assert res["coverage_days"] == 5
    assert res["raw_need"] == 50
    assert res["required_qty"] == 25

    # Case 3: Azithromycin (lead=4, safety=2 -> coverage=6, sales=5 -> raw_need=30, stock=15 -> req=15)
    res = calculate_need(current_stock=15, daily_sales=5, lead_time_days=4, safety_days=2)
    assert res["coverage_days"] == 6
    assert res["raw_need"] == 30
    assert res["required_qty"] == 15


def test_calculate_need_zero_when_surplus():
    """Verify required_qty is bounded at 0 if current stock exceeds raw need."""
    res = calculate_need(current_stock=200, daily_sales=20, lead_time_days=5, safety_days=2)
    assert res["raw_need"] == 140
    assert res["required_qty"] == 0


def test_calculate_need_custom_safety_days():
    """Verify calculate_need works with custom safety_days."""
    res = calculate_need(current_stock=50, daily_sales=10, lead_time_days=3, safety_days=4)
    # coverage = 3 + 4 = 7; raw_need = 70; req = 70 - 50 = 20
    assert res["coverage_days"] == 7
    assert res["raw_need"] == 70
    assert res["required_qty"] == 20


def test_check_expiry_tool():
    """
    Test 4: Expiry tool verification
    expiry_safe_qty = daily_sales * expiry_days_left
    """
    ref_date = date(2026, 9, 26)
    # 60 days in the future
    exp_date_str = (ref_date + timedelta(days=60)).strftime("%Y-%m-%d")

    res = check_expiry(expiry_date_str=exp_date_str, daily_sales=10, reference_date=ref_date, lead_time_days=5)
    assert res["expiry_days_left"] == 60
    assert res["expiry_safe_qty"] == 600
    assert res["expiry_risk"] is False


def test_check_expiry_near_expiry_risk():
    """Verify check_expiry flags risk when expiry is within 30 days or lead time."""
    ref_date = date(2026, 9, 26)
    exp_date_str = (ref_date + timedelta(days=15)).strftime("%Y-%m-%d")

    res = check_expiry(expiry_date_str=exp_date_str, daily_sales=10, reference_date=ref_date, lead_time_days=5)
    assert res["expiry_days_left"] == 15
    assert res["expiry_safe_qty"] == 150
    assert res["expiry_risk"] is True


def test_check_expiry_expired_or_invalid_date():
    """Verify check_expiry handles expired products and invalid date strings safely."""
    ref_date = date(2026, 9, 26)

    # Expired date
    past_date_str = (ref_date - timedelta(days=10)).strftime("%Y-%m-%d")
    res = check_expiry(expiry_date_str=past_date_str, daily_sales=10, reference_date=ref_date)
    assert res["expiry_days_left"] == -10
    assert res["expiry_safe_qty"] == 0
    assert res["expiry_risk"] is True

    # Invalid date string
    res_inv = check_expiry(expiry_date_str="invalid-date", daily_sales=10, reference_date=ref_date)
    assert res_inv["expiry_days_left"] == 0
    assert res_inv["expiry_safe_qty"] == 0
    assert res_inv["expiry_risk"] is True
    assert "error" in res_inv
