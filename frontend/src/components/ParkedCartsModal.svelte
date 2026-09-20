<script lang="ts">
  import { cart } from '../lib/cart.svelte'
  import { PauseCircle, PlayCircle, Trash2, X, ShoppingCart } from 'lucide-svelte'

  interface Props {
    onClose: () => void
  }

  let { onClose }: Props = $props()

  function handleResume(id: string) {
    cart.restoreParkedCart(id)
    onClose()
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }
</script>

<div
  class="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150"
  onkeydown={handleKeyDown}
  role="dialog"
  aria-modal="true"
  tabindex="-1"
>
  <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden flex flex-col max-h-[85vh]">
    <!-- Header -->
    <div class="px-5 py-4 bg-amber-700 text-white flex items-center justify-between">
      <div class="flex items-center gap-2">
        <PauseCircle class="w-5 h-5 text-amber-200" />
        <div>
          <h2 class="text-sm font-bold tracking-tight">Parked / Held Carts</h2>
          <p class="text-[11px] text-amber-100">Kwentahan Mamaya / Babalikan na Orders</p>
        </div>
      </div>
      <button
        type="button"
        onclick={onClose}
        class="text-amber-200 hover:text-white p-1 rounded-lg transition-colors"
      >
        <X class="w-5 h-5" />
      </button>
    </div>

    <!-- Carts List -->
    <div class="p-4 flex-1 overflow-y-auto space-y-3">
      {#if cart.parkedCarts.length === 0}
        <div class="py-12 text-center text-slate-400">
          <PauseCircle class="w-10 h-10 mx-auto text-slate-300 mb-2" />
          <p class="text-sm font-bold text-slate-600">No Parked Carts</p>
          <p class="text-xs text-slate-400 mt-0.5">Use "Hold (F4)" in the cart to park a customer while they grab money.</p>
        </div>
      {:else}
        {#each cart.parkedCarts as parked (parked.id)}
          <div class="p-3.5 bg-amber-50/50 border border-amber-200/80 rounded-xl flex items-center justify-between gap-3 hover:bg-amber-50 transition-colors">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-xs font-bold text-slate-900">{parked.note || 'Parked Order'}</span>
                <span class="text-[10px] font-mono font-semibold px-1.5 py-0.2 rounded bg-amber-200/60 text-amber-900">
                  {parked.timestamp}
                </span>
              </div>
              <p class="text-[11px] text-slate-600 mt-1 truncate">
                {parked.items.map(i => `${i.quantity}${i.unit === 'pc' ? '' : i.unit} ${i.product_name}`).join(', ')}
              </p>
              <p class="text-xs font-black font-mono text-amber-900 mt-1">
                Total: ₱{parked.total.toFixed(2)} ({parked.items.length} items)
              </p>
            </div>

            <div class="flex items-center gap-2 flex-shrink-0">
              <button
                type="button"
                onclick={() => handleResume(parked.id)}
                class="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white text-xs font-bold rounded-lg shadow-xs transition-all"
              >
                <PlayCircle class="w-4 h-4" />
                <span>Resume</span>
              </button>

              <button
                type="button"
                onclick={() => cart.deleteParkedCart(parked.id)}
                class="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                title="Discard Parked Cart"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <!-- Footer -->
    <div class="p-3 bg-slate-50 border-t border-slate-200 flex justify-end">
      <button
        type="button"
        onclick={onClose}
        class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900 rounded-lg"
      >
        Close (Esc)
      </button>
    </div>
  </div>
</div>
