<script lang="ts">
  import {
    Smartphone,
    Camera,
    Upload,
    Check,
    X,
    Loader2,
    ArrowDownLeft,
    ArrowUpRight,
    Copy,
    Image,
    AlertCircle
  } from 'lucide-svelte'
  import { onMount, onDestroy } from 'svelte'

  interface Props {
    onComplete: (msg: string) => void
    onClose: () => void
  }

  let { onComplete, onClose }: Props = $props()

  // Direction: 'GCASH_IN' (Customer buys GCash with Cash) or 'GCASH_OUT' (Customer sends GCash to get Cash)
  let transactionType = $state<'GCASH_IN' | 'GCASH_OUT'>('GCASH_OUT')
  let flowType = $state<'A' | 'B'>('B')

  // Financial fields
  let inputAmount = $state<string>('')
  let principalAmount = $state<number>(0)
  let calculatedFee = $state<number>(0)
  let totalCollected = $state<number>(0)
  let isCalculating = $state(false)

  // Extracted Receipt Details
  let mobileNumber = $state('')
  let recipientName = $state('')
  let referenceNumber = $state('')
  let gcashTimestamp = $state('')
  let receiptImage = $state<string | null>(null)

  // Camera & OCR state
  let isCameraActive = $state(false)
  let videoStream = $state<MediaStream | null>(null)
  let videoEl = $state<HTMLVideoElement | null>(null)
  let isOcrScanning = $state(false)
  let ocrError = $state('')
  let isSubmitting = $state(false)

  // Calculate fees whenever amount or flowType changes
  $effect(() => {
    const amt = parseFloat(inputAmount) || 0
    if (amt <= 0) {
      principalAmount = 0
      calculatedFee = 0
      totalCollected = 0
      return
    }

    if (transactionType === 'GCASH_IN') {
      // Flow A: Fee added on top
      // Default: ₱10 per 1000
      const fee = Math.ceil(amt / 1000) * 10
      principalAmount = amt
      calculatedFee = fee
      totalCollected = amt + fee
    } else {
      // GCash Out: Flow B (Customer transfers total amount, store deducts fee)
      // If customer sent 1000, fee is 10, store gives 990 cash
      const fee = Math.ceil(amt / 1000) * 10
      principalAmount = amt - fee > 0 ? amt - fee : amt
      calculatedFee = fee
      totalCollected = amt
    }
  })

  // Start Camera
  async function startCamera() {
    stopCamera()
    ocrError = ''
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
      })
      videoStream = stream
      isCameraActive = true
      setTimeout(() => {
        if (videoEl) {
          videoEl.srcObject = stream
          videoEl.play()
        }
      }, 100)
    } catch (err: any) {
      ocrError = 'Camera not available. Please upload a screenshot or paste (Ctrl+V).'
      isCameraActive = false
    }
  }

  function stopCamera() {
    if (videoStream) {
      videoStream.getTracks().forEach((track) => track.stop())
      videoStream = null
    }
    isCameraActive = false
  }

  function capturePhoto() {
    if (!videoEl) return
    const canvas = document.createElement('canvas')
    canvas.width = videoEl.videoWidth || 640
    canvas.height = videoEl.videoHeight || 480
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height)
      receiptImage = canvas.toDataURL('image/jpeg', 0.88)
      stopCamera()
      processImageOCR(receiptImage)
    }
  }

  function handleFileUpload(e: Event) {
    const input = e.target as HTMLInputElement
    if (!input.files || input.files.length === 0) return
    const file = input.files[0]
    const reader = new FileReader()
    reader.onload = () => {
      receiptImage = reader.result as string
      processImageOCR(receiptImage)
    }
    reader.readAsDataURL(file)
  }

  function handlePaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items
    if (!items) return
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        const file = items[i].getAsFile()
        if (file) {
          const reader = new FileReader()
          reader.onload = () => {
            receiptImage = reader.result as string
            processImageOCR(receiptImage)
          }
          reader.readAsDataURL(file)
        }
        break
      }
    }
  }

  // Tesseract OCR Processing & Regex Extraction
  async function processImageOCR(imgDataUrl: string) {
    const tesseract = (window as any).Tesseract
    if (!tesseract) {
      ocrError = 'OCR engine not loaded. Please fill in details manually.'
      return
    }

    isOcrScanning = true
    ocrError = ''

    try {
      const { data: { text } } = await tesseract.recognize(imgDataUrl, 'eng')
      console.log('[GCash OCR Text]:\n', text)
      parseGCashText(text)
    } catch (err: any) {
      console.error('[OCR Error]', err)
      ocrError = 'Could not auto-read text from image. Please verify details manually.'
    } finally {
      isOcrScanning = false
    }
  }

  function parseGCashText(text: string) {
    if (!text) return

    // 1. Mobile Number (e.g., +63 917 123 4567, 0917-123-4567, 09171234567)
    const phoneRegex = /(?:\+63|0)9\d{2}[\s-]?\d{3}[\s-]?\d{4}/g
    const phoneMatches = text.match(phoneRegex)
    if (phoneMatches && phoneMatches.length > 0) {
      let cleanPhone = phoneMatches[0].replace(/[\s-]/g, '')
      if (cleanPhone.startsWith('+63')) {
        cleanPhone = '0' + cleanPhone.substring(3)
      }
      mobileNumber = cleanPhone
    }

    // 2. Reference Number (e.g. Ref No. 5042 504 295085 or 10-14 digits)
    const refRegex = /(?:Ref\s*No\.?|Reference\s*No\.?|Ref)\s*:?\s*([\d\s-]{10,24})/i
    const refMatch = text.match(refRegex)
    if (refMatch) {
      referenceNumber = refMatch[1].replace(/[\s-]/g, '').substring(0, 14)
    } else {
      const longDigits = text.match(/\b\d[\d\s-]{9,15}\d\b/g)
      if (longDigits) {
        const found = longDigits.map((d) => d.replace(/[\s-]/g, '')).find((d) => d.length >= 10 && !d.startsWith('09'))
        if (found) referenceNumber = found
      }
    }

    // 3. Recipient or Sender Name (e.g. Sent to: MARIA D. or Express Send to ...)
    const toRegex = /(?:Sent\s+to|To:|Transferred\s+to|Received\s+from)\s*[:\s]+([A-Z\s\*\.]{3,24})/i
    const toMatch = text.match(toRegex)
    if (toMatch) {
      recipientName = toMatch[1].trim()
    }

    // 4. Direction detection (Sent out vs Received/Sent in)
    if (/received|cash\s*in/i.test(text)) {
      transactionType = 'GCASH_IN'
      flowType = 'A'
    } else if (/sent\s*via|express\s*send|amount\s*sent|paid/i.test(text)) {
      transactionType = 'GCASH_OUT'
      flowType = 'B'
    }

    // 5. Date & Time
    const dateRegex = /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)?/i
    const dateMatch = text.match(dateRegex)
    if (dateMatch) {
      gcashTimestamp = dateMatch[0]
    } else {
      gcashTimestamp = new Date().toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
    }

    // 6. Amount Sent (e.g. Total Amount Sent PHP 1,000.00 or Amount 1,000.00)
    const amountRegex = /(?:Total\s*Amount\s*Sent|Amount|PHP|₱|P)\s*[:\s]*(?:PHP|₱|P)?\s*([\d,]+\.\d{2})/i
    const amountMatch = text.match(amountRegex)
    if (amountMatch) {
      const parsed = parseFloat(amountMatch[1].replace(/,/g, ''))
      if (parsed > 0) {
        inputAmount = parsed.toString()
      }
    }
  }

  // Submit to Backend
  async function handleSubmit() {
    const amt = parseFloat(inputAmount) || 0
    if (amt <= 0) {
      ocrError = 'Please specify a valid amount.'
      return
    }

    isSubmitting = true
    ocrError = ''

    try {
      const payload = {
        transaction_type: transactionType,
        flow_type: flowType,
        input_amount: amt,
        principal_amount: principalAmount,
        fee: calculatedFee,
        total_collected: totalCollected,
        reference_number: referenceNumber.trim() || undefined,
        mobile_number: mobileNumber.trim() || undefined,
        receipt_image: receiptImage || undefined,
        gcash_timestamp: gcashTimestamp || new Date().toLocaleString('en-PH')
      }

      const res = await fetch('/api/gcash/transact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to record GCash transaction')
      }

      stopCamera()
      onComplete(`Recorded ${transactionType === 'GCASH_IN' ? 'Cash-In' : 'Cash-Out'} of ₱${amt.toFixed(2)} (Fee: ₱${calculatedFee.toFixed(2)})`)
    } catch (e: any) {
      ocrError = e.message || 'Transaction recording failed'
    } finally {
      isSubmitting = false
    }
  }

  onMount(() => {
    gcashTimestamp = new Date().toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
    window.addEventListener('paste', handlePaste)
  })

  onDestroy(() => {
    stopCamera()
    window.removeEventListener('paste', handlePaste)
  })
