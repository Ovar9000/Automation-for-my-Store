"""
Sari-Sari Store POS — Supabase Cloud Sync Engine
=================================================
Provides direct cloud backup and synchronization to Supabase:
1. Uploads timestamped SQLite backups to Supabase Storage.
2. Checks connection health to the configured Supabase project.
3. Syncs store records to Supabase tables.

Reads configuration from .env.local or admin_settings table.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx
from app.database import DB_PATH

# Root directory of the POS system
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ─── Read environment variables from .env.local if present ────────────
ENV_LOCAL_PATH = BASE_DIR / ".env.local"

def load_env_local() -> Dict[str, str]:
    """Parse key=value pairs from .env.local without requiring external packages."""
    env_vars = {}
    if ENV_LOCAL_PATH.exists():
        try:
            with open(ENV_LOCAL_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip("'\"")
        except Exception as e:
            print(f"[Supabase] Warning reading .env.local: {e}")
    return env_vars


class SupabaseSyncService:
    def __init__(self):
        env_vars = load_env_local()
        self.url = (
            os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
            or env_vars.get("NEXT_PUBLIC_SUPABASE_URL")
            or "https://dveufoeavxegvcgityax.supabase.co"
        ).rstrip("/")
        self.key = (
            os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
            or env_vars.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
            or "sb_publishable_HRsrNqo7SMk_H90617TQ3Q_VJqZR5KC"
        )
        self.bucket = (
            os.environ.get("SUPABASE_BUCKET")
            or env_vars.get("SUPABASE_BUCKET")
            or "store-backups"
        )

    def update_credentials(self, url: str, key: str, bucket: str = "store-backups"):
        """Dynamically update service credentials."""
        self.url = url.rstrip("/")
        self.key = key
        self.bucket = bucket

    def _headers(self, content_type: Optional[str] = "application/json") -> Dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    async def test_connection(self) -> Dict[str, Any]:
        """
        Verify connection to the Supabase project.
        Checks both the Auth health and Storage bucket accessibility.
        """
        if not self.url or not self.key:
            return {"connected": False, "error": "Supabase URL or API Key is missing."}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. Test Auth service health
                auth_res = await client.get(
                    f"{self.url}/auth/v1/health",
                    headers=self._headers()
                )
                auth_ok = auth_res.status_code == 200

                # 2. Check Storage service
                storage_res = await client.get(
                    f"{self.url}/storage/v1/bucket",
                    headers=self._headers()
                )
                storage_ok = storage_res.status_code == 200

                # Check if target bucket exists
                bucket_exists = False
                if storage_ok:
                    try:
                        buckets = storage_res.json()
                        bucket_exists = any(b.get("id") == self.bucket for b in buckets)
                    except Exception:
                        pass

                return {
                    "connected": auth_ok or storage_ok,
                    "supabase_url": self.url,
                    "auth_service": "online" if auth_ok else "unreachable",
                    "storage_service": "online" if storage_ok else "unreachable",
                    "bucket_name": self.bucket,
                    "bucket_exists": bucket_exists,
                }
        except Exception as e:
            return {
                "connected": False,
                "supabase_url": self.url,
                "error": str(e)
            }

    async def upload_db_backup(self, custom_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Upload the SQLite store.db file directly to Supabase Storage.
        Each backup is saved with a timestamped filename for full version history.
        """
        target_db = custom_path or DB_PATH
        if not target_db.exists():
            return {"success": False, "error": f"Database file not found at {target_db}"}

        filename = f"store_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        file_size_bytes = os.path.getsize(target_db)

        try:
            with open(target_db, "rb") as f:
                file_bytes = f.read()

            upload_url = f"{self.url}/storage/v1/object/{self.bucket}/{filename}"
            headers = self._headers(content_type="application/x-sqlite3")
            # x-upsert header allows overwriting if duplicate name
            headers["x-upsert"] = "true"

            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(upload_url, headers=headers, content=file_bytes)

                if res.status_code in (200, 201):
                    return {
                        "success": True,
                        "filename": filename,
                        "size_kb": round(file_size_bytes / 1024, 2),
                        "bucket": self.bucket,
                        "uploaded_at": datetime.now().isoformat(),
                        "url": f"{self.url}/storage/v1/object/public/{self.bucket}/{filename}",
                        "message": f"Successfully uploaded {filename} ({round(file_size_bytes / 1024, 2)} KB) to Supabase Storage."
                    }
                else:
                    err_msg = res.text
                    if "Bucket not found" in err_msg or res.status_code == 404:
                        return {
                            "success": False,
                            "error": f"Bucket '{self.bucket}' does not exist in your Supabase project. Please create the bucket '{self.bucket}' in your Supabase Storage dashboard or run the provided supabase_schema.sql script.",
                            "status_code": res.status_code
                        }
                    elif "row-level security" in err_msg.lower() or res.status_code == 403:
                        return {
                            "success": False,
                            "error": f"Permission denied on bucket '{self.bucket}'. Please ensure your bucket allows public/insert policies via supabase_schema.sql.",
                            "status_code": res.status_code
                        }
                    return {
                        "success": False,
                        "error": f"Supabase Storage error ({res.status_code}): {err_msg}",
                        "status_code": res.status_code
                    }

        except Exception as e:
            return {"success": False, "error": f"Upload failed: {str(e)}"}

    async def list_backups(self) -> List[Dict[str, Any]]:
        """List backup files stored in the Supabase Storage bucket."""
        try:
            url = f"{self.url}/storage/v1/object/list/{self.bucket}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    url,
                    headers=self._headers(),
                    json={"prefix": "store_backup_", "limit": 50, "sortBy": {"column": "created_at", "order": "desc"}}
                )
                if res.status_code == 200:
                    return res.json()
                return []
        except Exception:
            return []


# Global singleton service
supabase_service = SupabaseSyncService()
