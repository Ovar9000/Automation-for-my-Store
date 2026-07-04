"""
Sari-Sari Store POS — GCash Router
====================================
Handles GCash Cash-In / Cash-Out operations:
  - Fee calculation (Flow A: principal input, Flow B: total input)
  - Transaction recording (creates both transaction + gcash_transactions rows)

GCash is a major revenue source for sari-sari stores.
The fee engine supports two flows:
  Flow A: Customer says "I want to cash in 1000" → fee added on top
  Flow B: Customer hands 1010 total → reverse-calculate principal and fee
"""

from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.models import GCashCalculateRequest, GCashCalculateResponse, GCashTransactRequest
from app.services.gcash_engine import calculate_gcash

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# GCASH FEE CALCULATION
# ═══════════════════════════════════════════════════════════════

@router.post("/gcash/calculate")
async def gcash_calculate(data: GCashCalculateRequest):
    """
    Calculate GCash fees for a given amount and flow type.

    Business logic:
    - This is a stateless calculation — nothing is saved to DB yet.
    - The cashier uses this to preview the fee breakdown before confirming.
    - Flow A: Customer specifies the principal (GCash amount they want).
              Fee = ceil(principal / 1000) * fee_per_thousand.
              Total collected = principal + fee.
    - Flow B: Customer specifies the total cash they're handing over.
              Engine reverse-calculates the largest principal that fits.
              Store keeps the remainder as fee.

    Validates:
    - Amount must be positive (negative GCash makes no sense).
    - Flow type must be 'A' or 'B'.
    """

    # ── Validate amount ──────────────────────────────────────────────
    if data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than 0."
        )

    # ── Validate flow type ───────────────────────────────────────────
    if data.flow_type.upper() not in ("A", "B"):
        raise HTTPException(
            status_code=400,
            detail="flow_type must be 'A' or 'B'."
        )

    # ── Dispatch to the GCash calculation engine ─────────────────────
    # The engine is a pure function — no DB access, easy to unit test
    result = calculate_gcash(data.amount, data.flow_type)

    return result


# ═══════════════════════════════════════════════════════════════
# GCASH TRANSACTION RECORDING
# ═══════════════════════════════════════════════════════════════

@router.post("/gcash/transact")
async def gcash_transact(data: GCashTransactRequest, db=Depends(get_db)):
    """
    Record a completed GCash transaction.

    Business logic:
    - Creates TWO database rows:
      1. A row in `transactions` (the main ledger):
         - transaction_type: 'GCASH_IN' or 'GCASH_OUT'
         - total_amount: the total collected from customer
         - payment_method: 'GCASH'
      2. A row in `gcash_transactions` (detailed GCash breakdown):
         - Stores flow_type, input_amount, principal, fee, total_collected
         - Links back to the transaction via transaction_id

    - This dual-table approach lets us:
      a) Show GCash transactions in the main transaction history
      b) Keep detailed GCash fee data for the income report
      c) Calculate total GCash fees earned per day/month

    Flow:
    1. Frontend calls /gcash/calculate to preview
    2. Cashier confirms → frontend calls /gcash/transact
    3. Both tables are populated atomically
    """

    # ── Validate transaction type ────────────────────────────────────
    if data.transaction_type not in ("GCASH_IN", "GCASH_OUT"):
        raise HTTPException(
            status_code=400,
            detail="transaction_type must be 'GCASH_IN' or 'GCASH_OUT'."
        )

    # ── Insert into main transactions table ──────────────────────────
    # total_cost is 0 for GCash (no COGS — it's a service, not product sale)
    cursor = await db.execute(
        """INSERT INTO transactions
           (transaction_type, total_amount, total_cost, payment_method, receipt_printed)
           VALUES (?, ?, ?, ?, ?)""",
        (
            data.transaction_type,
            round(data.total_collected, 2),
            0,                              # No cost of goods for GCash
            "GCASH",
            0                               # Receipt printing handled separately
        )
    )
    transaction_id = cursor.lastrowid

    # ── Insert into gcash_transactions detail table ──────────────────
    cursor = await db.execute(
        """INSERT INTO gcash_transactions
           (transaction_id, flow_type, input_amount, principal_amount, fee, total_collected,
            reference_number, mobile_number, receipt_image, gcash_timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            transaction_id,
            data.flow_type.upper(),
            round(data.input_amount, 2),
            round(data.principal_amount, 2),
            round(data.fee, 2),
            round(data.total_collected, 2),
            data.reference_number,
            data.mobile_number,
            data.receipt_image,
            data.gcash_timestamp
        )
    )
    gcash_id = cursor.lastrowid

    # ── Commit both inserts atomically ───────────────────────────────
    await db.commit()

    # ── Fetch both created records for the response ──────────────────
    txn_cursor = await db.execute(
        "SELECT * FROM transactions WHERE id = ?",
        (transaction_id,)
    )
    txn_row = await txn_cursor.fetchone()

    gcash_cursor = await db.execute(
        "SELECT * FROM gcash_transactions WHERE id = ?",
        (gcash_id,)
    )
    gcash_row = await gcash_cursor.fetchone()

    return {
        "transaction": dict(txn_row),
        "gcash_detail": dict(gcash_row),
        "message": f"GCash {data.transaction_type} recorded successfully.",
    }


@router.get("/gcash/transactions")
async def list_gcash_transactions(db=Depends(get_db)):
    """
    List all GCash transactions recorded in the system.
    """
    cursor = await db.execute(
        """SELECT 
               t.id as transaction_id,
               t.transaction_type,
               t.total_amount,
               t.created_at as system_created_at,
               g.id as gcash_id,
               g.flow_type,
               g.input_amount,
               g.principal_amount,
               g.fee,
               g.total_collected,
               g.reference_number,
               g.mobile_number,
               g.receipt_image,
               g.gcash_timestamp
           FROM gcash_transactions g
           JOIN transactions t ON g.transaction_id = t.id
           ORDER BY t.created_at DESC"""
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
