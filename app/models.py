"""
Sari-Sari Store POS — Pydantic Models
=======================================
Request/response schemas for all API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# PRODUCT MODELS
# ═══════════════════════════════════════════════════════════════

class ProductCreate(BaseModel):
    """Schema for creating a new product."""
    barcode: Optional[str] = None
    name: str
    cost_price: float = 0
    selling_price: float = 0
    stock_qty: float = 0
    low_stock_threshold: float = 5
    unit: str = "pc"                    # 'pc', 'kg', 'L', 'ml'
    is_quick_item: bool = False
    quick_button_color: str = "#10b981"
    category: str = "General"


class ProductUpdate(BaseModel):
    """Schema for updating a product (all fields optional)."""
    barcode: Optional[str] = None
    name: Optional[str] = None
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    stock_qty: Optional[float] = None
    low_stock_threshold: Optional[float] = None
    unit: Optional[str] = None
    is_quick_item: Optional[bool] = None
    quick_button_color: Optional[str] = None
    category: Optional[str] = None


class ProductResponse(BaseModel):
    """Schema for a product in API responses."""
    id: int
    barcode: Optional[str]
    name: str
    cost_price: float
    selling_price: float
    stock_qty: float
    low_stock_threshold: float
    unit: str
    is_quick_item: bool
    quick_button_color: str
    category: str
    is_low_stock: bool = False          # Computed field


# ═══════════════════════════════════════════════════════════════
# CART & TRANSACTION MODELS
# ═══════════════════════════════════════════════════════════════

class CartItem(BaseModel):
    """A single item in the cashier's cart."""
    product_id: int
    product_name: str
    quantity: float = 1.0               # Decimal for weighted items
    unit_price: float
    cost_price: float = 0
    subtotal: float                     # quantity * unit_price


class TransactionCreate(BaseModel):
    """Schema for submitting a completed sale."""
    items: List[CartItem]
    total_amount: float
    payment_method: str = "CASH"        # 'CASH' or 'GCASH'
    amount_tendered: float = 0          # Cash given by customer
    print_receipt: bool = False


class TransactionResponse(BaseModel):
    """Schema for a completed transaction."""
    id: int
    transaction_type: str
    total_amount: float
    total_cost: float
    payment_method: str
    change: float = 0
    receipt_printed: bool
    created_at: str


# ═══════════════════════════════════════════════════════════════
# GCASH MODELS
# ═══════════════════════════════════════════════════════════════

class GCashCalculateRequest(BaseModel):
    """Request schema for GCash fee calculation."""
    amount: float                       # Amount entered by cashier
    flow_type: str = "A"                # 'A' = principal input, 'B' = total input


class GCashCalculateResponse(BaseModel):
    """Response with calculated GCash fee breakdown."""
    flow_type: str
    input_amount: float
    principal_amount: float             # Amount to send via GCash
    fee: float                          # Store's fee
    total_collected: float              # Total cash from customer


class GCashTransactRequest(BaseModel):
    """Request to record a GCash transaction."""
    flow_type: str
    input_amount: float
    principal_amount: float
    fee: float
    total_collected: float
    transaction_type: str = "GCASH_IN"  # 'GCASH_IN' or 'GCASH_OUT'


# ═══════════════════════════════════════════════════════════════
# REPORT MODELS
# ═══════════════════════════════════════════════════════════════

class DailyReportResponse(BaseModel):
    """Daily sales summary."""
    date: str
    total_sales: float                  # Gross revenue from sales
    total_cost: float                   # Total COGS
    net_profit: float                   # Sales - COGS
    total_gcash_fees: float             # GCash fees collected
    transaction_count: int
    gcash_transaction_count: int


class MonthlyReportResponse(BaseModel):
    """Monthly breakdown for a single month."""
    year: int
    month: int
    total_sales: float
    total_cost: float
    net_profit: float
    total_gcash_fees: float
    transaction_count: int


class TopProductResponse(BaseModel):
    """A product ranked by sales volume or profit."""
    product_id: int
    product_name: str
    total_qty_sold: float
    total_revenue: float
    total_cost: float
    total_profit: float


# ═══════════════════════════════════════════════════════════════
# ADMIN MODELS
# ═══════════════════════════════════════════════════════════════

class AdminLoginRequest(BaseModel):
    """Admin login payload."""
    password: str


class SettingUpdate(BaseModel):
    """Update a single admin setting."""
    key: str
    value: str
