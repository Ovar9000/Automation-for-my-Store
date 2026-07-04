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

@router.post("/transactions")
async def create_transaction(data: TransactionCreate, db=Depends(get_db)):
    """
    Create a complete sale transaction.

    Business logic flow:
    1. Validate that the cart is not empty.
    2. Calculate total COGS (cost of goods sold) for profit tracking.
    3. Insert the transaction header row.
    4. Insert each line item into transaction_items.
    5. Deduct stock quantities from the products table.
    6. Calculate change if payment is CASH.
    7. Return the completed transaction with change info.

    NOTE: All money values are rounded to 2 decimal places to avoid
    floating-point drift in financial calculations.

    Stock deduction happens here (not on the frontend) to prevent
    race conditions when multiple cashier tabs are open.
    """

    # ── Guard: Empty cart check ──────────────────────────────────────
    if not data.items or len(data.items) == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot create a transaction with an empty cart."
        )

    # ── Calculate total COGS from the cart items ─────────────────────
    # This is used for profit reporting: net_profit = total_sales - total_cost
    total_cost = round(
        sum(item.cost_price * item.quantity for item in data.items),
        2
    )

    # ── Determine if receipt should be flagged as printed ────────────
    receipt_printed = 1 if data.print_receipt else 0

    # ── Insert the transaction header ────────────────────────────────
    cursor = await db.execute(
        """INSERT INTO transactions
           (transaction_type, total_amount, total_cost, payment_method, receipt_printed)
           VALUES (?, ?, ?, ?, ?)""",
        ("SALE", round(data.total_amount, 2), total_cost, data.payment_method, receipt_printed)
    )
    transaction_id = cursor.lastrowid

    # ── Insert each line item and deduct stock ───────────────────────
    for item in data.items:
        # Insert the transaction line item
        # We store product_name as a snapshot because the product name
        # could be changed later in inventory management
        await db.execute(
            """INSERT INTO transaction_items
               (transaction_id, product_id, product_name, quantity, unit_price, cost_price, subtotal)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                transaction_id,
                item.product_id,
                item.product_name,
                round(item.quantity, 2),
                round(item.unit_price, 2),
                round(item.cost_price, 2),
                round(item.subtotal, 2),
            )
        )

        # Deduct stock from the product
        # Using MAX(0, ...) would prevent negative stock, but sari-sari stores
        # sometimes sell on credit or track negative stock intentionally.
        # We allow negative stock and flag it in the UI instead.
        await db.execute(
            "UPDATE products SET stock_qty = stock_qty - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (round(item.quantity, 2), item.product_id)
        )

    # ── Commit all changes atomically ────────────────────────────────
    await db.commit()

    # ── Calculate change ─────────────────────────────────────────────
    # Only relevant for CASH payments; GCASH doesn't need change
    change = round(data.amount_tendered - data.total_amount, 2) if data.payment_method == "CASH" else 0.0
    if change < 0:
        change = 0.0  # Safety: tendered can't be less than total (frontend validates)

    # ── Fetch the created transaction for the response ───────────────
    cursor = await db.execute(
        "SELECT * FROM transactions WHERE id = ?",
        (transaction_id,)
    )
    txn_row = await cursor.fetchone()
    txn = dict(txn_row)

    return {
        "id": txn["id"],
        "transaction_type": txn["transaction_type"],
        "total_amount": round(txn["total_amount"], 2),
        "total_cost": round(txn["total_cost"], 2),
        "payment_method": txn["payment_method"],
        "change": change,
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
