@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Khong tim thay .venv\Scripts\python.exe. Cai dependencies truoc khi chay.
    exit /b 1
)

if not defined DASH_PORT set "DASH_PORT=8050"

rem Do not silently open an older Dash process already bound to this port.
powershell.exe -NoProfile -Command "$port=[int]$env:DASH_PORT; try { $listeners=@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop) } catch { if ($_.FullyQualifiedErrorId -like '*CmdletizationQuery_NotFound*') { $listeners=@() } else { Write-Error $_; exit 1 } }; if ($listeners) { Write-Output ('DASH_PORT_IN_USE: port ' + $port + ', PID(s) ' + (($listeners.OwningProcess | Sort-Object -Unique) -join ',')); exit 2 } else { exit 0 }"
if errorlevel 2 (
    echo ERROR: port %DASH_PORT% is already in use. No browser was opened.
    echo Close the previous app instance, then rerun this launcher; do not assume another port has the latest code.
    exit /b 2
)
if errorlevel 1 (
    echo ERROR: could not verify whether port %DASH_PORT% is available. No browser was opened.
    echo Check PowerShell networking permissions, then rerun this launcher.
    exit /b 1
)

echo Starting the current repository version at http://127.0.0.1:%DASH_PORT%/

rem Wait for Dash to answer, then open the Windows default browser.
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -Command "$port=$env:DASH_PORT; $url='http://127.0.0.1:'+$port+'/'; for ($attempt=0; $attempt -lt 30; $attempt++) { try { $reply=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2; if ($reply.StatusCode -eq 200) { Start-Process $url; exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"

".venv\Scripts\python.exe" -m apps.individual_prediction_dash.app
endlocal
