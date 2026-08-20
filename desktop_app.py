"""
Sari-Sari Store POS — Windows Desktop Application Wrapper
=========================================================
Runs FastAPI/Uvicorn in the background and opens a clean desktop
POS kiosk window via WebView2 (or default browser).

Usage:
    python desktop_app.py
"""

import sys
import os
import time
import socket
import threading
import webbrowser
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

PORT = 8000
HOST = "127.0.0.1"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0


def start_server():
    """Start Uvicorn server in background thread."""
    import uvicorn
    from app.main import app
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def main():
    print("==================================================")
    print("  Sari-Sari Store POS — Desktop Terminal Launcher")
    print("==================================================")

    if not is_port_in_use(PORT):
        print(f"[*] Starting local POS server on http://{HOST}:{PORT}...")
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()

        # Wait for server to become healthy
        for _ in range(50):
            if is_port_in_use(PORT):
                break
            time.sleep(0.1)

    url = f"http://{HOST}:{PORT}"
    print(f"[+] POS Terminal active at: {url}")

    # Try launching with pywebview if installed, otherwise open in browser app mode
    try:
        import webview
        print("[*] Launching native Windows POS Kiosk window (WebView2)...")
        webview.create_window(
            title="Sari-Sari Store POS Terminal",
            url=url,
            width=1280,
            height=800,
            min_size=(1024, 700),
            confirm_close=True,
            easy_drag=False
        )
        webview.start()
    except ImportError:
        print("[*] pywebview not installed. Opening in optimized browser kiosk mode...")
        # Open in Chrome/Edge app window mode if possible
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        
        opened = False
        if os.path.exists(edge_path):
            os.system(f'start "" "{edge_path}" --app={url} --start-maximized')
            opened = True
        elif os.path.exists(chrome_path):
            os.system(f'start "" "{chrome_path}" --app={url} --start-maximized')
            opened = True

        if not opened:
            webbrowser.open(url)

        print("[+] POS is running in your browser. Press Ctrl+C in this terminal to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[!] Shutting down POS server.")
            sys.exit(0)


if __name__ == "__main__":
    main()
