<script lang="ts">
  import { cart } from '../lib/cart.svelte'
  import { submitCheckout, fetchDebtCustomers } from '../lib/api'
  import type { CustomerDebt, TransactionResult } from '../types'
  import { Banknote, Smartphone, BookOpen, X, Check, Printer, Loader2 } from 'lucide-svelte'
  import { onMount } from 'svelte'

  interface Props {
    onComplete: (res: TransactionResult) => void
    onClose: () => void
  }

  let { onComplete, onClose }: Props = $props()

  let method = $state<'CASH' | 'GCASH' | 'UTANG'>('CASH')
  let amountTendered = $state<string>('')
  let printReceipt = $state(false)
  let isSubmitting = $state(false)
  let errorMessage = $state('')

  // Utang fields
  let customerList = $state<CustomerDebt[]>([])
  let selectedCustomerName = $state('')
  let customerPhone = $state('')
  let partialPaidNow = $state<string>('0')
  let utangNotes = $state('')

  let inputTenderedEl = $state<HTMLInputElement | null>(null)

  let totalAmount = $derived(cart.subtotal)

  let changeAmount = $derived.by(() => {
    const tendered = parseFloat(amountTendered) || 0
    return tendered >= totalAmount ? Number((tendered - totalAmount).toFixed(2)) : 0
  })

  let isTenderedSufficient = $derived.by(() => {
    if (method === 'UTANG') return selectedCustomerName.trim().length > 0
    if (method === 'GCASH') return true
    const tendered = parseFloat(amountTendered) || 0
    return tendered >= totalAmount
  })

  function setDenomination(denom: number) {
    amountTendered = denom.toString()
  }

  function setExactAmount() {
    amountTendered = totalAmount.toString()
  }

  async function handleCheckout() {
    if (!isTenderedSufficient || isSubmitting) return

    isSubmitting = true
    errorMessage = ''

    try {
      const payload: any = {
        items: cart.items,
        total_amount: totalAmount,
        payment_method: method,
        amount_tendered: method === 'CASH' ? (parseFloat(amountTendered) || totalAmount) : totalAmount,
        print_receipt: printReceipt
      }

      if (method === 'UTANG') {
        payload.customer_name = selectedCustomerName.trim()
        payload.phone_number = customerPhone.trim() || undefined
        payload.notes = utangNotes.trim() || undefined
        payload.amount_paid_now = parseFloat(partialPaidNow) || 0
      }

      const result = await submitCheckout(payload)
      cart.clearCart()
      onComplete(result)
    } catch (err: any) {
      errorMessage = err.message || 'Payment processing failed'
    } finally {
      isSubmitting = false
    }
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    } else if (e.key === 'Enter' || e.key === 'F5') {
      e.preventDefault()
      handleCheckout()
    }
  }

  onMount(async () => {
    // Pre-populate exact amount
    setExactAmount()
    inputTenderedEl?.focus()
    inputTenderedEl?.select()

    try {
      customerList = await fetchDebtCustomers()
    } catch (e) {
      // quiet
    }
  })
</script>

<div
  class="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150"
  onkeydown={handleKeyDown}
  role="dialog"
  aria-modal="true"
  tabindex="-1"
