export interface ScaleBarcodeInfo {
  isScaleBarcode: boolean
  prefix?: string
  plu?: string
  value?: number
  isWeight?: boolean
  weightKg?: number
}

/**
 * Checks if a scanned barcode is an in-store EAN-13 price or weight-embedded scale barcode.
 * Standard format: 20XXXXXWWWWWC or 21XXXXXWWWWWC
 */
export function parseScaleBarcode(code: string): ScaleBarcodeInfo {
  const clean = code.trim()
  if ((clean.length === 12 || clean.length === 13) && /^\d+$/.test(clean)) {
    const prefix = clean.substring(0, 2)
    if (['20', '21', '02'].includes(prefix)) {
      const plu = clean.substring(2, 7)
      const value = parseInt(clean.substring(7, 12), 10)
      const weightKg = Number((value / 1000).toFixed(3))

      return {
        isScaleBarcode: true,
        prefix,
        plu,
        value,
        isWeight: true,
        weightKg
      }
    }
  }

  return { isScaleBarcode: false }
}

/**
 * Setup a global scanner keystroke listener that catches barcode gun scans
 * even if the input field is not focused.
 */
export function setupBarcodeListener(onScan: (barcode: string) => void) {
  let buffer = ''
  let lastKeyTime = Date.now()

  const handleKeyDown = (e: KeyboardEvent) => {
    // Ignore if target is an input or textarea that is actively focused,
    // UNLESS it's Enter and the buffer has collected barcode characters
    const target = e.target as HTMLElement
    const isInput = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')
    
    // If it's Enter, check if we have a scanned barcode
    if (e.key === 'Enter') {
      if (buffer.length >= 3) {
        e.preventDefault()
        const scanned = buffer.trim()
        buffer = ''
        onScan(scanned)
      }
      return
    }

    // Measure time between keystrokes (scanners emit keys in < 40ms)
    const now = Date.now()
    const diff = now - lastKeyTime
    lastKeyTime = now

    // Only collect printable characters
    if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
      if (diff > 250 && !isInput) {
        // Reset buffer if delay was long and not an input
        buffer = ''
      }
      if (!isInput) {
        buffer += e.key
      }
    }
  }

  window.addEventListener('keydown', handleKeyDown)
  return () => window.removeEventListener('keydown', handleKeyDown)
}
