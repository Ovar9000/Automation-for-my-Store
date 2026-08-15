"""
Sari-Sari Store POS — Cashier Router
======================================
Handles all customer-facing cashier operations:
  - Barcode product lookup
  - Product name search
  - Quick-button item retrieval
  - Sale transaction creation (with stock deduction)
  - Today's transaction history

All routes are intended to be mounted under /api by main.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db
from app.models import TransactionCreate, TransactionResponse

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# PRODUCT LOOKUP ROUTES
# ═══════════════════════════════════════════════════════════════

@router.get("/products/barcode/{barcode}")
async def get_product_by_barcode(barcode: str, db=Depends(get_db)):
    """
    Look up a single product by its barcode.

    Business logic:
    - Used when the cashier scans a barcode with a USB scanner.
    - Returns the full product dict so the frontend can add it to the cart.
    - Returns 404 if the barcode doesn't match any product (could be misprinted).
    """
    cursor = await db.execute(
        "SELECT * FROM products WHERE barcode = ?",
        (barcode,)
    )
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No product found with barcode: {barcode}"
        )

    product = dict(row)
    # Add computed low-stock flag for frontend warning indicators
    product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
    return product


@router.get("/products/search")
async def search_products(q: str = Query(..., min_length=1, description="Search query for product name"), db=Depends(get_db)):
    """
    Search products by name using SQL LIKE (case-insensitive).

    Business logic:
    - Used when the cashier types a product name in the search bar.
    - Returns partial matches so the cashier can quickly find items.
    - LIKE '%query%' matches anywhere in the name.
    """
    cursor = await db.execute(
        "SELECT * FROM products WHERE name LIKE ? ORDER BY name",
        (f"%{q}%",)
    )
    rows = await cursor.fetchall()

    # Convert each Row to a dict and add computed is_low_stock field
    products = []
    for row in rows:
        product = dict(row)
        product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
        products.append(product)

    return products


@router.get("/products/quick")
async def get_quick_items(db=Depends(get_db)):
    """
    Get all products marked as quick-button items.

    Business logic:
    - Quick items appear as large colored buttons on the cashier screen.
    - These are high-frequency items like Rice, Candy, Gasoline, etc.
    - The cashier can tap them instead of scanning/searching.
    - Sorted by name for consistent button layout.
    """
    cursor = await db.execute(
        "SELECT * FROM products WHERE is_quick_item = 1 ORDER BY name"
    )
    rows = await cursor.fetchall()

    products = []
    for row in rows:
        product = dict(row)
        product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
        products.append(product)

    return products


# ═══════════════════════════════════════════════════════════════
# TRANSACTION ROUTES
# ═══════════════════════════════════════════════════════════════

import uuid
from datetime import datetime

@router.post("/transactions")
async def create_transaction(data: TransactionCreate, db=Depends(get_db)):
    """
    Create a complete sale transaction atomically.

    Business logic flow:
    1. Validate that the cart is not empty.
    2. Calculate total COGS for profit tracking.
    3. Generate a receipt number.
    4. Insert the transaction header with full financial metadata.
    5. Insert each line item (including pack labels) and deduct inventory stock.
    6. If payment_method is UTANG, atomically update/create the customer's debt account.
    7. Commit all DB mutations atomically in one transaction.
    """

    # ── Guard: Empty cart check ──────────────────────────────────────
    if not data.items or len(data.items) == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot create a transaction with an empty cart."
        )

    # ── Calculate total COGS ─────────────────────────────────────────
    total_cost = round(
        sum(item.cost_price * item.quantity for item in data.items),
        2
    )
    total_amount = round(data.total_amount, 2)
    receipt_printed = 1 if data.print_receipt else 0

    # ── Generate Receipt Number ──────────────────────────────────────
    date_prefix = datetime.now().strftime("%Y%m%d")
    short_hash = uuid.uuid4().hex[:5].upper()
    receipt_no = f"TXN-{date_prefix}-{short_hash}"

    # ── Calculate payment amounts ────────────────────────────────────
    method = (data.payment_method or "CASH").upper()
    if method == "CASH":
        amount_tendered = round(data.amount_tendered, 2) if data.amount_tendered else total_amount
        change_amount = round(max(0, amount_tendered - total_amount), 2)
        customer_name = None
        notes = data.notes
    elif method == "UTANG":
        clean_cust_name = (data.customer_name or "").strip()
        if not clean_cust_name:
            raise HTTPException(status_code=400, detail="Customer name is required for Utang transactions.")
        customer_name = clean_cust_name
        amount_paid_now = round(max(0, data.amount_paid_now or 0), 2)
        amount_tendered = amount_paid_now
        change_amount = 0.0
        amount_charged = round(max(0, total_amount - amount_paid_now), 2)
        notes = data.notes or f"Utang Sale (Paid: ₱{amount_paid_now:.2f}, Charged: ₱{amount_charged:.2f})"
    else:  # GCASH
        amount_tendered = total_amount
        change_amount = 0.0
        customer_name = None
        notes = data.notes

    # ── Insert Transaction Header ────────────────────────────────────
    cursor = await db.execute(
        """INSERT INTO transactions
           (receipt_number, transaction_type, total_amount, total_cost, payment_method,
            amount_tendered, change_amount, customer_name, notes, receipt_printed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            receipt_no,
            "SALE",
            total_amount,
            total_cost,
            method,
            amount_tendered,
            change_amount,
            customer_name,
            notes,
            receipt_printed
        )
    )
    transaction_id = cursor.lastrowid

    # ── Insert Line Items & Deduct Stock ─────────────────────────────
    for item in data.items:
        await db.execute(
            """INSERT INTO transaction_items
               (transaction_id, product_id, product_name, quantity, unit_price, cost_price, subtotal, pack_label)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                transaction_id,
                item.product_id,
                item.product_name,
                round(item.quantity, 2),
                round(item.unit_price, 2),
                round(item.cost_price, 2),
                round(item.subtotal, 2),
                item.pack_label
            )
        )

        await db.execute(
            "UPDATE products SET stock_qty = stock_qty - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (round(item.quantity, 2), item.product_id)
        )

    # ── Atomic Utang Debt Ledger Update ──────────────────────────────
    if method == "UTANG":
        amount_charged = round(max(0, total_amount - (data.amount_paid_now or 0)), 2)
        if amount_charged > 0:
            c_cur = await db.execute(
                "SELECT * FROM customer_debts WHERE LOWER(customer_name) = LOWER(?)",
                (customer_name,)
            )
            existing = await c_cur.fetchone()
            if existing:
                debt_id = existing["id"]
                new_debt = round(existing["total_debt"] + amount_charged, 2)
                await db.execute(
                    "UPDATE customer_debts SET total_debt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_debt, debt_id)
                )
            else:
                new_debt = amount_charged
                ins_cur = await db.execute(
                    "INSERT INTO customer_debts (customer_name, total_debt, phone_number, notes) VALUES (?, ?, ?, ?)",
                    (customer_name, new_debt, data.phone_number, f"Created via Utang Sale #{receipt_no}")
                )
                debt_id = ins_cur.lastrowid

            # Record in debt_transactions log
            await db.execute(
                """INSERT INTO debt_transactions (debt_id, sale_id, type, amount, balance_after, notes)
                   VALUES (?, ?, 'CHARGE', ?, ?, ?)""",
                (debt_id, transaction_id, amount_charged, new_debt, f"Charged from Sale #{receipt_no}")
            )

    # ── Commit all changes atomically ────────────────────────────────
    await db.commit()

    # ── Fetch the created transaction for the response ───────────────
    cursor = await db.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    txn_row = await cursor.fetchone()
    txn = dict(txn_row)

    return {
        "id": txn["id"],
        "receipt_number": txn.get("receipt_number", receipt_no),
        "transaction_type": txn["transaction_type"],
        "total_amount": round(txn["total_amount"], 2),
        "total_cost": round(txn["total_cost"], 2),
        "payment_method": txn["payment_method"],
        "amount_tendered": round(txn.get("amount_tendered", amount_tendered), 2),
        "change": round(txn.get("change_amount", change_amount), 2),
        "customer_name": txn.get("customer_name"),
        "receipt_printed": bool(txn["receipt_printed"]),
        "created_at": txn["created_at"],
        "item_count": len(data.items),
    }


@router.get("/transactions/today")
async def get_today_transactions(db=Depends(get_db)):
    """
    Get all transactions created today (local time).

    Business logic:
    - Uses SQLite's date() with 'localtime' modifier to match
      today's date in the server's timezone.
    - Sorted newest-first so the latest sale appears at the top.
    - This is displayed in the cashier's "Recent Sales" sidebar panel.
    """
    cursor = await db.execute(
        """SELECT * FROM transactions
           WHERE date(created_at) = date('now', 'localtime')
           ORDER BY created_at DESC"""
    )
    rows = await cursor.fetchall()

    transactions = []
    for row in rows:
        txn = dict(row)
        # Round money values for display consistency
        txn["total_amount"] = round(txn["total_amount"], 2)
        txn["total_cost"] = round(txn["total_cost"], 2)
        txn["receipt_printed"] = bool(txn["receipt_printed"])
        transactions.append(txn)

    return transactions
