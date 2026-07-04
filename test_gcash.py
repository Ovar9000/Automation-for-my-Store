"""
Sari-Sari Store POS — GCash Fee Engine Unit Tests
===================================================
Run with: python test_gcash.py
"""

from app.services.gcash_engine import calculate_gcash, calculate_flow_a, calculate_flow_b


def test_gcash_flow_a():
    print("Testing Flow A (Fee on Top)...")
    
    # Example 1: 1000 -> Fee is 10 -> Total is 1010
    res = calculate_gcash(1000, "A")
    assert res["fee"] == 10.0, f"Expected 10.0, got {res['fee']}"
    assert res["total_collected"] == 1010.0, f"Expected 1010.0, got {res['total_collected']}"
    print("  1000 -> 1010 OK")

    # Example 2: 2400 -> Fee is 30 -> Total is 2430
    res = calculate_gcash(2400, "A")
    assert res["fee"] == 30.0, f"Expected 30.0, got {res['fee']}"
    assert res["total_collected"] == 2430.0, f"Expected 2430.0, got {res['total_collected']}"
    print("  2400 -> 2430 OK")

    # Edge cases
    assert calculate_gcash(0, "A")["fee"] == 0
    assert calculate_gcash(-50, "A")["fee"] == 0
    print("Flow A OK!\n")


def test_gcash_flow_b():
    print("Testing Flow B (Total Input - Reverse Calculation)...")

    # Standard reverse calculations
    # Example 1: 1010 -> Principal 1000, Fee 10
    res = calculate_gcash(1010, "B")
    assert res["principal_amount"] == 1000.0, f"Expected 1000.0, got {res['principal_amount']}"
    assert res["fee"] == 10.0, f"Expected 10.0, got {res['fee']}"
    print("  1010 -> P: 1000, F: 10 OK")

    # Example 2: 2430 -> Principal 2400, Fee 30
    res = calculate_gcash(2430, "B")
    assert res["principal_amount"] == 2400.0, f"Expected 2400.0, got {res['principal_amount']}"
    assert res["fee"] == 30.0, f"Expected 30.0, got {res['fee']}"
    print("  2430 -> P: 2400, F: 30 OK")

    # Example 3: 3030 -> Principal 3000, Fee 30
    res = calculate_gcash(3030, "B")
    assert res["principal_amount"] == 3000.0, f"Expected 3000.0, got {res['principal_amount']}"
    assert res["fee"] == 30.0, f"Expected 30.0, got {res['fee']}"
    print("  3030 -> P: 3000, F: 30 OK")

    # Example 4: 3040 -> Principal 3000, Fee 40
    res = calculate_gcash(3040, "B")
    assert res["principal_amount"] == 3000.0, f"Expected 3000.0, got {res['principal_amount']}"
    assert res["fee"] == 40.0, f"Expected 40.0, got {res['fee']}"
    print("  3040 -> P: 3000, F: 40 OK")

    # Generalized snap exception check:
    # Example 5: 4040 -> Principal 4000, Fee 40
    res = calculate_gcash(4040, "B")
    assert res["principal_amount"] == 4000.0, f"Expected 4000.0, got {res['principal_amount']}"
    assert res["fee"] == 40.0, f"Expected 40.0, got {res['fee']}"
    print("  4040 -> P: 4000, F: 40 OK")

    # Boundary edge cases
    assert calculate_gcash(0, "B")["principal_amount"] == 0
    assert calculate_gcash(-10, "B")["principal_amount"] == 0
    print("Flow B OK!\n")


if __name__ == "__main__":
    print("Running GCash engine tests...")
    test_gcash_flow_a()
    test_gcash_flow_b()
    print("All tests passed successfully!")
