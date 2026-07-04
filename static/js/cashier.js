/* ============================================================
   Sari-Sari POS — Cashier App (Alpine.js Component)
   ============================================================ */

function cashierApp() {
  return {
    // ── State ─────────────────────────────────────────────────
    cart: [],
    barcodeInput: '',
    searchQuery: '',
    searchResults: [],
    quickItems: [],
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

      // Auto-focus barcode input
      this.$nextTick(() => this.focusBarcode());

      // Bind global keyboard shortcuts
      document.addEventListener('keydown', (e) => this.handleKeyboard(e));
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
      this.focusBarcode();

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
      this.cart.splice(index, 1);
      this.saveCart();
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
    async scanBarcode() {
      const code = this.barcodeInput.trim();
      if (!code) return;

      try {
        const res = await fetch(`/api/products/barcode/${encodeURIComponent(code)}`);
        if (!res.ok) {
          this.showNotification('Product not found!', 'error');
          this.barcodeInput = '';
          this.focusBarcode();
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
      this.barcodeInput = '';
      this.focusBarcode();
    },

    focusBarcode() {
      const el = document.getElementById('barcode-input');
      if (el) el.focus();
    },

    // ── Product Search ───────────────────────────────────────
    async searchProducts() {
      if (this.searchQuery.length < 2) {
        this.searchResults = [];
        return;
      }
      try {
        const res = await fetch(`/api/products/search?q=${encodeURIComponent(this.searchQuery)}`);
        if (res.ok) {
          this.searchResults = await res.json();
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
      this.searchQuery = '';
      this.searchResults = [];
    },

    closeSearch() {
      // Delay to allow click events to fire first
      setTimeout(() => {
        this.searchResults = [];
      }, 200);
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
        this.saveCart();
      } catch (err) {
        this.showNotification('Error: ' + err.message, 'error');
      }

      this.isProcessing = false;
      this.focusBarcode();
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

    // ── Keyboard Shortcuts ───────────────────────────────────
    handleKeyboard(event) {
      // Don't intercept if user is typing inside an input/textarea (except F-keys)
      const tag = event.target.tagName;
      const isFKey = event.key.startsWith('F') && event.key.length <= 3;

      switch (event.key) {
        case 'F1':
          event.preventDefault();
          this.focusBarcode();
          break;
        case 'F2':
          event.preventDefault();
          this.openGcashModal('GCASH_IN');
          break;
        case 'F5':
          event.preventDefault();
          this.processPayment('CASH');
          break;
        case 'Escape':
          this.showGcashModal = false;
          this.showWeightModal = false;
          this.editingCartIndex = -1;
          this.searchResults = [];
          break;
        case 'F8':
          event.preventDefault();
          this.printZReport();
          break;
      }
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
