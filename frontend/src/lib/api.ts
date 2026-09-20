import type { Product, CartItem, CustomerDebt, TransactionResult } from '../types'

const BASE_URL = ''

export async function fetchQuickItems(): Promise<Product[]> {
  const res = await fetch(`${BASE_URL}/api/products/quick-items`)
  if (!res.ok) throw new Error('Failed to fetch quick items')
  return res.json()
}

export async function searchProducts(query: string): Promise<Product[]> {
  if (!query.trim()) return []
  const res = await fetch(`${BASE_URL}/api/products/search?q=${encodeURIComponent(query.trim())}`)
  if (!res.ok) throw new Error('Failed to search products')
  return res.json()
}

export async function lookupBarcode(barcode: string): Promise<Product> {
  const res = await fetch(`${BASE_URL}/api/products/barcode/${encodeURIComponent(barcode.trim())}`)
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.detail || `Product not found for barcode: ${barcode}`)
  }
  return res.json()
}

export async function smartScan(code: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/smart-scan?scanned_code=${encodeURIComponent(code.trim())}`, {
    method: 'POST'
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.detail || `Failed to scan code: ${code}`)
  }
  return res.json()
}

export async function submitCheckout(payload: {
  items: CartItem[]
  total_amount: number
  payment_method: 'CASH' | 'GCASH' | 'UTANG'
  amount_tendered: number
  print_receipt: boolean
  customer_name?: string
  phone_number?: string
  notes?: string
  amount_paid_now?: number
}): Promise<TransactionResult> {
  const res = await fetch(`${BASE_URL}/api/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({}))
    throw new Error(error.detail || 'Checkout failed')
  }
  return res.json()
}

export async function fetchDebtCustomers(): Promise<CustomerDebt[]> {
  const res = await fetch(`${BASE_URL}/api/debts/customers`)
  if (!res.ok) return []
  return res.json()
}

export async function printReceipt(receiptText: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE_URL}/api/printer/print-receipt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ receipt_text: receiptText })
  })
  return res.json()
}

export async function fetchDailyReport(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/reports/daily`)
  if (!res.ok) return null
  return res.json()
}
