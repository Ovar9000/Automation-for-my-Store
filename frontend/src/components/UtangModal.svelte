<script lang="ts">
  import { onMount } from 'svelte'
  import {
    BookOpen,
    X,
    Search,
    UserPlus,
    Receipt,
    Banknote,
    Clock,
    ArrowDownRight,
    ArrowUpRight,
    AlertCircle,
    CheckCircle2,
    ArrowLeft
  } from 'lucide-svelte'
  import {
    fetchDebtCustomers,
    payDebt,
    fetchDebtHistory,
    registerDebtCustomer
  } from '../lib/api'
  import type { CustomerDebt, DebtTransaction } from '../types'

  interface Props {
    onClose: () => void
    onPaymentRecorded?: (msg: string) => void
  }

  let { onClose, onPaymentRecorded }: Props = $props()

  // Main list state
  let customers = $state<CustomerDebt[]>([])
  let searchQuery = $state('')
  let isLoading = $state(false)
  let viewMode = $state<'list' | 'pay' | 'history' | 'register'>('list')
  let activeCustomer = $state<CustomerDebt | null>(null)
  let historyList = $state<DebtTransaction[]>([])

  // Pay form state
  let repaymentAmount = $state<number | ''>('')
  let repaymentNotes = $state('')

  // Register form state
  let regName = $state('')
  let regPhone = $state('')
  let regInitialDebt = $state<number | ''>('')
  let regNotes = $state('')

  // Status & Feedback state
  let isProcessing = $state(false)
  let errorMessage = $state<string | null>(null)
  let successMessage = $state<string | null>(null)

  // Derived state
  let totalOutstanding = $derived(
    customers.reduce((sum, c) => sum + (c.total_debt || 0), 0)
  )

  let remainingAfterPayment = $derived.by(() => {
    if (!activeCustomer || typeof repaymentAmount !== 'number') return 0
    return Math.max(0, activeCustomer.total_debt - repaymentAmount)
  })

  async function loadCustomers() {
    isLoading = true
    errorMessage = null
    try {
      customers = await fetchDebtCustomers(searchQuery)
    } catch (err: any) {
      errorMessage = err.message || 'Failed to load debt accounts'
    } finally {
      isLoading = false
    }
  }

  let searchTimeout: any = null
  function handleSearchInput() {
    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => {
      loadCustomers()
    }, 200)
  }

  function startPayment(customer: CustomerDebt) {
    activeCustomer = customer
    repaymentAmount = customer.total_debt > 0 ? customer.total_debt : ''
    repaymentNotes = ''
    errorMessage = null
    successMessage = null
    viewMode = 'pay'
  }

  async function viewCustomerHistory(customer: CustomerDebt) {
    activeCustomer = customer
    errorMessage = null
    successMessage = null
    isLoading = true
    viewMode = 'history'
    try {
      const data = await fetchDebtHistory(customer.id)
      historyList = data.history || []
    } catch (err: any) {
      errorMessage = err.message || 'Failed to fetch history'
    } finally {
      isLoading = false
    }
  }

  function openRegister() {
    regName = ''
    regPhone = ''
    regInitialDebt = ''
    regNotes = ''
    errorMessage = null
    successMessage = null
    viewMode = 'register'
  }

  async function handleProcessPayment() {
    if (!activeCustomer || typeof repaymentAmount !== 'number' || repaymentAmount <= 0) {
      errorMessage = 'Please enter a valid payment amount.'
      return
    }

    isProcessing = true
    errorMessage = null
    try {
      const res = await payDebt(activeCustomer.id, repaymentAmount, repaymentNotes.trim() || undefined)
      successMessage = res.message || `Payment of ₱${repaymentAmount.toFixed(2)} received!`
      if (onPaymentRecorded) {
        onPaymentRecorded(successMessage)
      }
      // Refresh list
      await loadCustomers()
      // Return to list after short pause
      setTimeout(() => {
        viewMode = 'list'
        activeCustomer = null
      }, 1000)
    } catch (err: any) {
      errorMessage = err.message || 'Payment processing failed.'
    } finally {
      isProcessing = false
    }
  }

  async function handleRegisterCustomer() {
    const cleanName = regName.trim()
    if (!cleanName) {
      errorMessage = 'Customer name is required.'
      return
    }

    isProcessing = true
    errorMessage = null
    try {
      const initial = typeof regInitialDebt === 'number' ? regInitialDebt : 0
      await registerDebtCustomer({
        customer_name: cleanName,
        amount_charged: initial,
        phone_number: regPhone.trim() || undefined,
        notes: regNotes.trim() || undefined
      })
      successMessage = `Customer "${cleanName}" registered successfully!`
      await loadCustomers()
      setTimeout(() => {
        viewMode = 'list'
      }, 1000)
    } catch (err: any) {
      errorMessage = err.message || 'Failed to register customer.'
    } finally {
      isProcessing = false
    }
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      if (viewMode !== 'list') {
        viewMode = 'list'
      } else {
        onClose()
      }
    }
  }

  onMount(() => {
    loadCustomers()
  })
