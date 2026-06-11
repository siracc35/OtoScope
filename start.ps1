# OtoScope local start — kills stale processes then starts backend + frontend

foreach ($port in @(8001, 5173, 5174)) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "Killed process on port $port"
    }
}

Start-Sleep -Seconds 1

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\server'; ..\\.venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8001"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\client'; npm run dev"

Write-Host ""
Write-Host "OtoScope baslatildi:"
Write-Host "  Frontend -> http://localhost:5173"
Write-Host "  Backend  -> http://localhost:8001"
