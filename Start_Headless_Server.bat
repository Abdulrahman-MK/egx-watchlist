@echo off
setlocal
echo Starting EGX Watchlist in Headless Background Mode...
start "" "%~dp0dist\EGX_Tracker.exe" --headless
echo.
echo [SUCCESS] EGX Terminal is now running in the background!
echo - No desktop window is opened on your laptop.

for /f "tokens=*" %%a in ('powershell -NoProfile -Command "(Get-NetIPAddress -InterfaceAlias '*Tailscale*' -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress"') do set TS_IP=%%a
if not "%TS_IP%"=="" (
    echo - Access from your phone at: http://%TS_IP%:8000
) else (
    echo - Access from your phone at: http://^<your-tailscale-ip^>:8000
)

echo - To stop the server at any time, run Stop_Server.bat
timeout /t 5 >nul
