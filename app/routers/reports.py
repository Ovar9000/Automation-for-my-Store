"""
Sari-Sari Store POS — Reports Router
======================================
Handles financial reporting for the store owner:
  - Daily income report (sales, COGS, profit, GCash fees)
  - Monthly income report (same metrics, aggregated by month)
  - Top-selling products analysis (by quantity, revenue, or profit)

Reports are critical for sari-sari store owners to track:
  1. Whether the store is profitable (net_profit = sales - COGS)
  2. How much GCash fee income they're earning
  3. Which products sell best (to inform restocking decisions)
"""

from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# DAILY REPORT
# ═══════════════════════════════════════════════════════════════

@router.get("/reports/daily")
async def daily_report(
    report_date: str = Query(None, alias="date", description="Date in YYYY-MM-DD format. Defaults to today."),
    db=Depends(get_db)
):
    """
    Generate a daily income report for a specific date.

    Business logic:
    - Calculates key financial metrics for the store owner:
      • total_sales: Sum of total_amount for all SALE transactions
      • total_cost: Sum of total_cost (COGS) for all SALE transactions
      • net_profit: total_sales - total_cost (what the owner actually earns)
      • total_gcash_fees: Sum of fees from GCash transactions (pure income)
      • transaction_count: Number of SALE transactions
      • gcash_transaction_count: Number of GCash transactions

    - Uses SQLite date() with 'localtime' modifier to match the local date.
    - If no date is provided, defaults to today.

    Financial insight:
    - net_profit tells the owner if the store made money that day
    - gcash_fees are 100% income (no COGS) — important revenue stream
    - transaction_count helps gauge foot traffic
    """

    # ── Default to today if no date provided ─────────────────────────
    if not report_date:
        report_date = date.today().isoformat()  # YYYY-MM-DD

    # ── Validate date format ─────────────────────────────────────────
    try:
        datetime.strptime(report_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD."
        )

    # ── Query total sales and COGS for SALE transactions ─────────────
    # Only count SALE transactions (not GCASH_IN/GCASH_OUT)
    cursor = await db.execute(
        """SELECT
               COALESCE(SUM(total_amount), 0) as total_sales,
               COALESCE(SUM(total_cost), 0)   as total_cost,
               COUNT(*)                        as transaction_count
           FROM transactions
           WHERE date(created_at, 'localtime') = ?
             AND transaction_type = 'SALE'""",
        (report_date,)
    )
    sales_row = await cursor.fetchone()
    sales_data = dict(sales_row)

    # ── Query GCash fee totals ───────────────────────────────────────
    # Join gcash_transactions with transactions to filter by date
    cursor = await db.execute(
        """SELECT
               COALESCE(SUM(g.fee), 0) as total_gcash_fees,
               COUNT(*)                as gcash_transaction_count
           FROM gcash_transactions g
           JOIN transactions t ON g.transaction_id = t.id
           WHERE date(t.created_at, 'localtime') = ?""",
        (report_date,)
    )
    gcash_row = await cursor.fetchone()
    gcash_data = dict(gcash_row)

    # ── Calculate net profit ─────────────────────────────────────────
    total_sales = round(sales_data["total_sales"], 2)
    total_cost = round(sales_data["total_cost"], 2)
    net_profit = round(total_sales - total_cost, 2)

    return {
        "date": report_date,
        "total_sales": total_sales,
        "total_cost": total_cost,
        "net_profit": net_profit,
        "total_gcash_fees": round(gcash_data["total_gcash_fees"], 2),
        "transaction_count": sales_data["transaction_count"],
        "gcash_transaction_count": gcash_data["gcash_transaction_count"],
    }


# ═══════════════════════════════════════════════════════════════
# MONTHLY REPORT
# ═══════════════════════════════════════════════════════════════

@router.get("/reports/monthly")
async def monthly_report(
    year: int = Query(None, description="Year (YYYY). Defaults to current year."),
    month: int = Query(None, description="Month (1-12). Defaults to current month."),
    db=Depends(get_db)
):
    """
    Generate a monthly income report.

    Business logic:
    - Same metrics as the daily report, but aggregated for an entire month.
    - Uses strftime('%Y', ...) and strftime('%m', ...) to filter by year+month.
    - Useful for the store owner's monthly accounting/budgeting.
    - If year/month not provided, defaults to the current month.

    The store owner typically checks this at end-of-month to assess:
    - Total revenue trend (is the store growing?)
    - Profit margins (are costs eating into sales?)
    - GCash fee income (is offering GCash services worth it?)
    """

    # ── Default to current year/month if not provided ────────────────
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    # ── Validate month range ─────────────────────────────────────────
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Month must be between 1 and 12."
        )

    # ── Format month as zero-padded string for SQL comparison ────────
    month_str = f"{month:02d}"  # e.g., "01", "02", ..., "12"

    # ── Query total sales and COGS for the month ─────────────────────
    cursor = await db.execute(
        """SELECT
               COALESCE(SUM(total_amount), 0) as total_sales,
               COALESCE(SUM(total_cost), 0)   as total_cost,
               COUNT(*)                        as transaction_count
           FROM transactions
           WHERE strftime('%Y', created_at, 'localtime') = ?
             AND strftime('%m', created_at, 'localtime') = ?
             AND transaction_type = 'SALE'""",
        (str(year), month_str)
    )
    sales_row = await cursor.fetchone()
    sales_data = dict(sales_row)

    # ── Query GCash fee totals for the month ─────────────────────────
    cursor = await db.execute(
        """SELECT
               COALESCE(SUM(g.fee), 0) as total_gcash_fees,
               COUNT(*)                as gcash_transaction_count
           FROM gcash_transactions g
           JOIN transactions t ON g.transaction_id = t.id
           WHERE strftime('%Y', t.created_at, 'localtime') = ?
             AND strftime('%m', t.created_at, 'localtime') = ?""",
        (str(year), month_str)
    )
    gcash_row = await cursor.fetchone()
    gcash_data = dict(gcash_row)

    # ── Calculate net profit ─────────────────────────────────────────
    total_sales = round(sales_data["total_sales"], 2)
    total_cost = round(sales_data["total_cost"], 2)
    net_profit = round(total_sales - total_cost, 2)

    return {
        "year": year,
        "month": month,
        "total_sales": total_sales,
        "total_cost": total_cost,
        "net_profit": net_profit,
        "total_gcash_fees": round(gcash_data["total_gcash_fees"], 2),
        "transaction_count": sales_data["transaction_count"],
        "gcash_transaction_count": gcash_data["gcash_transaction_count"],
    }


