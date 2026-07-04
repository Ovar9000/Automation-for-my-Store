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
    """Request to print a receipt for a specific transaction."""
    transaction_id: int


# ═══════════════════════════════════════════════════════════════
# RECEIPT PRINTING
# ═══════════════════════════════════════════════════════════════

@router.post("/print/receipt")
async def print_receipt(data: PrintReceiptRequest, db=Depends(get_db)):
    """
    Print a receipt for a completed transaction.

    Business logic flow:
    1. Look up the transaction by ID (verify it exists).
    2. Fetch all line items for that transaction.
    3. Load store settings (name, address, phone) for the receipt header.
    4. Format the receipt using the receipt_formatter service.
    5. Send the formatted text to the print_service.
    6. Mark the transaction as receipt_printed = 1.
    7. Return the receipt text (for frontend preview even if printer is offline).

    The receipt format is designed for 58mm thermal paper (32 chars per line).
    Even if the printer is disconnected, we still return the formatted text
    so the frontend can display it in a receipt preview modal.
    """

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

    receipt_text = format_sale_receipt(
        store_name=store_name,
        store_address=store_address,
        store_phone=store_phone,
        items=items,
        total=txn["total_amount"],
        amount_tendered=txn["total_amount"],     # We don't store amount_tendered in DB, use total
        change=0,                                 # Change was already given at sale time
        payment_method=txn["payment_method"],
        transaction_id=txn["id"],
        timestamp=timestamp,
    )

    # ── Step 5: Send to printer ──────────────────────────────────────
    # print_service.print_text() returns True if printed successfully
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

    Business logic:
    - A Z-Report is a standard POS concept: a summary of all transactions
      for the current business day.
    - Calculates:
      • Total cash sales (SALE transactions with payment_method='CASH')
      • Total GCash sales (SALE transactions with payment_method='GCASH')
      • Total GCash fees earned (from gcash_transactions table)
      • Grand total of all revenue
      • Transaction counts
    - Formats and prints the summary receipt.
    - Typically done at end of day before closing the store.

    The Z-Report helps the store owner:
    1. Verify the cash in the drawer matches expected sales
    2. Track daily GCash fee income
    3. Keep a physical paper trail of daily totals
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

    # ── Query GCash sales for today ──────────────────────────────────
    # These are SALE transactions paid via GCash (not GCash_IN/OUT services)
    cursor = await db.execute(
        """SELECT COALESCE(SUM(total_amount), 0) as total
           FROM transactions
           WHERE date(created_at, 'localtime') = date('now', 'localtime')
             AND transaction_type = 'SALE'
             AND payment_method = 'GCASH'"""
    )
    gcash_sale_row = await cursor.fetchone()
    total_gcash_sales = round(dict(gcash_sale_row)["total"], 2)

    # ── Query GCash fee income for today ─────────────────────────────
    # This is pure income from GCash cash-in/cash-out services
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
             AND transaction_type = 'SALE'"""
    )
    count_row = await cursor.fetchone()
    transaction_count = dict(count_row)["count"]

    # ── Calculate grand total ────────────────────────────────────────
    # Grand total = cash sales + GCash sales + GCash fees
    grand_total = round(total_cash_sales + total_gcash_sales + total_gcash_fees, 2)

    # ── Load store name for the receipt header ───────────────────────
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
        total_gcash_fees=total_gcash_fees,
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
            "total_gcash_sales": total_gcash_sales,
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
