/**
 * Jar QR & Mother-Pack Label Generator Controller
 * ================================================
 */

function labelsApp() {
  return {
    labelItems: [],
    printingItem: null,
    showEditModal: false,
    editForm: {
      id: null,
      name: '',
      unit: 'pc',
      jar_code: '',
      refill_price: 0,
      refill_qty: 1,
      pack_barcode: '',
      pcs_per_pack: 1,
      full_pack_price: 0
    },

    async init() {
      await this.loadItems();
    },

    async loadItems() {
      try {
        const res = await fetch('/api/admin/labels');
        if (res.ok) {
          this.labelItems = await res.json();
          this.$nextTick(() => {
            this.renderAllQRCodes();
          });
        }
      } catch (e) {
        console.error('Failed to load printable labels:', e);
      }
    },

    renderAllQRCodes() {
      this.labelItems.forEach(item => {
        const container = document.getElementById(`qr-preview-${item.id}`);
        if (!container) return;
        container.innerHTML = '';

        const codeVal = item.jar_code || item.pack_barcode || item.barcode;
        if (codeVal && typeof QRCode !== 'undefined') {
          try {
            new QRCode(container, {
              text: codeVal,
              width: 56,
              height: 56,
              correctLevel: QRCode.CorrectLevel.M
            });
          } catch (err) {
            container.innerHTML = `<span class="text-[9px] font-mono text-slate-400">QR</span>`;
          }
        } else {
          container.innerHTML = `<span class="text-[9px] font-mono text-slate-400">No Code</span>`;
        }
      });
    },

    openQuickEdit(item) {
      this.editForm = {
        id: item.id,
        name: item.name,
        unit: item.unit || 'pc',
        jar_code: item.jar_code || '',
        refill_price: item.refill_price || item.selling_price || 0,
        refill_qty: item.refill_qty || 1,
        pack_barcode: item.pack_barcode || '',
        pcs_per_pack: item.pcs_per_pack || 1,
        full_pack_price: item.full_pack_price || 0
      };
      this.showEditModal = true;
    },

    async saveQuickEdit() {
      try {
        const payload = {
          jar_code: this.editForm.jar_code || null,
          refill_price: this.editForm.refill_price ? parseFloat(this.editForm.refill_price) : null,
          refill_qty: this.editForm.refill_qty ? parseFloat(this.editForm.refill_qty) : 1.0,
          pack_barcode: this.editForm.pack_barcode || null,
          pcs_per_pack: this.editForm.pcs_per_pack ? parseInt(this.editForm.pcs_per_pack) : 1,
          full_pack_price: this.editForm.full_pack_price ? parseFloat(this.editForm.full_pack_price) : null,
        };

        const res = await fetch(`/api/products/${this.editForm.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          this.showEditModal = false;
          await this.loadItems();
        } else {
          const err = await res.json();
          alert(err.detail || 'Failed to update item codes.');
        }
      } catch (err) {
        alert('Network error: ' + err.message);
      }
    },

    printSingleLabel(item) {
      this.printingItem = item;
      this.$nextTick(() => {
        const target = document.getElementById('print-qr-target');
        if (target) {
          target.innerHTML = '';
          const codeVal = item.jar_code || item.pack_barcode || item.barcode;
          if (codeVal && typeof QRCode !== 'undefined') {
            new QRCode(target, {
              text: codeVal,
              width: 90,
              height: 90,
              correctLevel: QRCode.CorrectLevel.M
            });
          }
        }
        window.print();
      });
    },

    printAllLabels() {
      window.print();
    }
  };
}
