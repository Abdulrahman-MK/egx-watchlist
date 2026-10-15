"""EGX Terminal Desktop Application Launcher.

Provides a 1-click desktop window interface for the EGX Watchlist Tracker:
1. Spawns the FastAPI backend server (hosting React UI, SQLite & WebSockets) in a daemon thread.
2. Waits until http://127.0.0.1:8000 is accepting connections.
3. Opens a native application window using pywebview, with an automatic fallback
   to Microsoft Edge / Google Chrome in standalone App Mode (`--app=http://127.0.0.1:8000`).
4. When the desktop window is closed, cleanly requests `/api/system/shutdown`
   and halts the process immediately, leaving zero background processes or port retention.
"""

import os
import sys
import time
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
    """Fallback: Launches Microsoft Edge or Chrome in standalone native app mode."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]

    browser_bin = None
    for cand in candidates:
        if os.path.exists(cand):
            browser_bin = cand
            break

    if browser_bin:
        cmd = [
            browser_bin,
            f"--app={APP_URL}",
            "--window-size=1320,860",
            "--window-position=100,50",
        ]
        proc = subprocess.Popen(cmd)
        proc.wait()  # Blocks until user closes the standalone window
        return True
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

    # 2. Launch native desktop UI via pywebview, falling back to browser app mode
    window_opened = False
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
        window.events.closed += request_graceful_shutdown
        webview.start()
        window_opened = True
    except Exception as e:
        print(f"pywebview note: {e}. Falling back to app mode window...")

    if not window_opened:
        app_opened = launch_browser_app_mode()
        if not app_opened:
            # Last fallback: open in default browser
            webbrowser.open(APP_URL)
            print("Opened in default browser. Press CTRL+C in this terminal to exit.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    # 3. Clean exit: stop server and kill process
    request_graceful_shutdown()


if __name__ == "__main__":
    main()
