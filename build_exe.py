"""PyInstaller Packaging Script for EGX Real-Time Tracker.

Packages the full application (FastAPI server, SQLite persistence, upstream WebSockets,
and compiled React single-page application) into a single standalone Windows executable.

Usage:
    python build_exe.py
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
BACKEND_DIR = PROJECT_ROOT / "backend"


def build_frontend():
    """Compiles the React production bundle using Vite."""
    print("=" * 60)
    print("Step 1: Compiling React Production Bundle (frontend/dist)...")
    print("=" * 60)
    if not FRONTEND_DIR.exists():
        print(f"Error: {FRONTEND_DIR} does not exist.")
        sys.exit(1)

    cmd = "npm run build"
    result = subprocess.run(cmd, shell=True, cwd=str(FRONTEND_DIR))
    if result.returncode != 0:
        print("Frontend compilation failed.")
        sys.exit(1)
    print("Frontend compilation completed successfully.")


def package_executable():
    """Invokes PyInstaller to bundle backend, frontend assets, and desktop launcher."""
    print("=" * 60)
    print("Step 2: Bundling Standalone Windows Executable via PyInstaller...")
    print("=" * 60)

    try:
        import PyInstaller.__main__
    except ImportError:
        print("Error: PyInstaller is not installed in the current environment.")
        print("Run: pip install pyinstaller")
        sys.exit(1)

    launcher_script = str(PROJECT_ROOT / "desktop_launcher.py")
    dist_data_arg = f"{str(FRONTEND_DIST)};dist"
    backend_data_arg = f"{str(BACKEND_DIR)};backend"

    args = [
        launcher_script,
        "--name=EGX_Tracker",
        "--onefile",
        "--windowed",  # Suppress command prompt window
        f"--add-data={dist_data_arg}",
        f"--add-data={backend_data_arg}",
        f"--paths={str(BACKEND_DIR)}",
        "--hidden-import=main",
        "--hidden-import=uvicorn",
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
        "--hidden-import=websockets",
        "--hidden-import=httpx",
        "--hidden-import=pydantic_settings",
        "--hidden-import=pytz",
        "--hidden-import=app",
        "--hidden-import=app.config",
        "--hidden-import=app.database",
        "--hidden-import=app.symbols",
        "--hidden-import=app.market_guard",
        "--hidden-import=app.services",
        "--hidden-import=app.services.symbol_sync",
        "--hidden-import=app.services.stream_manager",
        "--hidden-import=app.routers",
        "--hidden-import=app.routers.system",
        "--hidden-import=app.routers.symbols",
        "--hidden-import=app.routers.watchlist",
        "--hidden-import=app.providers",
        "--hidden-import=app.providers.base",
        "--hidden-import=app.providers.tradingview",
        "--hidden-import=app.providers.egxapi",
        "--hidden-import=app.providers.mock_snapshot",
        "--hidden-import=multiprocessing",
        "--clean",
        "--noconfirm",
    ]

    print(f"Running PyInstaller with entry point: {launcher_script}")
    PyInstaller.__main__.run(args)

    print("=" * 60)
    print("SUCCESS: Standalone executable created at:")
    print(f"  {PROJECT_ROOT / 'dist' / 'EGX_Tracker.exe'}")
    print("=" * 60)


if __name__ == "__main__":
    build_frontend()
    package_executable()