</script>

<div
  class="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150"
  onkeydown={handleKeyDown}
  role="dialog"
  aria-modal="true"
  tabindex="-1"
>
  <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl overflow-hidden flex flex-col max-h-[90vh]">
    <!-- Header -->
    <div class="px-5 py-4 bg-slate-900 text-white flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-amber-500 text-white flex items-center justify-center font-bold shadow-xs">
          <BookOpen class="w-5 h-5" />
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-base font-bold tracking-tight">Customer Utang Ledger</h2>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
              F7 SHORTCUT
            </span>
          </div>
          <p class="text-xs text-slate-400">Store Credit, Customer Balances & Repayments</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <!-- Store Total Badge -->
        <div class="hidden sm:flex flex-col text-right">
          <span class="text-[10px] text-slate-400 uppercase font-semibold">Total Outstanding</span>
          <span class="text-sm font-bold font-mono text-amber-400">₱{totalOutstanding.toFixed(2)}</span>
        </div>

        <button
          type="button"
          onclick={onClose}
          class="text-slate-400 hover:text-white p-1 rounded-lg transition-colors cursor-pointer"
        >
          <X class="w-5 h-5" />
        </button>
      </div>
    </div>

    <!-- Notifications banner -->
    {#if errorMessage}
      <div class="px-5 py-2.5 bg-red-50 border-b border-red-200 flex items-center gap-2 text-xs font-semibold text-red-700">
        <AlertCircle class="w-4 h-4 text-red-500 shrink-0" />
        <span>{errorMessage}</span>
      </div>
    {/if}

    {#if successMessage}
      <div class="px-5 py-2.5 bg-emerald-50 border-b border-emerald-200 flex items-center gap-2 text-xs font-semibold text-emerald-700">
        <CheckCircle2 class="w-4 h-4 text-emerald-500 shrink-0" />
        <span>{successMessage}</span>
      </div>
    {/if}

    <!-- Content Views -->
    <div class="p-5 flex-1 overflow-y-auto min-h-[350px]">
      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- VIEW 1: Customer List & Balances -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      {#if viewMode === 'list'}
        <div class="space-y-4">
          <!-- Search & Register Action -->
          <div class="flex flex-col sm:flex-row gap-2.5 items-stretch sm:items-center justify-between">
            <div class="relative flex-1">
              <Search class="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                bind:value={searchQuery}
                oninput={handleSearchInput}
                placeholder="Search customer name or phone..."
                class="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <button
              type="button"
              onclick={openRegister}
              class="flex items-center justify-center gap-1.5 px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl shadow-xs transition-colors cursor-pointer whitespace-nowrap"
            >
              <UserPlus class="w-4 h-4" />
              <span>+ Register Customer</span>
            </button>
          </div>

          <!-- Customer Table -->
          <div class="border border-slate-200 rounded-xl overflow-hidden">
            <table class="w-full text-left text-xs text-slate-600">
              <thead class="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200 text-[10px]">
                <tr>
                  <th class="px-4 py-3">Customer Name</th>
                  <th class="px-4 py-3 text-right">Outstanding Debt</th>
                  <th class="px-4 py-3 text-center hidden sm:table-cell">Contact</th>
                  <th class="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                {#if isLoading}
                  <tr>
                    <td colspan="4" class="px-4 py-10 text-center text-slate-400 font-medium">
                      Loading customer debt records...
                    </td>
                  </tr>
                {:else if customers.length === 0}
                  <tr>
                    <td colspan="4" class="px-4 py-10 text-center text-slate-400 font-medium">
                      {searchQuery ? 'No matching customer accounts found.' : 'No customer debt records in database.'}
                    </td>
                  </tr>
                {:else}
                  {#each customers as c (c.id)}
                    <tr class="hover:bg-slate-50/80 transition-colors">
                      <td class="px-4 py-3">
                        <div class="font-bold text-slate-900">{c.customer_name}</div>
                        {#if c.notes}
                          <div class="text-[10px] text-slate-400">{c.notes}</div>
                        {/if}
                      </td>

                      <td class="px-4 py-3 text-right font-mono font-bold text-sm {c.total_debt > 0 ? 'text-amber-700' : 'text-emerald-600'}">
                        ₱{c.total_debt.toFixed(2)}
                      </td>

                      <td class="px-4 py-3 text-center text-slate-400 font-mono text-[11px] hidden sm:table-cell">
                        {c.phone_number || '—'}
                      </td>

                      <td class="px-4 py-3 text-right space-x-1.5 whitespace-nowrap">
                        <button
                          type="button"
                          onclick={() => viewCustomerHistory(c)}
                          class="px-2.5 py-1 text-[11px] font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors cursor-pointer"
                        >
                          History
                        </button>
                        <button
                          type="button"
                          onclick={() => startPayment(c)}
                          disabled={c.total_debt <= 0}
                          class="px-3 py-1 text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-30 disabled:hover:bg-emerald-600 rounded-lg transition-colors cursor-pointer"
                        >
                          Pay Debt
                        </button>
                      </td>
                    </tr>
                  {/each}
                {/if}
              </tbody>
            </table>
          </div>
        </div>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- VIEW 2: Receive Payment -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      {:else if viewMode === 'pay' && activeCustomer}
        <div class="max-w-md mx-auto space-y-4">
          <div class="flex items-center justify-between pb-2 border-b border-slate-100">
            <button
              type="button"
              onclick={() => viewMode = 'list'}
              class="flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-900 cursor-pointer"
            >
              <ArrowLeft class="w-3.5 h-3.5" />
              <span>Back to Ledger</span>
            </button>
            <span class="text-xs font-bold text-slate-500">Record Cash Repayment</span>
          </div>

          <!-- Customer Balance Card -->
          <div class="bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-center justify-between">
            <div>
              <span class="text-xs text-amber-800 font-bold block">{activeCustomer.customer_name}</span>
              <span class="text-[11px] text-amber-600">Current Outstanding Balance</span>
            </div>
            <span class="text-xl font-mono font-black text-amber-900">
              ₱{activeCustomer.total_debt.toFixed(2)}
            </span>
          </div>

          <!-- Quick Denomination Buttons -->
          <div>
            <span class="block text-[11px] font-semibold text-slate-600 mb-1.5">Quick Payment Amount:</span>
            <div class="grid grid-cols-4 gap-2">
              {#each [50, 100, 200, 500] as amt}
                <button
                  type="button"
                  onclick={() => repaymentAmount = amt}
                  class="py-1.5 text-xs font-mono font-bold rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-emerald-50 hover:border-emerald-300 transition-colors cursor-pointer"
                >
                  ₱{amt}
                </button>
              {/each}
            </div>
            <button
              type="button"
              onclick={() => repaymentAmount = activeCustomer?.total_debt || 0}
              class="w-full mt-2 py-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors cursor-pointer"
            >
              Pay Full Balance (₱{activeCustomer.total_debt.toFixed(2)})
            </button>
          </div>

          <!-- Payment Input -->
          <div>
            <label for="repayInput" class="block text-xs font-bold text-slate-700 mb-1">Payment Received (₱):</label>
            <input
              id="repayInput"
              type="number"
              step="0.01"
              min="0.01"
              bind:value={repaymentAmount}
              placeholder="0.00"
              class="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-lg font-black font-mono text-slate-900 text-right focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <!-- Resulting Balance Preview -->
          <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs">
            <span class="text-slate-500 font-semibold">Remaining Debt After Payment:</span>
            <span class="font-mono font-bold {remainingAfterPayment === 0 ? 'text-emerald-600' : 'text-amber-700'}">
              ₱{remainingAfterPayment.toFixed(2)}
            </span>
          </div>

          <!-- Notes -->
          <div>
            <label for="repayNotes" class="block text-[11px] font-semibold text-slate-600 mb-1">Notes / Remarks (Optional):</label>
            <input
              id="repayNotes"
              type="text"
              bind:value={repaymentNotes}
              placeholder="e.g. Received partial cash payment"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs"
            />
          </div>

          <!-- Submit Button -->
          <button
            type="button"
            onclick={handleProcessPayment}
            disabled={isProcessing || typeof repaymentAmount !== 'number' || repaymentAmount <= 0}
            class="w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm rounded-xl shadow-md transition-colors cursor-pointer disabled:opacity-40"
          >
            {isProcessing ? 'Processing...' : '✓ Confirm Payment & Deposit to Cash Drawer'}
          </button>
        </div>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- VIEW 3: Customer History -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      {:else if viewMode === 'history' && activeCustomer}
        <div class="space-y-4">
          <div class="flex items-center justify-between pb-2 border-b border-slate-100">
            <button
              type="button"
              onclick={() => viewMode = 'list'}
              class="flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-900 cursor-pointer"
            >
              <ArrowLeft class="w-3.5 h-3.5" />
              <span>Back to Ledger</span>
            </button>
            <div class="text-right">
              <span class="text-xs font-bold text-slate-900 block">{activeCustomer.customer_name}</span>
              <span class="text-[10px] text-slate-400">Current: ₱{activeCustomer.total_debt.toFixed(2)}</span>
            </div>
          </div>

          {#if isLoading}
            <div class="py-10 text-center text-xs text-slate-400 font-medium">
              Loading customer transaction records...
            </div>
          {:else if historyList.length === 0}
            <div class="py-10 text-center text-xs text-slate-400 font-medium">
              No transactions recorded for this customer yet.
            </div>
          {:else}
            <div class="space-y-2">
              {#each historyList as h}
                <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs">
                  <div class="flex items-center gap-3">
                    <div class="w-7 h-7 rounded-lg flex items-center justify-center font-bold {h.type === 'CHARGE' ? 'bg-red-100 text-red-700' : h.type === 'PAYMENT' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-700'}">
                      {#if h.type === 'CHARGE'}
                        <ArrowUpRight class="w-4 h-4" />
                      {:else if h.type === 'PAYMENT'}
                        <ArrowDownRight class="w-4 h-4" />
                      {:else}
                        <Clock class="w-4 h-4" />
                      {/if}
                    </div>
                    <div>
                      <div class="font-bold text-slate-900">
                        {h.type === 'CHARGE' ? 'Utang Charged' : h.type === 'PAYMENT' ? 'Debt Payment' : 'Account Registered'}
                        {#if h.receipt_number}
                          <span class="text-[10px] text-slate-400 font-mono ml-1.5">({h.receipt_number})</span>
                        {/if}
                      </div>
                      <div class="text-[10px] text-slate-400">
                        {h.notes || '—'} • {new Date(h.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>

                  <div class="text-right">
                    <div class="font-mono font-bold {h.type === 'CHARGE' ? 'text-red-600' : 'text-emerald-600'}">
                      {h.type === 'CHARGE' ? '+' : '-'}₱{h.amount.toFixed(2)}
                    </div>
                    <div class="text-[10px] text-slate-400 font-mono">
                      Bal: ₱{h.balance_after.toFixed(2)}
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- VIEW 4: Register New Account -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      {:else if viewMode === 'register'}
        <div class="max-w-md mx-auto space-y-4">
          <div class="flex items-center justify-between pb-2 border-b border-slate-100">
            <button
              type="button"
              onclick={() => viewMode = 'list'}
              class="flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-900 cursor-pointer"
            >
              <ArrowLeft class="w-3.5 h-3.5" />
              <span>Back to Ledger</span>
            </button>
            <span class="text-xs font-bold text-slate-500">New Utang Customer</span>
          </div>

          <div>
            <label for="newCustName" class="block text-xs font-bold text-slate-700 mb-1">Customer Full Name *</label>
            <input
              id="newCustName"
              type="text"
              bind:value={regName}
              placeholder="e.g. Aling Nena"
              class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label for="newCustPhone" class="block text-xs font-bold text-slate-700 mb-1">Phone Number (Optional)</label>
            <input
              id="newCustPhone"
              type="text"
              bind:value={regPhone}
              placeholder="09171234567"
              class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label for="newCustInitial" class="block text-xs font-bold text-slate-700 mb-1">Initial Outstanding Debt (₱)</label>
            <input
              id="newCustInitial"
              type="number"
              step="0.01"
              min="0"
              bind:value={regInitialDebt}
              placeholder="0.00"
              class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs font-mono text-right text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label for="newCustNotes" class="block text-xs font-bold text-slate-700 mb-1">Notes / Address (Optional)</label>
            <input
              id="newCustNotes"
              type="text"
              bind:value={regNotes}
              placeholder="e.g. Purok 4, neighbor across street"
              class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <button
            type="button"
            onclick={handleRegisterCustomer}
            disabled={isProcessing || !regName.trim()}
            class="w-full py-3 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl shadow-md transition-colors cursor-pointer disabled:opacity-40"
          >
            {isProcessing ? 'Registering...' : '✓ Create Customer Account'}
          </button>
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="px-5 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
      <div class="flex items-center gap-2">
        <kbd class="px-1.5 py-0.5 font-mono text-[10px] font-bold bg-white border border-slate-300 rounded shadow-2xs">Esc</kbd>
        <span>to close or go back</span>
      </div>
      <button
        type="button"
        onclick={onClose}
        class="font-semibold text-slate-600 hover:text-slate-900 cursor-pointer"
      >
        Close
      </button>
    </div>
  </div>
</div>
