/**
 * Sari-Sari POS — Cashier Controller (Clean Minimalist Edition)
 * =============================================================
 * Fast, keyboard-first, barcode-enabled cashier terminal.
 * Features:
 *  - Unified smart input (auto-detects barcodes vs product names)
 *  - Arrow-key navigation for search results and cart items
 *  - Atomic CASH, GCASH, and UTANG (Debt) checkout flows
 *  - Multi-pack pricing with clean inline selection
 *  - Crash-resistant localStorage cart synchronization
 */

function cashierApp() {
  return {
    // ── State ─────────────────────────────────────────────────
    cart: [],
    smartInput: '',
    searchResults: [],
    selectedSearchIndex: -1,
    selectedCartIndex: -1,
    quickItems: [],
    amountTendered: '',
    printReceipt: false,
    showGcashModal: false,
    showPaymentModal: false,
    paymentTab: 'cash',            // 'cash' | 'gcash' | 'utang'
    showSuccessModal: false,
    lastSaleDetails: { total: 0, tendered: 0, change: 0, itemsCount: 0, method: 'CASH', receiptNo: '' },
    lastScannedProduct: null,
    showBundleBanner: false,
    showWeightModal: false,
    weightInput: '',
    selectedWeightItem: null,
    isProcessing: false,
    notification: { show: false, message: '', type: 'success' },
    editingCartIndex: -1,
    editingQty: '',
    contextMode: 'scan',          // 'scan' | 'search' | 'cart' | 'pay'

    // Customer Debt (Utang) State
    showDebtLedgerModal: false,
    debtCustomers: [],
    debtSearchQuery: '',
    debtCustomerName: '',
    showDebtDropdown: false,
    debtPaidNow: '',
    showRepaymentModal: false,
    selectedDebtCustomer: null,
    repaymentAmount: '',
    showAddCustomerModal: false,
    newCustomerName: '',
    newCustomerPhone: '',
    newCustomerInitialDebt: '',

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

    get inputLooksLikeBarcode() {
      return /^[\d\-]+$/.test(this.smartInput.trim());
    },

    // ── Lifecycle ─────────────────────────────────────────────
    init() {
      try {
        const saved = localStorage.getItem('pos_cart');
        if (saved) {
          this.cart = JSON.parse(saved);
        }
      } catch (e) {
        console.warn('Failed to restore cart from localStorage:', e);
        this.cart = [];
      }

      this.loadQuickItems();
      this.loadDebtList();

      this.$nextTick(() => this.focusSmartInput());
      document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    },

    // ═══════════════════════════════════════════════════════════
    // SMART INPUT & BARCODE SCANNING
    // ═══════════════════════════════════════════════════════════

    onSmartInput() {
      const val = this.smartInput.trim();

      if (!val) {
        this.searchResults = [];
        this.selectedSearchIndex = -1;
        this.contextMode = 'scan';
        return;
      }

      if (this.inputLooksLikeBarcode) {
        this.searchResults = [];
        this.selectedSearchIndex = -1;
        this.contextMode = 'scan';
      } else {
        this.contextMode = 'search';
        this.debouncedSearch();
      }
    },

    async onSmartEnter() {
      const val = this.smartInput.trim();
      if (!val) {
        if (this.cart.length > 0) {
          this.initiatePayment();
        }
        return;
      }

      if (this.searchResults.length > 0 && this.selectedSearchIndex >= 0) {
        this.selectSearchResult(this.searchResults[this.selectedSearchIndex]);
        return;
      }

      if (this.searchResults.length > 0 && !this.inputLooksLikeBarcode) {
        this.selectSearchResult(this.searchResults[0]);
        return;
      }

      await this.scanBarcode(val);
    },

    _searchTimeout: null,
    debouncedSearch() {
      clearTimeout(this._searchTimeout);
      this._searchTimeout = setTimeout(() => {
        this.searchProducts();
      }, 180);
    },

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

    async scanBarcode(code) {
      if (!code) code = this.smartInput.trim();
      if (!code) return;

      try {
        const res = await fetch(`/api/products/barcode/${encodeURIComponent(code)}`);
        if (!res.ok) {
          this.showNotification(`No product with barcode "${code}"`, 'error');
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
      this.selectedCartIndex = -1;
      const el = document.getElementById('smart-input');
      if (el) el.focus();
    },

    // ═══════════════════════════════════════════════════════════
    // CART OPERATIONS
    // ═══════════════════════════════════════════════════════════

    _bundleBannerTimeout: null,
    addToCart(product, quantity = 1) {
      const existing = this.cart.find(item => item.product_id === product.id && !item.pack_label);
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
          pcs_per_pack: product.pcs_per_pack || 10,
          full_pack_price: product.full_pack_price || null,
          half_dozen_price: product.half_dozen_price || null,
          dozen_price: product.dozen_price || null,
          stock_qty: product.stock_qty,
          low_stock_threshold: product.low_stock_threshold,
          pack_label: null
        });
      }

      this.lastScannedProduct = product;
      if (product.pcs_per_pack && product.pcs_per_pack > 1) {
        this.showBundleBanner = true;
        clearTimeout(this._bundleBannerTimeout);
        this._bundleBannerTimeout = setTimeout(() => {
          this.showBundleBanner = false;
        }, 5000);
      }

      this.saveCart();
      this.showNotification(`Added ${product.name}`);
      this.focusSmartInput();

      this.$nextTick(() => {
        const el = document.getElementById('cart-total');
        if (el) {
          el.classList.remove('total-pulse');
          void el.offsetWidth;
          el.classList.add('total-pulse');
        }
      });
    },

    convertLastItemToPack(packType) {
      if (!this.lastScannedProduct || this.cart.length === 0) return;
      const item = this.cart.find(i => i.product_id === this.lastScannedProduct.id);
      if (!item) return;

      const packSize = this.lastScannedProduct.pcs_per_pack || 10;
      const halfQty = Math.max(1, Math.round(packSize / 2));
      const fullQty = packSize;

      if (packType === 'half') {
        item.quantity = halfQty;
        if (item.full_pack_price) {
          item.subtotal = Math.round((item.full_pack_price / 2) * 100) / 100;
        } else if (item.half_dozen_price) {
          item.subtotal = Math.round(item.half_dozen_price * 100) / 100;
        } else {
          item.subtotal = Math.round(halfQty * item.unit_price * 100) / 100;
        }
        item.pack_label = `Half-Pack (${halfQty}pcs)`;
        this.showNotification(`Set to Half-Pack (${halfQty}pcs) — ₱${item.subtotal.toFixed(2)}`, 'success');
      } else if (packType === 'full' || packType === 'dozen') {
        item.quantity = fullQty;
        if (item.full_pack_price) {
          item.subtotal = Math.round(item.full_pack_price * 100) / 100;
        } else if (item.dozen_price) {
          item.subtotal = Math.round(item.dozen_price * 100) / 100;
        } else {
          item.subtotal = Math.round(fullQty * item.unit_price * 100) / 100;
        }
        item.pack_label = `Full-Pack (${fullQty}pcs)`;
        this.showNotification(`Set to Full-Pack (${fullQty}pcs) — ₱${item.subtotal.toFixed(2)}`, 'success');
      }

      this.showBundleBanner = false;
      this.saveCart();
      this.focusSmartInput();
    },

    removeFromCart(index) {
      const name = this.cart[index]?.product_name || 'Item';
      this.cart.splice(index, 1);
      this.saveCart();
      if (this.selectedCartIndex >= this.cart.length) {
        this.selectedCartIndex = this.cart.length - 1;
      }
      this.showNotification(`Removed ${name}`, 'info');
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
      this.focusSmartInput();
    },

    saveCart() {
      try {
        localStorage.setItem('pos_cart', JSON.stringify(this.cart));
      } catch (e) {
        console.warn('Failed to save cart:', e);
      }
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

    addWeightedItem() {
      const weight = parseFloat(this.weightInput);
      if (!weight || weight <= 0) {
        this.showNotification('Please enter a valid amount', 'error');
        return;
      }
      this.addToCart(this.selectedWeightItem, weight);
      this.showWeightModal = false;
      this.selectedWeightItem = null;
      this.weightInput = '';
    },

    // ═══════════════════════════════════════════════════════════
    // CHECKOUT & ATOMIC PAYMENT
    // ═══════════════════════════════════════════════════════════

    initiatePayment() {
      if (this.cart.length === 0) {
        this.showNotification('Cart is empty', 'error');
        return;
      }

      this.showPaymentModal = true;
      this.paymentTab = 'cash';
      this.contextMode = 'pay';
      if (!this.amountTendered) {
        this.amountTendered = String(this.total);
      }

      this.$nextTick(() => {
        const el = document.getElementById('amount-tendered');
        if (el) {
          el.focus();
          el.select();
        }
      });
    },

    async processPayment(method = 'CASH') {
      if (this.cart.length === 0) return;

      const currentTotal = this.total;
      const currentItems = this.totalItems;
      const tenderedVal = parseFloat(this.amountTendered) || currentTotal;

      if (method === 'CASH' && tenderedVal < currentTotal) {
        this.showNotification('Amount tendered is less than total', 'error');
        return;
      }

      this.isProcessing = true;

      try {
        const payload = {
          items: this.cart,
          total_amount: currentTotal,
          payment_method: method,
          amount_tendered: method === 'CASH' ? tenderedVal : currentTotal,
          print_receipt: this.printReceipt,
        };

        const res = await fetch('/api/transactions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Transaction failed');
        }

        const result = await res.json();
        const changeAmount = result.change !== undefined ? result.change : Math.max(0, tenderedVal - currentTotal);

        this.lastSaleDetails = {
          total: currentTotal,
          tendered: method === 'CASH' ? tenderedVal : currentTotal,
          change: changeAmount,
          itemsCount: currentItems,
          method: method,
          receiptNo: result.receipt_number || `#${result.id}`
        };

        this.showPaymentModal = false;
        this.showSuccessModal = true;

        this.cart = [];
        this.amountTendered = '';
        this.selectedCartIndex = -1;
        this.saveCart();

        this.showNotification(`Sale complete! Change: ₱${changeAmount.toFixed(2)}`, 'success');
      } catch (err) {
        this.showNotification('Error: ' + err.message, 'error');
      } finally {
        this.isProcessing = false;
      }
    },

    async processUtangSale() {
      const custName = this.debtCustomerName.trim();
      if (!custName) {
        this.showNotification('Please enter a customer name for the debt record', 'error');
        return;
      }

      if (this.cart.length === 0) return;
      this.isProcessing = true;

      try {
        const amountPaidNow = parseFloat(this.debtPaidNow) || 0;

        const res = await fetch('/api/transactions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            items: this.cart,
            total_amount: this.total,
            payment_method: 'UTANG',
            amount_tendered: amountPaidNow,
            amount_paid_now: amountPaidNow,
            customer_name: custName,
            print_receipt: false,
          })
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Utang transaction failed');
        }

        const result = await res.json();

        this.lastSaleDetails = {
          total: this.total,
          tendered: amountPaidNow,
          change: 0,
          itemsCount: this.totalItems,
          method: 'UTANG',
          receiptNo: result.receipt_number || `#${result.id}`
        };

        this.showPaymentModal = false;
        this.showSuccessModal = true;
        this.cart = [];
        this.saveCart();
        this.debtCustomerName = '';
        this.debtPaidNow = '';
        await this.loadDebtList();
        this.showNotification(`Utang sale charged to ${custName}`, 'success');
      } catch (err) {
        this.showNotification(err.message || 'Utang sale failed', 'error');
      } finally {
        this.isProcessing = false;
      }
    },

    closeSuccessModal() {
      this.showSuccessModal = false;
      this.contextMode = 'scan';
      this.focusSmartInput();
    },

    // ── Quick Denominations ──────────────────────────────────
    setDenomination(amount) {
      this.amountTendered = String(amount);
    },

    setExactTendered() {
      this.amountTendered = String(this.total);
    },

    // ── End of Day Z-Report ───────────────────────────────────
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

    // ── Utang Ledger Management ──────────────────────────────
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

    findDebtCustomer(name) {
      if (!name || !name.trim()) return null;
      const clean = name.trim().toLowerCase();
      return this.debtCustomers.find(c => c.customer_name.toLowerCase() === clean) || null;
    },

    getMatchingDebtCustomers() {
      if (!this.debtCustomerName || !this.debtCustomerName.trim()) return this.debtCustomers.slice(0, 5);
      const query = this.debtCustomerName.trim().toLowerCase();
      return this.debtCustomers.filter(c => c.customer_name.toLowerCase().includes(query)).slice(0, 5);
    },

    focusDebtCustomerInput() {
      this.$nextTick(() => {
        const el = document.getElementById('debt-customer-name');
        if (el) { el.focus(); el.select(); }
      });
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
        this.showNotification('Debt repayment failed', 'error');
      } finally {
        this.isProcessing = false;
      }
    },

    async createNewCustomerAccount() {
      if (!this.newCustomerName.trim()) return;

      this.isProcessing = true;
      try {
        const initialDebt = parseFloat(this.newCustomerInitialDebt) || 0;
        const res = await fetch('/api/debts/charge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            customer_name: this.newCustomerName.trim(),
            amount_charged: initialDebt > 0 ? initialDebt : 0.01,
            phone_number: this.newCustomerPhone.trim() || null,
            notes: 'Registered via Utang Ledger'
          })
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to create customer account');
        }

        this.showNotification(`Created customer '${this.newCustomerName.trim()}'`, 'success');
        this.showAddCustomerModal = false;
        this.newCustomerName = '';
        this.newCustomerPhone = '';
        this.newCustomerInitialDebt = '';
        await this.loadDebtList();
      } catch (err) {
        this.showNotification(err.message || 'Failed to create customer', 'error');
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
    // KEYBOARD NAVIGATION HANDLER
    // ═══════════════════════════════════════════════════════════
    handleKeyboard(event) {
      const tag = event.target.tagName;
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
      const isSmartInput = event.target.id === 'smart-input';
      const isTenderedInput = event.target.id === 'amount-tendered';

      // ── Modal Dismiss / Complete with Enter/Esc ────────────
      if (this.showSuccessModal) {
        if (event.key === 'Enter' || event.key === 'Escape' || event.key === ' ') {
          event.preventDefault();
          this.closeSuccessModal();
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
            const el = document.getElementById('amount-tendered');
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
          if (this.paymentTab === 'utang') {
            event.preventDefault();
            this.processUtangSale();
            return;
          } else if (isTenderedInput || !isInput) {
            event.preventDefault();
            this.processPayment(this.paymentTab === 'cash' ? 'CASH' : 'GCASH');
            return;
          }
        }
      }

      // ── Function Keys ──────────────────────────────────────
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

        case 'Escape':
          event.preventDefault();
          if (this.showGcashModal) {
            this.showGcashModal = false;
          } else if (this.showWeightModal) {
            this.showWeightModal = false;
          } else if (this.showDebtLedgerModal) {
            this.showDebtLedgerModal = false;
            this.focusSmartInput();
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

      // ── Search Navigation (Arrow keys in smart input) ──────
      if (isSmartInput && this.searchResults.length > 0) {
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          this.selectedSearchIndex = Math.min(this.selectedSearchIndex + 1, this.searchResults.length - 1);
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

      // ── Tab: Cycle focus between smart input and cart list ─
      if (event.key === 'Tab' && !event.shiftKey && !isInput) {
        event.preventDefault();
        if (this.contextMode === 'scan' && this.cart.length > 0) {
          this.contextMode = 'cart';
          this.selectedCartIndex = 0;
        } else if (this.contextMode === 'cart') {
          this.contextMode = 'scan';
          this.selectedCartIndex = -1;
          this.focusSmartInput();
        }
        return;
      }

      // ── Cart Navigation (When not in any input field) ──────
      if (!isInput && this.contextMode === 'cart' && this.cart.length > 0) {
        switch (event.key) {
          case 'ArrowDown':
            event.preventDefault();
            this.selectedCartIndex = Math.min(this.selectedCartIndex + 1, this.cart.length - 1);
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

      // ── Auto-redirect printable keystrokes to smart input ──
      if (!isInput && !event.ctrlKey && !event.altKey && !event.metaKey) {
        if (event.key.length === 1) {
          this.focusSmartInput();
        }
      }
    },

    scrollSearchResultIntoView() {
      this.$nextTick(() => {
        const el = document.querySelector(`.search-row.kb-selected`);
        if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
    },

    scrollCartItemIntoView() {
      this.$nextTick(() => {
        const el = document.querySelector(`.cart-row.kb-selected`);
        if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
    },

    showNotification(message, type = 'success') {
      this.notification = { show: true, message, type };
      setTimeout(() => {
        this.notification.show = false;
      }, 3000);
    },

    formatPrice(n) {
      return '₱' + Number(n || 0).toLocaleString('en-PH', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    },

    formatQty(item) {
      if (item.unit === 'kg' || item.unit === 'L') {
        return item.quantity.toFixed(2) + ' ' + item.unit;
      }
      return item.quantity + 'x';
    },
  };
}
