# Sari-Sari Store POS System

A lightweight, local-first Point of Sale system for Philippine sari-sari stores.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
python run.py

# 3. Open in browser
# Cashier:  http://localhost:8000
# Admin:    http://localhost:8000/admin
```

## Tech Stack
- **Backend**: Python 3.10+ / FastAPI
- **Database**: SQLite (WAL mode)
- **Frontend**: HTML5, Tailwind CSS v4, Alpine.js 3.x
- **Printer**: 58mm thermal (OC-58IIH compatible) — optional

## Backup
Simply copy `data/store.db` to a USB drive or cloud storage daily.
The database file contains ALL your data.

## Default Admin Password
Username: `admin` | Password: `admin123`
Change this immediately from the Admin Dashboard → Settings.
