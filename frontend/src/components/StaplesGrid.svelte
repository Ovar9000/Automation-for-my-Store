<script lang="ts">
  import type { Product } from '../types'
  import { Sparkles, Flame, Coffee, Wheat, Smartphone, ArrowDownLeft, ArrowUpRight } from 'lucide-svelte'

  interface Props {
    quickItems: Product[]
    onSelectProduct: (product: Product, quantity?: number, price?: number, label?: string | null) => void
    onRequestWeightModal: (product: Product) => void
    onOpenGCash: (type: 'GCASH_IN' | 'GCASH_OUT') => void
  }

  let { quickItems, onSelectProduct, onRequestWeightModal, onOpenGCash }: Props = $props()

  let activeTab = $state<'staples' | 'tingi' | 'rice' | 'custom'>('staples')
  let multiplier = $state(1)

  // Built-in unbarcoded staples with fixed unique IDs
  const staples = [
    { id: 90001, name: 'Gasolina (1L Bote)', price: 75, unit: 'L', icon: '⛽', color: 'bg-amber-50 border-amber-300 text-amber-900', badge: '1L Bottle' },
    { id: 90002, name: 'Yelo (Tube/Block)', price: 5, unit: 'pc', icon: '🧊', color: 'bg-cyan-50 border-cyan-300 text-cyan-900', badge: '₱5 Ice' },
    { id: 90003, name: 'Ice Water (Supot)', price: 3, unit: 'pc', icon: '💧', color: 'bg-sky-50 border-sky-300 text-sky-900', badge: '₱3 Water' },
    { id: 90004, name: 'Ice Candy', price: 10, unit: 'pc', icon: '🍦', color: 'bg-pink-50 border-pink-300 text-pink-900', badge: '₱10 Sweet' },
    { id: 90005, name: 'Itlog (Medium)', price: 8, unit: 'pc', icon: '🥚', color: 'bg-amber-50 border-amber-300 text-amber-900', badge: '₱8 Egg' },
    { id: 90006, name: 'Mantika (Small Pouch)', price: 15, unit: 'pc', icon: '🛢️', color: 'bg-yellow-50 border-yellow-300 text-yellow-900', badge: 'Cooking Oil' },
    { id: 90007, name: 'Uling (1 Plastic)', price: 20, unit: 'pc', icon: '🪵', color: 'bg-stone-50 border-stone-300 text-stone-900', badge: 'Charcoal' },
    { id: 90008, name: 'Kendi (Maxx/Mentos)', price: 2, unit: 'pc', icon: '🍬', color: 'bg-rose-50 border-rose-300 text-rose-900', badge: 'Candy' }
  ]

  // Tingi single-stick and single-sachet items
  const tingiItems = [
    { id: 90011, name: 'Kopiko Blanca (Sachet)', price: 14, unit: 'pc', icon: '☕', color: 'bg-orange-50 border-orange-300 text-orange-900', badge: '1 Sachet' },
    { id: 90012, name: 'Kopiko Blanca (Banig 10s)', price: 135, unit: 'pc', icon: '📦', color: 'bg-orange-100 border-orange-400 text-orange-950', badge: '10s Banig' },
    { id: 90013, name: 'Great Taste White (Sachet)', price: 14, unit: 'pc', icon: '☕', color: 'bg-amber-50 border-amber-300 text-amber-900', badge: '1 Sachet' },
    { id: 90014, name: 'Nescafe 3-in-1 (Sachet)', price: 15, unit: 'pc', icon: '☕', color: 'bg-red-50 border-red-300 text-red-900', badge: '1 Sachet' },
    { id: 90015, name: 'Marlboro Red (1 Stick)', price: 9, unit: 'pc', icon: '🚬', color: 'bg-red-50 border-red-300 text-red-900', badge: '1 Stick' },
    { id: 90016, name: 'Marlboro Red (1 Pack 20s)', price: 175, unit: 'pc', icon: '📦', color: 'bg-red-100 border-red-400 text-red-950', badge: 'Full Pack' },
    { id: 90017, name: 'Fortune Red (1 Stick)', price: 8, unit: 'pc', icon: '🚬', color: 'bg-emerald-50 border-emerald-300 text-emerald-900', badge: '1 Stick' },
    { id: 90018, name: 'Champion Cigarette (1 Stick)', price: 7, unit: 'pc', icon: '🚬', color: 'bg-blue-50 border-blue-300 text-blue-900', badge: '1 Stick' }
  ]

  // Rice & Feeds items
  const riceItems = [
    { id: 90021, name: 'Bigas Dinorado (Special)', price: 54, unit: 'kg', icon: '🌾', color: 'bg-lime-50 border-lime-300 text-lime-900', badge: '₱54/kg' },
    { id: 90022, name: 'Bigas Sinandomeng (Regular)', price: 48, unit: 'kg', icon: '🌾', color: 'bg-emerald-50 border-emerald-300 text-emerald-900', badge: '₱48/kg' },
    { id: 90023, name: 'Asukal Puti (Refined)', price: 85, unit: 'kg', icon: '🧂', color: 'bg-slate-50 border-slate-300 text-slate-900', badge: '₱85/kg' },
    { id: 90024, name: 'Asukal Pula (Brown)', price: 72, unit: 'kg', icon: '🧂', color: 'bg-amber-50 border-amber-300 text-amber-900', badge: '₱72/kg' },
    { id: 90025, name: 'Corn Grits / Mais', price: 38, unit: 'kg', icon: '🌽', color: 'bg-yellow-50 border-yellow-300 text-yellow-900', badge: '₱38/kg' },
    { id: 90026, name: 'Starter Feeds (Manok)', price: 44, unit: 'kg', icon: '🐔', color: 'bg-teal-50 border-teal-300 text-teal-900', badge: '₱44/kg' }
  ]

  function handleGenericAdd(item: { id: number; name: string; price: number; unit: string; badge?: string }) {
    // Exact match in inventory if registered, otherwise use standalone item
    const existing = quickItems.find(p => p.name.trim().toLowerCase() === item.name.trim().toLowerCase())
    
    const productToAdd: Product = existing || {
      id: item.id,
      name: item.name,
      selling_price: item.price,
      cost_price: Number((item.price * 0.85).toFixed(2)),
      stock_qty: 100,
      low_stock_threshold: 5,
      unit: item.unit,
      is_quick_item: true,
      quick_button_color: '#10b981',
      category: item.unit === 'kg' ? 'Rice & Grains' : 'Staples'
    }

    if (item.unit === 'kg') {
      onRequestWeightModal(productToAdd)
    } else {
      onSelectProduct(productToAdd, multiplier, item.price, item.badge)
      multiplier = 1 // Reset multiplier after selection
    }
  }

  function handleCustomAdd(prod: Product) {
    if (['kg', 'l', 'g'].includes(prod.unit.toLowerCase())) {
      onRequestWeightModal(prod)
    } else {
      onSelectProduct(prod, multiplier)
      multiplier = 1
    }
  }