>
  <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden flex flex-col">
    <!-- Header -->
    <div class="px-5 py-4 bg-slate-900 text-white flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold tracking-tight">Complete Payment</h2>
        <p class="text-xs text-slate-400 mt-0.5">Total: <span class="text-emerald-400 font-mono font-bold">₱{totalAmount.toFixed(2)}</span> ({cart.itemCount} items)</p>
      </div>
      <button
        type="button"
        onclick={onClose}
        class="text-slate-400 hover:text-white p-1 rounded-lg transition-colors"
      >
        <X class="w-5 h-5" />
      </button>
    </div>

    <!-- Payment Methods -->
    <div class="p-5 space-y-4">
      <div class="grid grid-cols-3 gap-2 bg-slate-100 p-1 rounded-xl">
        <button
          type="button"
          onclick={() => { method = 'CASH'; setTimeout(() => inputTenderedEl?.focus(), 50) }}
          class="flex items-center justify-center gap-1.5 py-2.5 text-xs font-bold rounded-lg transition-all {method === 'CASH' ? 'bg-emerald-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
        >
          <Banknote class="w-4 h-4" />
          <span>CASH</span>
        </button>

        <button
          type="button"
          onclick={() => method = 'GCASH'}
          class="flex items-center justify-center gap-1.5 py-2.5 text-xs font-bold rounded-lg transition-all {method === 'GCASH' ? 'bg-blue-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
        >
          <Smartphone class="w-4 h-4" />
          <span>GCASH</span>
        </button>

        <button
          type="button"
          onclick={() => method = 'UTANG'}
          class="flex items-center justify-center gap-1.5 py-2.5 text-xs font-bold rounded-lg transition-all {method === 'UTANG' ? 'bg-amber-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
        >
          <BookOpen class="w-4 h-4" />
          <span>UTANG</span>
        </button>
      </div>

      {#if errorMessage}
        <div class="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-bold text-rose-700">
          ⚠️ {errorMessage}
        </div>
      {/if}

      <!-- Cash Mode -->
      {#if method === 'CASH'}
        <div class="space-y-3">
          <div>
            <label for="cashTendered" class="block text-xs font-bold text-slate-700 mb-1">Amount Tendered (Bayad):</label>
            <div class="relative flex items-center">
              <span class="absolute left-4 text-xl font-black text-slate-400">₱</span>
              <input
                id="cashTendered"
                bind:this={inputTenderedEl}
                bind:value={amountTendered}
                type="number"
                step="any"
                min="0"
                class="w-full pl-10 pr-4 py-3 bg-slate-50 border-2 border-emerald-500 rounded-xl text-2xl font-black font-mono text-slate-900 focus:outline-none focus:bg-white"
              />
            </div>
          </div>

          <!-- Quick Denomination Pills -->
          <div class="grid grid-cols-4 sm:grid-cols-7 gap-1.5">
            <button
              type="button"
              onclick={setExactAmount}
              class="py-2 text-xs font-bold rounded-lg bg-slate-200 text-slate-800 hover:bg-slate-300 transition-colors"
            >
              Exact
            </button>
            {#each [20, 50, 100, 200, 500, 1000] as denom}
              <button
                type="button"
                onclick={() => setDenomination(denom)}
                class="py-2 text-xs font-bold font-mono rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-emerald-50 hover:border-emerald-300 hover:text-emerald-800 transition-colors"
              >
                ₱{denom}
              </button>
            {/each}
          </div>

          <!-- Sukli Banner -->
          <div class="p-4 rounded-xl border flex items-center justify-between {changeAmount > 0 ? 'bg-emerald-50 border-emerald-300 text-emerald-950' : 'bg-slate-50 border-slate-200 text-slate-600'}">
            <span class="text-xs font-extrabold uppercase tracking-wider">Sukli (Change):</span>
            <span class="text-3xl font-black font-mono text-emerald-700">
              ₱{changeAmount.toFixed(2)}
            </span>
          </div>
        </div>

      <!-- GCash Mode -->
      {:else if method === 'GCASH'}
        <div class="p-4 bg-blue-50 border border-blue-200 rounded-xl space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-blue-900">GCash Direct Payment:</span>
            <span class="text-lg font-black font-mono text-blue-800">₱{totalAmount.toFixed(2)}</span>
          </div>
          <p class="text-xs text-blue-700 leading-relaxed">
            Scan store QRPh or send to store GCash number. Ensure reference SMS is verified before pressing checkout.
          </p>
        </div>

      <!-- Utang / Palista Mode -->
      {:else if method === 'UTANG'}
        <div class="space-y-3">
          <div>
            <label for="customerName" class="block text-xs font-bold text-slate-700 mb-1">Customer Name (Palista kay):</label>
            <input
              id="customerName"
              bind:value={selectedCustomerName}
              list="customerNamesList"
              placeholder="Type or pick customer name..."
              class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
            <datalist id="customerNamesList">
              {#each customerList as c}
                <option value={c.customer_name}>Current Balance: ₱{c.total_debt.toFixed(2)}</option>
              {/each}
            </datalist>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label for="customerPhone" class="block text-[11px] font-semibold text-slate-600 mb-1">Phone Number:</label>
              <input
                id="customerPhone"
                bind:value={customerPhone}
                placeholder="09..."
                class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs"
              />
            </div>
            <div>
              <label for="downPayment" class="block text-[11px] font-semibold text-slate-600 mb-1">Downpayment Now (₱):</label>
              <input
                id="downPayment"
                bind:value={partialPaidNow}
                type="number"
                min="0"
                class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs font-mono font-bold"
              />
            </div>
          </div>
        </div>
      {/if}

      <!-- Print Receipt Option -->
      <label class="flex items-center gap-2 cursor-pointer pt-2 text-xs font-semibold text-slate-700">
        <input
          type="checkbox"
          bind:checked={printReceipt}
          class="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 border-slate-300"
        />
        <Printer class="w-3.5 h-3.5 text-slate-400" />
        <span>Print 58mm Thermal Receipt</span>
      </label>
    </div>

    <!-- Actions -->
    <div class="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
      <button
        type="button"
        onclick={onClose}
        class="px-4 py-2.5 text-xs font-bold text-slate-600 hover:text-slate-900 rounded-xl"
      >
        Cancel (Esc)
      </button>

      <button
        type="button"
        onclick={handleCheckout}
        disabled={!isTenderedSufficient || isSubmitting}
        class="flex items-center gap-2 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-extrabold rounded-xl shadow-md transition-all"
      >
        {#if isSubmitting}
          <Loader2 class="w-4 h-4 animate-spin" />
          <span>Processing...</span>
        {:else}
          <Check class="w-4 h-4" />
          <span>Finish Sale (Enter / F5)</span>
        {/if}
      </button>
    </div>
  </div>
</div>
