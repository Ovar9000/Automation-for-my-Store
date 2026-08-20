"""
Automated Test Suite for Sari-Sari POS System Integrity
======================================================
Tests:
1. GCash Engine calculations (Flow A & Flow B)
2. PBKDF2 Password Hashing & Admin Session Login
3. Product Creation with Mother-Pack & Jar QR Refill Codes
4. Smart Scanner Dispatch: Mother-Pack auto-counting vs Jar QR vs Unit Barcode
5. Atomic Cash Sale (Stock deduction, receipt #, change)
6. Atomic Utang (Credit) Sale (Single DB transaction, customer account creation, ledger update)
7. Debt Repayment (Balance reduction, UTANG_PAYMENT transaction record)
8. 58mm Thermal Label Generation
9. Z-Report Cash Drawer Reconciliation (Cash Sales + Utang Repayments)
10. Daily & Monthly Financial Reports
"""

import asyncio
import os
import sys
import uuid

# Force UTF-8 on Windows stdout if possible
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, get_db, hash_password, verify_password
from app.services.gcash_engine import calculate_flow_a, calculate_flow_b
from app.services.receipt_formatter import format_sale_receipt, format_z_report
from app.models import ProductCreate, TransactionCreate, CartItem, DebtPaymentRequest, AdminLoginRequest
from app.routers.cashier import create_transaction, get_product_by_barcode, smart_scan_lookup
from app.routers.inventory import create_product, list_products, admin_login, list_printable_labels
from app.routers.debt import list_debts, pay_debt
from app.routers.printer import print_z_report
from app.routers.reports import daily_report, monthly_report


