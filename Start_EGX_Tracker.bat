@echo off
cd /d "%~dp0"

if exist "%~dp0backend\venv\Scripts\pythonw.exe" (
    start "" "%~dp0backend\venv\Scripts\pythonw.exe" "%~dp0desktop_launcher.py"
) else if exist "%~dp0backend\venv\Scripts\python.exe" (
    start "" "%~dp0backend\venv\Scripts\python.exe" "%~dp0desktop_launcher.py"
) else (
    start "" pythonw "%~dp0desktop_launcher.py"
)
exit
