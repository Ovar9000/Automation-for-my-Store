"""
Sari-Sari Store POS — Customer Debt (Utang) Router
======================================================
API endpoints for managing customer store credit, debt charges, and debt repayments.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import aiosqlite
from app.database import get_db

router = APIRouter()


# ─── Pydantic Schemas ────────────────────────────────────────────────

class DebtChargeRequest(BaseModel):
    customer_name: str
    sale_id: Optional[int] = None
    amount_charged: float
    amount_paid_now: float = 0
    phone_number: Optional[str] = None
    notes: Optional[str] = None


class DebtPaymentRequest(BaseModel):
    payment_amount: float
    notes: Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────────

@router.get("")
async def list_debts(search: Optional[str] = Query(None), db=Depends(get_db)):
    """List all customer debt accounts with total debt > 0 or matching search."""
    if search and search.strip():
        query = """
            SELECT * FROM customer_debts 
            WHERE customer_name LIKE ? 
            ORDER BY total_debt DESC, updated_at DESC
        """
        cursor = await db.execute(query, (f"%{search.strip()}%",))
    else:
        query = "SELECT * FROM customer_debts ORDER BY total_debt DESC, updated_at DESC"
        cursor = await db.execute(query)

    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/{debt_id}/history")
async def get_debt_history(debt_id: int, db=Depends(get_db)):
    """Get complete transaction history for a specific debt account."""
    # Check debt account exists
    cursor = await db.execute("SELECT * FROM customer_debts WHERE id = ?", (debt_id,))
    customer = await cursor.fetchone()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer debt account not found.")

    # Fetch debt transactions
    tx_cursor = await db.execute("""
        SELECT dt.*, t.receipt_number
        FROM debt_transactions dt
        LEFT JOIN transactions t ON dt.sale_id = t.id
        WHERE dt.debt_id = ?
        ORDER BY dt.created_at DESC
    """, (debt_id,))
    tx_rows = await tx_cursor.fetchall()

    return {
        "customer": dict(customer),
        "history": [dict(r) for r in tx_rows]
    }


@router.post("/charge")
async def charge_debt(req: DebtChargeRequest, db=Depends(get_db)):
    """Charge a sale amount (or partial balance) to a customer's Utang account."""
    clean_name = req.customer_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Customer name is required.")

    if req.amount_charged <= 0:
        raise HTTPException(status_code=400, detail="Amount charged must be greater than 0.")

    # Check if customer already exists (case-insensitive)
    cursor = await db.execute(
        "SELECT * FROM customer_debts WHERE LOWER(customer_name) = LOWER(?)",
        (clean_name,)
    )
    existing = await cursor.fetchone()

    if existing:
        debt_id = existing["id"]
        new_total = round(existing["total_debt"] + req.amount_charged, 2)
        await db.execute(
            "UPDATE customer_debts SET total_debt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_total, debt_id)
        )
    else:
        new_total = round(req.amount_charged, 2)
        ins_cursor = await db.execute(
            "INSERT INTO customer_debts (customer_name, total_debt, phone_number, notes) VALUES (?, ?, ?, ?)",
            (clean_name, new_total, req.phone_number, req.notes)
        )
        debt_id = ins_cursor.lastrowid

    # Log debt transaction
    await db.execute(
        """INSERT INTO debt_transactions (debt_id, sale_id, type, amount, balance_after, notes)
           VALUES (?, ?, 'CHARGE', ?, ?, ?)""",
        (debt_id, req.sale_id, req.amount_charged, new_total, req.notes or "Charged to Utang")
    )

    await db.commit()

    # Fetch updated record
    c_cur = await db.execute("SELECT * FROM customer_debts WHERE id = ?", (debt_id,))
    res = await c_cur.fetchone()
    return dict(res)


@router.post("/{debt_id}/pay")
async def pay_debt(debt_id: int, req: DebtPaymentRequest, db=Depends(get_db)):
    """Process a debt repayment from a customer."""
    if req.payment_amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than 0.")

    cursor = await db.execute("SELECT * FROM customer_debts WHERE id = ?", (debt_id,))
    customer = await cursor.fetchone()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer debt account not found.")

    current_debt = customer["total_debt"]
    payment = min(round(req.payment_amount, 2), current_debt)
    new_balance = round(current_debt - payment, 2)

    # Update customer debt balance
    await db.execute(
        "UPDATE customer_debts SET total_debt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_balance, debt_id)
    )

    # Log debt transaction
    await db.execute(
        """INSERT INTO debt_transactions (debt_id, type, amount, balance_after, notes)
           VALUES (?, 'PAYMENT', ?, ?, ?)""",
        (debt_id, payment, new_balance, req.notes or "Utang Repayment")
    )

    # Log cash entry in store transactions
    import uuid
    receipt_no = f"UTANG-PAY-{uuid.uuid4().hex[:6].upper()}"
    await db.execute(
        """INSERT INTO transactions
           (receipt_number, total_amount, payment_type, amount_tendered, change_amount, transaction_type, notes)
           VALUES (?, ?, 'CASH', ?, 0, 'UTANG_PAYMENT', ?)""",
        (receipt_no, payment, payment, f"Utang Payment from {customer['customer_name']}")
    )

    await db.commit()

    # Fetch updated customer
    c_cur = await db.execute("SELECT * FROM customer_debts WHERE id = ?", (debt_id,))
    res = await c_cur.fetchone()
    return {
        "message": f"Payment of ₱{payment:.2f} recorded for {customer['customer_name']}.",
        "customer": dict(res),
        "payment_amount": payment
    }
