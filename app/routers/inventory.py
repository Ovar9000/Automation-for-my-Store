"""
Sari-Sari Store POS — Inventory & Admin Router
================================================
Handles inventory management and admin settings:
  - Full CRUD for products (Create, Read, Update, Delete)
  - Low-stock alerts
  - Admin password login
  - Admin settings management (key-value store)

IMPORTANT — Route Ordering:
  FastAPI matches routes top-to-bottom. Path parameter routes like
  /products/{id} would swallow literal paths like /products/search
  if defined first. Therefore, ALL literal-path routes MUST be defined
  BEFORE the /products/{id} route:
    1. /products/barcode/{barcode}  (in cashier.py — no conflict here)
    2. /products/search             (defined here but actually in cashier.py)
    3. /products/quick              (defined here but actually in cashier.py)
    4. /products/low-stock          ← MUST be before {id}
    5. /products/{id}               ← LAST product sub-route
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db
from app.models import ProductCreate, ProductUpdate, AdminLoginRequest, SettingUpdate

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# PRODUCT LISTING & FILTERING
# ═══════════════════════════════════════════════════════════════

@router.get("/products")
async def list_products(
    category: str = Query(None, description="Filter by product category"),
    search: str = Query(None, description="Search by product name"),
    db=Depends(get_db)
):
    """
    List ALL products with optional filtering.

    Business logic:
    - Returns all products by default (for the admin inventory grid).
    - Supports filtering by category (exact match) and/or search (LIKE match).
    - Adds computed field `is_low_stock` for each product so the frontend
      can highlight items that need restocking.
    - Sorted alphabetically by name for consistent display.

    Query params:
    - ?category=Beverages — exact category filter
    - ?search=candy — name LIKE filter
    - Can combine both: ?category=Snacks&search=candy
    """

    # ── Build dynamic WHERE clause ───────────────────────────────────
    # Start with base query, add conditions based on provided params
    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)

    if search:
        conditions.append("name LIKE ?")
        params.append(f"%{search}%")

    # ── Construct the full SQL query ─────────────────────────────────
    query = "SELECT * FROM products"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY name"

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    # ── Convert rows to dicts with computed is_low_stock ─────────────
    products = []
    for row in rows:
        product = dict(row)
        # Computed field: frontend shows a red badge when stock is below threshold
        product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
        products.append(product)

    return products


@router.get("/products/low-stock")
async def get_low_stock_products(db=Depends(get_db)):
    """
    Get products where current stock is below the low-stock threshold.

    Business logic:
    - This powers the "Low Stock Alerts" badge on the admin dashboard.
    - A product is considered low-stock when stock_qty < low_stock_threshold.
    - Each product has its own threshold (rice might be 10kg, candy might be 50pcs).
    - Sorted by the "urgency" — smallest stock relative to threshold first.
    """
    cursor = await db.execute(
        """SELECT * FROM products
           WHERE stock_qty < low_stock_threshold
           ORDER BY (stock_qty - low_stock_threshold) ASC"""
    )
    rows = await cursor.fetchall()

    products = []
    for row in rows:
        product = dict(row)
        product["is_low_stock"] = True  # By definition, all results are low-stock
        products.append(product)

    return products


# ═══════════════════════════════════════════════════════════════
# SINGLE PRODUCT CRUD
# ═══════════════════════════════════════════════════════════════
# NOTE: /products/{id} is defined AFTER /products/low-stock above
# to prevent FastAPI from interpreting "low-stock" as an {id} value.

@router.get("/products/{id}")
async def get_product(id: int, db=Depends(get_db)):
    """
    Get a single product by its database ID.

    Business logic:
    - Used by the admin "Edit Product" form to pre-fill current values.
    - Returns 404 if the product was deleted (could happen if admin
      deletes while another tab has the edit form open).
    """
    cursor = await db.execute(
        "SELECT * FROM products WHERE id = ?",
        (id,)
    )
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Product with id {id} not found."
        )

    product = dict(row)
    product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
    return product


@router.post("/products")
async def create_product(data: ProductCreate, db=Depends(get_db)):
    """
    Create a new product in the inventory.

    Business logic:
    - Validates that the product name is not empty.
    - If a barcode is provided, checks for uniqueness (two products
      can't share the same barcode — that would cause scanner confusion).
    - is_quick_item is stored as INTEGER (0/1) in SQLite, so we convert
      the boolean from the Pydantic model.
    - Returns the newly created product with its auto-generated ID.
    """

    # ── Validate product name ────────────────────────────────────────
    if not data.name or not data.name.strip():
        raise HTTPException(
            status_code=400,
            detail="Product name cannot be empty."
        )

    # ── Check barcode uniqueness if provided ─────────────────────────
    if data.barcode:
        cursor = await db.execute(
            "SELECT id FROM products WHERE barcode = ?",
            (data.barcode,)
        )
        existing = await cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A product with barcode '{data.barcode}' already exists (id: {existing['id']})."
            )

    # ── Insert the new product ───────────────────────────────────────
    cursor = await db.execute(
        """INSERT INTO products
           (barcode, name, cost_price, selling_price, stock_qty, low_stock_threshold,
            unit, is_quick_item, quick_button_color, category, half_dozen_price, dozen_price,
            pcs_per_pack, bulk_cost_price, full_pack_price)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.barcode,
            data.name.strip(),
            round(data.cost_price, 2),
            round(data.selling_price, 2),
            round(data.stock_qty, 2),
            round(data.low_stock_threshold, 2),
            data.unit,
            1 if data.is_quick_item else 0,     # Bool → INTEGER for SQLite
            data.quick_button_color,
            data.category,
            round(data.half_dozen_price, 2) if data.half_dozen_price is not None else None,
            round(data.dozen_price, 2) if data.dozen_price is not None else None,
            data.pcs_per_pack or 1,
            round(data.bulk_cost_price, 2) if data.bulk_cost_price is not None else None,
            round(data.full_pack_price, 2) if data.full_pack_price is not None else None,
        )
    )
    product_id = cursor.lastrowid
    await db.commit()

    # ── Fetch and return the created product ─────────────────────────
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = await cursor.fetchone()
    product = dict(row)
    product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]

    return product


