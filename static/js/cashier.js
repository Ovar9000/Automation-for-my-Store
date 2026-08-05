/* ============================================================
   Sari-Sari POS — Cashier App (Keyboard-First Fork)
   ============================================================
   Design philosophy:
   - Barcode scanner input is the PRIMARY interaction
   - Keyboard shortcuts for ALL actions (no mouse required)
   - Unified smart input: digits + Enter → barcode, letters → search
   - Arrow-key navigation for search results and cart items
   ============================================================ */

function cashierApp() {
  return {
    // ── State ─────────────────────────────────────────────────
    cart: [],
    smartInput: '',               // Unified barcode + search input
    searchResults: [],
    selectedSearchIndex: -1,      // Keyboard nav: highlighted search result
    selectedCartIndex: -1,        // Keyboard nav: highlighted cart item
    quickItems: [],
    quickStripOpen: true,         // Quick items strip expanded by default
    amountTendered: '',
    printReceipt: false,
    showGcashModal: false,
    showPaymentModal: false,       // Big Payment Checkout Modal
    paymentTab: 'cash',            // 'cash' | 'gcash'
    showSuccessModal: false,       // Post-sale change display modal
    lastSaleDetails: { total: 0, tendered: 0, change: 0, itemsCount: 0 },
    lastScannedProduct: null,     // Most recently scanned item object
    showBundleBanner: false,      // Show Multi-Pack conversion banner
    showWeightModal: false,
    weightInput: '',
    selectedWeightItem: null,
    isProcessing: false,
    notification: { show: false, message: '', type: 'success' },
    editingCartIndex: -1,
    editingQty: '',
    paymentFocused: false,        // F5 flow
    contextMode: 'scan',          // 'scan' | 'search' | 'cart' | 'pay'

    // Customer Debt (Utang) State
    showDebtLedgerModal: false,
    debtCustomers: [],
    debtSearchQuery: '',
    debtCustomerName: '',
    debtPaidNow: '',
    showRepaymentModal: false,
    selectedDebtCustomer: null,
    repaymentAmount: '',

    // ── Computed ──────────────────────────────────────────────
    get total() {
      return this.cart.reduce((sum, item) => sum + item.subtotal, 0);
    },

    get totalItems() {
      return this.cart.reduce((sum, item) => sum + item.quantity, 0);
    },

    get change() {
      const tendered = parseFloat(this.amountTendered) || 0;
      return Math.max(0, tendered - this.total);
    },

    // Determine if input looks like a barcode (all digits, optionally with dashes)
    get inputLooksLikeBarcode() {
      return /^[\d\-]+$/.test(this.smartInput.trim());
    },

    // ── Lifecycle ────────────────────────────────────────────
    init() {
      // Restore cart from localStorage
      try {
        const saved = localStorage.getItem('pos_cart');
        if (saved) {
          this.cart = JSON.parse(saved);
        }
      } catch (e) {
        console.warn('Failed to restore cart from localStorage:', e);
        this.cart = [];
      }

      // Load quick-access items
      this.loadQuickItems();

      // Auto-focus smart input
      this.$nextTick(() => this.focusSmartInput());

      // Bind global keyboard shortcuts
      document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    },

    // ═══════════════════════════════════════════════════════════
    // UNIFIED SMART INPUT
    // ═══════════════════════════════════════════════════════════

    /**
     * Called on every keystroke in the smart input (debounced for search).
     * If input contains letters → product name search.
     * If input is all digits → just wait for Enter (barcode scan).
     */
    onSmartInput() {
      const val = this.smartInput.trim();

      if (!val) {
        this.searchResults = [];
        this.selectedSearchIndex = -1;
        this.contextMode = 'scan';
        return;
      }

      if (this.inputLooksLikeBarcode) {
        // Pure digits: barcode mode — don't search, wait for Enter
        this.searchResults = [];
        this.selectedSearchIndex = -1;
        this.contextMode = 'scan';
      } else {
        // Contains letters: name search mode
        this.contextMode = 'search';
        this.debouncedSearch();
      }
    },

    /**
     * Called on Enter in the smart input.
     * If barcode-like → barcode lookup API.
     * If search results visible + item selected → add selected to cart.
     * If search results visible + no selection → select first result.
     */
    async onSmartEnter() {
      const val = this.smartInput.trim();
      if (!val) {
        if (this.cart.length > 0) {
          this.initiatePayment();
        }
        return;
      }

      // If search results are showing and we have a selection
      if (this.searchResults.length > 0 && this.selectedSearchIndex >= 0) {
        this.selectSearchResult(this.searchResults[this.selectedSearchIndex]);
        return;
      }

      // If search results are showing but no selection, select first
      if (this.searchResults.length > 0 && !this.inputLooksLikeBarcode) {
        this.selectSearchResult(this.searchResults[0]);
        return;
      }

      // Otherwise treat as barcode scan
      await this.scanBarcode(val);
    },

    // Debounce helper for search
    _searchTimeout: null,
    debouncedSearch() {
      clearTimeout(this._searchTimeout);
      this._searchTimeout = setTimeout(() => {
        this.searchProducts();
      }, 200);
    },

    // ── Cart Operations ──────────────────────────────────────
    _bundleBannerTimeout: null,
    addToCart(product, quantity = 1) {
      const existing = this.cart.find(item => item.product_id === product.id);
      if (existing) {
        existing.quantity += quantity;
        existing.subtotal = Math.round(existing.quantity * existing.unit_price * 100) / 100;
      } else {
        this.cart.push({
          product_id: product.id,
          product_name: product.name,
          quantity: quantity,
          unit: product.unit || 'pc',
          unit_price: product.selling_price,
          cost_price: product.cost_price,
          subtotal: Math.round(quantity * product.selling_price * 100) / 100,
          pcs_per_pack: product.pcs_per_pack || 12,
          full_pack_price: product.full_pack_price || null,
          pack_label: null
        });
      }

      this.lastScannedProduct = product;
      this.showBundleBanner = true;
      clearTimeout(this._bundleBannerTimeout);
      this._bundleBannerTimeout = setTimeout(() => {
        this.showBundleBanner = false;
      }, 6000);

      this.saveCart();
      this.showNotification(`${product.name} added`);
      this.focusSmartInput();

      // Trigger total pulse animation
      this.$nextTick(() => {
        const el = document.getElementById('cart-total');
        if (el) {
          el.classList.remove('total-pulse');
          void el.offsetWidth; // force reflow
          el.classList.add('total-pulse');
        }
      });
    },

    convertLastItemToPack(packType) {
      if (!this.lastScannedProduct || this.cart.length === 0) return;

      const item = this.cart.find(i => i.product_id === this.lastScannedProduct.id);
      if (!item) return;

      const packSize = this.lastScannedProduct.pcs_per_pack || 12;
      const halfQty = Math.max(1, Math.round(packSize / 2));
      const fullQty = packSize;

      if (packType === 'half') {
        item.quantity = halfQty;
        if (item.full_pack_price) {
          item.subtotal = Math.round((item.full_pack_price / 2) * 100) / 100;
        } else {
          item.subtotal = Math.round(halfQty * item.unit_price * 100) / 100;
        }
        item.pack_label = `Half-Pack (${halfQty}pcs)`;
        this.showNotification(`✓ ${item.product_name} converted to Half-Pack (${halfQty}pcs) — ₱${item.subtotal.toFixed(2)}`, 'success');
      } else if (packType === 'dozen' || packType === 'full') {
        item.quantity = fullQty;
        if (item.full_pack_price) {
          item.subtotal = Math.round(item.full_pack_price * 100) / 100;
        } else {
          item.subtotal = Math.round(fullQty * item.unit_price * 100) / 100;
        }
        item.pack_label = `Full-Pack (${fullQty}pcs)`;
        this.showNotification(`✓ ${item.product_name} converted to Full-Pack (${fullQty}pcs) — ₱${item.subtotal.toFixed(2)}`, 'success');
      }

      this.showBundleBanner = false;
      this.saveCart();
      this.focusSmartInput();
    },

    removeFromCart(index) {
      const name = this.cart[index]?.product_name || 'Item';
      this.cart.splice(index, 1);
      this.saveCart();
      // Adjust selected cart index
      if (this.selectedCartIndex >= this.cart.length) {
        this.selectedCartIndex = this.cart.length - 1;
      }
      this.showNotification(`${name} removed`, 'info');
    },

    updateQuantity(index, newQty) {
      const qty = parseFloat(newQty);
      if (qty <= 0 || isNaN(qty)) {
        this.removeFromCart(index);
        return;
      }
      this.cart[index].quantity = qty;
      this.cart[index].subtotal = Math.round(qty * this.cart[index].unit_price * 100) / 100;
      this.saveCart();
      this.editingCartIndex = -1;
    },

    startEditingQty(index) {
      this.editingCartIndex = index;
      this.editingQty = String(this.cart[index].quantity);
      this.$nextTick(() => {
        const input = document.getElementById(`qty-edit-${index}`);
        if (input) {
          input.focus();
          input.select();
        }
      });
    },

    clearCart() {
      if (this.cart.length === 0) return;
      this.cart = [];
      this.amountTendered = '';
      this.selectedCartIndex = -1;
      this.saveCart();
      this.showNotification('Cart cleared', 'info');
    },

    saveCart() {
      try {
        localStorage.setItem('pos_cart', JSON.stringify(this.cart));
      } catch (e) {
        console.warn('Failed to save cart to localStorage:', e);
      }
    },

    // ── Barcode Scanning ─────────────────────────────────────
    async scanBarcode(code) {
      if (!code) code = this.smartInput.trim();
      if (!code) return;

      try {
        const res = await fetch(`/api/products/barcode/${encodeURIComponent(code)}`);
        if (!res.ok) {
          this.showNotification('Product not found!', 'error');
          this.smartInput = '';
          this.focusSmartInput();
          return;
        }
        const product = await res.json();
        if (product.unit === 'kg' || product.unit === 'L') {
          this.selectedWeightItem = product;
          this.weightInput = '';
          this.showWeightModal = true;
        } else {
          this.addToCart(product);
        }
      } catch (err) {
        this.showNotification('Scan error: ' + err.message, 'error');
      }
      this.smartInput = '';
      this.focusSmartInput();
    },

    focusSmartInput() {
      this.contextMode = 'scan';
      this.paymentFocused = false;
      this.selectedCartIndex = -1;
      const el = document.getElementById('smart-input');
      if (el) el.focus();
    },

    // Legacy alias for compatibility
    focusBarcode() {
      this.focusSmartInput();
    },

    // ── Product Search ───────────────────────────────────────
    async searchProducts() {
      const q = this.smartInput.trim();
      if (q.length < 2 || this.inputLooksLikeBarcode) {
        this.searchResults = [];
        this.selectedSearchIndex = -1;
        return;
      }
      try {
        const res = await fetch(`/api/products/search?q=${encodeURIComponent(q)}`);
        if (res.ok) {
          this.searchResults = await res.json();
          this.selectedSearchIndex = this.searchResults.length > 0 ? 0 : -1;
        }
      } catch (err) {
        console.error('Search error:', err);
      }
    },

    selectSearchResult(product) {
      if (product.unit === 'kg' || product.unit === 'L') {
        this.selectedWeightItem = product;
        this.weightInput = '';
        this.showWeightModal = true;
      } else {
        this.addToCart(product);
      }
      this.smartInput = '';
      this.searchResults = [];
      this.selectedSearchIndex = -1;
      this.contextMode = 'scan';
    },

    // ── Quick Items ──────────────────────────────────────────
    async loadQuickItems() {
      try {
        const res = await fetch('/api/products/quick');
        if (res.ok) {
          this.quickItems = await res.json();
        }
      } catch (err) {
        console.error('Failed to load quick items:', err);
      }
    },

    addQuickItem(item) {
      if (item.unit === 'kg' || item.unit === 'L') {
        this.selectedWeightItem = item;
        this.weightInput = '';
        this.showWeightModal = true;
      } else {
        this.addToCart(item);
      }
    },

    toggleQuickStrip() {
      this.quickStripOpen = !this.quickStripOpen;
    },

    addWeightedItem() {
      const weight = parseFloat(this.weightInput);
      if (!weight || weight <= 0) {
        this.showNotification('Enter a valid weight/quantity', 'error');
        return;
      }
      this.addToCart(this.selectedWeightItem, weight);
      this.showWeightModal = false;
      this.selectedWeightItem = null;
      this.weightInput = '';
    },

    // ── Payment Processing ───────────────────────────────────
    /**
     * F5 two-press flow:
     * 1st press: focus amount tendered input
     * 2nd press (or Enter in tendered field): complete sale
     */
    initiatePayment() {
      if (this.cart.length === 0) {
        this.showNotification('Cart is empty!', 'error');
        return;
      }

      this.showPaymentModal = true;
      this.paymentTab = 'cash';
      this.contextMode = 'pay';
      if (!this.amountTendered) {
        this.amountTendered = String(this.total);
      }

      this.$nextTick(() => {
        const el = document.getElementById('big-amount-tendered');
        if (el) {
          el.focus();
          el.select();
        }
      });
    },

    async processPayment(method = 'CASH') {
      if (this.cart.length === 0) {
        this.showNotification('Cart is empty!', 'error');
        return;
      }

      const currentTotal = this.total;
      const currentItems = this.totalItems;
      const tenderedVal = parseFloat(this.amountTendered) || currentTotal;

      if (method === 'CASH') {
        if (tenderedVal < currentTotal) {
          this.showNotification('Insufficient amount tendered!', 'error');
          return;
        }
      }

      this.isProcessing = true;

      try {
        const res = await fetch('/api/transactions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            items: this.cart,
            total_amount: currentTotal,
            payment_method: method,
            amount_tendered: tenderedVal,
            print_receipt: this.printReceipt,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Transaction failed');
        }

        const result = await res.json();
        const changeAmount = result.change !== undefined ? result.change : Math.max(0, tenderedVal - currentTotal);

        // Store last sale details for the Big Success Modal
        this.lastSaleDetails = {
          total: currentTotal,
          tendered: tenderedVal,
          change: changeAmount,
          itemsCount: currentItems,
          method: method
        };

        this.showPaymentModal = false;
        this.showSuccessModal = true;

        // Clear cart
        this.cart = [];
        this.amountTendered = '';
        this.selectedCartIndex = -1;
        this.paymentFocused = false;
        this.saveCart();

        this.showNotification(`Sale complete! Change: ₱${changeAmount.toFixed(2)}`, 'success');
      } catch (err) {
        this.showNotification('Error: ' + err.message, 'error');
      }

      this.isProcessing = false;
    },

    closeSuccessModal() {
      this.showSuccessModal = false;
      this.contextMode = 'scan';
      this.focusSmartInput();
    },

    // ── Quick Denomination ───────────────────────────────────
    setDenomination(amount) {
      this.amountTendered = String(amount);
    },

    addDenomination(amount) {
      const current = parseFloat(this.amountTendered) || 0;
      this.amountTendered = String(current + amount);
    },

    // ── Z-Report ─────────────────────────────────────────────
    async printZReport() {
      try {
        const res = await fetch('/api/print/z-report', { method: 'POST' });
        if (!res.ok) throw new Error('Z-Report request failed');
        const result = await res.json();
        this.showNotification('Z-Report generated!', 'success');
        if (result.report_text) {
          alert(result.report_text);
        }
      } catch (err) {
        this.showNotification('Z-Report error: ' + err.message, 'error');
      }
    },

    // ── Customer Debt (Utang) Operations ──────────────────────
    async openDebtLedgerModal() {
      this.showDebtLedgerModal = true;
      await this.loadDebtList();
    },

    async loadDebtList() {
      try {
        const query = this.debtSearchQuery.trim() ? `?search=${encodeURIComponent(this.debtSearchQuery.trim())}` : '';
        const res = await fetch(`/api/debts${query}`);
        if (res.ok) {
          this.debtCustomers = await res.json();
        }
      } catch (err) {
        console.error('Load debt list error:', err);
      }
    },

    focusDebtCustomerInput() {
      this.$nextTick(() => {
        const el = document.getElementById('debt-customer-name');
        if (el) { el.focus(); el.select(); }
      });
    },

    async processUtangSale() {
      if (!this.debtCustomerName.trim()) {
        alert('Please enter a customer name for the debt record.');
        return;
      }

      if (this.cart.length === 0) return;
      this.isProcessing = true;

      try {
        // 1. Process store checkout
        const payload = {
          items: this.cart.map(i => ({
            product_id: i.product_id,
            quantity: i.quantity,
            unit_price: i.unit_price,
            cost_price: i.cost_price,
            subtotal: i.subtotal
          })),
          total_amount: this.total,
          payment_type: 'UTANG',
          amount_tendered: parseFloat(this.debtPaidNow) || 0,
          change_amount: 0,
          notes: `Utang sale for ${this.debtCustomerName.trim()}`
        };

        const res = await fetch('/api/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Checkout failed');
        }

        const saleResult = await res.json();

        // 2. Charge balance to customer debt account
        const amountPaidNow = parseFloat(this.debtPaidNow) || 0;
        const amountCharged = Math.max(0, this.total - amountPaidNow);

        if (amountCharged > 0) {
          await fetch('/api/debts/charge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              customer_name: this.debtCustomerName.trim(),
              sale_id: saleResult.id,
              amount_charged: amountCharged,
              amount_paid_now: amountPaidNow,
              notes: `Store Sale #${saleResult.receipt_number}`
            })
          });
        }

        this.lastSaleDetails = {
          total: this.total,
          tendered: amountPaidNow,
          change: 0,
          itemsCount: this.totalItems
        };

        this.showPaymentModal = false;
        this.showSuccessModal = true;
        this.clearCart();
        this.debtCustomerName = '';
        this.debtPaidNow = '';
        await this.loadDebtList();
      } catch (err) {
        console.error('Utang sale error:', err);
        alert(err.message || 'Utang transaction failed.');
      } finally {
        this.isProcessing = false;
      }
    },

    openRepaymentModal(customer) {
      this.selectedDebtCustomer = customer;
      this.repaymentAmount = '';
      this.showRepaymentModal = true;
    },

    async processDebtRepayment() {
      if (!this.selectedDebtCustomer || !this.repaymentAmount || this.repaymentAmount <= 0) return;

      this.isProcessing = true;
      try {
        const res = await fetch(`/api/debts/${this.selectedDebtCustomer.id}/pay`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            payment_amount: parseFloat(this.repaymentAmount),
            notes: 'Cash debt repayment received at POS'
          })
        });

        if (!res.ok) throw new Error('Payment failed');

        const result = await res.json();
        this.showNotification(result.message, 'success');
        this.showRepaymentModal = false;
        await this.loadDebtList();
      } catch (err) {
        console.error('Repayment error:', err);
        alert('Debt repayment failed.');
      } finally {
        this.isProcessing = false;
      }
    },

    openGcashModal(type) {
      this.showGcashModal = true;
      this.$nextTick(() => {
        window.dispatchEvent(new CustomEvent('set-gcash-type', { detail: type }));
      });
    },

    // ═══════════════════════════════════════════════════════════
    // KEYBOARD SHORTCUT HANDLER (Keyboard-First)
    // ═══════════════════════════════════════════════════════════
    handleKeyboard(event) {
      const tag = event.target.tagName;
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA';
      const isSmartInput = event.target.id === 'smart-input';
      const isTenderedInput = event.target.id === 'amount-tendered';

      // ── Modal specific key handlers ───────────────────────
      if (this.showSuccessModal) {
        if (event.key === 'Enter' || event.key === 'Escape' || event.key === ' ') {
          event.preventDefault();
          this.closeSuccessModal();
          return;
        }
      }

      // ── Multi-Pack Hotkey Conversion ([1] for 6pcs, [2] for 12pcs) ──
      if (this.showBundleBanner && !this.showPaymentModal && !this.showSuccessModal && !this.showGcashModal && !this.showWeightModal) {
        if (event.key === '1' && (isSmartInput ? this.smartInput === '' : !isInput)) {
          event.preventDefault();
          this.convertLastItemToPack('half');
          return;
        }
        if (event.key === '2' && (isSmartInput ? this.smartInput === '' : !isInput)) {
          event.preventDefault();
          this.convertLastItemToPack('dozen');
          return;
        }
      }

      if (this.showPaymentModal) {
        if (event.key === 'Escape') {
          event.preventDefault();
          this.showPaymentModal = false;
          this.contextMode = 'scan';
          this.focusSmartInput();
          return;
        }
        if (event.key === 'F1') {
          event.preventDefault();
          this.paymentTab = 'cash';
          this.$nextTick(() => {
            const el = document.getElementById('big-amount-tendered');
            if (el) { el.focus(); el.select(); }
          });
          return;
        }
        if (event.key === 'F2') {
          event.preventDefault();
          this.paymentTab = 'gcash';
          return;
        }
        if (event.key === 'F4') {
          event.preventDefault();
          this.paymentTab = 'utang';
          this.focusDebtCustomerInput();
          return;
        }
        if (event.key === 'Enter') {
          const targetId = event.target.id;
          if (this.paymentTab === 'utang') {
            event.preventDefault();
            this.processUtangSale();
            return;
          } else if (targetId === 'big-amount-tendered' || !isInput) {
            event.preventDefault();
            this.processPayment(this.paymentTab === 'cash' ? 'CASH' : 'GCASH');
            return;
          }
        }
      }

      // ── F-Keys always work ──────────────────────────────────
      switch (event.key) {
        case 'F1':
          if (!this.showPaymentModal) {
            event.preventDefault();
            this.focusSmartInput();
            return;
          }
          break;

        case 'F2':
          if (!this.showPaymentModal) {
            event.preventDefault();
            this.openGcashModal('GCASH_IN');
            return;
          }
          break;

        case 'F3':
          event.preventDefault();
          this.focusSmartInput();
          return;

        case 'F4':
          event.preventDefault();
          if (this.cart.length > 0) {
            this.initiatePayment();
            this.paymentTab = 'utang';
            this.focusDebtCustomerInput();
          }
          return;

        case 'F5':
          event.preventDefault();
          if (!this.showPaymentModal) {
            this.initiatePayment();
          } else {
            this.processPayment(this.paymentTab === 'cash' ? 'CASH' : 'GCASH');
          }
          return;

        case 'F7':
          event.preventDefault();
          this.openDebtLedgerModal();
          return;

        case 'F8':
          event.preventDefault();
          this.printZReport();
          return;

        case 'F9':
          event.preventDefault();
          window.location.href = '/admin/inventory';
          return;

        case 'Escape':
          event.preventDefault();
          // Cascading escape: modals → search → payment → barcode
          if (this.showGcashModal) {
            this.showGcashModal = false;
          } else if (this.showWeightModal) {
            this.showWeightModal = false;
          } else if (this.showPaymentModal) {
            this.showPaymentModal = false;
            this.focusSmartInput();
          } else if (this.searchResults.length > 0) {
            this.searchResults = [];
            this.selectedSearchIndex = -1;
            this.smartInput = '';
            this.contextMode = 'scan';
          } else if (this.editingCartIndex >= 0) {
            this.editingCartIndex = -1;
          } else if (this.selectedCartIndex >= 0) {
            this.selectedCartIndex = -1;
            this.contextMode = 'scan';
            this.focusSmartInput();
          } else {
            this.smartInput = '';
            this.focusSmartInput();
          }
          return;
      }

      // ── Arrow keys in smart input: navigate search results ──
      if (isSmartInput && this.searchResults.length > 0) {
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          this.selectedSearchIndex = Math.min(
            this.selectedSearchIndex + 1,
            this.searchResults.length - 1
          );
          this.scrollSearchResultIntoView();
          return;
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault();
          this.selectedSearchIndex = Math.max(this.selectedSearchIndex - 1, 0);
          this.scrollSearchResultIntoView();
          return;
        }
      }

      // ── Enter in amount tendered: complete payment ──────────
      if (isTenderedInput && event.key === 'Enter') {
        event.preventDefault();
        this.processPayment('CASH');
        return;
      }

      // ── Tab key: cycle context modes ────────────────────────
      if (event.key === 'Tab' && !event.shiftKey && !isInput) {
        event.preventDefault();
        if (this.contextMode === 'scan' && this.cart.length > 0) {
          // Switch to cart navigation
          this.contextMode = 'cart';
          this.selectedCartIndex = 0;
        } else if (this.contextMode === 'cart') {
          // Switch back to scan
          this.contextMode = 'scan';
          this.selectedCartIndex = -1;
          this.focusSmartInput();
        }
        return;
      }

      // ── Cart navigation when not in an input field ──────────
      if (!isInput && this.contextMode === 'cart' && this.cart.length > 0) {
        switch (event.key) {
          case 'ArrowDown':
            event.preventDefault();
            this.selectedCartIndex = Math.min(
              this.selectedCartIndex + 1,
              this.cart.length - 1
            );
            this.scrollCartItemIntoView();
            return;

          case 'ArrowUp':
            event.preventDefault();
            this.selectedCartIndex = Math.max(this.selectedCartIndex - 1, 0);
            this.scrollCartItemIntoView();
            return;

          case 'Delete':
          case 'Backspace':
            event.preventDefault();
            if (this.selectedCartIndex >= 0 && this.selectedCartIndex < this.cart.length) {
              this.removeFromCart(this.selectedCartIndex);
            }
            return;

          case '+':
          case '=':
            event.preventDefault();
            if (this.selectedCartIndex >= 0) {
              const item = this.cart[this.selectedCartIndex];
              if (item.unit === 'pc') {
                item.quantity += 1;
                item.subtotal = Math.round(item.quantity * item.unit_price * 100) / 100;
                this.saveCart();
              }
            }
            return;

          case '-':
            event.preventDefault();
            if (this.selectedCartIndex >= 0) {
              const item = this.cart[this.selectedCartIndex];
              if (item.unit === 'pc' && item.quantity > 1) {
                item.quantity -= 1;
                item.subtotal = Math.round(item.quantity * item.unit_price * 100) / 100;
                this.saveCart();
              } else if (item.quantity <= 1) {
                this.removeFromCart(this.selectedCartIndex);
              }
            }
            return;

          case 'Enter':
            event.preventDefault();
            if (this.selectedCartIndex >= 0) {
              this.startEditingQty(this.selectedCartIndex);
            }
            return;
        }
      }

      // ── Any printable char while not in input → focus smart input ──
      if (!isInput && !event.ctrlKey && !event.altKey && !event.metaKey) {
        if (event.key.length === 1) {
          // Single printable character — redirect to smart input
          this.focusSmartInput();
          // Don't prevent default — let the character type into the now-focused input
        }
      }
    },

    // ── Scroll helpers ───────────────────────────────────────
    scrollSearchResultIntoView() {
      this.$nextTick(() => {
        const el = document.querySelector(`.search-result-row.kb-selected`);
        if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
    },

    scrollCartItemIntoView() {
      this.$nextTick(() => {
        const el = document.querySelector(`.cart-item.kb-selected`);
        if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
    },

    // ── Notifications ────────────────────────────────────────
    showNotification(message, type = 'success') {
      this.notification = { show: true, message, type };
      setTimeout(() => {
        this.notification.show = false;
      }, 3000);
    },

    // ── Formatting Helpers ───────────────────────────────────
    formatPrice(n) {
      return '₱' + Number(n).toFixed(2);
    },

    formatQty(item) {
      if (item.unit === 'kg' || item.unit === 'L') {
        return item.quantity.toFixed(2) + ' ' + item.unit;
      }
      return item.quantity + 'x';
    },
  };
}
