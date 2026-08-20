"""
Sari-Sari Store POS — Inventory & Admin Router
================================================
Handles inventory management, pack barcodes, jar QR refills, and admin authentication:
  - Full CRUD for products (with pack barcode & jar code support)
  - Low-stock alerts
  - Secure PBKDF2 admin login with session tokens
  - Jar QR and Mother-Pack thermal label generation
  - Admin settings management
"""

import secrets
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from app.database import get_db, hash_password, verify_password
from app.models import ProductCreate, ProductUpdate, AdminLoginRequest, SettingUpdate, AdminAuthResponse

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# PRODUCT LISTING & FILTERING
# ═══════════════════════════════════════════════════════════════

@router.get("/products")
async def list_products(
    category: str = Query(None, description="Filter by product category"),
    search: str = Query(None, description="Search by product name, barcode, or jar code"),
    db=Depends(get_db)
):
    """List ALL products with optional category and search filtering."""
    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)

    if search:
        conditions.append("(name LIKE ? OR barcode LIKE ? OR pack_barcode LIKE ? OR jar_code LIKE ?)")
        term = f"%{search.strip()}%"
        params.extend([term, term, term, term])

    query = "SELECT * FROM products"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY name"

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    products = []
    for row in rows:
        product = dict(row)
        product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
        products.append(product)

    return products


@router.get("/products/low-stock")
async def get_low_stock_products(db=Depends(get_db)):
    """Get products where current stock is below threshold."""
    cursor = await db.execute(
        """SELECT * FROM products
           WHERE stock_qty < low_stock_threshold
           ORDER BY (stock_qty - low_stock_threshold) ASC"""
    )
    rows = await cursor.fetchall()

    products = []
    for row in rows:
        product = dict(row)
        product["is_low_stock"] = True
        products.append(product)

    return products


# ═══════════════════════════════════════════════════════════════
# SINGLE PRODUCT CRUD
# ═══════════════════════════════════════════════════════════════

@router.get("/products/{id}")
async def get_product(id: int, db=Depends(get_db)):
    """Get a single product by ID."""
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (id,))
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Product with id {id} not found.")

    product = dict(row)
    product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
    return product


