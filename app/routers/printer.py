"""
Sari-Sari Store POS — Printer Router
======================================
Handles receipt printing operations:
  - Print a sale receipt (by transaction ID)
  - Print a Z-Report (end-of-day summary)
  - Check printer connection status

The printer service is currently a placeholder that outputs to console.
When physical hardware (58mm USB thermal printer) is connected,
only the print_service module needs to change — these routes stay the same.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.database import get_db
from app.services.receipt_formatter import format_sale_receipt, format_z_report
from app.services.print_service import print_service

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS (local to this router)
# ═══════════════════════════════════════════════════════════════

class PrintReceiptRequest(BaseModel):
    """Request to print a receipt for a specific transaction or raw receipt text."""
    transaction_id: Optional[int] = None
    receipt_text: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# RECEIPT PRINTING
# ═══════════════════════════════════════════════════════════════

@router.post("/print/receipt")
@router.post("/printer/print-receipt")
async def print_receipt(data: PrintReceiptRequest, db=Depends(get_db)):
    """
    Print a receipt for a completed transaction or direct formatted text.
    Handles both direct text printing and database transaction formatting.
    """
    # ── Path A: Direct receipt text printing ────────────────────────
    if data.receipt_text and data.receipt_text.strip():
        print_success = print_service.print_text(data.receipt_text)
        return {
            "success": print_success,
            "message": "Receipt sent to printer!" if print_success else "Printer error",
            "receipt_text": data.receipt_text,
            "transaction_id": data.transaction_id
        }

    # ── Path B: Look up transaction from database ───────────────────
    if not data.transaction_id:
        raise HTTPException(
            status_code=400,
            detail="Either transaction_id or receipt_text must be provided."
        )

    # ── Step 1: Look up the transaction ──────────────────────────────
    cursor = await db.execute(
        "SELECT * FROM transactions WHERE id = ?",
        (data.transaction_id,)
    )
    txn_row = await cursor.fetchone()

    if not txn_row:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction #{data.transaction_id} not found."
        )

    txn = dict(txn_row)

    # ── Step 2: Fetch line items for the transaction ─────────────────
    cursor = await db.execute(
        "SELECT * FROM transaction_items WHERE transaction_id = ? ORDER BY id",
        (data.transaction_id,)
    )
    item_rows = await cursor.fetchall()
    items = [dict(row) for row in item_rows]

    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"No items found for transaction #{data.transaction_id}."
        )

    # ── Step 3: Load store settings for receipt header ───────────────
    cursor = await db.execute("SELECT key, value FROM admin_settings")
    settings_rows = await cursor.fetchall()
    settings = {}
    for row in settings_rows:
        r = dict(row)
        settings[r["key"]] = r["value"]

    store_name = settings.get("store_name", "Sari-Sari Store")
    store_address = settings.get("store_address", "")
    store_phone = settings.get("store_phone", "")

    # ── Step 4: Format the receipt ───────────────────────────────────
    # Parse the created_at timestamp for display on the receipt
    try:
        timestamp = datetime.strptime(txn["created_at"], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        timestamp = datetime.now()

    amount_tendered = float(txn.get("amount_tendered") or txn["total_amount"])
    change = float(txn.get("change_amount") or 0.0)

    receipt_text = format_sale_receipt(
        store_name=store_name,
        store_address=store_address,
        store_phone=store_phone,
        items=items,
        total=txn["total_amount"],
        amount_tendered=amount_tendered,
        change=change,
        payment_method=txn["payment_method"],
        transaction_id=txn["id"],
        timestamp=timestamp,
    )

    # ── Step 5: Send to printer ──────────────────────────────────────
    print_success = print_service.print_text(receipt_text)

    # ── Step 6: Mark transaction as receipt printed ──────────────────
    if print_success:
        await db.execute(
            "UPDATE transactions SET receipt_printed = 1 WHERE id = ?",
            (data.transaction_id,)
        )
        await db.commit()

    return {
        "success": print_success,
        "message": "Receipt sent to printer!" if print_success else "Printer error",
        "receipt_text": receipt_text,
        "transaction_id": data.transaction_id,
    }


# ═══════════════════════════════════════════════════════════════
# Z-REPORT (END OF DAY SUMMARY)
# ═══════════════════════════════════════════════════════════════

@router.post("/print/z-report")
async def print_z_report(db=Depends(get_db)):
    """
    Print a Z-Report (End-of-Day summary receipt).
    Calculates Cash Sales, Debt Repayments, GCash Sales, Utang Credit, and Cash in Drawer.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    # ── Query cash sales for today ───────────────────────────────────
    cursor = await db.execute(
        """SELECT COALESCE(SUM(total_amount), 0) as total
           FROM transactions
           WHERE date(created_at, 'localtime') = date('now', 'localtime')
             AND transaction_type = 'SALE'
             AND payment_method = 'CASH'"""
    )
    cash_row = await cursor.fetchone()
    total_cash_sales = round(dict(cash_row)["total"], 2)

    # ── Query Utang repayments collected in cash today ───────────────
    cursor = await db.execute(
        """SELECT COALESCE(SUM(total_amount), 0) as total
           FROM transactions
           WHERE date(created_at, 'localtime') = date('now', 'localtime')
             AND transaction_type = 'UTANG_PAYMENT'"""
    )
    debt_pay_row = await cursor.fetchone()
    total_debt_payments = round(dict(debt_pay_row)["total"], 2)

    # ── Query GCash sales for today ──────────────────────────────────
    cursor = await db.execute(
        """SELECT COALESCE(SUM(total_amount), 0) as total
           FROM transactions
           WHERE date(created_at, 'localtime') = date('now', 'localtime')
             AND transaction_type = 'SALE'
             AND payment_method = 'GCASH'"""
    )
    gcash_sale_row = await cursor.fetchone()
    total_gcash_sales = round(dict(gcash_sale_row)["total"], 2)

    # ── Query Utang credit sales & cash downpayments for today ──────
    cursor = await db.execute(
        """SELECT COALESCE(SUM(total_amount), 0) as total,
                  COALESCE(SUM(amount_tendered), 0) as downpayments
           FROM transactions
           WHERE date(created_at, 'localtime') = date('now', 'localtime')
             AND transaction_type = 'SALE'
             AND payment_method = 'UTANG'"""
    )
    utang_sale_row = await cursor.fetchone()
    utang_data = dict(utang_sale_row)
    total_utang_sales = round(utang_data["total"], 2)
    total_utang_downpayments = round(utang_data["downpayments"], 2)

    # ── Query GCash fee income for today ─────────────────────────────
    cursor = await db.execute(
        """SELECT COALESCE(SUM(g.fee), 0) as total_fees,
                  COUNT(*) as gcash_count
           FROM gcash_transactions g
           JOIN transactions t ON g.transaction_id = t.id
           WHERE date(t.created_at, 'localtime') = date('now', 'localtime')"""
    )
    gcash_fee_row = await cursor.fetchone()
    gcash_fee_data = dict(gcash_fee_row)
    total_gcash_fees = round(gcash_fee_data["total_fees"], 2)
    gcash_count = gcash_fee_data["gcash_count"]

    # ── Query total transaction count for today ──────────────────────
    cursor = await db.execute(
        """SELECT COUNT(*) as count
           FROM transactions
           WHERE date(created_at, 'localtime') = date('now', 'localtime')
             AND transaction_type IN ('SALE', 'UTANG_PAYMENT')"""
    )
    count_row = await cursor.fetchone()
    transaction_count = dict(count_row)["count"]

    # ── Calculate grand total & cash in drawer ───────────────────────
    total_cash_drawer = round(total_cash_sales + total_utang_downpayments + total_debt_payments, 2)
    grand_total = round(total_cash_sales + total_gcash_sales + total_utang_sales + total_gcash_fees, 2)

    # ── Load store name for receipt header ───────────────────────────
    cursor = await db.execute(
        "SELECT value FROM admin_settings WHERE key = 'store_name'"
    )
    name_row = await cursor.fetchone()
    store_name = dict(name_row)["value"] if name_row else "Sari-Sari Store"

    # ── Format the Z-Report ──────────────────────────────────────────
    report_text = format_z_report(
        store_name=store_name,
        date=today_str,
        total_cash_sales=total_cash_sales,
        total_gcash_sales=total_gcash_sales,
        total_utang_sales=total_utang_sales,
        total_gcash_fees=total_gcash_fees,
        total_debt_payments=total_debt_payments,
        grand_total=grand_total,
        transaction_count=transaction_count,
        gcash_count=gcash_count,
    )

    # ── Print the report ─────────────────────────────────────────────
    print_success = print_service.print_text(report_text)

    return {
        "success": print_success,
        "report_text": report_text,
        "date": today_str,
        "summary": {
            "total_cash_sales": total_cash_sales,
            "total_utang_downpayments": total_utang_downpayments,
            "total_debt_payments": total_debt_payments,
            "total_cash_in_drawer": total_cash_drawer,
            "total_gcash_sales": total_gcash_sales,
            "total_utang_sales": total_utang_sales,
            "total_gcash_fees": total_gcash_fees,
            "grand_total": grand_total,
            "transaction_count": transaction_count,
            "gcash_count": gcash_count,
        }
    }


# ═══════════════════════════════════════════════════════════════
# PRINTER STATUS
# ═══════════════════════════════════════════════════════════════

@router.get("/printer/status")
async def printer_status():
    """
    Check if a physical printer is connected.

    Business logic:
    - Returns a simple {connected: bool} response.
    - The frontend uses this to show/hide the "Print Receipt" button
      or to display a "Printer Offline" warning badge.
    - Currently always returns false (placeholder mode).
    - When hardware is connected, the print_service will detect the USB device.
    """
    return {
        "connected": print_service.is_connected(),
    }