</script>

<div class="flex flex-col h-full bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
  <!-- Tabs & Multiplier Header -->
  <div class="p-3 bg-slate-50/80 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
    <!-- Category Tabs -->
    <div class="flex items-center gap-1 bg-slate-200/70 p-1 rounded-xl text-xs font-semibold">
      <button
        type="button"
        onclick={() => activeTab = 'staples'}
        class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition-all {activeTab === 'staples' ? 'bg-white text-emerald-800 shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
      >
        <Flame class="w-3.5 h-3.5 text-amber-500" />
        <span>Staples</span>
      </button>

      <button
        type="button"
        onclick={() => activeTab = 'tingi'}
        class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition-all {activeTab === 'tingi' ? 'bg-white text-emerald-800 shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
      >
        <Coffee class="w-3.5 h-3.5 text-orange-500" />
        <span>Kape & Tingi</span>
      </button>

      <button
        type="button"
        onclick={() => activeTab = 'rice'}
        class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition-all {activeTab === 'rice' ? 'bg-white text-emerald-800 shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
      >
        <Wheat class="w-3.5 h-3.5 text-lime-600" />
        <span>Bigas & Feeds</span>
      </button>

      {#if quickItems.length > 0}
        <button
          type="button"
          onclick={() => activeTab = 'custom'}
          class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg transition-all {activeTab === 'custom' ? 'bg-white text-emerald-800 shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
        >
          <Sparkles class="w-3.5 h-3.5 text-indigo-500" />
          <span>Quick Items ({quickItems.length})</span>
        </button>
      {/if}
    </div>

    <!-- GCash Service Shortcuts & Multiplier -->
    <div class="flex items-center gap-2">
      <!-- Quick GCash In/Out Trigger Buttons -->
      <div class="hidden sm:flex items-center gap-1 bg-blue-50 border border-blue-200 p-0.5 rounded-xl text-[11px] font-bold">
        <button
          type="button"
          onclick={() => onOpenGCash('GCASH_OUT')}
          class="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center gap-1 transition-colors"
          title="Customer sends GCash -> Store hands cash"
        >
          <ArrowDownLeft class="w-3 h-3" />
          <span>Cash-Out</span>
        </button>
        <button
          type="button"
          onclick={() => onOpenGCash('GCASH_IN')}
          class="px-2 py-1 bg-white hover:bg-blue-100 text-blue-900 rounded-lg flex items-center gap-1 transition-colors"
          title="Customer gives cash -> Store sends GCash"
        >
          <ArrowUpRight class="w-3 h-3" />
          <span>Cash-In</span>
        </button>
      </div>

      <!-- Quantity Multiplier Pills -->
      <div class="flex items-center gap-1 bg-slate-200/70 p-1 rounded-xl text-xs font-bold">
        <span class="text-[10px] text-slate-500 px-1 font-semibold uppercase">Qty:</span>
        {#each [1, 2, 3, 5, 10, 12] as num}
          <button
            type="button"
            onclick={() => multiplier = num}
            class="px-2 py-1 rounded-lg transition-all {multiplier === num ? 'bg-emerald-600 text-white shadow-xs' : 'bg-white text-slate-700 hover:bg-slate-100'}"
          >
            {num}x
          </button>
        {/each}
      </div>
    </div>
  </div>

  <!-- Tiles Grid -->
  <div class="p-3 flex-1 overflow-y-auto">
    {#if activeTab === 'staples'}
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {#each staples as item}
          <button
            type="button"
            onclick={() => handleGenericAdd(item)}
            class="group p-3 rounded-xl border text-left transition-all active:scale-[0.98] hover:shadow-md flex flex-col justify-between min-h-[96px] {item.color}"
          >
            <div class="flex items-start justify-between">
              <span class="text-2xl group-hover:scale-110 transition-transform">{item.icon}</span>
              <span class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-white/80 border border-slate-200/60 shadow-2xs">
                {item.badge}
              </span>
            </div>
            <div>
              <p class="text-xs font-bold tracking-tight line-clamp-1 leading-snug">{item.name}</p>
              <p class="text-sm font-extrabold font-mono mt-0.5">₱{item.price.toFixed(2)}</p>
            </div>
          </button>
        {/each}
      </div>

    {:else if activeTab === 'tingi'}
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {#each tingiItems as item}
          <button
            type="button"
            onclick={() => handleGenericAdd(item)}
            class="group p-3 rounded-xl border text-left transition-all active:scale-[0.98] hover:shadow-md flex flex-col justify-between min-h-[96px] {item.color}"
          >
            <div class="flex items-start justify-between">
              <span class="text-2xl group-hover:scale-110 transition-transform">{item.icon}</span>
              <span class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-white/80 border border-slate-200/60 shadow-2xs">
                {item.badge}
              </span>
            </div>
            <div>
              <p class="text-xs font-bold tracking-tight line-clamp-1 leading-snug">{item.name}</p>
              <p class="text-sm font-extrabold font-mono mt-0.5">₱{item.price.toFixed(2)}</p>
            </div>
          </button>
        {/each}
      </div>

    {:else if activeTab === 'rice'}
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
        {#each riceItems as item}
          <button
            type="button"
            onclick={() => handleGenericAdd(item)}
            class="group p-3.5 rounded-xl border text-left transition-all active:scale-[0.98] hover:shadow-md flex flex-col justify-between min-h-[100px] {item.color}"
          >
            <div class="flex items-start justify-between">
              <span class="text-2xl group-hover:scale-110 transition-transform">{item.icon}</span>
              <span class="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-600 text-white">
                WEIGH / PESO
              </span>
            </div>
            <div>
              <p class="text-xs font-bold tracking-tight line-clamp-1 leading-snug">{item.name}</p>
              <p class="text-sm font-extrabold font-mono mt-0.5">₱{item.price.toFixed(2)} / {item.unit}</p>
            </div>
          </button>
        {/each}
      </div>

    {:else if activeTab === 'custom'}
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {#each quickItems as prod}
          <button
            type="button"
            onclick={() => handleCustomAdd(prod)}
            class="group p-3 rounded-xl border border-slate-200 bg-white hover:border-emerald-400 text-left transition-all active:scale-[0.98] hover:shadow-md flex flex-col justify-between min-h-[96px]"
          >
            <div class="flex items-start justify-between">
              <span class="w-3 h-3 rounded-full" style="background-color: {prod.quick_button_color || '#10b981'}"></span>
              <span class="px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 bg-slate-100 rounded">
                {prod.stock_qty} {prod.unit}
              </span>
            </div>
            <div>
              <p class="text-xs font-bold text-slate-900 line-clamp-1 leading-snug">{prod.name}</p>
              <p class="text-sm font-extrabold font-mono text-emerald-700 mt-0.5">₱{prod.selling_price.toFixed(2)}</p>
            </div>
          </button>
        {/each}
      </div>
    {/if}
  </div>
</div>
