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
# SMART SCAN & PRODUCT LOOKUP ROUTES
# ═══════════════════════════════════════════════════════════════

@router.get("/products/smart-scan/{code}")
async def smart_scan_lookup(code: str, db=Depends(get_db)):
    """
    Intelligent scanner endpoint:
    Automatically identifies whether a scanned code is:
      1. A Mother-Pack Barcode (auto-sets pack size & full-pack discount)
      2. A Jar Refill QR Code (auto-sets preset refill price & volume)
      3. A Standard Single-Piece Barcode (adds 1 unit)
    """
    clean_code = code.strip()

    # 1. Check Mother-Pack Barcode first
    cursor = await db.execute(
        "SELECT * FROM products WHERE pack_barcode = ?",
        (clean_code,)
    )
    row = await cursor.fetchone()
    if row:
        product = dict(row)
        product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
        pcs = product.get("pcs_per_pack") or 10
        pack_price = product.get("full_pack_price") if (product.get("full_pack_price") and product["full_pack_price"] > 0) else round(pcs * product["selling_price"], 2)
        unit_price = round(pack_price / pcs, 2)

        return {
            "scan_type": "mother_pack",
            "product": product,
            "quantity_to_add": float(pcs),
            "effective_unit_price": unit_price,
            "effective_subtotal": pack_price,
            "pack_label": f"Full-Pack ({pcs}pcs)",
            "message": f"Mother-Pack Scanned: {product['name']} ({pcs}pcs Pack — ₱{pack_price:.2f})"
        }

    # 2. Check Jar Refill QR Code
    cursor = await db.execute(
        "SELECT * FROM products WHERE jar_code = ? OR jar_code = ?",
        (clean_code, f"JAR:{clean_code}")
    )
    row = await cursor.fetchone()
    if row:
        product = dict(row)
        product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
        refill_price = product.get("refill_price") if (product.get("refill_price") and product["refill_price"] > 0) else product["selling_price"]
        refill_qty = product.get("refill_qty") or 1.0

        return {
            "scan_type": "jar_refill",
            "product": product,
            "quantity_to_add": float(refill_qty),
            "effective_unit_price": float(refill_price),
            "effective_subtotal": round(refill_qty * refill_price, 2),
            "pack_label": f"Jar Refill ({refill_qty}{product['unit']})",
            "message": f"Jar QR Scanned: {product['name']} (Refill ₱{refill_price:.2f})"
        }

    # 3. Check Standard Single-Unit Barcode
    cursor = await db.execute(
        "SELECT * FROM products WHERE barcode = ?",
        (clean_code,)
    )
    row = await cursor.fetchone()
    if row:
        product = dict(row)
        product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]

        return {
            "scan_type": "unit",
            "product": product,
            "quantity_to_add": 1.0,
            "effective_unit_price": float(product["selling_price"]),
            "effective_subtotal": float(product["selling_price"]),
            "pack_label": None,
            "message": f"Scanned: {product['name']} (₱{product['selling_price']:.2f})"
        }

    raise HTTPException(
        status_code=404,
        detail=f"No product matches scanned code: {clean_code}"
    )


@router.get("/products/barcode/{barcode}")
async def get_product_by_barcode(barcode: str, db=Depends(get_db)):
    """
    Look up a single product by barcode, pack barcode, or jar code.
    Maintains full backward compatibility while supporting packs & jar QRs.
    """
    clean_code = barcode.strip()

    # Search in order: pack_barcode -> jar_code -> barcode
    cursor = await db.execute(
        """SELECT * FROM products 
           WHERE barcode = ? OR pack_barcode = ? OR jar_code = ? OR jar_code = ?""",
        (clean_code, clean_code, clean_code, f"JAR:{clean_code}")
    )
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No product found with barcode or QR code: {clean_code}"
        )

    product = dict(row)
    product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]

    # Annotate scan metadata
    if product.get("pack_barcode") == clean_code:
        pcs = product.get("pcs_per_pack") or 10
        pack_price = product.get("full_pack_price") if (product.get("full_pack_price") and product["full_pack_price"] > 0) else round(pcs * product["selling_price"], 2)
        product["scan_type"] = "mother_pack"
        product["default_qty"] = float(pcs)
        product["default_price"] = round(pack_price / pcs, 2)
        product["default_subtotal"] = pack_price
        product["pack_label"] = f"Full-Pack ({pcs}pcs)"
    elif product.get("jar_code") in (clean_code, f"JAR:{clean_code}"):
        refill_price = product.get("refill_price") if (product.get("refill_price") and product["refill_price"] > 0) else product["selling_price"]
        refill_qty = product.get("refill_qty") or 1.0
        product["scan_type"] = "jar_refill"
        product["default_qty"] = float(refill_qty)
        product["default_price"] = float(refill_price)
        product["default_subtotal"] = round(refill_qty * refill_price, 2)
        product["pack_label"] = f"Jar Refill ({refill_qty}{product['unit']})"
    else:
        product["scan_type"] = "unit"
        product["default_qty"] = 1.0
        product["default_price"] = float(product["selling_price"])
        product["default_subtotal"] = float(product["selling_price"])
        product["pack_label"] = None

    return product


@router.get("/products/search")
async def search_products(q: str = Query(..., min_length=1, description="Search query for product name, barcode, or jar code"), db=Depends(get_db)):
    """
    Search products by name, barcode, pack_barcode, or jar_code using SQL LIKE.
    """
    term = f"%{q.strip()}%"
    cursor = await db.execute(
        """SELECT * FROM products 
           WHERE name LIKE ? OR barcode LIKE ? OR pack_barcode LIKE ? OR jar_code LIKE ?
           ORDER BY name""",
        (term, term, term, term)
    )
    rows = await cursor.fetchall()

    products = []
    for row in rows:
        product = dict(row)
        product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
        products.append(product)

    return products


@router.get("/products/quick")
async def get_quick_items(db=Depends(get_db)):
    """Get products marked for fast-access."""
    cursor = await db.execute(
        "SELECT * FROM products WHERE is_quick_item = 1 OR jar_code IS NOT NULL ORDER BY name"
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
