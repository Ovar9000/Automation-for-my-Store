"""
Sari-Sari Store POS — Database Manager
========================================
Handles SQLite connection, schema creation, and WAL mode.
The database file is stored at data/store.db relative to project root.

Usage:
    from app.database import get_db, init_db
"""

import aiosqlite
import os
from pathlib import Path

# ─── Database file path ──────────────────────────────────────────────
# Store the DB in the data/ directory so it's easy to find and backup
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "store.db"


# ─── SQL Schema ──────────────────────────────────────────────────────
SCHEMA_SQL = """
-- =============================================================
-- PRODUCTS TABLE
-- Stores all inventory items (barcoded, weighted, quick items)
-- =============================================================
CREATE TABLE IF NOT EXISTS products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode             TEXT UNIQUE,                        -- Optional, nullable for non-barcoded items
    name                TEXT NOT NULL,                      -- Display name
    cost_price          REAL NOT NULL DEFAULT 0,            -- Purchase/cost price per unit
    selling_price       REAL NOT NULL DEFAULT 0,            -- Selling price per unit
    stock_qty           REAL NOT NULL DEFAULT 0,            -- Current stock (decimal for kg/liters)
    low_stock_threshold REAL NOT NULL DEFAULT 5,            -- Alert when stock falls below this
    unit                TEXT NOT NULL DEFAULT 'pc',         -- Unit of measure: 'pc', 'kg', 'L', 'ml'
    is_quick_item       INTEGER NOT NULL DEFAULT 0,         -- 1 = show as quick button on cashier
    quick_button_color  TEXT DEFAULT '#10b981',             -- Hex color for the quick button
    category            TEXT DEFAULT 'General',             -- Category for grouping
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================
-- TRANSACTIONS TABLE
-- Each sale or GCash transaction creates one row here
-- =============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_type    TEXT NOT NULL DEFAULT 'SALE',       -- 'SALE', 'GCASH_IN', 'GCASH_OUT'
    total_amount        REAL NOT NULL DEFAULT 0,            -- Grand total charged to customer
    total_cost          REAL NOT NULL DEFAULT 0,            -- Total COGS for profit calc
    payment_method      TEXT DEFAULT 'CASH',                -- 'CASH' or 'GCASH'
    receipt_printed     INTEGER NOT NULL DEFAULT 0,         -- 1 = receipt was printed
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================
-- TRANSACTION ITEMS TABLE
-- Line items for each sale transaction
-- =============================================================
CREATE TABLE IF NOT EXISTS transaction_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id      INTEGER NOT NULL,
    product_id          INTEGER,                            -- Nullable if product was deleted
    product_name        TEXT NOT NULL,                      -- Snapshot of name at sale time
    quantity            REAL NOT NULL DEFAULT 1,            -- Qty sold (decimal for weighted items)
    unit_price          REAL NOT NULL DEFAULT 0,            -- Price per unit at sale time
    cost_price          REAL NOT NULL DEFAULT 0,            -- Cost per unit at sale time
    subtotal            REAL NOT NULL DEFAULT 0,            -- quantity * unit_price
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

-- =============================================================
-- GCASH TRANSACTIONS TABLE
-- Detailed GCash cash-in/cash-out records
-- =============================================================
CREATE TABLE IF NOT EXISTS gcash_transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id      INTEGER NOT NULL,                   -- Links to transactions table
    flow_type           TEXT NOT NULL,                      -- 'A' = fee on top, 'B' = fee deducted
    input_amount        REAL NOT NULL,                      -- What the cashier typed
    principal_amount    REAL NOT NULL,                      -- Computed principal (GCash amount)
    fee                 REAL NOT NULL,                      -- Computed fee (store income)
    total_collected     REAL NOT NULL,                      -- Cash collected from customer
    reference_number    TEXT,                               -- GCash Reference No.
    mobile_number       TEXT,                               -- Customer mobile number
    receipt_image       TEXT,                               -- Base64 receipt capture image
    gcash_timestamp     TEXT,                               -- GCash receipt actual date/time
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
);

-- =============================================================
-- ADMIN SETTINGS TABLE
-- Key-value store for app configuration
-- =============================================================
CREATE TABLE IF NOT EXISTS admin_settings (
    key                 TEXT PRIMARY KEY,
    value               TEXT
);

-- =============================================================
-- INDEXES for fast lookups
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_quick ON products(is_quick_item);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_transaction_items_txn ON transaction_items(transaction_id);
CREATE INDEX IF NOT EXISTS idx_gcash_txn ON gcash_transactions(transaction_id);
"""

# ─── Default settings to insert on first run ─────────────────────────
DEFAULT_SETTINGS = {
    "store_name": "Sari-Sari Store",
    "store_address": "",
    "store_phone": "",
    "admin_password": "admin123",        # Default password — change immediately!
    "receipt_enabled": "1",
    "gcash_fee_per_thousand": "10",       # Fee per 1000 PHP block
}

# ─── Sample quick items for first-run demo ───────────────────────────
SAMPLE_PRODUCTS = [
    # (barcode, name, cost, sell, stock, threshold, unit, is_quick, color, category)
    (None, "Gasoline (per Liter)", 55.00, 62.00, 100.0, 20.0, "L", 1, "#ef4444", "Fuel"),
    (None, "Rice (per Kilo)", 38.00, 45.00, 50.0, 10.0, "kg", 1, "#f59e0b", "Staples"),
    (None, "Candy", 0.50, 1.00, 200.0, 50.0, "pc", 1, "#ec4899", "Snacks"),
    (None, "Softdrinks (bottle)", 12.00, 15.00, 48.0, 12.0, "pc", 1, "#3b82f6", "Beverages"),
    (None, "Feeds (per Kilo)", 28.00, 35.00, 100.0, 20.0, "kg", 1, "#8b5cf6", "Feeds"),
    (None, "Pork (per Kilo)", 200.00, 250.00, 20.0, 5.0, "kg", 1, "#f97316", "Meat"),
    ("4800016121005", "Lucky Me Pancit Canton", 9.00, 12.00, 100.0, 20.0, "pc", 0, "#10b981", "Noodles"),
    ("4800361413022", "Kopiko Brown 25g", 5.00, 7.00, 80.0, 15.0, "pc", 0, "#10b981", "Beverages"),
]


async def init_db():
    """
    Initialize the database: create tables, set WAL mode,
    insert default settings and sample products on first run.
    """
    # Ensure the data directory exists
    os.makedirs(DB_PATH.parent, exist_ok=True)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        # ── Enable WAL mode for better concurrent read performance ──
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # ── Create all tables ──
        await db.executescript(SCHEMA_SQL)

        # ── Insert default settings if not present ──
        for key, value in DEFAULT_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO admin_settings (key, value) VALUES (?, ?)",
                (key, value)
            )

        # ── Insert sample products if table is empty ──
        cursor = await db.execute("SELECT COUNT(*) FROM products")
        row = await cursor.fetchone()
        if row[0] == 0:
            await db.executemany(
                """INSERT INTO products
                   (barcode, name, cost_price, selling_price, stock_qty,
                    low_stock_threshold, unit, is_quick_item, quick_button_color, category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                SAMPLE_PRODUCTS
            )

        await db.commit()
    print(f"[DB] Database initialized at: {DB_PATH}")


async def get_db():
    """
    FastAPI dependency — yields an aiosqlite connection for each request.
    Usage in routes:
        @router.get("/api/items")
        async def list_items(db = Depends(get_db)):
            ...
    """
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row     # Access columns by name
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()