# ═══════════════════════════════════════════════════════════════
# TOP PRODUCTS REPORT
# ═══════════════════════════════════════════════════════════════

@router.get("/reports/top-products")
async def top_products(
    period: str = Query("day", description="Time period: 'day', 'month', or 'all'"),
    limit: int = Query(10, ge=1, le=100, description="Number of top products to return"),
    sort_by: str = Query("quantity", description="Sort by: 'quantity', 'revenue', or 'profit'"),
    db=Depends(get_db)
):
    """
    Get top-selling products ranked by quantity, revenue, or profit.

    Business logic:
    - Joins transaction_items with transactions to filter by date period.
    - Groups by product_name (not product_id) because:
      a) A product might be deleted but we still want its sales history
      b) product_name is snapshotted at sale time, so it's always available
    - Supports three ranking modes:
      • quantity: Most units sold (helps with restocking decisions)
      • revenue: Most money earned (identifies high-value products)
      • profit: Most profit generated (identifies best margin products)
    - Period filtering:
      • day: Today's sales only
      • month: Current month's sales
      • all: All-time sales data

    This report helps the store owner decide:
    - What to restock (quantity leaders)
    - What generates the most income (revenue leaders)
    - What's most profitable per unit (profit leaders)
    """

    # ── Validate sort_by parameter ───────────────────────────────────
    valid_sort = {"quantity": "total_qty", "revenue": "total_revenue", "profit": "total_profit"}
    if sort_by not in valid_sort:
        raise HTTPException(
            status_code=400,
            detail=f"sort_by must be one of: {', '.join(valid_sort.keys())}"
        )
    order_column = valid_sort[sort_by]

    # ── Build date filter based on period ────────────────────────────
    date_filter = ""
    params = []

    if period == "day":
        # Today's transactions only
        date_filter = "AND date(t.created_at, 'localtime') = date('now', 'localtime')"
    elif period == "month":
        # Current month's transactions
        today = date.today()
        date_filter = """AND strftime('%Y', t.created_at, 'localtime') = ?
                         AND strftime('%m', t.created_at, 'localtime') = ?"""
        params.extend([str(today.year), f"{today.month:02d}"])
    elif period == "all":
        # No date filter — all time
        date_filter = ""
    else:
        raise HTTPException(
            status_code=400,
            detail="period must be 'day', 'month', or 'all'"
        )

    # ── Query top products ───────────────────────────────────────────
    # We use ti.product_id as a fallback identifier, but group primarily by name
    # because product_id could be NULL (deleted products)
    query = f"""
        SELECT
            COALESCE(ti.product_id, 0)            as product_id,
            ti.product_name                        as product_name,
            ROUND(SUM(ti.quantity), 2)             as total_qty,
            ROUND(SUM(ti.subtotal), 2)             as total_revenue,
            ROUND(SUM(ti.quantity * ti.cost_price), 2) as total_cost,
            ROUND(SUM(ti.subtotal) - SUM(ti.quantity * ti.cost_price), 2) as total_profit
        FROM transaction_items ti
        JOIN transactions t ON ti.transaction_id = t.id
        WHERE t.transaction_type = 'SALE'
        {date_filter}
        GROUP BY ti.product_name
        ORDER BY {order_column} DESC
        LIMIT ?
    """
    params.append(limit)

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    # ── Convert to response format ───────────────────────────────────
    products = []
    for row in rows:
        product = dict(row)
        # Ensure all money values are properly rounded
        product["total_qty"] = round(product["total_qty"], 2)
        product["total_revenue"] = round(product["total_revenue"], 2)
        product["total_cost"] = round(product["total_cost"], 2)
        product["total_profit"] = round(product["total_profit"], 2)
        products.append(product)

    return {
        "period": period,
        "sort_by": sort_by,
        "limit": limit,
        "products": products,
    }