@router.put("/products/{id}")
async def update_product(id: int, data: ProductUpdate, db=Depends(get_db)):
    """
    Update an existing product (partial update — only update provided fields).

    Business logic:
    - Uses Pydantic's model_dump(exclude_unset=True) to get ONLY the fields
      the client explicitly sent. This prevents accidentally zeroing out
      fields the client didn't intend to change.
    - Builds a dynamic UPDATE SET clause from the provided fields.
    - If barcode is being changed, checks uniqueness against other products.
    - Timestamps updated_at for change tracking.
    """

    # ── Verify product exists ────────────────────────────────────────
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (id,))
    existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"Product with id {id} not found."
        )

    # ── Get only the fields that were explicitly set in the request ──
    # exclude_unset=True is the key: it ignores fields not present in JSON
    update_data = data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update."
        )

    # ── Handle is_quick_item boolean → integer conversion ────────────
    if "is_quick_item" in update_data:
        update_data["is_quick_item"] = 1 if update_data["is_quick_item"] else 0

    # ── Round money/quantity values to 2 decimal places ──────────────
    money_fields = ["cost_price", "selling_price", "stock_qty", "low_stock_threshold"]
    for field in money_fields:
        if field in update_data and update_data[field] is not None:
            update_data[field] = round(update_data[field], 2)

    # ── Check barcode uniqueness if barcode is being changed ─────────
    if "barcode" in update_data and update_data["barcode"]:
        cursor = await db.execute(
            "SELECT id FROM products WHERE barcode = ? AND id != ?",
            (update_data["barcode"], id)
        )
        conflict = await cursor.fetchone()
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Another product (id: {conflict['id']}) already has barcode '{update_data['barcode']}'."
            )

    # ── Build dynamic UPDATE query ───────────────────────────────────
    # Always update the updated_at timestamp
    set_clauses = [f"{key} = ?" for key in update_data.keys()]
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

    values = list(update_data.values())
    values.append(id)  # For the WHERE clause

    query = f"UPDATE products SET {', '.join(set_clauses)} WHERE id = ?"

    await db.execute(query, values)
    await db.commit()

    # ── Fetch and return the updated product ─────────────────────────
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (id,))
    row = await cursor.fetchone()
    product = dict(row)
    product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]

    return product


