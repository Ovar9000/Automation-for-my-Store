/**
 * Sari-Sari Store POS — Reports and Analytics Controller
 * =======================================================
 * Alpine JS controller managing daily receipts audit, monthly summaries,
 * and top products analytics displaying pure CSS bar graphs.
 */

function reportsApp() {
  return {
    activeTab: 'daily',
    
    // Daily report state
    dailyDate: new Date().toISOString().split('T')[0],
    dailyReport: null,
    
    // Monthly report state
    monthlyYear: new Date().getFullYear(),
    monthlyMonth: new Date().getMonth() + 1,
    monthlyReport: null,

    // Product ranking analytics state
    topProducts: [],
    topPeriod: 'day',      // 'day', 'month', 'all'
    topSortBy: 'quantity', // 'quantity', 'revenue', 'profit'
    topLimit: 10,
    maxTopValue: 1,

    async init() {
      // Security Check
      if (!sessionStorage.getItem('admin_auth')) {
        window.location.href = '/admin';
        return;
      }
      await this.loadDailyReport();
    },

    async loadDailyReport() {
      try {
        const res = await fetch(`/api/reports/daily?date=${this.dailyDate}`);
        if (res.ok) {
          this.dailyReport = await res.json();
        }
      } catch (err) {
        console.error('Error loading daily report:', err);
      }
    },

    async loadMonthlyReport() {
      try {
        const res = await fetch(`/api/reports/monthly?year=${this.monthlyYear}&month=${this.monthlyMonth}`);
        if (res.ok) {
          this.monthlyReport = await res.json();
        }
      } catch (err) {
        console.error('Error loading monthly report:', err);
      }
    },

    async loadTopProducts() {
      try {
        const res = await fetch(`/api/reports/top-products?period=${this.topPeriod}&sort_by=${this.topSortBy}&limit=${this.topLimit}`);
        if (res.ok) {
          this.topProducts = await res.json();
          
          // Calculate max value for horizontal bar graph scale factor
          if (this.topProducts.length > 0) {
            const key = this.topSortBy === 'quantity' 
              ? 'total_qty_sold' 
              : this.topSortBy === 'revenue' 
                ? 'total_revenue' 
                : 'total_profit';
            
            this.maxTopValue = Math.max(...this.topProducts.map(p => p[key])) || 1;
          } else {
            this.maxTopValue = 1;
          }
        }
      } catch (err) {
        console.error('Error loading top products analytics:', err);
      }
    },

    switchTab(tab) {
      this.activeTab = tab;
      if (tab === 'daily') {
        this.loadDailyReport();
      } else if (tab === 'monthly') {
        this.loadMonthlyReport();
      } else if (tab === 'top') {
        this.loadTopProducts();
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
