/* ============================================================
   Sari-Sari POS — GCash Component (Alpine.js)
   ============================================================ */

function gcashApp() {
  return {
    // ── State ─────────────────────────────────────────────────
    flowType: 'A',           // 'A' = I know the principal, 'B' = Customer gave me total
    amount: '',
    transactionType: 'GCASH_IN',   // 'GCASH_IN' or 'GCASH_OUT'
    result: null,
    isCalculating: false,
    error: '',
    debounceTimer: null,

    // ── Debounced Calculate ──────────────────────────────────
    scheduleCalculate() {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.calculate(), 300);
    },

    // ── Calculate Fee ────────────────────────────────────────
    async calculate() {
      const amt = parseFloat(this.amount);
      if (!amt || amt <= 0) {
        this.result = null;
        this.error = '';
        return;
      }

      this.isCalculating = true;
      this.error = '';

      try {
        const res = await fetch('/api/gcash/calculate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            amount: amt,
            flow_type: this.flowType,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Calculation failed');
        }

        this.result = await res.json();
        this.error = '';
      } catch (err) {
        this.error = err.message;
        this.result = null;
      }

      this.isCalculating = false;
    },

    // ── Confirm Transaction ──────────────────────────────────
    async confirm(cashierAppRef) {
      if (!this.result) return;

      this.error = '';

      try {
        const res = await fetch('/api/gcash/transact', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            flow_type: this.result.flow_type,
            input_amount: this.result.input_amount,
            principal_amount: this.result.principal_amount,
            fee: this.result.fee,
            total_collected: this.result.total_collected,
            transaction_type: this.transactionType,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'GCash transaction failed');
        }

        const txLabel = this.transactionType === 'GCASH_IN' ? 'Cash-In' : 'Cash-Out';
        cashierAppRef.showNotification(
          `GCash ${txLabel} recorded! Fee earned: ${this.formatPrice(this.result.fee)}`,
          'success'
        );
        cashierAppRef.showGcashModal = false;
        this.reset();
      } catch (err) {
        this.error = err.message;
      }
    },

    // ── Reset ────────────────────────────────────────────────
    reset() {
      this.flowType = 'A';
      this.amount = '';
      this.transactionType = 'GCASH_IN';
      this.result = null;
      this.error = '';
      clearTimeout(this.debounceTimer);
    },

    // ── Switch Flow (re-calculate if amount present) ─────────
    switchFlow(type) {
      this.flowType = type;
      this.result = null;
      if (this.amount) {
        this.scheduleCalculate();
      }
    },

    // ── Formatting ───────────────────────────────────────────
    formatPrice(n) {
      return '₱' + Number(n).toFixed(2);
    },
  };
}
