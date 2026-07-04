/**
 * Sari-Sari Store POS — Admin GCash Audit Controller
 * ====================================================
 * Alpine JS controller managing GCash transactions list, filtering,
 * fee total calculation, and local receipt image viewer popups.
 */

function adminGcashApp() {
  return {
    transactions: [],
    filteredTransactions: [],
    searchQuery: '',
    typeFilter: '',
    
    // Modal popup state for previewing base64 snapshots
    showImageModal: false,
    modalImage: '',
    modalTxn: null,

    async init() {
      // Security Check
      if (!sessionStorage.getItem('admin_auth')) {
        window.location.href = '/admin';
        return;
      }
      await this.loadTransactions();
    },

    async loadTransactions() {
      try {
        const res = await fetch('/api/gcash/transactions');
        if (!res.ok) throw new Error('Failed to load GCash transaction database.');
        
        this.transactions = await res.json();
        this.filterTransactions();
      } catch (err) {
        console.error('Error loading GCash transaction database:', err);
      }
    },

    filterTransactions() {
      const query = this.searchQuery.toLowerCase().trim();
      const type = this.typeFilter; // 'GCASH_IN' or 'GCASH_OUT'

      this.filteredTransactions = this.transactions.filter(t => {
        // Search matches: Mobile Number, Reference No, date/time timestamps
        const matchesQuery = !query || 
          (t.mobile_number && t.mobile_number.toLowerCase().includes(query)) ||
          (t.reference_number && t.reference_number.toLowerCase().includes(query)) ||
          (t.gcash_timestamp && t.gcash_timestamp.toLowerCase().includes(query)) ||
          t.system_created_at.includes(query);

        const matchesType = !type || t.transaction_type === type;
        return matchesQuery && matchesType;
      });
    },

    totalFeesEarned() {
      return this.filteredTransactions.reduce((sum, t) => sum + (t.fee || 0), 0);
    },

    openImageModal(img, txn) {
      this.modalImage = img;
      this.modalTxn = txn;
      this.showImageModal = true;
    },

    formatSystemDate(dateStr) {
      if (!dateStr) return '—';
      try {
        // Parse "YYYY-MM-DD HH:MM:SS"
        const d = new Date(dateStr.replace(' ', 'T') + 'Z');
        return d.toLocaleDateString('en-PH', {
          year: 'numeric',
          month: 'short',
          day: '2-digit'
        }) + ' ' + d.toLocaleTimeString('en-PH', {
          hour: '2-digit',
          minute: '2-digit'
        });
      } catch (e) {
        return dateStr;
      }
    },

    formatCurrency(n) {
      return '₱' + Number(n || 0).toLocaleString('en-PH', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    },

    logout() {
      sessionStorage.removeItem('admin_auth');
      window.location.href = '/admin';
    }
  };
}
