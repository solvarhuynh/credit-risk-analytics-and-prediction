@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Khong tim thay .venv\Scripts\python.exe. Cai dependencies truoc khi chay.
    exit /b 1
)

if not defined DASH_PORT set "DASH_PORT=8050"

rem Wait for Dash to answer, then open the Windows default browser.
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -Command "$port=$env:DASH_PORT; $url='http://127.0.0.1:'+$port+'/'; for ($attempt=0; $attempt -lt 30; $attempt++) { try { $reply=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2; if ($reply.StatusCode -eq 200) { Start-Process $url; exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"

".venv\Scripts\python.exe" -m apps.individual_prediction_dash.app
endlocal
