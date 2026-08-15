"""
Automated Test Suite for Sari-Sari POS System Integrity
======================================================
Tests:
1. GCash Engine calculations (Flow A & Flow B)
2. Product CRUD with bulk pack / tie pricing
3. Atomic Cash Sale (Stock deduction, receipt #, change)
4. Atomic Utang (Credit) Sale (Single DB transaction, customer account creation, ledger update)
5. Debt Repayment (Balance reduction, UTANG_PAYMENT transaction record)
6. Z-Report Cash Drawer Reconciliation (Cash Sales + Utang Repayments)
7. Daily & Monthly Financial Reports
"""

import asyncio
import os
import sys
import uuid

# Force UTF-8 on Windows stdout if possible
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, get_db
from app.services.gcash_engine import calculate_flow_a, calculate_flow_b
from app.services.receipt_formatter import format_sale_receipt, format_z_report
from app.models import ProductCreate, TransactionCreate, CartItem, DebtPaymentRequest
from app.routers.cashier import create_transaction, get_product_by_barcode
from app.routers.inventory import create_product, list_products
from app.routers.debt import list_debts, pay_debt
from app.routers.printer import print_z_report
from app.routers.reports import daily_report, monthly_report


async def run_all_tests():
    print("\n" + "="*60)
    print("[*] STARTING POS SYSTEM INTEGRITY VERIFICATION SUITE")
    print("="*60 + "\n")

    # 1. Initialize Database
    await init_db()
    print("[+] Database initialized successfully (WAL mode + Schema migrations).")

    # 2. GCash Engine Unit Tests
    print("\n--- Testing GCash Engine ---")
    res_a = calculate_flow_a(500)
    assert res_a["fee"] == 10.0, f"Expected fee 10.0, got {res_a['fee']}"
    assert res_a["total_collected"] == 510.0, f"Expected 510.0, got {res_a['total_collected']}"

    res_b = calculate_flow_b(510)
    assert res_b["fee"] == 10.0, f"Expected fee 10.0, got {res_b['fee']}"
    assert res_b["principal_amount"] == 500.0, f"Expected principal 500.0, got {res_b['principal_amount']}"
    print("[+] GCash Fee calculation Flow A & Flow B passed.")

    unique_barcode = f"88{uuid.uuid4().int % 10000000000:010d}"

    async for db in get_db():
        # 3. Product Creation with Multi-Pack Pricing
        print("\n--- Testing Product Creation with Multi-Pack ---")
        p_data = ProductCreate(
            name="Test Coffee Stick 20g",
            barcode=unique_barcode,
            cost_price=10.0,
            selling_price=12.0,
            stock_qty=100.0,
            low_stock_threshold=10.0,
            unit="pc",
            is_quick_item=1,
            quick_button_color="#3b82f6",
            category="Beverages",
            pcs_per_pack=10,
            bulk_cost_price=90.0,
            full_pack_price=110.0,
        )
        created_prod = await create_product(p_data, db=db)
        prod_id = created_prod["id"]
        assert created_prod["name"] == "Test Coffee Stick 20g"
        assert created_prod["full_pack_price"] == 110.0
        print(f"[+] Product created: ID {prod_id}, Barcode: {created_prod['barcode']}")

        # 4. Atomic Cash Sale
        print("\n--- Testing Atomic Cash Sale ---")
        sale_data = TransactionCreate(
            items=[
                CartItem(
                    product_id=prod_id,
                    product_name="Test Coffee Stick 20g",
                    quantity=5.0,
                    unit_price=12.0,
                    cost_price=10.0,
                    subtotal=60.0
                )
            ],
            total_amount=60.0,
            payment_method="CASH",
            amount_tendered=100.0,
            print_receipt=False
        )
        txn_res = await create_transaction(sale_data, db=db)
        assert txn_res["total_amount"] == 60.0
        assert txn_res["amount_tendered"] == 100.0
        assert txn_res["change"] == 40.0
        assert txn_res["receipt_number"].startswith("TXN-")

        # Verify stock deduction
        cur = await db.execute("SELECT stock_qty FROM products WHERE id = ?", (prod_id,))
        p_row = await cur.fetchone()
        assert p_row["stock_qty"] == 95.0, f"Expected 95.0 stock, got {p_row['stock_qty']}"
        print(f"[+] Cash sale complete. Receipt #{txn_res['receipt_number']}, Change: {txn_res['change']:.2f}, Remaining Stock: {p_row['stock_qty']}")

        # 5. Atomic Utang (Debt) Sale
        print("\n--- Testing Atomic Utang (Credit) Sale ---")
        test_cust_name = f"Juan Dela Cruz {uuid.uuid4().hex[:4]}"
        utang_data = TransactionCreate(
            items=[
                CartItem(
                    product_id=prod_id,
                    product_name="Test Coffee Stick 20g",
                    quantity=10.0,
                    unit_price=12.0,
                    cost_price=10.0,
                    subtotal=120.0,
                    pack_label="Full-Pack (10pcs)"
                )
            ],
            total_amount=120.0,
            payment_method="UTANG",
            customer_name=test_cust_name,
            phone_number="09181234567",
            amount_paid_now=20.0,
            notes="Partial downpayment on 1 tie coffee"
        )
        utang_res = await create_transaction(utang_data, db=db)
        assert utang_res["total_amount"] == 120.0
        assert utang_res["customer_name"] == test_cust_name
        assert utang_res["amount_tendered"] == 20.0  # Paid now

        # Verify customer debt record was created atomically
        cur = await db.execute("SELECT * FROM customer_debts WHERE customer_name = ?", (test_cust_name,))
        debt_row = await cur.fetchone()
        assert debt_row is not None, "Customer debt record was not created!"
        assert debt_row["total_debt"] == 100.0, f"Expected 100.0 debt, got {debt_row['total_debt']}"

        # Verify debt_transactions log
        cur = await db.execute("SELECT * FROM debt_transactions WHERE debt_id = ?", (debt_row["id"],))
        log_row = await cur.fetchone()
        assert log_row["type"] == "CHARGE"
        assert log_row["amount"] == 100.0
        print(f"[+] Atomic Utang sale complete. Customer '{debt_row['customer_name']}' balance: {debt_row['total_debt']:.2f}")

        # 6. Customer Debt Repayment
        print("\n--- Testing Debt Repayment ---")
        repay_req = DebtPaymentRequest(payment_amount=50.0, notes="Cash debt installment")
        pay_res = await pay_debt(debt_row["id"], repay_req, db=db)
        assert pay_res["customer"]["total_debt"] == 50.0, f"Expected 50.0 balance, got {pay_res['customer']['total_debt']}"

        # Verify transaction log entry created for repayment
        cur = await db.execute("SELECT * FROM transactions WHERE transaction_type = 'UTANG_PAYMENT' ORDER BY id DESC LIMIT 1")
        pay_txn = await cur.fetchone()
        assert pay_txn is not None
        assert pay_txn["total_amount"] == 50.0
        assert pay_txn["payment_method"] == "CASH"
        print(f"[+] Debt repayment processed. New balance: {pay_res['customer']['total_debt']:.2f}")

        # 7. Z-Report Reconciliation
        print("\n--- Testing Z-Report Cash Drawer Reconciliation ---")
        z_res = await print_z_report(db=db)
        summary = z_res["summary"]
        print(f"Z-Report Summary: {summary}")
        assert summary["total_cash_sales"] >= 60.0
        assert summary["total_debt_payments"] >= 50.0
        assert summary["total_cash_in_drawer"] == round(summary["total_cash_sales"] + summary["total_debt_payments"], 2)
        print(f"[+] Z-Report accurately reconciled cash drawer (Cash Sales: {summary['total_cash_sales']:.2f} + Debt Repayments: {summary['total_debt_payments']:.2f} = Total Drawer: {summary['total_cash_in_drawer']:.2f})")

        # 8. Financial Reports
        print("\n--- Testing Daily & Monthly Reports ---")
        d_report = await daily_report(db=db)
        assert d_report["total_sales"] >= 180.0
        assert d_report["total_debt_payments"] >= 50.0
        print(f"[+] Daily Report: Total Sales = {d_report['total_sales']:.2f}, Net Profit = {d_report['net_profit']:.2f}, Debt Payments = {d_report['total_debt_payments']:.2f}")

        m_report = await monthly_report(db=db)
        assert m_report["total_sales"] >= 180.0
        print(f"[+] Monthly Report: Total Sales = {m_report['total_sales']:.2f}, Net Profit = {m_report['net_profit']:.2f}")

        break

    print("\n" + "="*60)
    print("[SUCCESS] ALL SYSTEM INTEGRITY & BUSINESS LOGIC TESTS PASSED 100%!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
