<script lang="ts">
  import { HelpCircle, X, Keyboard } from 'lucide-svelte'

  interface Props {
    onClose: () => void
  }

  let { onClose }: Props = $props()

  const shortcuts = [
    { key: 'F2', desc: 'Focus Smart Barcode / Product Search Input' },
    { key: 'F4', desc: 'Hold / Park Current Cart ("Kwentahan Mamaya")' },
    { key: 'F5', desc: 'Open Payment / Complete Checkout' },
    { key: 'F7', desc: 'Open Customer Utang Ledger & Record Repayments' },
    { key: 'Enter', desc: 'Confirm Scan / Add Highlighted Item / Finish Sale' },
    { key: 'Esc', desc: 'Close Active Modal / Clear Search / Reset State' },
    { key: '↑ / ↓', desc: 'Navigate Search Results Dropdown' },
    { key: '1x - 12x', desc: 'Click Qty Multiplier before tapping any staple tile' },
    { key: '20/21 Barcodes', desc: 'Automatic Weighing Scale EAN-13 Barcode Decoder' }
  ]
</script>

<div
  class="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150"
  role="dialog"
  aria-modal="true"
  tabindex="-1"
>
  <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden flex flex-col">
    <!-- Header -->
    <div class="px-5 py-4 bg-slate-900 text-white flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Keyboard class="w-5 h-5 text-emerald-400" />
        <h2 class="text-sm font-bold tracking-tight">Keyboard Shortcuts & Scanner Tips</h2>
      </div>
      <button
        type="button"
        onclick={onClose}
        class="text-slate-400 hover:text-white p-1 rounded-lg transition-colors"
      >
        <X class="w-5 h-5" />
      </button>
    </div>

    <!-- Shortcuts List -->
    <div class="p-4 divide-y divide-slate-100 max-h-96 overflow-y-auto">
      {#each shortcuts as s}
        <div class="py-2.5 flex items-center justify-between">
          <span class="text-xs text-slate-600 font-medium">{s.desc}</span>
          <kbd class="px-2 py-1 text-xs font-mono font-bold text-slate-800 bg-slate-100 border border-slate-300 rounded-md shadow-2xs">
            {s.key}
          </kbd>
        </div>
      {/each}
    </div>

    <!-- Footer -->
    <div class="p-3 bg-slate-50 border-t border-slate-200 flex justify-end">
      <button
        type="button"
        onclick={onClose}
        class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900 rounded-lg"
      >
        Got it (Esc)
      </button>
    </div>
  </div>
</div>
