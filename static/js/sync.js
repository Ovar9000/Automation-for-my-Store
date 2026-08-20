/**
 * Cloud Sync & Backup Controller
 * ===============================
 */

function syncApp() {
  return {
    status: {
      database_file: '',
      database_size_kb: 0,
      total_products: 0,
      total_transactions: 0,
      active_debts: 0,
      cloud_sync_endpoint: '',
      last_sync: 'Never'
    },
    config: {
      endpoint: '',
      apiKey: ''
    },
    isSyncing: false,

    async init() {
      if (!sessionStorage.getItem('admin_auth')) {
        window.location.href = '/admin';
        return;
      }
      await this.loadStatus();
      await this.loadConfig();
    },

    async loadStatus() {
      try {
        const res = await fetch('/api/sync/status');
        if (res.ok) {
          this.status = await res.json();
        }
      } catch (e) {
        console.error('Failed to load sync status:', e);
      }
    },

    async loadConfig() {
      try {
        const res = await fetch('/api/admin/settings');
        if (res.ok) {
          const settings = await res.json();
          this.config.endpoint = settings.cloud_sync_endpoint || '';
          this.config.apiKey = settings.cloud_api_key || '';
        }
      } catch (e) {
        console.error('Failed to load cloud config:', e);
      }
    },

    async saveConfig() {
      try {
        await fetch('/api/admin/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: 'cloud_sync_endpoint', value: this.config.endpoint.trim() })
        });
        await fetch('/api/admin/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: 'cloud_api_key', value: this.config.apiKey.trim() })
        });
        alert('Cloud settings saved successfully.');
        await this.loadStatus();
      } catch (e) {
        alert('Failed to save settings: ' + e.message);
      }
    },

    async pushToCloud() {
      if (!this.config.endpoint) {
        alert('Please configure your Cloud Sync Endpoint URL first.');
        return;
      }
      this.isSyncing = true;
      try {
        const res = await fetch('/api/sync/push-to-cloud', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          alert('Success: ' + data.message);
          await this.loadStatus();
        } else {
          alert('Sync Failed: ' + (data.detail || 'Unknown error'));
        }
      } catch (e) {
        alert('Network Error during sync: ' + e.message);
      } finally {
        this.isSyncing = false;
      }
    }
  };
}
