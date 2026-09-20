import type { CartItem, ParkedCart, Product } from '../types'

const STORAGE_KEY = 'pos_cart_svelte'
const PARKED_KEY = 'pos_parked_carts_svelte'

function loadStorage<T>(key: string, fallback: T): T {
  try {
    const data = localStorage.getItem(key)
    return data ? JSON.parse(data) : fallback
  } catch (e) {
    console.error(`Failed to load ${key} from localStorage`, e)
    return fallback
  }
}

function saveStorage(key: string, data: any) {
  try {
    localStorage.setItem(key, JSON.stringify(data))
  } catch (e) {
    console.error(`Failed to save ${key} to localStorage`, e)
  }
}

class CartStore {
  items = $state<CartItem[]>(loadStorage<CartItem[]>(STORAGE_KEY, []))
  parkedCarts = $state<ParkedCart[]>(loadStorage<ParkedCart[]>(PARKED_KEY, []))

  // Derived totals
  subtotal = $derived(
    Number(this.items.reduce((sum, item) => sum + item.subtotal, 0).toFixed(2))
  )

  itemCount = $derived(
    this.items.reduce((sum, item) => sum + (item.unit === 'pc' ? Math.round(item.quantity) : 1), 0)
  )

  totalQuantity = $derived(
    this.items.reduce((sum, item) => sum + item.quantity, 0)
  )

  constructor() {
    // Keep localStorage in sync whenever items or parked change
    $effect.root(() => {
      $effect(() => {
        saveStorage(STORAGE_KEY, this.items)
      })
      $effect(() => {
        saveStorage(PARKED_KEY, this.parkedCarts)
      })
    })
  }

  addItem(
    product: Product,
    quantity: number = 1.0,
    customUnitPrice?: number,
    packLabel?: string | null
  ) {
    const price = customUnitPrice !== undefined ? customUnitPrice : product.selling_price
    const isPiece = product.unit === 'pc'

    // Look for existing item with matching product_id and pack_label
    const existingIndex = this.items.findIndex(
      (item) => item.product_id === product.id && item.pack_label === (packLabel || null)
    )

    if (existingIndex >= 0 && isPiece && !packLabel) {
      // Increment piece quantity
      const existing = this.items[existingIndex]
      const newQty = existing.quantity + quantity
      this.items[existingIndex] = {
        ...existing,
        quantity: newQty,
        subtotal: Number((newQty * existing.unit_price).toFixed(2))
      }
    } else {
      // Add new cart item entry
      const subtotal = Number((quantity * price).toFixed(2))
      const newItem: CartItem = {
        id: `${product.id}-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
        product_id: product.id,
        product_name: product.name,
        quantity,
        unit_price: price,
        cost_price: product.cost_price || 0,
        subtotal,
        unit: product.unit,
        pack_label: packLabel || null
      }
      this.items = [newItem, ...this.items]
    }
  }

  updateQuantity(id: string, newQty: number) {
    if (newQty <= 0) {
      this.removeItem(id)
      return
    }
    const index = this.items.findIndex((item) => item.id === id)
    if (index >= 0) {
      const item = this.items[index]
      this.items[index] = {
        ...item,
        quantity: newQty,
        subtotal: Number((newQty * item.unit_price).toFixed(2))
      }
    }
  }

  removeItem(id: string) {
    this.items = this.items.filter((item) => item.id !== id)
  }

  clearCart() {
    this.items = []
  }

  // Park / Hold Cart flow ("Ate balikan ko lang mamaya")
  parkCurrentCart(note?: string) {
    if (this.items.length === 0) return false

    const parked: ParkedCart = {
      id: `PARK-${Date.now()}-${Math.random().toString(36).substring(2, 5).toUpperCase()}`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      items: [...this.items],
      note: note || `Customer (${this.itemCount} items)`,
      total: this.subtotal
    }

    this.parkedCarts = [parked, ...this.parkedCarts]
    this.items = []
    return true
  }

  restoreParkedCart(parkedId: string) {
    const found = this.parkedCarts.find((p) => p.id === parkedId)
    if (!found) return false

    // If current cart has items, park it first
    if (this.items.length > 0) {
      this.parkCurrentCart('Previous Unsaved Cart')
    }

    this.items = [...found.items]
    this.parkedCarts = this.parkedCarts.filter((p) => p.id !== parkedId)
    return true
  }

  deleteParkedCart(parkedId: string) {
    this.parkedCarts = this.parkedCarts.filter((p) => p.id !== parkedId)
  }
}

export const cart = new CartStore()
