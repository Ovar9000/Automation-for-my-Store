<script lang="ts">
  import type { TransactionResult } from '../types'
  import { printReceipt } from '../lib/api'
  import { CheckCircle2, Printer, ArrowRight, X } from 'lucide-svelte'
  import { onMount } from 'svelte'

  interface Props {
    transaction: TransactionResult
    onClose: () => void
  }

  let { transaction, onClose }: Props = $props()

  let isPrinting = $state(false)
  let printStatus = $state('')

  function formatReceipt(): string {
    const LINE_WIDTH = 32
    const center = (s: string) => s.length >= LINE_WIDTH ? s : ' '.repeat(Math.floor((LINE_WIDTH - s.length) / 2)) + s
    const twoCol = (left: string, right: string) => {
      const space = LINE_WIDTH - left.length - right.length
      return space > 0 ? left + ' '.repeat(space) + right : `${left} ${right}`
    }

    const lines: string[] = [
      center("SARI-SARI STORE"),
      center("Official POS Receipt"),
      "-".repeat(LINE_WIDTH),
      twoCol("Receipt #:", transaction.receipt_number),
      twoCol("Date:", new Date(transaction.created_at).toLocaleDateString()),
      twoCol("Time:", new Date(transaction.created_at).toLocaleTimeString()),
      "-".repeat(LINE_WIDTH)
    ]

    for (const item of transaction.items) {
      lines.push(twoCol(
        `${item.quantity}${item.unit === 'pc' ? 'x' : item.unit} ${item.product_name.substring(0, 16)}`,
        `P${item.subtotal.toFixed(2)}`
      ))
    }

    lines.push("-".repeat(LINE_WIDTH))
    lines.push(twoCol("TOTAL AMOUNT:", `P${transaction.total_amount.toFixed(2)}`))
    lines.push(twoCol("Payment Method:", transaction.payment_method))
    const changeVal = transaction.change ?? transaction.change_amount ?? 0
    lines.push(twoCol("CHANGE (SUKLI):", `P${changeVal.toFixed(2)}`))

    if (transaction.customer_name) {
      lines.push(twoCol("Customer:", transaction.customer_name))
    }

    lines.push("=".repeat(LINE_WIDTH))
    lines.push(center("Salamat po sa pagbili!"))
    lines.push(center("Please come again."))

    return lines.join("\n")
  }

  async function handlePrint() {
    isPrinting = true
    printStatus = ''
    try {
      const text = formatReceipt()
      const res = await printReceipt(text)
      printStatus = res.message || 'Receipt sent to printer!'
    } catch (e: any) {
      printStatus = 'Printer offline or not connected'
    } finally {
      isPrinting = false
    }
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === 'Escape') {
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
  <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden flex flex-col">
    <!-- Success Banner -->
    <div class="p-6 bg-emerald-600 text-white text-center flex flex-col items-center">
      <CheckCircle2 class="w-12 h-12 text-emerald-200 mb-2" />
      <h2 class="text-xl font-black tracking-tight">Sale Completed!</h2>
      <p class="text-xs text-emerald-100 mt-0.5">Receipt: {transaction.receipt_number}</p>

      <!-- Change Banner -->
      <div class="mt-4 w-full bg-emerald-700/80 rounded-xl p-3 border border-emerald-500/50 flex items-baseline justify-between">
        <span class="text-xs font-bold uppercase tracking-wider text-emerald-100">Sukli (Change):</span>
        <span class="text-3xl font-black font-mono">₱{(transaction.change ?? transaction.change_amount ?? 0).toFixed(2)}</span>
      </div>
    </div>

    <!-- 58mm Thermal Preview -->
    <div class="p-4 bg-slate-50 border-y border-slate-200 flex-1 max-h-60 overflow-y-auto">
      <div class="bg-white p-3 border border-slate-300 rounded-lg shadow-inner font-mono text-[11px] leading-tight text-slate-800 whitespace-pre">
        {formatReceipt()}
      </div>
      {#if printStatus}
        <p class="text-[11px] font-bold text-center mt-2 {printStatus.includes('offline') ? 'text-amber-700' : 'text-emerald-700'}">
          {printStatus}
        </p>
      {/if}
    </div>

    <!-- Actions -->
    <div class="p-4 bg-white flex items-center justify-between gap-2">
      <button
        type="button"
        onclick={handlePrint}
        disabled={isPrinting}
        class="flex items-center gap-1.5 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl transition-all"
      >
        <Printer class="w-4 h-4" />
        <span>{isPrinting ? 'Printing...' : 'Print 58mm'}</span>
      </button>

      <button
        type="button"
        onclick={onClose}
        class="flex items-center gap-1.5 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white text-xs font-extrabold rounded-xl shadow-xs transition-all"
      >
        <span>Next Sale (Enter)</span>
        <ArrowRight class="w-4 h-4" />
      </button>
    </div>
  </div>
</div>
