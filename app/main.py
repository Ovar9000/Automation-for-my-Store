"""
Sari-Sari Store POS — FastAPI Application Entry Point
=======================================================
Mounts static files, registers Jinja2 templates, includes all API routers,
and initializes the database on startup.

Run with: python run.py  (or: uvicorn app.main:app --reload)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.database import init_db
from app.routers import cashier, gcash, inventory, reports, printer


# ─── Paths ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


# ─── Lifespan: runs on startup and shutdown ──────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    await init_db()
    print("[APP] Sari-Sari POS system is ready!")
    yield
    print("[APP] Shutting down...")


# ─── Create FastAPI app ──────────────────────────────────────────────
app = FastAPI(
    title="Sari-Sari Store POS",
    description="Local-first POS system for Philippine sari-sari stores",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Mount static files (CSS, JS, assets) ────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ─── Jinja2 templates ────────────────────────────────────────────────
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ═══════════════════════════════════════════════════════════════
# PAGE ROUTES (serve HTML templates)
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def cashier_page(request: Request):
    """Cashier terminal — the main POS interface."""
    return templates.TemplateResponse(request=request, name="cashier.html")


@app.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page."""
    return templates.TemplateResponse(request=request, name="admin/login.html")


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    """Admin dashboard — overview of today's performance."""
    return templates.TemplateResponse(request=request, name="admin/dashboard.html")


@app.get("/admin/inventory", response_class=HTMLResponse)
async def admin_inventory_page(request: Request):
    """Admin inventory management page."""
    return templates.TemplateResponse(request=request, name="admin/inventory.html")


@app.get("/admin/reports", response_class=HTMLResponse)
async def admin_reports_page(request: Request):
    """Admin reports and analytics page."""
    return templates.TemplateResponse(request=request, name="admin/reports.html")


@app.get("/admin/gcash", response_class=HTMLResponse)
async def admin_gcash_page(request: Request):
    """Admin GCash transactions list page."""
    return templates.TemplateResponse(request=request, name="admin/gcash.html")


# ═══════════════════════════════════════════════════════════════
# API ROUTERS (JSON endpoints)
# ═══════════════════════════════════════════════════════════════

app.include_router(cashier.router, prefix="/api", tags=["Cashier"])
app.include_router(gcash.router, prefix="/api", tags=["GCash"])
app.include_router(inventory.router, prefix="/api", tags=["Inventory"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(printer.router, prefix="/api", tags=["Printer"])
