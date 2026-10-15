"""EGX Terminal Desktop Application Launcher.

Provides a 1-click desktop window interface for the EGX Watchlist Tracker:
1. Spawns the FastAPI backend server (hosting React UI, SQLite & WebSockets) in a daemon thread.
2. Waits until http://127.0.0.1:8000 is accepting connections.
3. Opens a standalone desktop window using Microsoft Edge / Chrome in native App Mode
   (`--app=http://127.0.0.1:8000` with an isolated profile), or pywebview fallback.
4. When the desktop window is closed, cleanly executes graceful shutdown
   and halts the process immediately, leaving zero background processes or port retention.
"""

import os
import sys
import time
import tempfile
import threading
import subprocess
import urllib.request
import webbrowser
import multiprocessing
from pathlib import Path

# Required for PyInstaller frozen executable on Windows
multiprocessing.freeze_support()

# Determine paths
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    BACKEND_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
    BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

APP_URL = "http://127.0.0.1:8000"
global_server = None


def run_backend_server():
    """Starts Uvicorn serving FastAPI in a background daemon thread."""
    global global_server
    try:
        import uvicorn
        from main import app

        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=8000,
            log_level="warning",
            access_log=False,
        )
        global_server = uvicorn.Server(config)
        # In a background thread, disable uvicorn's OS signal handlers to prevent ValueError
        global_server.install_signal_handlers = lambda: None
        global_server.run()
    except Exception as e:
        print(f"[BackendServer] Startup error: {e}")


def is_server_running(url: str) -> bool:
    """Checks if the local server is already responding."""
    try:
        with urllib.request.urlopen(f"{url}/api/status", timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_for_server(url: str, timeout: float = 12.0) -> bool:
    """Waits for local server to become ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_server_running(url):
            return True
        time.sleep(0.25)
    return False


def request_graceful_shutdown():
    """Calls backend shutdown endpoint, stops uvicorn, and exits completely."""
    global global_server
    try:
        req = urllib.request.Request(
            f"{APP_URL}/api/system/shutdown",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            pass
    except Exception:
        pass

    if global_server:
        try:
            global_server.should_exit = True
        except Exception:
            pass

    # Give sockets 300ms to finish closing then terminate process cleanly
    time.sleep(0.3)
    os._exit(0)


def launch_browser_app_mode() -> bool:
    """Launches Microsoft Edge or Chrome in standalone native app mode.

    Using a dedicated --user-data-dir ensures it runs as an independent window process
    and does not instantly return if the user already has personal browser tabs open.
    """
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
    ]

    browser_bin = None
    for cand in candidates:
        if os.path.exists(cand):
            browser_bin = cand
            break

    if browser_bin:
        profile_dir = os.path.join(tempfile.gettempdir(), "egx_tracker_profile")
        cmd = [
            browser_bin,
            f"--app={APP_URL}",
            f"--user-data-dir={profile_dir}",
            "--window-size=1320,860",
            "--window-position=100,50",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        try:
            proc = subprocess.Popen(cmd)
            proc.wait()  # Blocks until user closes the standalone window
            return True
        except Exception as e:
            print(f"Browser app mode launch error: {e}")
            return False
    return False


def launch_pywebview() -> bool:
    """Attempts to launch a desktop window using pywebview."""
    try:
        import webview
        window = webview.create_window(
            title="EGX Terminal — Egyptian Exchange Watchlist",
            url=APP_URL,
            width=1320,
            height=860,
            min_size=(960, 600),
            background_color="#0a0d14",
            text_select=True,
        )
        webview.start()
        return True
    except Exception as e:
        print(f"pywebview note: {e}")
        return False


def main():
    print("=" * 60)
    print("  EGX TERMINAL — Real-Time Egyptian Exchange Watchlist")
    print("  Starting local environment on http://127.0.0.1:8000...")
    print("=" * 60)

    # 1. Start backend server if not already running
    if not is_server_running(APP_URL):
        server_thread = threading.Thread(target=run_backend_server, daemon=True)
        server_thread.start()

        if not wait_for_server(APP_URL):
            print("Error: Backend server failed to start within timeout.")
            sys.exit(1)

    print("Server ready! Launching native desktop window...")

    # 2. Prefer standalone App Mode (Edge/Chrome native window with isolated profile)
    opened = launch_browser_app_mode()

    # 3. Fallback to pywebview if standalone browser app mode was unavailable
    if not opened:
        opened = launch_pywebview()

    # 4. Fallback to default browser
    if not opened:
        webbrowser.open(APP_URL)
        print("Opened in default browser. Press CTRL+C in this terminal to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # 5. Clean exit: stop server and kill process
    request_graceful_shutdown()


if __name__ == "__main__":
    main()
