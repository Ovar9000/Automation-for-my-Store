<script lang="ts">
  import { cart } from '../lib/cart.svelte'
  import { Trash2, Plus, Minus, ShoppingCart, PauseCircle, Ban } from 'lucide-svelte'

  interface Props {
    onOpenPayment: () => void
    onHoldCart: () => void
  }

  let { onOpenPayment, onHoldCart }: Props = $props()
</script>

<div class="flex flex-col h-full bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
  <!-- Cart Header -->
  <div class="px-4 py-3 bg-slate-50/90 border-b border-slate-200 flex items-center justify-between flex-shrink-0">
    <div class="flex items-center gap-2">
      <ShoppingCart class="w-4 h-4 text-slate-600" />
      <h2 class="text-xs font-bold uppercase tracking-wider text-slate-700">Current Cart</h2>
      {#if cart.items.length > 0}
        <span class="px-2 py-0.5 rounded-full text-[11px] font-extrabold bg-emerald-100 text-emerald-800">
          {cart.itemCount} items
        </span>
      {/if}
    </div>

    {#if cart.items.length > 0}
      <div class="flex items-center gap-1.5">
        <button
          type="button"
          onclick={onHoldCart}
          class="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg transition-all"
          title="Hold/Park Cart (F4)"
        >
          <PauseCircle class="w-3.5 h-3.5" />
          <span>Hold (F4)</span>
        </button>

        <button
          type="button"
          onclick={() => cart.clearCart()}
          class="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all"
          title="Clear Cart"
        >
          <Ban class="w-4 h-4" />
        </button>
      </div>
    {/if}
  </div>

  <!-- Cart Items List -->
  <div class="flex-1 overflow-y-auto divide-y divide-slate-100 p-2">
    {#if cart.items.length === 0}
      <div class="h-full flex flex-col items-center justify-center p-6 text-center text-slate-400">
        <div class="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center mb-3">
          <ShoppingCart class="w-6 h-6 text-slate-300" />
        </div>
        <p class="text-sm font-bold text-slate-600">Cart is Empty</p>
        <p class="text-xs text-slate-400 mt-1 max-w-[200px]">
          Scan with barcode gun, type name in search, or tap from Staples tiles.
        </p>
      </div>
    {:else}
      {#each cart.items as item (item.id)}
        <div class="py-2.5 px-2 flex items-center justify-between gap-2 hover:bg-slate-50/80 rounded-xl transition-colors">
          <!-- Item Details -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <p class="text-xs font-bold text-slate-900 truncate leading-snug">
                {item.product_name}
              </p>
              {#if item.pack_label}
                <span class="px-1.5 py-0.2 rounded text-[9px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 flex-shrink-0">
                  {item.pack_label}
                </span>
              {/if}
            </div>
            <p class="text-[11px] font-mono text-slate-500 mt-0.5">
              ₱{item.unit_price.toFixed(2)} / {item.unit}
            </p>
          </div>

          <!-- Quantity Stepper -->
          <div class="flex items-center gap-1 flex-shrink-0 bg-slate-100 rounded-lg p-0.5">
            <button
              type="button"
              onclick={() => cart.updateQuantity(item.id, item.unit === 'pc' ? item.quantity - 1 : Number((item.quantity - 0.25).toFixed(3)))}
              class="w-6 h-6 flex items-center justify-center rounded-md bg-white hover:bg-slate-200 text-slate-700 font-bold transition-colors"
            >
              <Minus class="w-3 h-3" />
            </button>

            <span class="min-w-8 text-center text-xs font-bold font-mono text-slate-800">
              {item.unit === 'pc' ? item.quantity : item.quantity.toFixed(3)}
            </span>

            <button
              type="button"
              onclick={() => cart.updateQuantity(item.id, item.unit === 'pc' ? item.quantity + 1 : Number((item.quantity + 0.25).toFixed(3)))}
              class="w-6 h-6 flex items-center justify-center rounded-md bg-white hover:bg-slate-200 text-slate-700 font-bold transition-colors"
            >
              <Plus class="w-3 h-3" />
            </button>
          </div>

          <!-- Subtotal & Remove -->
          <div class="flex items-center gap-2 flex-shrink-0 text-right">
            <span class="text-xs font-extrabold font-mono text-slate-900 w-16">
              ₱{item.subtotal.toFixed(2)}
            </span>
            <button
              type="button"
              onclick={() => cart.removeItem(item.id)}
              class="text-slate-400 hover:text-rose-600 p-1 rounded transition-colors"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      {/each}
    {/if}
  </div>

  <!-- Cart Footer / Big Total & Checkout -->
  <div class="p-4 bg-slate-50/90 border-t border-slate-200 flex-shrink-0 space-y-3">
    <div class="flex items-baseline justify-between">
      <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Total Amount:</span>
      <span class="text-3xl font-black font-mono text-slate-900 tracking-tight">
        ₱{cart.subtotal.toFixed(2)}
      </span>
    </div>

    <!-- Big Checkout Button -->
    <button
      type="button"
      onclick={onOpenPayment}
      disabled={cart.items.length === 0}
      class="w-full py-3.5 px-4 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:opacity-40 disabled:cursor-not-allowed text-white font-extrabold text-sm rounded-xl shadow-md transition-all flex items-center justify-between"
    >
      <span class="flex items-center gap-2">
        <span>Proceed to Payment</span>
        <kbd class="px-1.5 py-0.5 text-[10px] font-mono bg-emerald-700/80 rounded">F5</kbd>
      </span>
      <span class="text-base font-mono">₱{cart.subtotal.toFixed(2)}</span>
    </button>
  </div>
</div>
