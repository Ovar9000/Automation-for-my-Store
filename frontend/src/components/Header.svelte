<script lang="ts">
  import { cart } from '../lib/cart.svelte'
  import { onMount } from 'svelte'
  import { fetchDailyReport } from '../lib/api'
  import { Store, Clock, PauseCircle, ShieldAlert, Sparkles, HelpCircle, Smartphone, BookOpen } from 'lucide-svelte'

  interface Props {
    onOpenParked: () => void
    onOpenShortcuts: () => void
    onOpenGCash: () => void
    onOpenUtang: () => void
  }

  let { onOpenParked, onOpenShortcuts, onOpenGCash, onOpenUtang }: Props = $props()

  let currentTime = $state('')
  let drawerCash = $state<number | null>(null)

  function updateClock() {
    const now = new Date()
    currentTime = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    })
  }

  async function loadDrawer() {
    try {
      const data = await fetchDailyReport()
      if (data && data.cash_in_drawer !== undefined) {
        drawerCash = data.cash_in_drawer
      }
    } catch (e) {
      // quiet fail
    }
  }

  onMount(() => {
    updateClock()
    const timer = setInterval(updateClock, 1000)
    loadDrawer()
    const drawerTimer = setInterval(loadDrawer, 30000)
    return () => {
      clearInterval(timer)
      clearInterval(drawerTimer)
    }
  })
</script>

<header class="bg-white border-b border-slate-200 px-4 py-2.5 flex items-center justify-between shadow-xs z-10 select-none">
  <!-- Brand & Status -->
  <div class="flex items-center gap-3">
    <div class="w-9 h-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold shadow-xs">
      <Store class="w-5 h-5" />
    </div>
    <div>
      <div class="flex items-center gap-2">
        <h1 class="text-sm font-bold text-slate-900 tracking-tight leading-none">Sari-Sari POS</h1>
        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
          SCAN READY
        </span>
      </div>
      <p class="text-[11px] text-slate-500 font-medium mt-0.5">High-Speed Terminal (Svelte 5)</p>
    </div>
  </div>

  <!-- Center: Live Clock & Cash in Drawer -->
  <div class="hidden md:flex items-center gap-4 text-xs">
    <div class="flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 font-medium">
      <Clock class="w-3.5 h-3.5 text-slate-400" />
      <span>{currentTime}</span>
    </div>

    {#if drawerCash !== null}
      <div class="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 font-semibold">
        <span>💵 Drawer: ₱{drawerCash.toFixed(2)}</span>
      </div>
    {/if}
  </div>

  <!-- Right Actions -->
  <div class="flex items-center gap-2">
    <!-- Utang Ledger Button -->
    <button
      type="button"
      onclick={onOpenUtang}
      class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-amber-800 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100 transition-all shadow-2xs cursor-pointer"
      title="Customer Utang Ledger & Repayments (F7)"
    >
      <BookOpen class="w-4 h-4 text-amber-600" />
      <span>Utang Ledger (F7)</span>
    </button>

    <!-- GCash Service Button -->
    <button
      type="button"
      onclick={onOpenGCash}
      class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-all shadow-2xs cursor-pointer"
      title="GCash Cash-In & Cash-Out Transaction Scanner"
    >
      <Smartphone class="w-4 h-4 text-blue-600" />
      <span>GCash Money</span>
    </button>

    <!-- Parked Carts Button -->
    <button
      onclick={onOpenParked}
      class="relative flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition-all {cart.parkedCarts.length > 0 ? 'bg-amber-50 border-amber-300 text-amber-800 hover:bg-amber-100' : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'}"
      title="Park / Hold Carts (F4)"
    >
      <PauseCircle class="w-4 h-4 {cart.parkedCarts.length > 0 ? 'text-amber-600' : 'text-slate-400'}" />
      <span>Hold/Park (F4)</span>
      {#if cart.parkedCarts.length > 0}
        <span class="w-5 h-5 rounded-full bg-amber-500 text-white font-bold text-[10px] flex items-center justify-center">
          {cart.parkedCarts.length}
        </span>
      {/if}
    </button>

    <!-- Shortcuts Help -->
    <button
      onclick={onOpenShortcuts}
      class="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-all"
      title="Keyboard Shortcuts"
    >
      <HelpCircle class="w-4 h-4" />
    </button>

    <!-- Admin Link -->
    <a
      href="/admin"
      target="_blank"
      class="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-all"
    >
      <span>Admin</span>
    </a>
  </div>
</header>
