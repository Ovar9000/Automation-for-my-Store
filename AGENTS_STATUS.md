# Sari-Sari POS — Agent Status

## Project: Sari-Sari Store POS System
- **Status**: Completed / Pushed to GitHub Repository
- **Completed**: 2026-07-04
- **Remote Repo**: https://github.com/Ovar9000/Automation-for-my-Store.git
- **Tech Stack**: FastAPI (v0.139.0) + SQLite (WAL mode) + Tailwind CSS v4 + Alpine.js (v3)

## Features Implemented
- [x] Project structure & launcher (`run.py` opens default browser automatically)
- [x] Database schema (products, transactions, transaction_items, gcash_transactions, admin_settings)
- [x] GCash fee engine (Flow A: fee on top, Flow B: reverse calculation with snap-to-thousand fallback)
- [x] Cashier interface (barcode scanning, live search, quick buttons, cart management, decimal weight modal)
- [x] Admin dashboard (login, inventory, reports with tabs and pure CSS graphs)
- [x] Receipt formatting (32-char width text helper for 58mm thermal printers)
- [x] localStorage cart recovery (`pos_cart` key)
- [x] **Keyboard-First Cashier Fork** (2026-07-05) — Full UI redesign for barcode-first / keyboard-driven workflow

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

### 4. Keyboard-First Cashier Fork
- **Unified Smart Input**: Merged barcode + search into a single input. Auto-detects mode: digits → barcode scan on Enter, letters → live product search with debounce.
- **Keyboard-Navigable Search Results**: Arrow keys (↑/↓) navigate results, Enter adds the highlighted item to cart. Results show product name, barcode, stock, price, and unit.
- **Cart Keyboard Navigation**: Tab to enter cart mode, ↑/↓ to select items, +/- to adjust quantity, Delete/Backspace to remove, Enter to inline-edit quantity.
- **F5 Two-Press Payment**: First F5 focuses the amount tendered input, second F5 (or Enter) completes the sale. This enables a fully keyboard-driven checkout flow.
- **F3 Quick Items Toggle**: Quick items displayed as a horizontal strip (**expanded by default**). F3 toggles visibility. Items are still clickable but keyboard shortcuts remain the primary interaction.
- **Quick Denomination Buttons**: ₱20, ₱50, ₱100, ₱200, ₱500, ₱1000 buttons below the amount tendered field for fast cash entry.
- **Context Mode Indicator**: Header shows current mode (READY TO SCAN, SEARCHING, CART NAV, PAYMENT) with a pulsing green dot for scan readiness.
- **Cascading Escape**: Escape cascades through modals → search → payment → cart nav → clean scan state. Always returns to barcode input.
- **Always-Visible Remove Buttons**: Cart item remove buttons are always visible (no hover-only dependency), critical for keyboard-first UX.
- **Auto-Redirect Typing**: Any printable character typed while not focused on an input automatically redirects to the smart input.

## Agent Learnings & Troubleshooting
- **Subagent Rate Limits**: During development, parallel subagents hit the `RESOURCE_EXHAUSTED 429` rate limit. In these situations, the parent agent must gracefully take over and complete code creation sequentially.
- **Route Ordering in FastAPI**: Defined paths like `/products/low-stock` and `/products/barcode/{barcode}` *before* parameterized paths like `/products/{id}`. Otherwise, FastAPI interprets paths like "low-stock" as an item ID, leading to casting errors.
- **FastAPI Mount Catch-All**: Keep REST API route definitions above static mounts. Static mounting with `html=True` acts as a wildcard catch-all, which would intercept API calls if registered first.
- **Git Workspace Isolation & DB Exclusion**: For nested projects, initializing a dedicated git repository prevents staging user home directory files. Additionally, adding `data/store.db` to `.gitignore` ensures that the active/local database state is excluded from commits.
- **Alpine.js `template x-if` + SVG = cloneNode Error**: Alpine.js's `<template x-if>` directive cannot wrap SVG elements because SVG uses a different DOM namespace and `cloneNode()` fails to properly recreate SVG nodes. **Solution**: Use `x-show` on a `<span>` wrapper around the SVG instead. This only toggles `display` rather than cloning DOM nodes, avoiding the error entirely.
- **Keyboard-First UX Pattern**: When designing for keyboard-driven workflows, avoid hover-only UI states (e.g., show-on-hover remove buttons). Use context modes and visual indicators to communicate which keyboard area is active. Auto-redirect stray keystrokes to the primary input field so USB barcode scanners work even when focus is lost.