@router.post("/products")
async def create_product(data: ProductCreate, db=Depends(get_db)):
    """Create a new product with dual barcode and jar refill QR support."""
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Product name cannot be empty.")

    # Check barcode uniqueness
    if data.barcode:
        cursor = await db.execute("SELECT id FROM products WHERE barcode = ?", (data.barcode,))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"A product with barcode '{data.barcode}' already exists.")

    if data.pack_barcode:
        cursor = await db.execute("SELECT id FROM products WHERE pack_barcode = ?", (data.pack_barcode,))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"A product with pack barcode '{data.pack_barcode}' already exists.")

    if data.jar_code:
        cursor = await db.execute("SELECT id FROM products WHERE jar_code = ?", (data.jar_code,))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"A product with Jar QR Code '{data.jar_code}' already exists.")

    cursor = await db.execute(
        """INSERT INTO products
           (barcode, pack_barcode, jar_code, refill_price, refill_qty, name, cost_price, selling_price, stock_qty, low_stock_threshold,
            unit, is_quick_item, quick_button_color, category, half_dozen_price, dozen_price,
            pcs_per_pack, bulk_cost_price, full_pack_price)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.barcode,
            data.pack_barcode,
            data.jar_code,
            round(data.refill_price, 2) if data.refill_price is not None else None,
            round(data.refill_qty, 2) if data.refill_qty is not None else 1.0,
            data.name.strip(),
            round(data.cost_price, 2),
            round(data.selling_price, 2),
            round(data.stock_qty, 2),
            round(data.low_stock_threshold, 2),
            data.unit,
            1 if data.is_quick_item else 0,
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

    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = await cursor.fetchone()
    product = dict(row)
    product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
    return product


@router.put("/products/{id}")
async def update_product(id: int, data: ProductUpdate, db=Depends(get_db)):
    """Update an existing product."""
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (id,))
    existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail=f"Product with id {id} not found.")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    if "is_quick_item" in update_data:
        update_data["is_quick_item"] = 1 if update_data["is_quick_item"] else 0

    money_fields = ["cost_price", "selling_price", "stock_qty", "low_stock_threshold", "refill_price", "refill_qty", "bulk_cost_price", "full_pack_price"]
    for field in money_fields:
        if field in update_data and update_data[field] is not None:
            update_data[field] = round(update_data[field], 2)

    # Check barcode conflicts
    if "barcode" in update_data and update_data["barcode"]:
        cursor = await db.execute("SELECT id FROM products WHERE barcode = ? AND id != ?", (update_data["barcode"], id))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"Barcode '{update_data['barcode']}' is already used by another product.")

    if "pack_barcode" in update_data and update_data["pack_barcode"]:
        cursor = await db.execute("SELECT id FROM products WHERE pack_barcode = ? AND id != ?", (update_data["pack_barcode"], id))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"Pack barcode '{update_data['pack_barcode']}' is already used.")

    if "jar_code" in update_data and update_data["jar_code"]:
        cursor = await db.execute("SELECT id FROM products WHERE jar_code = ? AND id != ?", (update_data["jar_code"], id))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"Jar QR '{update_data['jar_code']}' is already used.")

    set_clauses = [f"{key} = ?" for key in update_data.keys()]
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values = list(update_data.values())
    values.append(id)

    query = f"UPDATE products SET {', '.join(set_clauses)} WHERE id = ?"
    await db.execute(query, values)
    await db.commit()

    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (id,))
    row = await cursor.fetchone()
    product = dict(row)
    product["is_low_stock"] = product["stock_qty"] < product["low_stock_threshold"]
    return product


@router.delete("/products/{id}")
async def delete_product(id: int, db=Depends(get_db)):
    """Delete a product while preserving historical line items."""
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Product with id {id} not found.")

    product_name = dict(row)["name"]
    await db.execute("DELETE FROM products WHERE id = ?", (id,))
    await db.commit()

    return {"success": True, "message": f"Product '{product_name}' deleted successfully."}


# ═══════════════════════════════════════════════════════════════
# JAR QR & PACK LABEL GENERATOR
# ═══════════════════════════════════════════════════════════════

@router.get("/admin/labels")
async def list_printable_labels(db=Depends(get_db)):
    """
    Get all products configured with Jar QR codes or Mother-Pack barcodes
    for generating 58mm thermal sticker labels.
    """
    cursor = await db.execute(
        """SELECT id, name, category, barcode, pack_barcode, jar_code, refill_price, refill_qty, unit, selling_price, full_pack_price, pcs_per_pack
           FROM products
           ORDER BY category, name"""
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
# ADMIN AUTHENTICATION & SETTINGS
# ═══════════════════════════════════════════════════════════════

@router.post("/admin/login", response_model=AdminAuthResponse)
async def admin_login(data: AdminLoginRequest, db=Depends(get_db)):
    """Authenticate admin with secure password verification and return a session token."""
    cursor = await db.execute("SELECT value FROM admin_settings WHERE key = 'admin_password'")
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="Admin password not configured in database.")

    stored_password = row["value"]

    if verify_password(data.password, stored_password):
        # Generate session token valid for 7 days
        token = secrets.token_urlsafe(32)
        await db.execute(
            "INSERT INTO admin_sessions (token, expires_at) VALUES (?, datetime('now', '+7 days'))",
            (token,)
        )
        await db.commit()

        return {
            "success": True,
            "token": token,
            "message": "Login successful."
        }
    else:
        return {
            "success": False,
            "token": None,
            "message": "Incorrect password."
        }


@router.get("/admin/settings")
async def get_admin_settings(db=Depends(get_db)):
    """Get all admin settings."""
    cursor = await db.execute("SELECT key, value FROM admin_settings")
    rows = await cursor.fetchall()
    settings = {}
    for row in rows:
        r = dict(row)
        if r["key"] == "admin_password":
            settings["admin_password_set"] = "1"
        else:
            settings[r["key"]] = r["value"]
    return settings


@router.put("/admin/settings")
async def update_admin_setting(data: SettingUpdate, db=Depends(get_db)):
    """Update an admin setting. Hashes admin_password if being changed."""
    if not data.key or not data.key.strip():
        raise HTTPException(status_code=400, detail="Setting key cannot be empty.")

    key = data.key.strip()
    val = data.value

    # If updating password, hash it securely
    if key == "admin_password":
        if not val or len(val) < 4:
            raise HTTPException(status_code=400, detail="Password must be at least 4 characters long.")
        val = hash_password(val)

    await db.execute(
        "INSERT OR REPLACE INTO admin_settings (key, value) VALUES (?, ?)",
        (key, val)
    )
    await db.commit()

    return {
        "success": True,
        "message": f"Setting '{key}' updated successfully.",
        "key": key,
        "value": "***" if key == "admin_password" else val
    }
