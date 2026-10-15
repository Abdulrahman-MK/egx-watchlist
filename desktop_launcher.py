"""EGX Terminal Desktop Application Launcher.

Provides a 1-click desktop window interface for the EGX Watchlist Tracker:
1. Spawns the FastAPI backend server (hosting React UI, SQLite & WebSockets) in a daemon thread.
2. Waits until http://127.0.0.1:8000 is accepting connections.
3. Opens a standalone desktop window using Microsoft Edge / Chrome in native App Mode
   (`--app=http://127.0.0.1:8000` with an isolated profile), or system browser fallback.
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
import traceback
import ctypes
from pathlib import Path

# Required for PyInstaller frozen executable on Windows
multiprocessing.freeze_support()

# Determine paths (supports both standard execution and PyInstaller frozen executable)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    BACKEND_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    BACKEND_DIR = BASE_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Log file next to the launcher/executable
LOG_FILE = BASE_DIR / "egx_launcher.log"


def log_msg(msg: str):
    """Appends status messages to egx_launcher.log for easy troubleshooting."""
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except Exception:
        pass


def show_alert(title: str, message: str):
    """Displays a native Windows message box if a fatal error occurs."""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0x10)
    except Exception:
        print(f"[{title}] {message}")


# Top-level import forces PyInstaller AST analysis to collect all FastAPI & app modules
try:
    import uvicorn
    from main import app
except Exception as e:
    err_str = traceback.format_exc()
    log_msg(f"Failed to import backend modules: {err_str}")
    show_alert("EGX Terminal Startup Error", f"Failed to load backend modules:\n\n{e}\n\nSee egx_launcher.log for details.")
    sys.exit(1)


APP_URL = "http://127.0.0.1:8000"
global_server = None


def run_backend_server():
    """Starts Uvicorn serving FastAPI in a background daemon thread."""
    global global_server
    try:
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
        log_msg("Uvicorn server starting on 127.0.0.1:8000...")
        global_server.run()
    except Exception as e:
        err_str = traceback.format_exc()
        log_msg(f"Uvicorn server crashed: {err_str}")


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
    log_msg("Graceful shutdown requested. Releasing port 8000 and closing connections...")
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

    time.sleep(0.3)
    log_msg("EGX Terminal closed cleanly. Process exiting.")
    os._exit(0)


def launch_browser_app_mode() -> bool:
    """Launches Microsoft Edge or Chrome in standalone native app mode.

    Using a dedicated --user-data-dir ensures it runs as an independent window process
    and does not instantly return if the user already has personal browser tabs open.
    """
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
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
            log_msg(f"Launching standalone window via: {browser_bin}")
            proc = subprocess.Popen(cmd)
            proc.wait()  # Blocks until user closes the standalone window!
            log_msg("Standalone window was closed by user.")
            return True
        except Exception as e:
            log_msg(f"Browser app mode launch error: {e}")
            return False
    return False


def main():
    log_msg("=== EGX Terminal Starting ===")

    # 1. Start backend server if not already running
    if not is_server_running(APP_URL):
        server_thread = threading.Thread(target=run_backend_server, daemon=True)
        server_thread.start()

        if not wait_for_server(APP_URL):
            msg = "Backend server failed to start within 12 seconds."
            log_msg(f"Error: {msg}")
            show_alert("EGX Terminal Error", f"{msg}\nCheck egx_launcher.log for details.")
            sys.exit(1)

    log_msg("Server is responding at http://127.0.0.1:8000. Launching native window...")

    # 2. Launch standalone App Mode (Edge/Chrome native window with isolated profile)
    opened = launch_browser_app_mode()

    # 3. Fallback to default browser if standalone app mode was unavailable
    if not opened:
        log_msg("App mode unavailable, opening in default browser...")
        webbrowser.open(APP_URL)
        # Keep process alive while user uses browser
        try:
            while is_server_running(APP_URL):
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # 4. Clean exit: stop server and kill process
    request_graceful_shutdown()


if __name__ == "__main__":
    main()
