<script lang="ts">
  import { searchProducts, lookupBarcode } from '../lib/api'
  import { parseScaleBarcode } from '../lib/scanner'
  import type { Product } from '../types'
  import { Search, Barcode, Scale, Loader2, ArrowRight } from 'lucide-svelte'
  import { onMount } from 'svelte'

  interface Props {
    onSelectProduct: (product: Product, quantity?: number, price?: number, label?: string | null) => void
    onRequestWeightModal: (product: Product) => void
  }

  let { onSelectProduct, onRequestWeightModal }: Props = $props()

  let inputEl = $state<HTMLInputElement | null>(null)
  let query = $state('')
  let results = $state<Product[]>([])
  let selectedIndex = $state(-1)
  let isLoading = $state(false)
  let errorMessage = $state('')
  let debounceTimer: any = null

  export function focusInput() {
    inputEl?.focus()
    inputEl?.select()
  }

  export function clear() {
    query = ''
    results = []
    selectedIndex = -1
    errorMessage = ''
  }

  function handleInput() {
    errorMessage = ''
    const val = query.trim()

    if (!val) {
      results = []
      selectedIndex = -1
      return
    }

    // If it's purely digits and >= 8 digits, don't query search API immediately; let Enter handle barcode scan
    if (/^\d{8,}$/.test(val)) {
      results = []
      return
    }

    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(async () => {
      isLoading = true
      try {
        results = await searchProducts(val)
        selectedIndex = results.length > 0 ? 0 : -1
      } catch (e) {
        results = []
      } finally {
        isLoading = false
      }
    }, 180)
  }

  async function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (results.length > 0) {
        selectedIndex = (selectedIndex + 1) % results.length
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (results.length > 0) {
        selectedIndex = (selectedIndex - 1 + results.length) % results.length
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const val = query.trim()
      if (!val) return

      // If a dropdown item is highlighted and we were searching text
      if (results.length > 0 && selectedIndex >= 0 && selectedIndex < results.length) {
        selectProduct(results[selectedIndex])
        return
      }

      // Otherwise treat as barcode / scale barcode lookup
      await processBarcodeOrCode(val)
    } else if (e.key === 'Escape') {
      clear()
    }
  }

  export async function processBarcodeOrCode(code: string) {
    isLoading = true
    errorMessage = ''
    try {
      // Check if it matches an EAN-13 scale barcode (prefix 20/21)
      const scaleInfo = parseScaleBarcode(code)
      const product = await lookupBarcode(code)

      if (scaleInfo.isScaleBarcode && product.scan_type === 'scale_weight') {
        // Automatically add weighed item from scale barcode
        onSelectProduct(
          product,
          product.default_qty || scaleInfo.weightKg || 1,
          product.default_price || product.selling_price,
          product.pack_label || `Scale Weighed (${product.default_qty}kg)`
        )
      } else if (product.scan_type === 'mother_pack') {
        onSelectProduct(
          product,
          product.default_qty || product.pcs_per_pack || 10,
          product.default_price || product.selling_price,
          product.pack_label || `Full-Pack (${product.pcs_per_pack}pcs)`
        )
      } else if (product.scan_type === 'jar_refill') {
        onSelectProduct(
          product,
          product.default_qty || product.refill_qty || 1,
          product.default_price || product.refill_price || product.selling_price,
          product.pack_label || `Jar Refill (${product.refill_qty}${product.unit})`
        )
      } else if (['kg', 'l', 'g'].includes(product.unit.toLowerCase()) && !scaleInfo.isScaleBarcode) {
        // Weighed item without scale barcode -> trigger Dual Weight / Peso Modal!
        onRequestWeightModal(product)
      } else {
        // Standard item
        onSelectProduct(product)
      }

      clear()
    } catch (err: any) {
      errorMessage = err.message || `No product found for "${code}"`
    } finally {
      isLoading = false
    }
  }

  function selectProduct(product: Product) {
    if (['kg', 'l', 'g'].includes(product.unit.toLowerCase())) {
      onRequestWeightModal(product)
    } else {
      onSelectProduct(product)
    }
    clear()
    focusInput()
  }

  onMount(() => {
    focusInput()
  })
</script>

<div class="relative w-full">
  <div class="relative flex items-center">
    <div class="absolute left-3.5 flex items-center gap-1.5 text-slate-400 pointer-events-none">
      {#if isLoading}
        <Loader2 class="w-4 h-4 animate-spin text-emerald-600" />
      {:else if /^\d+$/.test(query.trim()) && query.trim().length >= 8}
        <Barcode class="w-4 h-4 text-emerald-600" />
      {:else}
        <Search class="w-4 h-4" />
      {/if}
    </div>

    <input
      bind:this={inputEl}
      bind:value={query}
      oninput={handleInput}
      onkeydown={handleKeyDown}
      type="text"
      placeholder="Scan Barcode / Scale Sticker OR Type Name... (F2)"
      class="w-full pl-10 pr-16 py-2.5 bg-white border border-slate-300 rounded-xl text-sm font-medium text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 shadow-xs transition-all"
    />

    <div class="absolute right-2.5 flex items-center gap-1">
      <kbd class="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 bg-slate-100 border border-slate-200 rounded">F2</kbd>
      <kbd class="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 bg-slate-100 border border-slate-200 rounded">Enter</kbd>
    </div>
  </div>

  <!-- Error Message Alert -->
  {#if errorMessage}
    <div class="absolute top-full mt-1.5 left-0 right-0 z-50 p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 shadow-md flex items-center justify-between">
      <span>⚠️ {errorMessage}</span>
      <button onclick={() => errorMessage = ''} class="text-rose-500 hover:text-rose-700 text-sm font-bold">×</button>
    </div>
  {/if}

  <!-- Live Search Results Dropdown -->
  {#if results.length > 0}
    <div class="absolute top-full mt-1.5 left-0 right-0 z-50 bg-white border border-slate-200 rounded-xl shadow-xl max-h-72 overflow-y-auto divide-y divide-slate-100">
      {#each results as product, index}
        <button
          type="button"
          onclick={() => selectProduct(product)}
          class="w-full px-3.5 py-2.5 text-left flex items-center justify-between transition-colors {index === selectedIndex ? 'bg-emerald-50 text-emerald-950' : 'hover:bg-slate-50 text-slate-800'}"
        >
          <div class="flex items-center gap-2.5 min-w-0">
            <span class="text-base flex-shrink-0">
              {['kg', 'g'].includes(product.unit) ? '⚖️' : product.category === 'Drinks' ? '🧃' : product.category === 'Cigarettes' ? '🚬' : '📦'}
            </span>
            <div class="min-w-0">
              <p class="text-xs font-bold truncate {index === selectedIndex ? 'text-emerald-950' : 'text-slate-900'}">
                {product.name}
              </p>
              <div class="flex items-center gap-2 text-[10px] text-slate-500">
                <span>Stock: {product.stock_qty} {product.unit}</span>
                {#if product.barcode}
                  <span>• Barcode: {product.barcode}</span>
                {/if}
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 flex-shrink-0 ml-2">
            <span class="text-xs font-bold font-mono text-emerald-700 bg-emerald-100/60 px-2 py-0.5 rounded">
              ₱{product.selling_price.toFixed(2)} / {product.unit}
            </span>
            {#if index === selectedIndex}
              <ArrowRight class="w-3.5 h-3.5 text-emerald-600" />
            {/if}
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>
