@echo off
:: EGX Terminal — One-Click Silent Desktop Launcher
:: Uses pythonw.exe to run without leaving a command prompt terminal open.

cd /d "%~dp0"

set VENV_PYTHONW="%~dp0backend\venv\Scripts\pythonw.exe"
set VENV_PYTHON="%~dp0backend\venv\Scripts\python.exe"

if exist %VENV_PYTHONW% (
    start "" %VENV_PYTHONW% "%~dp0desktop_launcher.py"
) else if exist %VENV_PYTHON% (
    start "" %VENV_PYTHON% "%~dp0desktop_launcher.py"
) else (
    start "" pythonw "%~dp0desktop_launcher.py"
)
exit