async def run_all_tests():
    print("\n" + "="*60)
    print("[*] STARTING POS SYSTEM INTEGRITY & SMART FEATURES SUITE")
    print("="*60 + "\n")

    # 1. Initialize Database
    await init_db()
    print("[+] Database initialized successfully (WAL mode + Schema migrations).")

    # 2. PBKDF2 Cryptographic Password Verification
    print("\n--- Testing PBKDF2 Password Hashing & Admin Auth ---")
    pwd = "MyStoreSecurePassword2026"
    hashed = hash_password(pwd)
    assert hashed.startswith("pbkdf2_sha256$100000$"), "Invalid hash format"
    assert verify_password(pwd, hashed), "Password verification failed"
    assert not verify_password("wrongpassword", hashed), "Wrong password should fail"
    print("[+] PBKDF2-HMAC-SHA256 password hashing & verification verified.")

    # 3. GCash Engine Unit Tests
    print("\n--- Testing GCash Engine ---")
    res_a = calculate_flow_a(500)
    assert res_a["fee"] == 10.0, f"Expected fee 10.0, got {res_a['fee']}"
    assert res_a["total_collected"] == 510.0, f"Expected 510.0, got {res_a['total_collected']}"

    res_b = calculate_flow_b(510)
    assert res_b["fee"] == 10.0, f"Expected fee 10.0, got {res_b['fee']}"
    assert res_b["principal_amount"] == 500.0, f"Expected principal 500.0, got {res_b['principal_amount']}"
    print("[+] GCash Fee calculation Flow A & Flow B passed.")

    unit_barcode = f"88{uuid.uuid4().int % 10000000000:010d}"
    pack_barcode = f"{unit_barcode}-PACK"
    jar_code = f"JAR:SUGAR-{uuid.uuid4().hex[:4].upper()}"

    async for db in get_db():
        # 4. Admin Login with Session Token Generation
        print("\n--- Testing Admin Session Login Endpoint ---")
        login_res = await admin_login(AdminLoginRequest(password="admin123"), db=db)
        assert login_res["success"] is True
        assert login_res["token"] is not None and len(login_res["token"]) > 20
        print(f"[+] Admin logged in securely. Session token issued: {login_res['token'][:10]}...")

        # 5. Product Creation with Mother-Pack & Jar QR Refill Codes
        print("\n--- Testing Product Creation (Mother-Pack + Jar QR) ---")
        p_data = ProductCreate(
            name="Lucky Me Pancit Canton Kalamansi",
            barcode=unit_barcode,
            pack_barcode=pack_barcode,
            jar_code=jar_code,
            refill_price=35.0,
            refill_qty=0.5,
            cost_price=9.0,
            selling_price=12.0,
            stock_qty=150.0,
            low_stock_threshold=20.0,
            unit="pc",
            is_quick_item=0,
            category="Noodles",
            pcs_per_pack=10,
            bulk_cost_price=85.0,
            full_pack_price=115.0,
        )
        created_prod = await create_product(p_data, db=db)
        prod_id = created_prod["id"]
        assert created_prod["name"] == "Lucky Me Pancit Canton Kalamansi"
        assert created_prod["pack_barcode"] == pack_barcode
        assert created_prod["jar_code"] == jar_code
        print(f"[+] Product created: ID {prod_id}, Pack Barcode: {created_prod['pack_barcode']}, Jar QR: {created_prod['jar_code']}")

        # 6. Smart Scanner Dispatch Tests
        print("\n--- Testing Smart Scanner Auto-Dispatch ---")
        
        # 6a. Mother-Pack Scan (Auto-counts 10pcs)
        pack_scan = await smart_scan_lookup(pack_barcode, db=db)
        assert pack_scan["scan_type"] == "mother_pack"
        assert pack_scan["quantity_to_add"] == 10.0
        assert pack_scan["effective_subtotal"] == 115.0
        assert pack_scan["pack_label"] == "Full-Pack (10pcs)"
        print(f"[+] Mother-Pack scan: Auto-counted 10pcs @ ₱115.00 full pack")

        # 6b. Jar Refill QR Scan
        jar_scan = await smart_scan_lookup(jar_code, db=db)
        assert jar_scan["scan_type"] == "jar_refill"
        assert jar_scan["quantity_to_add"] == 0.5
        assert jar_scan["effective_unit_price"] == 35.0
        assert "Jar Refill" in jar_scan["pack_label"]
        print(f"[+] Jar QR scan: Portion 0.5 unit @ ₱35.00 refill price")

        # 6c. Standard 1-piece Barcode Scan
        unit_scan = await smart_scan_lookup(unit_barcode, db=db)
        assert unit_scan["scan_type"] == "unit"
        assert unit_scan["quantity_to_add"] == 1.0
        assert unit_scan["effective_unit_price"] == 12.0
        print(f"[+] Unit barcode scan: 1 pc @ ₱12.00")

        # 7. Atomic Cash Sale with Mother-Pack Deduction
        print("\n--- Testing Atomic Cash Sale with Mother-Pack ---")
        sale_data = TransactionCreate(
            items=[
                CartItem(
                    product_id=prod_id,
                    product_name="Lucky Me Pancit Canton Kalamansi",
                    quantity=10.0,
                    unit_price=11.5,
                    cost_price=8.5,
                    subtotal=115.0,
                    pack_label="Full-Pack (10pcs)"
                )
            ],
            total_amount=115.0,
            payment_method="CASH",
            amount_tendered=200.0,
            print_receipt=False
        )
        txn_res = await create_transaction(sale_data, db=db)
        assert txn_res["total_amount"] == 115.0
        assert txn_res["amount_tendered"] == 200.0
        assert txn_res["change"] == 85.0
        assert txn_res["receipt_number"].startswith("TXN-")

        # Verify stock deduction (150 - 10 = 140)
        cur = await db.execute("SELECT stock_qty FROM products WHERE id = ?", (prod_id,))
        p_row = await cur.fetchone()
        assert p_row["stock_qty"] == 140.0, f"Expected 140.0 stock, got {p_row['stock_qty']}"
        print(f"[+] Pack sale complete. Receipt #{txn_res['receipt_number']}, Change: ₱{txn_res['change']:.2f}, Remaining Stock: {p_row['stock_qty']} pcs")

        # 8. Atomic Utang (Debt) Sale
        print("\n--- Testing Atomic Utang (Credit) Sale ---")
        test_cust_name = f"Aling Nena {uuid.uuid4().hex[:4]}"
        utang_data = TransactionCreate(
            items=[
                CartItem(
                    product_id=prod_id,
                    product_name="Lucky Me Pancit Canton Kalamansi",
                    quantity=5.0,
                    unit_price=12.0,
                    cost_price=8.5,
                    subtotal=60.0
                )
            ],
            total_amount=60.0,
            payment_method="UTANG",
            customer_name=test_cust_name,
            phone_number="09181234567",
            amount_paid_now=10.0,
            notes="Partial downpayment"
        )
        utang_res = await create_transaction(utang_data, db=db)
        assert utang_res["total_amount"] == 60.0
        assert utang_res["customer_name"] == test_cust_name
        assert utang_res["amount_tendered"] == 10.0

        # Verify customer debt record
        cur = await db.execute("SELECT * FROM customer_debts WHERE customer_name = ?", (test_cust_name,))
        debt_row = await cur.fetchone()
        assert debt_row is not None, "Customer debt record was not created!"
        assert debt_row["total_debt"] == 50.0, f"Expected 50.0 debt, got {debt_row['total_debt']}"
        print(f"[+] Atomic Utang sale complete. Customer '{debt_row['customer_name']}' balance: ₱{debt_row['total_debt']:.2f}")

        # 9. Customer Debt Repayment
        print("\n--- Testing Debt Repayment ---")
        repay_req = DebtPaymentRequest(payment_amount=50.0, notes="Cash settlement")
        pay_res = await pay_debt(debt_row["id"], repay_req, db=db)
        assert pay_res["customer"]["total_debt"] == 0.0, f"Expected 0.0 balance, got {pay_res['customer']['total_debt']}"
        print(f"[+] Debt repayment processed. New balance: ₱{pay_res['customer']['total_debt']:.2f}")

        # 10. Label Generator Endpoint Test
        print("\n--- Testing 58mm Label Generator API ---")
        labels = await list_printable_labels(db=db)
        assert len(labels) > 0
        found_test_item = any(l["id"] == prod_id for l in labels)
        assert found_test_item, "Created test item not present in printable labels list"
        print(f"[+] Found {len(labels)} products available for 58mm QR / Barcode thermal label printing.")

        # 11. Z-Report Cash Drawer Reconciliation
        print("\n--- Testing Z-Report Cash Drawer Reconciliation ---")
        z_res = await print_z_report(db=db)
        summary = z_res["summary"]
        assert summary["total_cash_sales"] >= 115.0
        assert summary["total_debt_payments"] >= 50.0
        assert summary["total_cash_in_drawer"] == round(summary["total_cash_sales"] + summary["total_debt_payments"], 2)
        print(f"[+] Z-Report accurately reconciled cash drawer (Cash Sales: ₱{summary['total_cash_sales']:.2f} + Debt Repayments: ₱{summary['total_debt_payments']:.2f} = Total Drawer: ₱{summary['total_cash_in_drawer']:.2f})")

        # 12. Financial Reports
        print("\n--- Testing Daily & Monthly Reports ---")
        d_report = await daily_report(db=db)
        assert d_report["total_sales"] >= 175.0
        print(f"[+] Daily Report: Total Sales = ₱{d_report['total_sales']:.2f}, Net Profit = ₱{d_report['net_profit']:.2f}")

        m_report = await monthly_report(db=db)
        assert m_report["total_sales"] >= 175.0
        print(f"[+] Monthly Report: Total Sales = ₱{m_report['total_sales']:.2f}, Net Profit = ₱{m_report['net_profit']:.2f}")

        break

    print("\n" + "="*60)
    print("[SUCCESS] ALL SYSTEM INTEGRITY & BUSINESS LOGIC TESTS PASSED 100%!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())

