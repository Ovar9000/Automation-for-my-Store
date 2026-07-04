"""
Sari-Sari Store POS — GCash Fee Calculation Engine
====================================================
Handles two calculation flows for GCash Cash-In/Cash-Out:

Flow A (Principal Input — Fee Added On Top):
    Customer says "I want to cash in X pesos."
    Fee = ceil(X / 1000) * fee_per_thousand
    Total to collect = X + Fee

Flow B (Total Input — Reverse Calculation):
    Customer hands you T pesos total.
    Find the largest principal P where P + ceil(P/1000) * fee_per_thousand <= T.
    Fee = T - P (store keeps the rest).

    This uses a generalized algorithm — no hardcoded exceptions.
    Examples: 3030 → P=3000, fee=30
              3040 → P=3000, fee=40
              4040 → P=4000, fee=40
"""

import math


# Default fee: 10 PHP per 1,000 PHP block
DEFAULT_FEE_PER_THOUSAND = 10


def calculate_flow_a(amount: float, fee_per_thousand: float = DEFAULT_FEE_PER_THOUSAND) -> dict:
    """
    Flow A: Principal Amount Input — Fee is added on top.

    Args:
        amount: The principal amount the customer wants to transact.
        fee_per_thousand: Fee charged per 1,000 PHP block (default: 10).

    Returns:
        dict with principal_amount, fee, total_collected.

    Examples:
        >>> calculate_flow_a(1000)
        {'principal_amount': 1000.0, 'fee': 10.0, 'total_collected': 1010.0}

        >>> calculate_flow_a(2400)
        {'principal_amount': 2400.0, 'fee': 30.0, 'total_collected': 2430.0}
    """
    if amount <= 0:
        return {"principal_amount": 0, "fee": 0, "total_collected": 0}

    # Fee = ceil(amount / 1000) * fee_per_thousand
    # e.g., 2400 → ceil(2.4) = 3 → 3 * 10 = 30
    blocks = math.ceil(amount / 1000)
    fee = blocks * fee_per_thousand
    total = amount + fee

    return {
        "principal_amount": round(amount, 2),
        "fee": round(fee, 2),
        "total_collected": round(total, 2),
    }


def calculate_flow_b(total: float, fee_per_thousand: float = DEFAULT_FEE_PER_THOUSAND) -> dict:
    """
    Flow B: Total Amount Input — Reverse-calculate principal and fee.

    Algorithm:
        1. Try exact reverse: for each possible fee bracket k, check if
           P = total - k * fee_per_thousand has ceil(P/1000) == k.
        2. If no exact match, snap principal down to the nearest thousand.
           Fee = total - principal.

    Args:
        total: The total cash amount handed by the customer.
        fee_per_thousand: Fee per 1,000 PHP block (default: 10).

    Returns:
        dict with principal_amount, fee, total_collected.

    Examples:
        >>> calculate_flow_b(1010)
        {'principal_amount': 1000.0, 'fee': 10.0, 'total_collected': 1010.0}

        >>> calculate_flow_b(2430)
        {'principal_amount': 2400.0, 'fee': 30.0, 'total_collected': 2430.0}

        >>> calculate_flow_b(3030)
        {'principal_amount': 3000.0, 'fee': 30.0, 'total_collected': 3030.0}

        >>> calculate_flow_b(3040)  # No exact inverse → snap to 3000
        {'principal_amount': 3000.0, 'fee': 40.0, 'total_collected': 3040.0}

        >>> calculate_flow_b(4040)
        {'principal_amount': 4000.0, 'fee': 40.0, 'total_collected': 4040.0}
    """
    if total <= 0:
        return {"principal_amount": 0, "fee": 0, "total_collected": 0}

    # ── Step 1: Try exact reverse calculation ────────────────────────
    # For each possible number of thousand-blocks k:
    #   If P = total - k * fee_per_thousand, and ceil(P / 1000) == k, it's exact.
    max_k = math.ceil(total / 1000) + 1
    for k in range(1, max_k + 1):
        principal = total - k * fee_per_thousand
        if principal <= 0:
            break
        if math.ceil(principal / 1000) == k:
            return {
                "principal_amount": round(principal, 2),
                "fee": round(k * fee_per_thousand, 2),
                "total_collected": round(total, 2),
            }

    # ── Step 2: No exact match → snap to nearest thousand below ──────
    # This handles "gap" amounts like 3040, where no P cleanly reverses.
    # Principal snaps to floor(total / 1000) * 1000 (nearest thousand down).
    principal = math.floor(total / 1000) * 1000
    if principal <= 0:
        principal = 0
    fee = total - principal

    return {
        "principal_amount": round(principal, 2),
        "fee": round(fee, 2),
        "total_collected": round(total, 2),
    }


def calculate_gcash(amount: float, flow_type: str, fee_per_thousand: float = DEFAULT_FEE_PER_THOUSAND) -> dict:
    """
    Main entry point — dispatches to Flow A or Flow B.

    Args:
        amount: The amount entered by the cashier.
        flow_type: 'A' for principal input, 'B' for total input.
        fee_per_thousand: Fee per thousand block (default: 10).

    Returns:
        dict with flow_type, input_amount, principal_amount, fee, total_collected.
    """
    if flow_type.upper() == "A":
        result = calculate_flow_a(amount, fee_per_thousand)
    else:
        result = calculate_flow_b(amount, fee_per_thousand)

    return {
        "flow_type": flow_type.upper(),
        "input_amount": round(amount, 2),
        **result,
    }
