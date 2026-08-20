"""
Sari-Sari Store POS — Windows .EXE Build Script
==============================================
Builds a standalone executable using PyInstaller.

Usage:
    python build_desktop.py
"""

import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def build():
    print("==================================================")
    print("  Building Standalone Sari-Sari Store POS .EXE   ")
    print("==================================================")

    # Check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller is not installed. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "pywebview"])

    # Define build command
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
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=aiosqlite",
        "--hidden-import=jinja2",
        "--hidden-import=pydantic",
        str(PROJECT_ROOT / "desktop_app.py")
    ]

    print(f"[*] Running command: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(PROJECT_ROOT))

    print("\n==================================================")
    print("  BUILD SUCCESSFUL!")
    print(f"  Executable output: dist/SariSariPOS/SariSariPOS.exe")
    print("==================================================")

if __name__ == "__main__":
    build()
