"""
Sari-Sari Store POS — Print Service (Placeholder)
====================================================
Provides an abstraction for receipt printing.
Currently outputs to console/log since printer hardware is TBD.

When a physical printer is connected, replace the `print_text()` method
with actual ESC/POS commands via python-escpos.
"""

import logging

logger = logging.getLogger(__name__)


class PrintService:
    """
    Printer abstraction layer.
    Currently logs receipt text to console.
    Replace with USB printer when hardware is ready.
    """

    def __init__(self):
        self.connected = False
        self.printer = None
        logger.info("[PRINTER] Print service initialized (placeholder mode)")

    def is_connected(self) -> bool:
        """Check if a physical printer is connected."""
        return self.connected

    def print_text(self, text: str) -> bool:
        """
        Print formatted receipt text.

        Args:
            text: Pre-formatted receipt string (32-char lines).

        Returns:
            True if printed successfully, False otherwise.
        """
        # ── Placeholder: print to console ──
        print("\n" + "=" * 40)
        print("  [RECEIPT OUTPUT - PRINTER PLACEHOLDER]")
        print("=" * 40)
        print(text)
        print("=" * 40 + "\n")
        return True

        # ── Future: USB thermal printer ──
        # Uncomment when hardware is ready:
        #
        # from escpos.printer import Usb
        # try:
        #     printer = Usb(0x0416, 0x5011)  # Replace with your VID:PID
        #     printer.text(text)
        #     printer.cut()
        #     printer.close()
        #     return True
        # except Exception as e:
        #     logger.error(f"[PRINTER] Print failed: {e}")
        #     return False


# ── Singleton instance ──
print_service = PrintService()