@router.delete("/products/{id}")
async def delete_product(id: int, db=Depends(get_db)):
    """
    Delete a product from the inventory.

    Business logic:
    - Checks the product exists before attempting deletion.
    - The ON DELETE SET NULL foreign key on transaction_items means
      past sales referencing this product will keep their product_name
      snapshot but set product_id to NULL.
    - This is intentional: we never want to lose sales history.
    """

    # ── Verify product exists ────────────────────────────────────────
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (id,))
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Product with id {id} not found."
        )

    product_name = dict(row)["name"]

    # ── Delete the product ───────────────────────────────────────────
    await db.execute("DELETE FROM products WHERE id = ?", (id,))
    await db.commit()

    return {
        "success": True,
        "message": f"Product '{product_name}' (id: {id}) deleted successfully.",
    }


# ═══════════════════════════════════════════════════════════════
# ADMIN AUTHENTICATION & SETTINGS
# ═══════════════════════════════════════════════════════════════

@router.post("/admin/login")
async def admin_login(data: AdminLoginRequest, db=Depends(get_db)):
    """
    Authenticate admin with a simple password check.

    Business logic:
    - Compares the provided password against the stored admin_password
      in the admin_settings table.
    - This is a simple password gate — no JWT or sessions.
    - The frontend stores a "logged in" flag in localStorage.
    - Default password is 'admin123' — the admin should change it immediately.

    Security note: This is NOT production-grade auth. It's a local POS
    system on a trusted network with a single admin user.
    """
    # ── Fetch the stored admin password ──────────────────────────────
    cursor = await db.execute(
        "SELECT value FROM admin_settings WHERE key = 'admin_password'"
    )
    row = await cursor.fetchone()

    if not row:
        # No password set in DB — this shouldn't happen with default seeding
        raise HTTPException(
            status_code=500,
            detail="Admin password not configured in database."
        )

    stored_password = row["value"]

    # ── Compare passwords (plain text — local POS, not a web app) ────
    if data.password == stored_password:
        return {
            "success": True,
            "message": "Login successful.",
        }
    else:
        return {
            "success": False,
            "message": "Incorrect password.",
        }


@router.get("/admin/settings")
async def get_admin_settings(db=Depends(get_db)):
    """
    Get all admin settings as a key-value dictionary.

    Business logic:
    - Returns settings like store_name, store_address, gcash_fee, etc.
    - The admin dashboard settings page uses this to populate form fields.
    - Password is included (the settings page needs it for the "change password" field).
    """
    cursor = await db.execute("SELECT key, value FROM admin_settings")
    rows = await cursor.fetchall()

    # Convert to a flat dict: {"store_name": "My Store", "admin_password": "...", ...}
    settings = {}
    for row in rows:
        r = dict(row)
        settings[r["key"]] = r["value"]

    return settings


@router.put("/admin/settings")
async def update_admin_setting(data: SettingUpdate, db=Depends(get_db)):
    """
    Update a single admin setting by key.

    Business logic:
    - Uses INSERT OR REPLACE to handle both new and existing keys.
    - The frontend sends one key-value pair at a time (e.g., updating store name).
    - Validates that key is not empty.
    """

    if not data.key or not data.key.strip():
        raise HTTPException(
            status_code=400,
            detail="Setting key cannot be empty."
        )

    # ── Upsert the setting ───────────────────────────────────────────
    # INSERT OR REPLACE ensures the key exists or is created
    await db.execute(
        "INSERT OR REPLACE INTO admin_settings (key, value) VALUES (?, ?)",
        (data.key.strip(), data.value)
    )
    await db.commit()

    return {
        "success": True,
        "message": f"Setting '{data.key}' updated successfully.",
        "key": data.key.strip(),
        "value": data.value,
    }
