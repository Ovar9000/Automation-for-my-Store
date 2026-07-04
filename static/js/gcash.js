/* ============================================================
   Sari-Sari POS — GCash Component (Alpine.js)
   ============================================================ */

function gcashApp() {
  return {
    // ── State ─────────────────────────────────────────────────
    flowType: 'A',                 // 'A' = I know the principal, 'B' = Customer gave me total
    amount: '',
    transactionType: 'GCASH_IN',   // 'GCASH_IN' or 'GCASH_OUT'
    result: null,
    isCalculating: false,
    error: '',
    debounceTimer: null,

    // Step state for camera scanner flow
    step: 1,                       // 1 = calculation, 2 = scanner/details step
    mobileNumber: '',
    referenceNumber: '',
    receiptImage: null,
    gcashTimestamp: '',            // GCash receipt date/time
    useCamera: false,
    videoStream: null,
    isOcrScanning: false,          // OCR loading indicator

    // ── Lifecycle Init ────────────────────────────────────────
    init() {
      // Listen for window event dispatched by cashierApp to pre-select type
      window.addEventListener('set-gcash-type', (e) => {
        this.reset();
        this.transactionType = e.detail;
        
        if (this.transactionType === 'GCASH_OUT') {
          // Cash-Out: Go directly to photo taking / details step
          this.step = 2;
          this.flowType = 'B'; // Cash-Out always uses Flow B (reverse calc on amount sent)
          this.startCamera();
        } else {
          // Cash-In: Start on calculation step 1
          this.step = 1;
          this.flowType = 'A';
        }
      });
    },

    // ── Debounced Calculate ──────────────────────────────────
    scheduleCalculate() {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => this.calculate(), 300);
    },

    // ── Calculate Fee ────────────────────────────────────────
    async calculate() {
      const amt = parseFloat(this.amount);
      if (!amt || amt <= 0) {
        this.result = null;
        this.error = '';
        return;
      }

      this.isCalculating = true;
      this.error = '';

      try {
        const res = await fetch('/api/gcash/calculate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            amount: amt,
            flow_type: this.flowType,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Calculation failed');
        }

        this.result = await res.json();
        this.error = '';
      } catch (err) {
        this.error = err.message;
        this.result = null;
      }

      this.isCalculating = false;
    },

    // ── Next Step (For Cash-In) ──────────────────────────────
    async nextStep() {
      if (!this.result) return;
      this.step = 2;
      
      // Auto-set timestamp to current time as default
      this.gcashTimestamp = new Date().toLocaleString('en-PH');
      await this.startCamera(); // Both Cash-In and Cash-Out open camera on Step 2
    },

    // ── Back to step 1 (For Cash-In only) ───────────────────
    prevStep() {
      this.step = 1;
      this.stopCamera();
    },

    // ── Camera Methods ───────────────────────────────────────
    async startCamera() {
      this.stopCamera();
      this.useCamera = false;
      this.receiptImage = null;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } }
        });
        this.videoStream = stream;
        
        // Wait for DOM update so the video tag is rendered and visible
        this.$nextTick(() => {
          const video = document.getElementById('scanner-video');
          if (video) {
            video.srcObject = stream;
            video.play();
            this.useCamera = true;
          }
        });
      } catch (err) {
        console.warn('Camera blocked or unsupported by hardware. Using mock simulator.', err);
        this.useCamera = false;
      }
    },

    stopCamera() {
      if (this.videoStream) {
        this.videoStream.getTracks().forEach(track => track.stop());
        this.videoStream = null;
      }
      this.useCamera = false;
    },

    captureSnapshot() {
      const video = document.getElementById('scanner-video');
      let imageSrc = null;

      if (video && this.useCamera) {
        try {
          const canvas = document.createElement('canvas');
          canvas.width = video.videoWidth || 640;
          canvas.height = video.videoHeight || 480;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          imageSrc = canvas.toDataURL('image/jpeg', 0.85);
          this.receiptImage = imageSrc;
          this.stopCamera();
        } catch (e) {
          console.error('Failed to grab camera frame:', e);
        }
      }

      // If camera capture failed or wasn't active, use fallback
      if (!imageSrc) {
        // Fallback simulated white pixel
        this.receiptImage = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
        imageSrc = this.receiptImage;
      }

      // ── Automated OCR Extraction using Tesseract.js ─────────
      if (typeof Tesseract !== 'undefined') {
        this.isOcrScanning = true;
        this.error = '';

        Tesseract.recognize(imageSrc, 'eng')
          .then(({ data: { text } }) => {
            console.log('[OCR Result]:', text);
            this.parseOcrText(text);
          })
          .catch(err => {
            console.warn('[OCR Error]:', err);
            this.error = 'OCR recognition failed. Please enter details manually.';
          })
          .finally(() => {
            this.isOcrScanning = false;
          });
      } else {
        console.warn('Tesseract.js not loaded. Cannot run automated OCR.');
      }
    },

    // ── OCR Text Parser ──────────────────────────────────────
    parseOcrText(text) {
      if (!text) return;

      // 1. Extract Mobile Number (formats: +63 977 115 9126, 0977-115-9126, +639771159126, etc)
      const phoneRegex = /(?:\+63|0)9\d{2}[\s-]?\d{3}[\s-]?\d{4}/g;
      const phoneMatch = text.match(phoneRegex);
      if (phoneMatch) {
        let rawPhone = phoneMatch[0].replace(/[\s-]/g, '');
        if (rawPhone.startsWith('+63')) {
          rawPhone = '0' + rawPhone.substring(3);
        }
        this.mobileNumber = rawPhone;
      }

      // 2. Extract Reference Number (format: Ref No. 5042 504 295085)
      const refRegex = /(?:Ref\s*No\.?|Reference\s*No\.?|Ref)\s*:?\s*([\d\s-]{10,22})/i;
      const refMatch = text.match(refRegex);
      if (refMatch) {
        this.referenceNumber = refMatch[1].replace(/[\s-]/g, '').substring(0, 13);
      } else {
        const longDigits = text.match(/\b\d[\d\s-]{9,16}\d\b/g);
        if (longDigits) {
          const cleanDigits = longDigits.map(d => d.replace(/[\s-]/g, ''));
          const probableRef = cleanDigits.find(d => d.length >= 10 && d.length <= 13 && !d.startsWith('09') && !d.startsWith('63'));
          if (probableRef) {
            this.referenceNumber = probableRef;
          }
        }
      }

      // 3. Extract Date and Time (format: Jul 03, 2026 5:27 PM)
      const dateRegex = /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)?/i;
      const dateMatch = text.match(dateRegex);
      if (dateMatch) {
        this.gcashTimestamp = dateMatch[0];
      } else {
        const timeOnly = text.match(/\b\d{1,2}:\d{2}\s*(?:AM|PM)?/i);
        if (timeOnly) {
          this.gcashTimestamp = new Date().toLocaleDateString('en-US') + ' ' + timeOnly[0];
        }
      }

      // 4. Extract Amount Sent (format: Total Amount Sent P2,020.00 or Amount 2,020.00)
      let amountMatch = text.match(/Total\s*Amount\s*Sent\s*(?:₱|P)?\s*([\d,]+\.\d{2})/i);
      if (!amountMatch) {
        amountMatch = text.match(/Amount\s*(?:₱|P)?\s*([\d,]+\.\d{2})/i);
      }
      if (amountMatch) {
        const parsedAmount = parseFloat(amountMatch[1].replace(/,/g, ''));
        if (parsedAmount > 0) {
          this.amount = parsedAmount;
          this.flowType = this.transactionType === 'GCASH_IN' ? 'A' : 'B';
          this.calculate();
        }
      }
    },

    simulateOCR(cashierAppRef) {
      // Simulate reading a receipt using camera OCR
      this.isOcrScanning = true;
      setTimeout(() => {
        const mockText = this.transactionType === 'GCASH_IN' 
          ? `
            GCash Send Money Success
            To: CH********R C. (0977 115 9126)
            Amount: 1,000.00
            Ref No. 5042 504 295085
            Jul 03, 2026 5:27 PM
          `
          : `
            CH********R C.
            +63 977 115 9126
            Sent via GCash
            Amount 2,020.00
            Total Amount Sent P2,020.00
            Ref No. 5042 504 295085   Jul 03, 2026 5:27 PM
          `;
        this.parseOcrText(mockText);
        this.receiptImage = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
        this.isOcrScanning = false;
        
        if (cashierAppRef) {
          cashierAppRef.showNotification('Receipt details scanned & parsed!', 'info');
        }
      }, 800);
    },

    // ── Confirm Transaction ──────────────────────────────────
    async confirm(cashierAppRef) {
      if (!this.result) return;
      this.error = '';

      // Validate inputs: both require mobileNumber and referenceNumber now
      if (!this.mobileNumber.trim() || !this.referenceNumber.trim()) {
        this.error = 'Mobile number and Reference are required for verification';
        return;
      }

      try {
        const res = await fetch('/api/gcash/transact', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            flow_type: this.result.flow_type,
            input_amount: this.result.input_amount,
            principal_amount: this.result.principal_amount,
            fee: this.result.fee,
            total_collected: this.result.total_collected,
            transaction_type: this.transactionType,
            reference_number: this.referenceNumber.trim() || null,
            mobile_number: this.mobileNumber.trim() || null,
            receipt_image: this.receiptImage || null,
            gcash_timestamp: this.gcashTimestamp.trim() || null
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'GCash transaction failed');
        }

        const txLabel = this.transactionType === 'GCASH_IN' ? 'Cash-In' : 'Cash-Out';
        cashierAppRef.showNotification(
          `GCash ${txLabel} recorded! Fee earned: ${this.formatPrice(this.result.fee)}`,
          'success'
        );
        cashierAppRef.showGcashModal = false;
        this.reset();
      } catch (err) {
        this.error = err.message;
      }
    },

    // ── Reset ────────────────────────────────────────────────
    reset() {
      this.flowType = 'A';
      this.amount = '';
      this.transactionType = 'GCASH_IN';
      this.result = null;
      this.error = '';
      this.step = 1;
      this.mobileNumber = '';
      this.referenceNumber = '';
      this.receiptImage = null;
      this.gcashTimestamp = '';
      this.isOcrScanning = false;
      this.stopCamera();
      clearTimeout(this.debounceTimer);
    },

    // ── Switch Flow (re-calculate if amount present) ─────────
    switchFlow(type) {
      this.flowType = type;
      this.result = null;
      if (this.amount) {
        this.scheduleCalculate();
      }
    },

    // ── Formatting ───────────────────────────────────────────
    formatPrice(n) {
      return '₱' + Number(n).toFixed(2);
    },
  };
}
