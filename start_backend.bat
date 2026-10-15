@echo off
echo Starting EGX Watchlist Backend on 127.0.0.1:8000...
cd /d "%~dp0backend"
call venv\Scripts\activate.bat
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
