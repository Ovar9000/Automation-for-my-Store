import asyncio
from starlette.testclient import TestClient
from app.main import app
from app.database import init_db, get_db

async def run_audit_verification():
    await init_db()
    client = TestClient(app)

    print("\n--- 1. Testing Checkout with Uncataloged Item (product_id = None) ---")
    uncataloged_payload = {
        "items": [
            {
                "id": "item-test-1",
                "product_id": None,
                "product_name": "Tingi Candy Custom",
                "quantity": 3.0,
                "unit_price": 2.0,
                "cost_price": 1.5,
                "subtotal": 6.0,
                "unit": "pc"
            }
        ],
        "total_amount": 6.0,
        "payment_method": "CASH",
        "amount_tendered": 10.0,
        "print_receipt": False
    }
    res = client.post("/api/checkout", json=uncataloged_payload)
    assert res.status_code == 200, f"Checkout failed: {res.text}"
    data = res.json()
    assert data["total_amount"] == 6.0
    assert data["change"] == 4.0
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] is None
    print(f"[+] Uncataloged item checkout succeeded without FK error: Receipt {data['receipt_number']}, Change P{data['change']}")

    print("\n--- 2. Testing Printer Endpoints (both /api/printer/print-receipt and /api/print/receipt) ---")
    # By raw text
    res_text = client.post("/api/printer/print-receipt", json={"receipt_text": "Sample 58mm Thermal Text"})
    assert res_text.status_code == 200, f"Printer by text failed: {res_text.text}"
    print(f"[+] Printer route /api/printer/print-receipt (raw text): {res_text.json()['message']}")

    # By transaction_id
    res_id = client.post("/api/print/receipt", json={"transaction_id": data["id"]})
    assert res_id.status_code == 200, f"Printer by id failed: {res_id.text}"
    print(f"[+] Printer route /api/print/receipt (txn ID): {res_id.json()['message']}")

    print("\n--- 3. Testing GCash Calculation Endpoint ---")
    calc_res = client.post("/api/gcash/calculate", json={"amount": 1000.0, "flow_type": "A"})
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["fee"] == 10.0
    assert calc_data["total_collected"] == 1010.0
    print(f"[+] GCash calculate Flow A: P{calc_data['principal_amount']} -> Fee: P{calc_data['fee']}, Total: P{calc_data['total_collected']}")

    print("\n--- 4. Testing Daily Report with Cash In Drawer ---")
    rep_res = client.get("/api/reports/daily")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert "cash_in_drawer" in rep_data
    print(f"[+] Daily Report cash_in_drawer confirmed: P{rep_data['cash_in_drawer']}")

    print("\n--- 5. Testing Top Products Report Field Alignment ---")
    top_res = client.get("/api/reports/top-products")
    assert top_res.status_code == 200
    top_data = top_res.json()
    assert "products" in top_data
    if top_data["products"]:
        first = top_data["products"][0]
        assert "total_qty_sold" in first
        print(f"[+] Top product '{first['product_name']}' has total_qty_sold: {first['total_qty_sold']}")

    print("\n--- 6. Testing Cloud/Database Export Security Masking ---")
    # Login as admin to get session
    login_res = client.post("/api/admin/login", json={"password": "password123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    export_res = client.get("/api/sync/export-json", headers={"Authorization": f"Bearer {token}"})
    assert export_res.status_code == 200
    export_data = export_res.json()
    settings = export_data["tables"]["admin_settings"]
    for s in settings:
        if s["key"] in ("admin_password", "cloud_api_key", "supabase_key"):
            assert s["value"] == "***", f"Sensitive key {s['key']} was not masked!"
    print("[+] Admin export safely masked all sensitive credentials (***).")

    print("\n============================================================")
    print("[SUCCESS] ALL AUDIT & REFACTOR VERIFICATIONS PASSED!")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(run_audit_verification())
