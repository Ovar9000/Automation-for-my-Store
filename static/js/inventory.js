/**
 * Sari-Sari Store POS — Inventory Management Controller
 * ======================================================
 * Alpine JS controller handling Product CRUD operations, stock tracking,
 * alert highlighting, quick-button selections, and Scan & Quick Price UX.
 *
 * Scan & Quick Price:
 *   - Hero barcode input at the top of inventory page
 *   - Scan a barcode → if product found → show Quick Price Card
 *   - Quick Price Card lets admin update cost/selling price inline
 *   - "Save & Next" saves + refocuses scanner for batch pricing
 *   - Unknown barcode → opens Add Product modal with barcode pre-filled
 */

function inventoryApp() {
  return {
    products: [],
    filteredProducts: [],
    searchQuery: '',
    categoryFilter: '',
    categories: [],
    showModal: false,
    showDeleteConfirm: false,
    isEditing: false,
    editingId: null,
    deleteTarget: null,

    // ── Scan & Quick Price state ──────────────────────────────
    scanInput: '',                  // Hero barcode scan input
    quickPriceProduct: null,        // Product object for Quick Price Card
    quickCostPrice: '',             // Editable cost price in Quick Price Card
    quickSellingPrice: '',          // Editable selling price in Quick Price Card
    scanStatus: 'idle',             // 'idle' | 'found' | 'not-found' | 'saving'
    scanNotification: '',           // Feedback message below scan input
    scanNotificationType: '',       // 'success' | 'error' | 'info'
    priceSessionCount: 0,           // Number of items priced in this session

    // Form fields mapped directly to the schema
    form: {
      barcode: '',
      name: '',
      cost_price: 0,
      selling_price: 0,
      stock_qty: 0,
      low_stock_threshold: 5,
      unit: 'pc',
      category: 'General',
      is_quick_item: false,
      quick_button_color: '#10b981',
      pcs_per_pack: 1,
      bulk_cost_price: '',
      full_pack_price: ''
    },

    calculateBulkCost() {
      const pcs = parseInt(this.form.pcs_per_pack) || 1;
      const bulkCost = parseFloat(this.form.bulk_cost_price) || 0;
      if (pcs > 0 && bulkCost > 0) {
        this.form.cost_price = Math.round((bulkCost / pcs) * 100) / 100;
      }
    },

    async init() {
      // Security Check
      if (!sessionStorage.getItem('admin_auth')) {
        window.location.href = '/admin';
        return;
      }
      await this.loadProducts();

      // Auto-focus scan input on load
      this.$nextTick(() => this.focusScanInput());

      // Bind global keyboard shortcuts for scan redirect
      document.addEventListener('keydown', (e) => this.handleScanKeyboard(e));
    },

    // ═══════════════════════════════════════════════════════════
    // SCAN & QUICK PRICE
    // ═══════════════════════════════════════════════════════════

    focusScanInput() {
      const el = document.getElementById('scan-price-input');
      if (el) {
        el.focus();
        el.select();
      }
    },

    /**
     * Handle barcode scan (Enter pressed in scan input).
     * Digits + Enter → barcode lookup via API.
     */
    async onScanEnter() {
      const code = this.scanInput.trim();
      if (!code) return;

      this.scanStatus = 'saving'; // Show spinner briefly
      this.quickPriceProduct = null;
      this.scanNotification = '';

      try {
        const res = await fetch(`/api/products/barcode/${encodeURIComponent(code)}`);

        if (res.ok) {
          // ── Product FOUND ─────────────────────────────────────
          const product = await res.json();
          this.quickPriceProduct = product;
          this.quickCostPrice = Number(product.cost_price).toFixed(2);
          this.quickSellingPrice = Number(product.selling_price).toFixed(2);
          this.scanStatus = 'found';
          this.showScanNotification(`Found: ${product.name}`, 'success');
          this.scanInput = ''; // Clear for next scan

          // Focus cost price input for immediate editing
          this.$nextTick(() => {
            const costEl = document.getElementById('quick-cost-price');
            if (costEl) {
              costEl.focus();
              costEl.select();
            }
          });
        } else {
          // ── Product NOT FOUND ─────────────────────────────────
          this.scanStatus = 'not-found';
          this.showScanNotification(`No product with barcode "${code}" — Register it now?`, 'info');
          // Keep scanInput so user can see the barcode
        }
      } catch (err) {
        this.scanStatus = 'idle';
        this.showScanNotification('Network error: ' + err.message, 'error');
      }
    },

    /**
     * Open Add Product modal with barcode pre-filled.
     */
    openAddWithBarcode() {
      const barcode = this.scanInput.trim();
      this.resetForm();
      this.form.barcode = barcode;
      this.isEditing = false;
      this.editingId = null;
      this.showModal = true;
      this.scanStatus = 'idle';
      this.scanInput = '';
      this.scanNotification = '';
      this.$nextTick(() => {
        const el = document.getElementById('form-name');
        if (el) {
          el.focus();
          el.select();
        }
      });
    },

    /**
     * Dismiss the "not found" prompt and reset.
     */
    dismissScanPrompt() {
      this.scanStatus = 'idle';
      this.scanInput = '';
      this.scanNotification = '';
      this.focusScanInput();
    },

    /**
     * Save quick price changes (cost + selling price only).
     * Then refocus scan input for batch workflow.
     */
    async saveQuickPrice() {
      if (!this.quickPriceProduct) return;

      const cost = parseFloat(this.quickCostPrice);
      const sell = parseFloat(this.quickSellingPrice);

      if (isNaN(cost) || cost < 0) {
        this.showScanNotification('Invalid cost price', 'error');
        return;
      }
      if (isNaN(sell) || sell < 0) {
        this.showScanNotification('Invalid selling price', 'error');
        return;
      }

      this.scanStatus = 'saving';

      try {
        const res = await fetch(`/api/products/${this.quickPriceProduct.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            cost_price: cost,
            selling_price: sell
          })
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to save');
        }

        this.priceSessionCount++;
        this.showScanNotification(
          `✓ ${this.quickPriceProduct.name} — ₱${sell.toFixed(2)} saved! (${this.priceSessionCount} item${this.priceSessionCount > 1 ? 's' : ''} this session)`,
          'success'
        );

        // Close Quick Price Card, reload table, refocus scanner
        this.quickPriceProduct = null;
        this.scanStatus = 'idle';
        await this.loadProducts();
        this.$nextTick(() => this.focusScanInput());

      } catch (err) {
        this.scanStatus = 'found'; // Stay on the card so user can retry
        this.showScanNotification('Save error: ' + err.message, 'error');
      }
    },

    /**
     * Close Quick Price Card without saving.
     */
    closeQuickPrice() {
      this.quickPriceProduct = null;
      this.scanStatus = 'idle';
      this.scanNotification = '';
      this.focusScanInput();
    },

    /**
     * Open the full Edit modal from Quick Price Card.
     */
    editFullDetails() {
      if (this.quickPriceProduct) {
        this.openEditModal(this.quickPriceProduct);
        this.quickPriceProduct = null;
        this.scanStatus = 'idle';
      }
    },

    // ── Computed: Margin ────────────────────────────────────────
    get quickMargin() {
      const cost = parseFloat(this.quickCostPrice) || 0;
      const sell = parseFloat(this.quickSellingPrice) || 0;
      return sell - cost;
    },

    get quickMarginPercent() {
      const cost = parseFloat(this.quickCostPrice) || 0;
      if (cost <= 0) return 0;
      return ((this.quickMargin / cost) * 100);
    },

    // ── Scan Notification ──────────────────────────────────────
    _scanNotifTimeout: null,
    showScanNotification(msg, type = 'info') {
      clearTimeout(this._scanNotifTimeout);
      this.scanNotification = msg;
      this.scanNotificationType = type;
      // Auto-hide after 6s (longer for batch workflow so user can read)
      this._scanNotifTimeout = setTimeout(() => {
        this.scanNotification = '';
      }, 6000);
    },

    // ── Keyboard redirect: digits typed while unfocused → scan input ──
    handleScanKeyboard(event) {
      const tag = event.target.tagName;
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

      // F1 → focus scan input
      if (event.key === 'F1') {
        event.preventDefault();
        this.focusScanInput();
        return;
      }

      // Escape → close Quick Price Card or dismiss prompt
      if (event.key === 'Escape') {
        if (this.quickPriceProduct) {
          event.preventDefault();
          this.closeQuickPrice();
          return;
        }
        if (this.scanStatus === 'not-found') {
          event.preventDefault();
          this.dismissScanPrompt();
          return;
        }
      }

      // Auto-redirect digits to scan input when not in any input field
      if (!isInput && !event.ctrlKey && !event.altKey && !event.metaKey) {
        if (/^\d$/.test(event.key)) {
          this.focusScanInput();
          // Don't prevent default — let the digit type into the now-focused input
        }
      }

      // Enter when product not found → open Register Product modal
      if (event.key === 'Enter' && this.scanStatus === 'not-found' && !this.showModal) {
        event.preventDefault();
        this.openAddWithBarcode();
        return;
      }

      // Enter in Quick Price Card cost/sell inputs → save
      if (event.key === 'Enter' && this.quickPriceProduct) {
        const targetId = event.target.id;
        if (targetId === 'quick-cost-price' || targetId === 'quick-sell-price') {
          event.preventDefault();
          this.saveQuickPrice();
        }
      }

      // Tab between cost and sell in Quick Price Card
      if (event.key === 'Tab' && !event.shiftKey && this.quickPriceProduct) {
        const targetId = event.target.id;
        if (targetId === 'quick-cost-price') {
          event.preventDefault();
          const sellEl = document.getElementById('quick-sell-price');
          if (sellEl) {
            sellEl.focus();
            sellEl.select();
          }
        }
      }
    },

    // ═══════════════════════════════════════════════════════════
    // ORIGINAL INVENTORY CRUD (unchanged)
    // ═══════════════════════════════════════════════════════════

    async loadProducts() {
      try {
        const res = await fetch('/api/products');
        if (!res.ok) throw new Error('Failed to load products');
        
        this.products = await res.json();
        
        // Extract unique categories for filter list
        this.categories = [...new Set(this.products.map(p => p.category))].filter(Boolean);
        this.filterProducts();
      } catch (err) {
        console.error('Error loading inventory products:', err);
      }
    },

    filterProducts() {
      const query = this.searchQuery.toLowerCase().trim();
      this.filteredProducts = this.products.filter(p => {
        const matchesSearch = !query || p.name.toLowerCase().includes(query) || (p.barcode && p.barcode.includes(query));
        const matchesCat = !this.categoryFilter || p.category === this.categoryFilter;
        return matchesSearch && matchesCat;
      });
    },

    openAddModal() {
      this.isEditing = false;
      this.editingId = null;
      this.resetForm();
      this.showModal = true;
    },

    openEditModal(product) {
      this.isEditing = true;
      this.editingId = product.id;
      
      // Load current values into form model
      Object.keys(this.form).forEach(key => {
        if (product[key] !== undefined) {
          this.form[key] = product[key];
        }
      });
      this.showModal = true;
    },

    async saveProduct() {
      if (!this.form.name || !this.form.name.trim()) {
        alert('Please enter a Product Name before saving.');
        return;
      }
      const sellPrice = parseFloat(this.form.selling_price) || 0;
      if (sellPrice <= 0) {
        alert('Please enter a valid Selling Price (> ₱0.00) before saving.');
        return;
      }

      const url = this.isEditing ? `/api/products/${this.editingId}` : '/api/products';
      const method = this.isEditing ? 'PUT' : 'POST';

      try {
        const body = {
          ...this.form,
          name: this.form.name.trim(),
          cost_price: parseFloat(this.form.cost_price) || 0,
          selling_price: sellPrice,
          stock_qty: parseFloat(this.form.stock_qty) || 0,
          low_stock_threshold: parseFloat(this.form.low_stock_threshold) || 0,
          barcode: this.form.barcode && this.form.barcode.trim() ? this.form.barcode.trim() : null,
          pcs_per_pack: parseInt(this.form.pcs_per_pack) || 1,
          bulk_cost_price: this.form.bulk_cost_price !== '' && this.form.bulk_cost_price !== null ? parseFloat(this.form.bulk_cost_price) : null,
          full_pack_price: this.form.full_pack_price !== '' && this.form.full_pack_price !== null ? parseFloat(this.form.full_pack_price) : null
        };

        const res = await fetch(url, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });

        if (!res.ok) {
          const errData = await res.json();
          alert(errData.detail || 'Failed to save product details.');
          return;
        }

        this.showModal = false;
        await this.loadProducts();
        this.$nextTick(() => this.focusScanInput());
      } catch (err) {
        console.error('Save product error:', err);
        alert('Server validation or connection error.');
      }
    },

    confirmDelete(product) {
      this.deleteTarget = product;
      this.showDeleteConfirm = true;
    },

    async deleteProduct() {
      if (!this.deleteTarget) return;

      try {
        const res = await fetch(`/api/products/${this.deleteTarget.id}`, {
          method: 'DELETE'
        });

        if (!res.ok) throw new Error('Delete failed');

        this.showDeleteConfirm = false;
        this.deleteTarget = null;
        await this.loadProducts();
      } catch (err) {
        console.error('Delete product error:', err);
        alert('Could not delete product.');
      }
    },

    resetForm() {
      this.form = {
        barcode: '',
        name: '',
        cost_price: 0,
        selling_price: 0,
        stock_qty: 0,
        low_stock_threshold: 5,
        unit: 'pc',
        category: 'General',
        is_quick_item: false,
        quick_button_color: '#10b981',
        pcs_per_pack: 1,
        bulk_cost_price: '',
        full_pack_price: ''
      };
    },

    formatCurrency(n) {
      return '₱' + Number(n || 0).toFixed(2);
    },

    logout() {
      sessionStorage.removeItem('admin_auth');
      window.location.href = '/admin';
    }
  };
}
