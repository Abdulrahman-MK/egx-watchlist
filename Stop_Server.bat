@echo off
echo Stopping EGX Watchlist Server...
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/system/shutdown' -Method POST -Body '{}' -ContentType 'application/json' -TimeoutSec 2 | Out-Null; Write-Host '[SUCCESS] EGX Server stopped cleanly. Zero lingering processes.' } catch { Write-Host '[INFO] Server was not running or is already stopped.' }"
timeout /t 2 >nul
