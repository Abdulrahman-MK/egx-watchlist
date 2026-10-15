@echo off
echo Starting EGX Watchlist Frontend on 127.0.0.1:5173...
cd /d "%~dp0frontend"
npm run dev
pause
