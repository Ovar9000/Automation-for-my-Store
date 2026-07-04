/**
 * Sari-Sari Store POS — Inventory Management Controller
 * ======================================================
 * Alpine JS controller handling Product CRUD operations, stock tracking,
 * alert highlighting, and quick-button selections.
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
      quick_button_color: '#10b981'
    },

    async init() {
      // Security Check
      if (!sessionStorage.getItem('admin_auth')) {
        window.location.href = '/admin';
        return;
      }
      await this.loadProducts();
    },

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
      const url = this.isEditing ? `/api/products/${this.editingId}` : '/api/products';
      const method = this.isEditing ? 'PUT' : 'POST';

      try {
        // Map form values to JSON request body.
        // Ensure values are numbers before transmitting.
        const body = {
          ...this.form,
          cost_price: parseFloat(this.form.cost_price) || 0,
          selling_price: parseFloat(this.form.selling_price) || 0,
          stock_qty: parseFloat(this.form.stock_qty) || 0,
          low_stock_threshold: parseFloat(this.form.low_stock_threshold) || 0,
          barcode: this.form.barcode.trim() || null
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
        quick_button_color: '#10b981'
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
