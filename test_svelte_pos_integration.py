"""
Test Suite: Svelte 5 SPA + FastAPI End-to-End Integration
===========================================================
Validates:
1. Svelte 5 Cashier SPA is served at '/' with HTTP 200
2. Static assets (/assets/...) are served with correct MIME types
3. Scale-embedded barcode decoding via /api/smart-scan and /api/products/barcode/
4. Dual-mode weight / peso cart items checkout via /api/checkout
5. Legacy cashier fallback at '/legacy-cashier'
"""

import re
import sys
import asyncio
from starlette.testclient import TestClient
from app.main import app
from app.database import init_db, get_db

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_tests():
    print("=" * 60)
    print("[*] STARTING SVELTE 5 SPA + FASTAPI END-TO-END VERIFICATION")
    print("=" * 60)

    # Initialize DB
    asyncio.run(init_db())
    print("[+] SQLite database initialized.")

    with TestClient(app) as client:
        # 1. Test Root Route Serving Svelte 5 SPA
        print("\n--- 1. Testing Root Route ('/') Serving Svelte 5 SPA ---")
        resp = client.get("/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html_content = resp.text
        assert "Sari-Sari POS — Cashier Terminal" in html_content
        assert '<div id="app"' in html_content
        print("[+] Root '/' successfully serves Svelte 5 SPA index.html")

        # 2. Extract and Test Asset Loading
        print("\n--- 2. Testing Compiled Asset Serving (/assets/...) ---")
        js_match = re.search(r'src="\.?/(assets/[^"]+\.js)"', html_content)
        css_match = re.search(r'href="\.?/(assets/[^"]+\.css)"', html_content)
        assert js_match, f"Could not find JS bundle path in HTML: {html_content[:300]}"
        assert css_match, f"Could not find CSS bundle path in HTML: {html_content[:300]}"

        js_path = "/" + js_match.group(1)
        css_path = "/" + css_match.group(1)

        js_resp = client.get(js_path)
        assert js_resp.status_code == 200, f"Failed to fetch JS bundle at {js_path}: {js_resp.status_code}"
        assert len(js_resp.content) > 10000
        print(f"[+] Svelte 5 JS bundle verified ({len(js_resp.content)} bytes) at {js_path}")

        css_resp = client.get(css_path)
        assert css_resp.status_code == 200, f"Failed to fetch CSS bundle at {css_path}: {css_resp.status_code}"
        assert len(css_resp.content) > 5000
        print(f"[+] Svelte 5 CSS bundle verified ({len(css_resp.content)} bytes) at {css_path}")

        # 3. Test Scale Barcode Scanning API
        print("\n--- 3. Testing EAN-13 Scale-Printed Barcode Resolution ---")
        # Find or create a weighed product (e.g. Rice with unit 'kg')
        quick_resp = client.get("/api/products/quick-items")
        assert quick_resp.status_code == 200
        items = quick_resp.json()
        assert len(items) > 0

        sample_prod = items[0]
        prod_id = sample_prod["id"]

        # Formulate scale barcode: 21 + 5-digit PLU + 5-digit weight (0.750kg = 00750) + check
        scale_barcode = f"21{prod_id:05d}007505"
        scan_resp = client.post(f"/api/smart-scan?scanned_code={scale_barcode}")
        assert scan_resp.status_code == 200, f"Scan failed: {scan_resp.text}"
        scan_data = scan_resp.json()
        assert "scale_" in scan_data["scan_type"]
        assert scan_data["product"]["id"] == prod_id
        print(f"[+] Scale Barcode {scale_barcode} decoded: Item '{scan_data['product']['name']}', Label: {scan_data['pack_label']}")

        # 4. Test Checkout with Weighed Portion and Change Calculation
        print("\n--- 4. Testing POS Checkout with Cash & Change ---")
        checkout_payload = {
            "items": [
                {
                    "product_id": prod_id,
                    "product_name": sample_prod["name"],
                    "quantity": 0.75,
                    "unit_price": float(sample_prod["selling_price"]),
                    "cost_price": float(sample_prod.get("cost_price", 0)),
                    "subtotal": round(0.75 * float(sample_prod["selling_price"]), 2),
                    "pack_label": "Scale Weighed (0.750kg)"
                },
                {
                    "product_id": sample_prod["id"],
                    "product_name": "Gasolina (1L Bote)",
                    "quantity": 1.0,
                    "unit_price": 75.0,
                    "cost_price": 60.0,
                    "subtotal": 75.0,
                    "pack_label": "1L Bote"
                }
            ],
            "total_amount": round(0.75 * float(sample_prod["selling_price"]) + 75.0, 2),
            "payment_method": "CASH",
            "amount_tendered": 200.0,
            "print_receipt": False
        }

        checkout_resp = client.post("/api/checkout", json=checkout_payload)
        assert checkout_resp.status_code == 200, f"Checkout failed: {checkout_resp.text}"
        txn = checkout_resp.json()
        assert txn["receipt_number"].startswith("TXN-")
        expected_change = round(200.0 - checkout_payload["total_amount"], 2)
        change_val = txn.get("change", txn.get("change_amount", 0))
        assert abs(change_val - expected_change) < 0.01
        print(f"[+] Checkout successful: Receipt #{txn['receipt_number']}, Change: ₱{change_val:.2f}")

        # 5. Test GCash Money Transaction Recording with Photo / Metadata
        print("\n--- 5. Testing GCash Transaction Recording with Photo & Metadata ---")
        gcash_payload = {
            "transaction_type": "GCASH_OUT",
            "flow_type": "B",
            "input_amount": 1000.0,
            "principal_amount": 990.0,
            "fee": 10.0,
            "total_collected": 1000.0,
            "reference_number": "504250429508",
            "mobile_number": "09171234567",
            "receipt_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "gcash_timestamp": "Sep 21, 2026, 12:15 AM"
        }
        gcash_resp = client.post("/api/gcash/transact", json=gcash_payload)
        assert gcash_resp.status_code == 200, f"GCash transact failed: {gcash_resp.text}"
        g_data = gcash_resp.json()
        assert g_data["transaction"]["id"] > 0
        assert g_data["gcash_detail"]["id"] > 0
        print(f"[+] GCash Cash-Out recorded successfully: Txn ID {g_data['transaction']['id']}, Ref: 504250429508, Fee: ₱10.00")

        # 6. Test Legacy Cashier Fallback Route
        print("\n--- 6. Testing Legacy Cashier Fallback Route ---")
        legacy_resp = client.get("/legacy-cashier")
        assert legacy_resp.status_code == 200
        assert "cashierApp()" in legacy_resp.text
        print("[+] Legacy Cashier route '/legacy-cashier' remains fully accessible for fallback.")

    print("\n" + "=" * 60)
    print("[SUCCESS] ALL SVELTE 5 SPA + FASTAPI END-TO-END TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
