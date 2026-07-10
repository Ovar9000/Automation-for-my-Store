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
    showWeightModal: false,
    weightInput: '',
    selectedWeightItem: null,
    isProcessing: false,
    notification: { show: false, message: '', type: 'success' },
    editingCartIndex: -1,
    editingQty: '',
    paymentFocused: false,        // F5 two-press flow: true when tendered input focused
    contextMode: 'scan',          // 'scan' | 'search' | 'cart' | 'pay'

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
      if (!val) return;

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
        });
      }
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

      if (!this.paymentFocused) {
        // First press: focus the amount tendered input
        this.paymentFocused = true;
        this.contextMode = 'pay';
        this.$nextTick(() => {
          const el = document.getElementById('amount-tendered');
          if (el) {
            el.focus();
            el.select();
          }
        });
      } else {
        // Second press: complete the sale
        this.processPayment('CASH');
      }
    },

    async processPayment(method = 'CASH') {
      if (this.cart.length === 0) {
        this.showNotification('Cart is empty!', 'error');
        return;
      }

      if (method === 'CASH') {
        const tendered = parseFloat(this.amountTendered) || 0;
        if (tendered < this.total) {
          this.showNotification('Insufficient amount!', 'error');
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
            total_amount: this.total,
            payment_method: method,
            amount_tendered: parseFloat(this.amountTendered) || this.total,
            print_receipt: this.printReceipt,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Transaction failed');
        }

        const result = await res.json();
        const changeAmount = result.change?.toFixed(2) || '0.00';
        this.showNotification(`Sale complete! Change: ₱${changeAmount}`, 'success');

        // Clear cart
        this.cart = [];
        this.amountTendered = '';
        this.selectedCartIndex = -1;
        this.paymentFocused = false;
        this.saveCart();
      } catch (err) {
        this.showNotification('Error: ' + err.message, 'error');
      }

      this.isProcessing = false;
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

      // ── F-Keys always work ──────────────────────────────────
      switch (event.key) {
        case 'F1':
          event.preventDefault();
          this.focusSmartInput();
          return;

        case 'F2':
          event.preventDefault();
          this.openGcashModal('GCASH_IN');
          return;

        case 'F3':
          event.preventDefault();
          this.toggleQuickStrip();
          return;

        case 'F5':
          event.preventDefault();
          this.initiatePayment();
          return;

        case 'F8':
          event.preventDefault();
          this.printZReport();
          return;

        case 'Escape':
          event.preventDefault();
          // Cascading escape: modals → search → payment → barcode
          if (this.showGcashModal) {
            this.showGcashModal = false;
          } else if (this.showWeightModal) {
            this.showWeightModal = false;
          } else if (this.searchResults.length > 0) {
            this.searchResults = [];
            this.selectedSearchIndex = -1;
            this.smartInput = '';
            this.contextMode = 'scan';
          } else if (this.paymentFocused) {
            this.paymentFocused = false;
            this.contextMode = 'scan';
            this.focusSmartInput();
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
