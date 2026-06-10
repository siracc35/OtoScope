# start.ps1 — backend + frontend'i tek komutla başlatır.
# Kullanım:  .\start.ps1
# Durdurmak için: bu pencerede Ctrl+C (ikisi de kapanır).

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "OtoScope başlatılıyor..." -ForegroundColor Cyan

# Backend'i ayrı bir job olarak başlat (port 8000)
$backend = Start-Process -PassThru -NoNewWindow `
    -FilePath "$root\.venv\Scripts\uvicorn.exe" `
    -ArgumentList "main:app", "--app-dir", "server", "--reload", "--port", "8000"

Write-Host "  [+] Backend  -> http://127.0.0.1:8000  (PID $($backend.Id))" -ForegroundColor Green
Write-Host "  [+] Frontend -> http://localhost:5173" -ForegroundColor Green
Write-Host "Çıkmak için Ctrl+C." -ForegroundColor DarkGray

# Frontend'i ön planda çalıştır; pencere kapanınca backend'i de öldür.
try {
    & npm run dev --prefix "$root\client"
} finally {
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
    Write-Host "OtoScope durduruldu." -ForegroundColor Cyan
}
