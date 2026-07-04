"""
Sari-Sari Store POS — Receipt Formatter
==========================================
Formats receipt text for a 58mm thermal printer (32 characters per line).
Outputs plain text strings that can be sent to any printer or displayed on screen.
"""

from datetime import datetime
from typing import List, Optional


# 58mm thermal paper = approximately 32 characters per line
LINE_WIDTH = 32
SEPARATOR = "=" * LINE_WIDTH
THIN_SEP = "-" * LINE_WIDTH


def center(text: str, width: int = LINE_WIDTH) -> str:
    """Center-align text within the line width."""
    return text.center(width)


def left_right(left: str, right: str, width: int = LINE_WIDTH) -> str:
    """Format a line with left-aligned and right-aligned text."""
    space = width - len(left) - len(right)
    if space < 1:
        # Truncate left text if line is too long
        left = left[:width - len(right) - 1]
        space = 1
    return left + " " * space + right


def format_price(amount: float) -> str:
    """Format a price as Philippine Peso string."""
    return f"P{amount:,.2f}"


def truncate(text: str, max_len: int) -> str:
    """Truncate text and add ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "."


def format_sale_receipt(
    store_name: str,
    store_address: str,
    store_phone: str,
    items: List[dict],
    total: float,
    amount_tendered: float,
    change: float,
    payment_method: str = "CASH",
    transaction_id: int = 0,
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Format a customer sale receipt.

    Args:
        store_name: Store display name.
        items: List of dicts with keys: product_name, quantity, unit_price, subtotal.
        total: Grand total.
        amount_tendered: Cash given by customer.
        change: Change to return.
        payment_method: 'CASH' or 'GCASH'.
        transaction_id: Transaction ID number.
        timestamp: Sale timestamp (defaults to now).

    Returns:
        Multi-line string formatted for 32-char width.
    """
    if timestamp is None:
        timestamp = datetime.now()

    lines = []

    # ── Header ────────────────────────────────────
    lines.append(center(store_name[:LINE_WIDTH]))
    if store_address:
        # Wrap address to fit width
        addr = store_address[:LINE_WIDTH]
        lines.append(center(addr))
    if store_phone:
        lines.append(center(store_phone[:LINE_WIDTH]))
    lines.append(SEPARATOR)

    # ── Transaction info ──────────────────────────
    lines.append(left_right("TXN#:", str(transaction_id)))
    lines.append(left_right("Date:", timestamp.strftime("%Y-%m-%d")))
    lines.append(left_right("Time:", timestamp.strftime("%H:%M:%S")))
    lines.append(THIN_SEP)

    # ── Items ─────────────────────────────────────
    for item in items:
        name = truncate(item["product_name"], 20)
        qty = item["quantity"]
        price = item["unit_price"]
        subtotal = item["subtotal"]

        # Line 1: Item name + subtotal
        lines.append(left_right(name, format_price(subtotal)))

        # Line 2: Quantity x Unit Price (indented)
        qty_str = f"  {qty}x {format_price(price)}"
        lines.append(qty_str)

    lines.append(THIN_SEP)

    # ── Totals ────────────────────────────────────
    lines.append(left_right("TOTAL", format_price(total)))
    lines.append(left_right(payment_method, format_price(amount_tendered)))
    if payment_method == "CASH" and change > 0:
        lines.append(left_right("CHANGE", format_price(change)))

    lines.append(SEPARATOR)

    # ── Footer ────────────────────────────────────
    lines.append(center("Thank you!"))
    lines.append(center("Please come again"))
    lines.append("")
    lines.append("")

    return "\n".join(lines)


def format_gcash_receipt(
    store_name: str,
    transaction_type: str,
    principal: float,
    fee: float,
    total_collected: float,
    transaction_id: int = 0,
    timestamp: Optional[datetime] = None,
) -> str:
    """Format a GCash transaction receipt."""
    if timestamp is None:
        timestamp = datetime.now()

    lines = []
    lines.append(center(store_name[:LINE_WIDTH]))
    lines.append(SEPARATOR)
    lines.append(center(f"GCASH {transaction_type}"))
    lines.append(SEPARATOR)
    lines.append(left_right("TXN#:", str(transaction_id)))
    lines.append(left_right("Date:", timestamp.strftime("%Y-%m-%d %H:%M")))
    lines.append(THIN_SEP)
    lines.append(left_right("Principal:", format_price(principal)))
    lines.append(left_right("Fee:", format_price(fee)))
    lines.append(THIN_SEP)
    lines.append(left_right("TOTAL", format_price(total_collected)))
    lines.append(SEPARATOR)
    lines.append(center("Thank you!"))
    lines.append("")
    lines.append("")

    return "\n".join(lines)


def format_z_report(
    store_name: str,
    date: str,
    total_cash_sales: float,
    total_gcash_sales: float,
    total_gcash_fees: float,
    grand_total: float,
    transaction_count: int,
    gcash_count: int,
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Format an End-of-Day Z-Report summary receipt.
    """
    if timestamp is None:
        timestamp = datetime.now()

    lines = []
    lines.append(center(store_name[:LINE_WIDTH]))
    lines.append(SEPARATOR)
    lines.append(center("*** Z-REPORT ***"))
    lines.append(center("End of Day Summary"))
    lines.append(SEPARATOR)
    lines.append(left_right("Print Time:", timestamp.strftime("%H:%M:%S")))
    lines.append(left_right("Report Date:", date))
    lines.append(THIN_SEP)

    lines.append(left_right("Cash Sales:", format_price(total_cash_sales)))
    lines.append(left_right("GCash Sales:", format_price(total_gcash_sales)))
    lines.append(left_right("GCash Fees:", format_price(total_gcash_fees)))
    lines.append(THIN_SEP)

    lines.append(left_right("GRAND TOTAL", format_price(grand_total)))
    lines.append(THIN_SEP)

    lines.append(left_right("Transactions:", str(transaction_count)))
    lines.append(left_right("GCash Txns:", str(gcash_count)))
    lines.append(SEPARATOR)
    lines.append(center("** END OF REPORT **"))
    lines.append("")
    lines.append("")

    return "\n".join(lines)
