"""
Sari-Sari Store POS — Database Manager
========================================
Handles SQLite connection, schema creation, WAL mode, migrations,
and cryptographic security utilities.
The database file is stored at data/store.db relative to project root.

Usage:
    from app.database import get_db, init_db, hash_password, verify_password
"""

import aiosqlite
import hashlib
import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ─── Database file path (Supports frozen .exe and regular python) ────
if getattr(sys, "frozen", False):
    # Running as compiled .exe: store DB next to the executable
    BASE_DIR = Path(sys.executable).parent
else:
    # Running from source code
    BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = BASE_DIR / "data" / "store.db"



# ─── Cryptographic Password Utilities ────────────────────────────────
def hash_password(plain_password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with 100,000 iterations and random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"pbkdf2_sha256$100000${salt}${key.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify a plain password against stored hash (or legacy plaintext with auto-upgrade)."""
    if not stored_hash:
        return False
    if not stored_hash.startswith("pbkdf2_sha256$"):
        # Legacy plain-text check for backwards compatibility
        return plain_password == stored_hash

    try:
        parts = stored_hash.split("$")
        if len(parts) != 4:
            return False
        _, iterations_str, salt, expected_hash = parts
        iterations = int(iterations_str)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return secrets.compare_digest(key.hex(), expected_hash)
    except Exception:
        return False


# ─── SQL Schema ──────────────────────────────────────────────────────
SCHEMA_SQL = """
-- =============================================================
-- PRODUCTS TABLE
-- Stores all inventory items (barcoded, weighted, packs, jar refills)
-- =============================================================
CREATE TABLE IF NOT EXISTS products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode             TEXT UNIQUE,                        -- Single unit barcode (e.g. 1 sachet)
    pack_barcode        TEXT UNIQUE,                        -- Mother-pack / hanging tie barcode
    jar_code            TEXT UNIQUE,                        -- Jar / Dispenser QR code (e.g. JAR-SUGAR-100G)
    refill_price        REAL,                               -- Selling price per refill
    refill_qty          REAL DEFAULT 1.0,                   -- Stock quantity deducted per refill
    name                TEXT NOT NULL,                      -- Display name
    cost_price          REAL NOT NULL DEFAULT 0,            -- Purchase/cost price per unit
    selling_price       REAL NOT NULL DEFAULT 0,            -- Selling price per unit
    stock_qty           REAL NOT NULL DEFAULT 0,            -- Current stock (decimal for kg/liters/pcs)
    low_stock_threshold REAL NOT NULL DEFAULT 5,            -- Alert when stock falls below this
    unit                TEXT NOT NULL DEFAULT 'pc',         -- Unit of measure: 'pc', 'kg', 'L', 'ml', 'g'
    is_quick_item       INTEGER NOT NULL DEFAULT 0,         -- 1 = quick button item (legacy support)
    quick_button_color  TEXT DEFAULT '#3b82f6',             -- Hex color
    category            TEXT DEFAULT 'General',             -- Category for grouping
    pcs_per_pack        INTEGER DEFAULT 1,                  -- Pack/tie size (e.g. 10pcs per tie)
    bulk_cost_price     REAL,                               -- Total cost paid for 1 bulk pack/tie
    full_pack_price     REAL,                               -- Selling price for 1 full bulk pack/tie
    half_dozen_price    REAL,                               -- Legacy bundle price
    dozen_price         REAL,                               -- Legacy bundle price
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================
-- TRANSACTIONS TABLE
-- Each sale, GCash, or Utang payment creates one row here
-- =============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_number      TEXT,                               -- Formatted receipt # (e.g. TXN-20260815-A1B2)
    transaction_type    TEXT NOT NULL DEFAULT 'SALE',       -- 'SALE', 'GCASH_IN', 'GCASH_OUT', 'UTANG_PAYMENT'
    total_amount        REAL NOT NULL DEFAULT 0,            -- Grand total charged to customer
    total_cost          REAL NOT NULL DEFAULT 0,            -- Total COGS for profit calc
    payment_method      TEXT DEFAULT 'CASH',                -- 'CASH', 'GCASH', 'UTANG'
    amount_tendered     REAL NOT NULL DEFAULT 0,            -- Cash received from customer
    change_amount       REAL NOT NULL DEFAULT 0,            -- Change returned to customer
    customer_name       TEXT,                               -- For Utang sales / customer reference
    notes               TEXT,                               -- Optional notes/memo
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
    pack_label          TEXT,                               -- E.g. 'Full-Pack (10pcs)', 'Jar Refill'
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
-- ADMIN SETTINGS & AUTH SESSIONS TABLE
-- Key-value store for app configuration and active sessions
-- =============================================================
CREATE TABLE IF NOT EXISTS admin_settings (
    key                 TEXT PRIMARY KEY,
    value               TEXT
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    token               TEXT PRIMARY KEY,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at          DATETIME
);

-- =============================================================
-- CUSTOMER DEBTS & UTANG SYSTEM
-- =============================================================
CREATE TABLE IF NOT EXISTS customer_debts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name       TEXT NOT NULL UNIQUE,
    total_debt          REAL NOT NULL DEFAULT 0,
    phone_number        TEXT,
    notes               TEXT,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS debt_transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_id             INTEGER NOT NULL,
    sale_id             INTEGER,
    type                TEXT NOT NULL,                      -- 'CHARGE' or 'PAYMENT'
    amount              REAL NOT NULL,
    balance_after       REAL NOT NULL,
    notes               TEXT,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (debt_id) REFERENCES customer_debts(id) ON DELETE CASCADE,
    FOREIGN KEY (sale_id) REFERENCES transactions(id) ON DELETE SET NULL
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
CREATE INDEX IF NOT EXISTS idx_customer_debts_name ON customer_debts(customer_name);
CREATE INDEX IF NOT EXISTS idx_debt_txns_debt_id ON debt_transactions(debt_id);
"""

# ─── Default settings to insert on first run ─────────────────────────
DEFAULT_SETTINGS = {
    "store_name": "Sari-Sari Store",
    "store_address": "",
    "store_phone": "",
    "admin_password": hash_password("admin123"), # Secure default password hash
    "receipt_enabled": "1",
    "gcash_fee_per_thousand": "10",              # Fee per 1000 PHP block
    "cloud_sync_enabled": "0",
    "cloud_sync_endpoint": "",
    "cloud_api_key": ""
}

# ─── Sample products for first-run demo ──────────────────────────────
SAMPLE_PRODUCTS = [
    # (barcode, pack_barcode, jar_code, refill_price, refill_qty, name, cost, sell, stock, threshold, unit, is_quick, color, category, pcs_per_pack, bulk_cost, full_pack)
    (None, None, "JAR:GAS-1L", 62.00, 1.0, "Gasoline Refill (1L Bottle)", 55.00, 62.00, 100.0, 20.0, "L", 0, "#ef4444", "Fuel", 1, None, None),
    (None, None, "JAR:RICE-1KG", 45.00, 1.0, "Sinandomeng Rice (1 Kilo)", 38.00, 45.00, 150.0, 20.0, "kg", 0, "#f59e0b", "Staples", 1, None, None),
    (None, None, "JAR:SUGAR-500G", 35.00, 0.5, "White Sugar Refill (500g)", 28.00, 35.00, 80.0, 15.0, "kg", 0, "#10b981", "Staples", 1, None, None),
    (None, None, "JAR:OIL-250ML", 20.00, 0.25, "Cooking Oil (250ml Pouch)", 15.00, 20.00, 50.0, 10.0, "L", 0, "#eab308", "Cooking", 1, None, None),
    (None, None, "JAR:CANDY-MAXX", 1.00, 1.0, "Maxx Menthol Candy (Jar)", 0.50, 1.00, 300.0, 50.0, "pc", 0, "#ec4899", "Snacks", 50, 22.00, 45.00),
    ("4800016121005", "4800016121005-PACK", None, None, 1.0, "Lucky Me Pancit Canton Original", 9.00, 12.00, 120.0, 20.0, "pc", 0, "#10b981", "Noodles", 10, 85.00, 115.00),
    ("4800361413022", "4800361413022-PACK", "JAR:KOPIKO-STICK", 7.00, 1.0, "Kopiko Brown Coffee 25g", 5.00, 7.00, 100.0, 15.0, "pc", 0, "#8b5cf6", "Beverages", 10, 48.00, 65.00),
]


async def init_db():
    """
    Initialize the database: create tables, set WAL mode,
    insert default settings, run schema migrations.
    """
    os.makedirs(DB_PATH.parent, exist_ok=True)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # Create all tables
        await db.executescript(SCHEMA_SQL)

        # ── Column Migrations ──
        migrations = [
            "ALTER TABLE products ADD COLUMN pack_barcode TEXT",
            "ALTER TABLE products ADD COLUMN jar_code TEXT",
            "ALTER TABLE products ADD COLUMN refill_price REAL",
            "ALTER TABLE products ADD COLUMN refill_qty REAL DEFAULT 1.0",
            "ALTER TABLE products ADD COLUMN half_dozen_price REAL",
            "ALTER TABLE products ADD COLUMN dozen_price REAL",
            "ALTER TABLE products ADD COLUMN pcs_per_pack INTEGER DEFAULT 1",
            "ALTER TABLE products ADD COLUMN bulk_cost_price REAL",
            "ALTER TABLE products ADD COLUMN full_pack_price REAL",
            "ALTER TABLE gcash_transactions ADD COLUMN reference_number TEXT",
            "ALTER TABLE gcash_transactions ADD COLUMN mobile_number TEXT",
            "ALTER TABLE gcash_transactions ADD COLUMN receipt_image TEXT",
            "ALTER TABLE gcash_transactions ADD COLUMN gcash_timestamp TEXT",
            "ALTER TABLE transactions ADD COLUMN receipt_number TEXT",
            "ALTER TABLE transactions ADD COLUMN notes TEXT",
            "ALTER TABLE transactions ADD COLUMN change_amount REAL DEFAULT 0",
            "ALTER TABLE transactions ADD COLUMN customer_name TEXT",
            "ALTER TABLE transaction_items ADD COLUMN pack_label TEXT",
        ]

        for stmt in migrations:
            try:
                await db.execute(stmt)
            except Exception:
                pass

        # ── Create additional indexes ──
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_products_pack_barcode ON products(pack_barcode)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_products_jar_code ON products(jar_code)")
        except Exception:
            pass

        # ── Insert default settings if not present ──
        for key, value in DEFAULT_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO admin_settings (key, value) VALUES (?, ?)",
                (key, value)
            )

        # ── Upgrade legacy plaintext password if present ──
        cursor = await db.execute("SELECT value FROM admin_settings WHERE key = 'admin_password'")
        pwd_row = await cursor.fetchone()
        if pwd_row and pwd_row[0] and not pwd_row[0].startswith("pbkdf2_sha256$"):
            hashed = hash_password(pwd_row[0])
            await db.execute(
                "UPDATE admin_settings SET value = ? WHERE key = 'admin_password'",
                (hashed,)
            )

        # ── Insert sample products if table is empty ──
        cursor = await db.execute("SELECT COUNT(*) FROM products")
        row = await cursor.fetchone()
        if row[0] == 0:
            await db.executemany(
                """INSERT INTO products
                   (barcode, pack_barcode, jar_code, refill_price, refill_qty, name, cost_price, selling_price, stock_qty,
                    low_stock_threshold, unit, is_quick_item, quick_button_color, category, pcs_per_pack, bulk_cost_price, full_pack_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                SAMPLE_PRODUCTS
            )

        await db.commit()
    print(f"[DB] Database initialized and secured at: {DB_PATH}")


async def get_db():
    """FastAPI dependency — yields an aiosqlite connection for each request."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()