</script>

<div
  class="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 z-50 animate-in fade-in duration-150"
  role="dialog"
  aria-modal="true"
  tabindex="-1"
>
  <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[92vh] overflow-hidden flex flex-col">
    <!-- Header -->
    <div class="px-5 py-3.5 bg-blue-600 text-white flex items-center justify-between flex-shrink-0">
      <div class="flex items-center gap-2.5">
        <div class="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
          <Smartphone class="w-5 h-5 text-white" />
        </div>
        <div>
          <h2 class="text-sm font-bold tracking-tight">GCash Transaction & Receipt Scanner</h2>
          <p class="text-[11px] text-blue-100">Camera OCR Photo Capture & Fee Recording</p>
        </div>
      </div>
      <button
        type="button"
        onclick={() => { stopCamera(); onClose(); }}
        class="text-blue-200 hover:text-white p-1 rounded-lg transition-colors"
      >
        <X class="w-5 h-5" />
      </button>
    </div>

    <!-- Scrollable Body -->
    <div class="p-4 overflow-y-auto space-y-4 flex-1">
      <!-- Direction Toggle -->
      <div class="grid grid-cols-2 gap-2 bg-slate-100 p-1 rounded-xl text-xs font-bold">
        <button
          type="button"
          onclick={() => { transactionType = 'GCASH_OUT'; flowType = 'B'; }}
          class="flex items-center justify-center gap-2 py-2.5 rounded-lg transition-all {transactionType === 'GCASH_OUT' ? 'bg-blue-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
        >
          <ArrowDownLeft class="w-4 h-4" />
          <span>💵 Cash-Out (Customer Sent GCash)</span>
        </button>

        <button
          type="button"
          onclick={() => { transactionType = 'GCASH_IN'; flowType = 'A'; }}
          class="flex items-center justify-center gap-2 py-2.5 rounded-lg transition-all {transactionType === 'GCASH_IN' ? 'bg-blue-600 text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'}"
        >
          <ArrowUpRight class="w-4 h-4" />
          <span>💸 Cash-In (Store Sends GCash)</span>
        </button>
      </div>

      {#if ocrError}
        <div class="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-bold text-rose-700 flex items-center gap-2">
          <AlertCircle class="w-4 h-4 flex-shrink-0" />
          <span>{ocrError}</span>
        </div>
      {/if}

      <!-- Photo Capture / OCR Scanner Box -->
      <div class="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
            <Camera class="w-4 h-4 text-blue-600" />
            <span>Receipt Photo / Screenshot OCR</span>
          </span>
          <span class="text-[10px] text-slate-400 font-medium">Auto-reads Phone, Ref #, Name, Time & Amount</span>
        </div>

        {#if isCameraActive}
          <div class="relative rounded-xl overflow-hidden bg-black aspect-video max-h-56 flex items-center justify-center">
            <!-- svelte-ignore a11y_media_has_caption -->
            <video bind:this={videoEl} class="w-full h-full object-contain" autoplay playsinline></video>
            <div class="absolute bottom-3 left-0 right-0 flex justify-center gap-2">
              <button
                type="button"
                onclick={capturePhoto}
                class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-lg flex items-center gap-1.5"
              >
                <Camera class="w-4 h-4" />
                <span>Snap Receipt Photo</span>
              </button>
              <button
                type="button"
                onclick={stopCamera}
                class="px-3 py-2 bg-slate-800/80 text-white text-xs font-bold rounded-xl"
              >
                Cancel
              </button>
            </div>
          </div>
        {:else if receiptImage}
          <div class="flex items-center gap-3 p-2 bg-white border border-slate-200 rounded-xl">
            <img src={receiptImage} alt="Receipt Preview" class="w-16 h-20 object-cover rounded-lg border" />
            <div class="flex-1 min-w-0">
              <p class="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <span>Receipt Photo Captured</span>
                {#if isOcrScanning}
                  <span class="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600">
                    <Loader2 class="w-3 h-3 animate-spin" /> Scanning OCR...
                  </span>
                {:else}
                  <span class="text-[10px] text-emerald-600 font-bold">✓ Scanned</span>
                {/if}
              </p>
              <p class="text-[11px] text-slate-500 mt-0.5">Details extracted below. You can adjust fields manually.</p>
              <div class="flex gap-2 mt-2">
                <button
                  type="button"
                  onclick={startCamera}
                  class="text-[11px] font-bold text-blue-600 hover:underline"
                >
                  Retake Photo
                </button>
                <button
                  type="button"
                  onclick={() => receiptImage = null}
                  class="text-[11px] font-bold text-rose-600 hover:underline"
                >
                  Remove
                </button>
              </div>
            </div>
          </div>
        {:else}
          <!-- Action Buttons for Image Input -->
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <button
              type="button"
              onclick={startCamera}
              class="flex items-center justify-center gap-1.5 p-3 rounded-xl border border-blue-200 bg-blue-50 text-blue-800 text-xs font-bold hover:bg-blue-100 transition-colors"
            >
              <Camera class="w-4 h-4 text-blue-600" />
              <span>Use Camera</span>
            </button>

            <label class="flex items-center justify-center gap-1.5 p-3 rounded-xl border border-slate-200 bg-white text-slate-700 text-xs font-bold hover:bg-slate-50 cursor-pointer transition-colors">
              <Upload class="w-4 h-4 text-slate-500" />
              <span>Upload Screenshot</span>
              <input type="file" accept="image/*" class="hidden" onchange={handleFileUpload} />
            </label>

            <div class="hidden sm:flex items-center justify-center gap-1 p-3 rounded-xl border border-dashed border-slate-300 text-slate-400 text-[11px] font-medium text-center">
              <span>Press <strong>Ctrl+V</strong> to paste</span>
            </div>
          </div>
        {/if}
      </div>

      <!-- Financial Calculator Breakdown -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <!-- Input Amount -->
        <div>
          <label for="gcashAmount" class="block text-xs font-bold text-slate-700 mb-1">
            {transactionType === 'GCASH_IN' ? 'Cash Given (₱):' : 'GCash Sent (₱):'}
          </label>
          <div class="relative flex items-center">
            <span class="absolute left-3 font-bold text-slate-400">₱</span>
            <input
              id="gcashAmount"
              bind:value={inputAmount}
              type="number"
              step="any"
              min="1"
              placeholder="e.g. 1000"
              class="w-full pl-8 pr-3 py-2.5 bg-slate-50 border-2 border-blue-400 rounded-xl text-lg font-black font-mono text-slate-900 focus:outline-none focus:bg-white"
            />
          </div>
        </div>

        <!-- Calculated Fee -->
        <div>
          <p class="block text-xs font-bold text-slate-700 mb-1">Store Fee (Kita):</p>
          <div class="px-3 py-2.5 bg-amber-50 border border-amber-200 rounded-xl text-lg font-black font-mono text-amber-900">
            ₱{calculatedFee.toFixed(2)}
          </div>
        </div>

        <!-- Net / Collected -->
        <div>
          <p class="block text-xs font-bold text-slate-700 mb-1">
            {transactionType === 'GCASH_IN' ? 'Total Cash Collected:' : 'Physical Cash to Hand Out:'}
          </p>
          <div class="px-3 py-2.5 bg-emerald-50 border border-emerald-300 rounded-xl text-lg font-black font-mono text-emerald-800">
            ₱{(transactionType === 'GCASH_IN' ? totalCollected : principalAmount).toFixed(2)}
          </div>
        </div>
      </div>

      <!-- Extracted Details Form Grid -->
      <div class="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-600">Extracted Transaction Details</h3>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <!-- Mobile Number -->
          <div>
            <label for="gcashMobile" class="block text-[11px] font-bold text-slate-700 mb-1">Mobile Number (Customer):</label>
            <input
              id="gcashMobile"
              bind:value={mobileNumber}
              type="text"
              placeholder="0917-XXX-XXXX"
              class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs font-mono font-bold text-slate-900"
            />
          </div>

          <!-- Reference Number -->
          <div>
            <label for="gcashRef" class="block text-[11px] font-bold text-slate-700 mb-1">GCash Reference No.:</label>
            <input
              id="gcashRef"
              bind:value={referenceNumber}
              type="text"
              placeholder="e.g. 504250429508"
              class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs font-mono font-bold text-slate-900"
            />
          </div>

          <!-- Recipient / Sender Name -->
          <div>
            <label for="gcashRecipient" class="block text-[11px] font-bold text-slate-700 mb-1">Recipient / Sender Name:</label>
            <input
              id="gcashRecipient"
              bind:value={recipientName}
              type="text"
              placeholder="e.g. MARIA D."
              class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs font-semibold text-slate-900"
            />
          </div>

          <!-- Date & Time -->
          <div>
            <label for="gcashTime" class="block text-[11px] font-bold text-slate-700 mb-1">Receipt Date & Time:</label>
            <input
              id="gcashTime"
              bind:value={gcashTimestamp}
              type="text"
              class="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-xs font-mono text-slate-900"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Footer Actions -->
    <div class="p-3.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between flex-shrink-0">
      <button
        type="button"
        onclick={() => { stopCamera(); onClose(); }}
        class="px-4 py-2 text-xs font-bold text-slate-600 hover:text-slate-900 rounded-lg"
      >
        Cancel
      </button>

      <button
        type="button"
        onclick={handleSubmit}
        disabled={isSubmitting || (parseFloat(inputAmount) || 0) <= 0}
        class="flex items-center gap-1.5 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-extrabold rounded-xl shadow-md transition-all"
      >
        {#if isSubmitting}
          <Loader2 class="w-4 h-4 animate-spin" />
          <span>Recording...</span>
        {:else}
          <Check class="w-4 h-4" />
          <span>Record GCash Transaction</span>
        {/if}
      </button>
    </div>
  </div>
</div>
