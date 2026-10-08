"""
Complete Verification Script for Pharma Nexus Realistic ERP Dataset Expansion.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from database.db import get_db_connection, init_db
from database.seed import seed_db
from agent.store_agent import StoreAgent
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def run_verification():
    print("=" * 60)
    print("PHARMA NEXUS ERP DATASET EXPANSION VERIFICATION")
    print("=" * 60)

    # 1. Reset / reseed database
    init_db()
    seed_db()
    print("[OK] Database re-initialized and re-seeded cleanly.")

    # 2. Print Counts
    conn = get_db_connection()
    med_count = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    vendor_count = conn.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
    offer_count = conn.execute("SELECT COUNT(*) FROM vendor_offers").fetchone()[0]
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    conn.close()

    print(f"\nDATABASE SUMMARY:")
    print(f"  MEDICINES COUNT:       {med_count}")
    print(f"  VENDORS COUNT:         {vendor_count}")
    print(f"  VENDOR OFFERS COUNT:   {offer_count}")
    print(f"  PURCHASE ORDERS COUNT: {po_count}")

    assert med_count == 18, f"Expected 18 medicines, got {med_count}"
    assert vendor_count == 6, f"Expected 6 vendors, got {vendor_count}"
    assert offer_count == 98, f"Expected 98 vendor offers, got {offer_count}"
    assert po_count == 0, f"Expected 0 initial POs, got {po_count}"
    print("[OK] Database count assertions passed.")

    # 3. Verify Endpoints
    r_health = client.get("/health")
    assert r_health.status_code == 200 and r_health.json() == {"status": "ok"}

    r_inv = client.get("/inventory")
    assert r_inv.status_code == 200 and len(r_inv.json()) == 18

    r_ven = client.get("/vendors")
    assert r_ven.status_code == 200 and len(r_ven.json()) == 6

    r_offers = client.get("/vendor-offers")
    assert r_offers.status_code == 200 and len(r_offers.json()) == 98

    r_pos = client.get("/purchase-orders")
    assert r_pos.status_code == 200 and len(r_pos.json()) == 0
    print("[OK] REST API endpoints (GET /health, /inventory, /vendors, /vendor-offers, /purchase-orders) verified.")

    # 4. Run Store Procurement Agent
    agent = StoreAgent()
    run_result = agent.run()

    print(f"\nAGENT EVALUATION RUN:")
    print(f"  Medicines Evaluated:       {run_result['medicines_evaluated']}")
    print(f"  Procurement Needed:        {run_result['procurement_needed_count']}")
    print(f"  Selected Vendor Count:     {run_result['selected_vendor_count']}")
    print(f"  Deals Accepted:            {run_result['deals_accepted_count']}")
    print(f"  Total Negotiated Savings:  ${run_result['total_savings']:.2f}")

    # 5. Verify Hero Scenarios
    med1 = next(m for m in run_result["medicines"] if m["med_id"] == 1)
    med2 = next(m for m in run_result["medicines"] if m["med_id"] == 2)
    med3 = next(m for m in run_result["medicines"] if m["med_id"] == 3)

    assert med1["name"] == "Paracetamol"
    assert med1["decision"] == "ACCEPT"
    assert med1["selected_vendor"]["vendor_id"] == 2
    assert med1["best_offer"]["unit_price"] == 7.86
    assert med1["best_offer"]["quantity"] == 250
    assert med1["best_offer"]["total_cost"] == 1965.00
    assert med1["best_offer"]["savings"] == 160.00
    print("[OK] Hero Scenario 1 (Paracetamol) strictly preserved.")

    assert med2["name"] == "Cetirizine"
    assert med2["decision"] == "ACCEPT"
    assert med2["selected_vendor"]["vendor_id"] == 2
    assert med2["best_offer"]["unit_price"] == 2.04
    assert med2["best_offer"]["quantity"] == 30
    assert med2["best_offer"]["total_cost"] == 61.20
    assert med2["best_offer"]["savings"] == 4.80
    print("[OK] Hero Scenario 2 (Cetirizine) strictly preserved.")

    assert med3["name"] == "Azithromycin"
    assert med3["decision"] == "ACCEPT"
    assert med3["selected_vendor"]["vendor_id"] == 2
    assert med3["best_offer"]["unit_price"] == 13.41
    assert med3["best_offer"]["quantity"] == 20
    assert med3["best_offer"]["total_cost"] == 268.20
    assert med3["best_offer"]["savings"] == 21.80
    print("[OK] Hero Scenario 3 (Azithromycin) strictly preserved.")

    # 6. Verify Healthy Stock items have NO_PROCUREMENT
    healthy_meds = [m for m in run_result["medicines"] if not m["procurement_needed"]]
    assert len(healthy_meds) == 6
    print(f"[OK] Healthy stock medicines correctly skipped ({len(healthy_meds)} medicines: {[m['name'] for m in healthy_meds]}).")

    # 7. Verify PO Execution for an accepted new medicine
    # Check execution of Paracetamol
    exec_p1 = client.post("/procurement/execute", json={"medicine_id": 1}).json()
    assert exec_p1["success"] is True
    assert exec_p1["inventory"]["after"] == 290
    print("[OK] Paracetamol PO executed: inventory 40 -> 290.")

    # Execute PO for all accepted deals via POST /procurement/execute
    exec_all = client.post("/procurement/execute").json()
    assert exec_all["success"] is True
    print(f"[OK] Batch PO execution executed {exec_all['execution_result']['executed_count']} purchase orders.")

    # 8. Check PO list
    r_pos_after = client.get("/purchase-orders")
    orders = r_pos_after.json()
    print(f"[OK] Total purchase orders in ERP after execution: {len(orders)}.")

    print("\n" + "=" * 60)
    print("ALL INTEGRITY AND SCENARIO CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_verification()
