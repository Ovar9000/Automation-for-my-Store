"""
Sari-Sari Store POS — Windows .EXE Builder
==========================================
Bundles the POS app into a single standalone folder / executable with PyInstaller.

Usage:
    python build_desktop.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def build():
    print("==================================================")
    print("  Building Standalone Sari-Sari Store POS .EXE   ")
    print("==================================================")

    # Clean old build artifacts
    for folder in ["build", "dist"]:
        p = PROJECT_ROOT / folder
        if p.exists():
            try:
                shutil.rmtree(p)
            except Exception as e:
                print(f"[!] Warning cleaning {folder}: {e}")

    # Build command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=SariSariPOS",
        f"--add-data={PROJECT_ROOT / 'templates'};templates",
        f"--add-data={PROJECT_ROOT / 'static'};static",
        f"--add-data={PROJECT_ROOT / 'data'};data",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.loops.asyncio",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.http.h11_impl",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=aiosqlite",
        "--hidden-import=jinja2",
        "--hidden-import=pydantic",
        "--hidden-import=webview",
        "--hidden-import=clr",
        "--hidden-import=httpx",
        "--collect-all=webview",
        str(PROJECT_ROOT / "desktop_app.py")
    ]

    print(f"[*] Running PyInstaller...")
    subprocess.check_call(cmd, cwd=str(PROJECT_ROOT))

    print("\n==================================================")
    print("  BUILD SUCCESSFUL!")
    print(f"  Output folder: {PROJECT_ROOT / 'dist' / 'SariSariPOS'}")
    print(f"  Executable:    {PROJECT_ROOT / 'dist' / 'SariSariPOS' / 'SariSariPOS.exe'}")
    print("==================================================")

if __name__ == "__main__":
    build()
