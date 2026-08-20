"""
Sari-Sari Store POS — Cloud Synchronization & Backup Router
============================================================
Handles data export, backup download/restore, and cloud synchronization
between the offline-first local .exe POS and the remote cloud admin portal.
"""

import os
import sys
import json
import httpx
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from app.database import get_db, DB_PATH

router = APIRouter(prefix="/api/sync", tags=["Cloud Sync"])


@router.get("/status")
async def get_sync_status(db=Depends(get_db)):
    """Get local database size, transaction counts, and cloud sync status."""
    db_size = 0
    if os.path.exists(DB_PATH):
        db_size = os.path.getsize(DB_PATH)

    cursor = await db.execute("SELECT COUNT(*) FROM products")
    product_count = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT COUNT(*) FROM transactions")
    txn_count = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT COUNT(*) FROM customer_debts WHERE total_debt > 0")
    debt_count = (await cursor.fetchone())[0]

    cursor = await db.execute("SELECT value FROM admin_settings WHERE key = 'cloud_sync_endpoint'")
    endpoint_row = await cursor.fetchone()
    endpoint = endpoint_row[0] if endpoint_row else ""

    cursor = await db.execute("SELECT value FROM admin_settings WHERE key = 'last_cloud_sync'")
    last_sync_row = await cursor.fetchone()
    last_sync = last_sync_row[0] if last_sync_row else "Never"

    return {
        "database_file": str(DB_PATH),
        "database_size_kb": round(db_size / 1024, 2),
        "total_products": product_count,
        "total_transactions": txn_count,
        "active_debts": debt_count,
        "cloud_sync_endpoint": endpoint,
        "last_sync": last_sync
    }


@router.get("/export-json")
async def export_database_json(db=Depends(get_db)):
    """Export all store data to a portable JSON backup payload."""
    payload = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "tables": {}
    }

    tables = ["products", "transactions", "transaction_items", "customer_debts", "debt_transactions", "gcash_transactions", "admin_settings"]
    for tbl in tables:
        try:
            cursor = await db.execute(f"SELECT * FROM {tbl}")
            rows = await cursor.fetchall()
            payload["tables"][tbl] = [dict(r) for r in rows]
        except Exception:
            payload["tables"][tbl] = []

    return payload


@router.get("/download-db")
async def download_sqlite_db():
    """Download the raw SQLite database file for 1-click physical backup."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Database file not found.")

    filename = f"store_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return FileResponse(
        path=str(DB_PATH),
        filename=filename,
        media_type="application/x-sqlite3"
    )


@router.post("/push-to-cloud")
async def push_to_cloud(db=Depends(get_db)):
    """
    Push local database snapshot to the configured Cloud Web Portal.
    Allows store owner to view real-time sales and reports on their phone.
    """
    cursor = await db.execute("SELECT value FROM admin_settings WHERE key = 'cloud_sync_endpoint'")
    endpoint_row = await cursor.fetchone()
    endpoint = endpoint_row[0] if endpoint_row else None

    cursor = await db.execute("SELECT value FROM admin_settings WHERE key = 'cloud_api_key'")
    key_row = await cursor.fetchone()
    api_key = key_row[0] if key_row else ""

    if not endpoint or not endpoint.strip():
        raise HTTPException(status_code=400, detail="Cloud Sync Endpoint URL is not configured in Admin Settings.")

    # Prepare export payload
    export_data = await export_database_json(db=db)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else ""
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint.strip(), json=export_data, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Cloud server returned error: {resp.text}")

        # Update last sync timestamp
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("INSERT OR REPLACE INTO admin_settings (key, value) VALUES ('last_cloud_sync', ?)", (now_str,))
        await db.commit()

        return {"success": True, "message": f"Successfully synced with cloud portal at {now_str}"}

    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Failed to connect to cloud endpoint: {str(e)}")
