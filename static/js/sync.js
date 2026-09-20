/**
 * Cloud Sync & Supabase Backup Controller
 * ========================================
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
      last_sync: 'Never',
      supabase_url: '',
      supabase_bucket: 'store-backups',
      last_supabase_sync: 'Never'
    },
    supabase: {
      url: 'https://dveufoeavxegvcgityax.supabase.co',
      key: 'sb_publishable_HRsrNqo7SMk_H90617TQ3Q_VJqZR5KC',
      bucket: 'store-backups'
    },
    config: {
      endpoint: '',
      apiKey: ''
    },
    supabaseConnected: false,
    isTestingSupabase: false,
    isUploadingSupabase: false,
    isSyncing: false,
    supabaseBackups: [],

    async init() {
      if (!sessionStorage.getItem('admin_auth')) {
        window.location.href = '/admin';
        return;
      }
      await this.loadStatus();
      await this.loadConfig();
      await this.testSupabase(true); // background silent test
      await this.loadSupabaseBackups();
    },

    async loadStatus() {
      try {
        const res = await fetch('/api/sync/status');
        if (res.ok) {
          this.status = await res.json();
          if (this.status.supabase_url) this.supabase.url = this.status.supabase_url;
          if (this.status.supabase_bucket) this.supabase.bucket = this.status.supabase_bucket;
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
          if (settings.supabase_url) this.supabase.url = settings.supabase_url;
          if (settings.supabase_key) this.supabase.key = settings.supabase_key;
          if (settings.supabase_bucket) this.supabase.bucket = settings.supabase_bucket;
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
        alert('Web portal settings saved successfully.');
        await this.loadStatus();
      } catch (e) {
        alert('Failed to save settings: ' + e.message);
      }
    },

    async saveSupabaseConfig() {
      try {
        const res = await fetch('/api/sync/supabase/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: this.supabase.url.trim(),
            key: this.supabase.key.trim(),
            bucket: this.supabase.bucket.trim()
          })
        });
        const data = await res.json();
        if (res.ok) {
          alert('Supabase configuration saved successfully.');
          await this.testSupabase();
          await this.loadStatus();
        } else {
          alert('Error: ' + (data.detail || 'Could not save settings'));
        }
      } catch (e) {
        alert('Failed to save Supabase settings: ' + e.message);
      }
    },

    async testSupabase(silent = false) {
      this.isTestingSupabase = true;
      try {
        const res = await fetch('/api/sync/supabase/test', { method: 'POST' });
        const data = await res.json();
        this.supabaseConnected = data.connected === true;
        if (!silent) {
          if (this.supabaseConnected) {
            let msg = '🟢 Connected to Supabase!\n- Auth Service: ' + data.auth_service + '\n- Storage Service: ' + data.storage_service;
            if (!data.bucket_exists) {
              msg += '\n\n⚠️ Bucket "' + this.supabase.bucket + '" not found yet.\nRun the supabase_schema.sql script in your Supabase SQL editor to create it.';
            }
            alert(msg);
          } else {
            alert('🔴 Failed to connect to Supabase:\n' + (data.error || 'Check your URL and API key.'));
          }
        }
      } catch (e) {
        this.supabaseConnected = false;
        if (!silent) alert('Network error testing Supabase: ' + e.message);
      } finally {
        this.isTestingSupabase = false;
      }
    },

    async uploadToSupabase() {
      this.isUploadingSupabase = true;
      try {
        const res = await fetch('/api/sync/supabase/upload-backup', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
          alert('✅ ' + data.message);
          await this.loadStatus();
          await this.loadSupabaseBackups();
        } else {
          alert('❌ Upload Failed:\n' + (data.error || data.detail || 'Unknown error'));
        }
      } catch (e) {
        alert('Network Error during upload: ' + e.message);
      } finally {
        this.isUploadingSupabase = false;
      }
    },

    async loadSupabaseBackups() {
      try {
        const res = await fetch('/api/sync/supabase/backups');
        if (res.ok) {
          const list = await res.json();
          this.supabaseBackups = Array.isArray(list) ? list : [];
        }
      } catch (e) {
        console.error('Failed to load backup list:', e);
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
