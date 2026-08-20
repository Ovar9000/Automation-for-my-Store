"""
Sari-Sari Store POS — Standalone Windows Desktop App
=====================================================
Boots the local FastAPI server in the background and opens a native
borderless kiosk window using Microsoft Edge WebView2 (pywebview)
or optimized browser app mode.

Usage:
    python desktop_app.py
"""

import sys
import os
import time
import socket
import threading
import urllib.request
import multiprocessing
from pathlib import Path

# Fix sys.stdout/sys.stderr for Windows windowed mode
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Resolve project base directory
if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    sys.path.insert(0, str(BASE_DIR))
    sys.path.insert(0, str(Path(sys.executable).parent))
else:
    BASE_DIR = Path(__file__).resolve().parent
    sys.path.insert(0, str(BASE_DIR))

PORT = 8000
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"


def wait_for_server(timeout=15.0):
    """Wait until the FastAPI server responds with HTTP 200."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "POS-Launcher"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def start_uvicorn():
    """Start uvicorn in a dedicated worker thread with asyncio event loop."""
    import asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn
    from app.main import app

    config = uvicorn.Config(
        app=app,
        host=HOST,
        port=PORT,
        log_level="critical",
        access_log=False,
        loop="asyncio",
        workers=1
    )
    server = uvicorn.Server(config)
    server.run()


def main():
    multiprocessing.freeze_support()

    # 1. Start server in background thread if not already running
    server_thread = threading.Thread(target=start_uvicorn, daemon=True)
    server_thread.start()

    # 2. Wait for HTTP 200 before launching UI
    server_ready = wait_for_server(timeout=10.0)

    # 3. Launch native desktop window (WebView2)
    try:
        import webview
        window = webview.create_window(
            title="Sari-Sari Store POS Terminal",
            url=URL,
            width=1280,
            height=820,
            min_size=(1024, 700),
            confirm_close=True,
            easy_drag=False
        )
        webview.start(private_mode=False)
    except Exception as e:
        # Fallback: launch Edge or Chrome in standalone kiosk app mode
        import webbrowser
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        if os.path.exists(edge_path):
            os.system(f'start "" "{edge_path}" --app={URL} --start-maximized')
        elif os.path.exists(chrome_path):
            os.system(f'start "" "{chrome_path}" --app={URL} --start-maximized')
        else:
            webbrowser.open(URL)

        # Keep process alive while fallback browser window is active
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()
