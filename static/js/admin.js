/**
 * Sari-Sari Store POS — Admin Dashboard Controller
 * ==================================================
 * Handles session authentication verification and daily report overview fetching.
 */

function adminDashboard() {
  return {
    report: null,
    lowStockProducts: [],
    recentTransactions: [],
    isLoading: true,

    async init() {
      // ── Security Check ──
      // Verify session login before loading dashboard metrics
      if (!sessionStorage.getItem('admin_auth')) {
        window.location.href = '/admin';
        return;
      }
      await this.loadDashboard();
    },

    async loadDashboard() {
      this.isLoading = true;
      try {
        const [reportRes, lowStockRes, txnRes] = await Promise.all([
          fetch('/api/reports/daily'),
          fetch('/api/products/low-stock'),
          fetch('/api/transactions/today'),
        ]);

        if (reportRes.ok) this.report = await reportRes.json();
        if (lowStockRes.ok) this.lowStockProducts = await lowStockRes.json();
        if (txnRes.ok) {
          const txns = await txnRes.json();
          // Sort by timestamp desc and take top 20
          this.recentTransactions = txns
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
            .slice(0, 20);
        }
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      } finally {
        this.isLoading = false;
      }
    },

    logout() {
      sessionStorage.removeItem('admin_auth');
      window.location.href = '/admin';
    },

    formatCurrency(n) {
      return '₱' + Number(n || 0).toLocaleString('en-PH', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    }
  };
}
