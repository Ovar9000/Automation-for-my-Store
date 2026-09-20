export interface Product {
  id: number
  barcode?: string | null
  pack_barcode?: string | null
  jar_code?: string | null
  refill_price?: number | null
  refill_qty?: number | null
  name: string
  cost_price: number
  selling_price: number
  stock_qty: number
  low_stock_threshold: number
  unit: string // 'pc', 'kg', 'g', 'L', 'ml'
  is_quick_item: boolean
  quick_button_color: string
  category: string
  half_dozen_price?: number | null
  dozen_price?: number | null
  pcs_per_pack?: number | null
  bulk_cost_price?: number | null
  full_pack_price?: number | null
  is_low_stock?: boolean
  scan_type?: 'unit' | 'mother_pack' | 'jar_refill' | 'scale_weight' | 'scale_price'
  default_qty?: number
  default_price?: number
  default_subtotal?: number
  pack_label?: string | null
}

export interface CartItem {
  id: string // unique UUID for cart item
  product_id: number
  product_name: string
  quantity: number
  unit_price: number
  cost_price: number
  subtotal: number
  unit: string
  pack_label?: string | null
}

export interface ParkedCart {
  id: string
  timestamp: string
  items: CartItem[]
  note?: string
  total: number
}

export interface CustomerDebt {
  id: number
  customer_name: string
  phone_number?: string | null
  total_debt: number
  last_transaction_date?: string | null
  created_at?: string
  updated_at?: string
}

export interface DebtTransaction {
  id: number
  debt_id: number
  sale_id?: number | null
  type: string
  amount: number
  balance_after: number
  notes?: string | null
  receipt_number?: string | null
  created_at: string
}

export interface TransactionResult {
  id: number
  receipt_number: string
  total_amount: number
  amount_tendered: number
  change?: number
  change_amount?: number
  payment_method: string
  customer_name?: string | null
  created_at: string
  items: CartItem[]
}
