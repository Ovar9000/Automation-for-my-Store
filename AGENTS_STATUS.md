# Sari-Sari POS — Agent Status

## Project: Sari-Sari Store POS System
- **Status**: Completed / Ready for Deployment
- **Completed**: 2026-07-04
- **Tech Stack**: FastAPI (v0.139.0) + SQLite (WAL mode) + Tailwind CSS v4 + Alpine.js (v3)

## Features Implemented
- [x] Project structure & launcher (`run.py` opens default browser automatically)
- [x] Database schema (products, transactions, transaction_items, gcash_transactions, admin_settings)
- [x] GCash fee engine (Flow A: fee on top, Flow B: reverse calculation with snap-to-thousand fallback)
- [x] Cashier interface (barcode scanning, live search, quick buttons, cart management, decimal weight modal)
- [x] Admin dashboard (login, inventory, reports with tabs and pure CSS graphs)
- [x] Receipt formatting (32-char width text helper for 58mm thermal printers)
- [x] localStorage cart recovery (`pos_cart` key)

## Understanding of the Features

### 1. Cashier Workflow
- Barcode Scanner emulation behaves exactly like keyboard inputs ending with `Enter`. When scanned, it immediately pulls product info from `/api/products/barcode/{barcode}` and calls `addToCart`.
- Items measured in pieces (`pc`) increment the quantity by 1. Items measured in kilograms (`kg`) or Liters (`L`) trigger a weight modal prompting the cashier to type the decimal quantity.
- All cart actions trigger saving state to `localStorage` ensuring that the POS remains fully crash-resistant.

### 2. GCash Calculation (Reverse Algorithm)
- Rather than hardcoding specific inputs (e.g. 3030 or 3040), the engine employs a generalized approach.
- Flow A: `fee = math.ceil(amount / 1000) * 10`, total = amount + fee.
- Flow B: Searches for a valid principal `P` where `P + fee == total`. If none exists (due to fee-step gaps, e.g. 3040), it floors the principal to the nearest thousand (e.g. 3000) and charges the remainder as a fee.

### 3. Database Resilience
- Enabled Write-Ahead Logging (`PRAGMA journal_mode=WAL`) on SQLite connections. This improves concurrent read/write throughput which is critical since both interfaces share a single database file.

## Agent Learnings & Troubleshooting
- **Subagent Rate Limits**: During development, parallel subagents hit the `RESOURCE_EXHAUSTED 429` rate limit. In these situations, the parent agent must gracefully take over and complete code creation sequentially.
- **Route Ordering in FastAPI**: Defined paths like `/products/low-stock` and `/products/barcode/{barcode}` *before* parameterized paths like `/products/{id}`. Otherwise, FastAPI interprets paths like "low-stock" as an item ID, leading to casting errors.
- **FastAPI Mount Catch-All**: Keep REST API route definitions above static mounts. Static mounting with `html=True` acts as a wildcard catch-all, which would intercept API calls if registered first.
